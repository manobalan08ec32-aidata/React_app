"""
WebSocket chat router for streaming chat responses.
Handles real-time bidirectional communication with the frontend.
"""
import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Flag to enable/disable real workflow (set to False for testing without Databricks)
USE_REAL_WORKFLOW = True


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        # Map of session_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and store a new connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        """Remove a connection."""
        self.active_connections.pop(session_id, None)

    async def send_json(self, session_id: str, data: Dict[str, Any]):
        """Send JSON data to a specific session."""
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(data)

    async def broadcast(self, message: str):
        """Broadcast message to all connections."""
        for websocket in self.active_connections.values():
            await websocket.send_text(message)


# Global connection manager
manager = ConnectionManager()


async def stream_response_placeholder(
    websocket: WebSocket,
    session_id: str,
    question: str,
    user_id: str,
    state: Dict[str, Any]
) -> str:
    """
    Placeholder streaming for testing without Databricks.
    Demonstrates the streaming message protocol.
    """
    from app.main import storage

    # Send status: processing
    await websocket.send_json({
        "type": "status",
        "status": "processing",
        "message": "Processing your question..."
    })

    # Placeholder response
    placeholder_response = (
        f"I received your question: '{question}'. "
        "This is a placeholder response for testing. "
        "Connect Databricks credentials to enable the full workflow."
    )

    # Stream tokens
    words = placeholder_response.split()
    full_response = ""

    for word in words:
        token = word + " "
        full_response += token

        await websocket.send_json({
            "type": "stream",
            "token": token,
            "done": False
        })

        await asyncio.sleep(0.03)

    # Send completion
    await websocket.send_json({
        "type": "stream",
        "token": "",
        "done": True
    })

    await websocket.send_json({
        "type": "complete",
        "response": full_response.strip(),
        "session_id": session_id,
        "turn_number": state.get("turn_number", 1),
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "placeholder"
        }
    })

    # Save to storage if available
    if storage:
        try:
            turn_number = state.get("turn_number", 0) + 1
            await storage.save_turn(
                session_id=session_id,
                turn_number=turn_number,
                user_question=question,
                agent_response=full_response.strip(),
                state_snapshot=state,
                metadata={"placeholder": True}
            )

            await storage.save_session(
                session_id=session_id,
                user_id=user_id,
                state={**state, "turn_number": turn_number},
                title=question[:100] if turn_number == 1 else None
            )
        except Exception as e:
            print(f"Warning: Could not save to storage: {e}")

    return full_response.strip()


async def stream_response_workflow(
    websocket: WebSocket,
    session_id: str,
    question: str,
    user_id: str,
    user_email: Optional[str],
    state: Dict[str, Any]
) -> str:
    """
    Stream response using the real LangGraph workflow.
    """
    from app.main import storage
    from app.services.workflow import get_workflow_service

    # Get workflow service
    workflow_service = await get_workflow_service()

    # Send initial status
    await websocket.send_json({
        "type": "status",
        "status": "processing",
        "message": "Processing your question..."
    })

    full_response = ""
    final_state = state.copy()

    try:
        # Run workflow and stream events
        async for event in workflow_service.run_workflow(
            question=question,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
            existing_state=state
        ):
            event_type = event.get("type", "")

            if event_type == "workflow_start":
                await websocket.send_json({
                    "type": "status",
                    "status": "started",
                    "message": "Workflow started..."
                })

            elif event_type == "node_complete":
                # Node completed - send status update
                await websocket.send_json({
                    "type": "status",
                    "status": "processing",
                    "message": event.get("status", f"Completed {event.get('node', '')}..."),
                    "node": event.get("node")
                })

            elif event_type == "narrative":
                # Stream narrative content
                content = event.get("content", "")
                if content:
                    full_response = content

                    # Stream the narrative word by word for smooth UI
                    words = content.split()
                    for word in words:
                        await websocket.send_json({
                            "type": "stream",
                            "token": word + " ",
                            "done": False
                        })
                        await asyncio.sleep(0.02)

            elif event_type == "sql_result":
                # Send SQL results
                await websocket.send_json({
                    "type": "data",
                    "data_type": "sql_result",
                    "data": event.get("data")
                })

            elif event_type == "chart":
                # Send chart specification
                await websocket.send_json({
                    "type": "data",
                    "data_type": "chart",
                    "spec": event.get("spec")
                })

            elif event_type == "followup_questions":
                # Send follow-up questions
                await websocket.send_json({
                    "type": "data",
                    "data_type": "followup_questions",
                    "questions": event.get("questions", [])
                })

            elif event_type == "workflow_end":
                final_state = event.get("state", {})

                # Check for special responses
                if final_state.get("greeting_response"):
                    full_response = final_state["greeting_response"]
                    # Stream greeting
                    words = full_response.split()
                    for word in words:
                        await websocket.send_json({
                            "type": "stream",
                            "token": word + " ",
                            "done": False
                        })
                        await asyncio.sleep(0.02)

                elif final_state.get("domain_followup_question"):
                    full_response = final_state["domain_followup_question"]
                    await websocket.send_json({
                        "type": "clarification",
                        "clarification_type": "domain",
                        "message": full_response
                    })

                elif final_state.get("dataset_followup_question"):
                    full_response = final_state["dataset_followup_question"]
                    await websocket.send_json({
                        "type": "clarification",
                        "clarification_type": "dataset",
                        "message": full_response
                    })

                elif final_state.get("sql_followup_question"):
                    full_response = final_state["sql_followup_question"]
                    await websocket.send_json({
                        "type": "clarification",
                        "clarification_type": "sql",
                        "message": full_response
                    })

            elif event_type == "error":
                await websocket.send_json({
                    "type": "error",
                    "error": event.get("error", "Unknown error")
                })

        # Send stream completion
        await websocket.send_json({
            "type": "stream",
            "token": "",
            "done": True
        })

        # Send final complete message
        turn_number = state.get("turn_number", 0) + 1
        await websocket.send_json({
            "type": "complete",
            "response": full_response,
            "session_id": session_id,
            "turn_number": turn_number,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "question_type": final_state.get("question_type"),
                "next_agent": final_state.get("next_agent")
            }
        })

        # Save to storage
        if storage:
            try:
                await storage.save_turn(
                    session_id=session_id,
                    turn_number=turn_number,
                    user_question=question,
                    agent_response=full_response,
                    state_snapshot=final_state,
                    metadata={"workflow": True}
                )

                await storage.save_session(
                    session_id=session_id,
                    user_id=user_id,
                    state={**final_state, "turn_number": turn_number},
                    title=question[:100] if turn_number == 1 else None
                )
            except Exception as e:
                print(f"Warning: Could not save to storage: {e}")

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })

    return full_response


async def stream_response(
    websocket: WebSocket,
    session_id: str,
    question: str,
    user_id: str,
    state: Dict[str, Any],
    user_email: Optional[str] = None
) -> str:
    """
    Main streaming function that routes to appropriate implementation.
    """
    if USE_REAL_WORKFLOW:
        try:
            return await stream_response_workflow(
                websocket=websocket,
                session_id=session_id,
                question=question,
                user_id=user_id,
                user_email=user_email,
                state=state
            )
        except ImportError as e:
            print(f"Workflow import failed, falling back to placeholder: {e}")
            # Fall back to placeholder if imports fail
            return await stream_response_placeholder(
                websocket=websocket,
                session_id=session_id,
                question=question,
                user_id=user_id,
                state=state
            )
    else:
        return await stream_response_placeholder(
            websocket=websocket,
            session_id=session_id,
            question=question,
            user_id=user_id,
            state=state
        )


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for chat.

    Protocol:
    - Client sends: {"type": "message", "session_id": "...", "user_id": "...", "question": "..."}
    - Server sends:
        - {"type": "status", "status": "processing|error", "message": "..."}
        - {"type": "stream", "token": "...", "done": false}  (repeated for streaming)
        - {"type": "stream", "token": "", "done": true}  (end of stream)
        - {"type": "complete", "response": "...", "session_id": "...", "metadata": {...}}
        - {"type": "data", "data_type": "sql_result|chart|followup_questions", "data": {...}}
        - {"type": "clarification", "clarification_type": "domain|dataset|sql", "message": "..."}
    """
    session_id = None

    try:
        await websocket.accept()

        while True:
            # Receive message from client
            data = await websocket.receive_json()

            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "message":
                session_id = data.get("session_id") or str(uuid.uuid4())
                user_id = data.get("user_id", "anonymous")
                user_email = data.get("user_email")
                question = data.get("question", "").strip()

                if not question:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Question cannot be empty"
                    })
                    continue

                # Register connection
                manager.active_connections[session_id] = websocket

                # Load existing session state
                from app.main import storage
                state = {}

                if storage:
                    try:
                        existing_session = await storage.get_session(session_id)
                        if existing_session:
                            state = existing_session.get("state", {})
                    except Exception:
                        pass

                # Update state
                state["current_question"] = question
                state["user_question"] = question
                state["session_id"] = session_id
                state["user_id"] = user_id

                # Process and stream response
                try:
                    await stream_response(
                        websocket=websocket,
                        session_id=session_id,
                        question=question,
                        user_id=user_id,
                        state=state,
                        user_email=user_email
                    )
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })

    except WebSocketDisconnect:
        if session_id:
            manager.disconnect(session_id)
        print(f"Client disconnected: {session_id}")

    except Exception as e:
        print(f"WebSocket error: {e}")
        if session_id:
            manager.disconnect(session_id)


@router.websocket("/chat/{session_id}")
async def websocket_chat_session(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for resuming a specific session.
    Same protocol as /chat but with predefined session_id.
    """
    try:
        await websocket.accept()
        manager.active_connections[session_id] = websocket

        # Load existing session
        from app.main import storage
        state = {}

        if storage:
            try:
                existing_session = await storage.get_session(session_id)
                if existing_session:
                    state = existing_session.get("state", {})

                    # Send session history
                    turns = await storage.get_turns(session_id)
                    await websocket.send_json({
                        "type": "history",
                        "session_id": session_id,
                        "turns": [
                            {
                                "turn_number": t["turn_number"],
                                "question": t["user_question"],
                                "response": t["agent_response"]
                            }
                            for t in turns
                        ]
                    })
            except Exception as e:
                print(f"Could not load session: {e}")

        while True:
            data = await websocket.receive_json()

            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "message":
                user_id = data.get("user_id", state.get("user_id", "anonymous"))
                user_email = data.get("user_email")
                question = data.get("question", "").strip()

                if not question:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Question cannot be empty"
                    })
                    continue

                state["current_question"] = question
                state["user_question"] = question
                state["session_id"] = session_id
                state["user_id"] = user_id

                try:
                    await stream_response(
                        websocket=websocket,
                        session_id=session_id,
                        question=question,
                        user_id=user_id,
                        state=state,
                        user_email=user_email
                    )
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        print(f"Client disconnected from session: {session_id}")

    except Exception as e:
        print(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(session_id)

"""
REST API router for session management.
Handles listing, retrieving, and deleting chat sessions.
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

router = APIRouter()


# =========================================================================
# PYDANTIC MODELS
# =========================================================================

class SessionSummary(BaseModel):
    """Session summary for list view."""
    session_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TurnResponse(BaseModel):
    """Single conversation turn."""
    turn_number: int
    question: str
    response: str
    created_at: Optional[str] = None


class SessionDetail(BaseModel):
    """Full session details with conversation history."""
    session_id: str
    user_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    turns: List[TurnResponse] = []


class SessionListResponse(BaseModel):
    """Paginated session list response."""
    sessions: List[SessionSummary]
    total: int
    limit: int
    offset: int


class DeleteResponse(BaseModel):
    """Delete operation response."""
    success: bool
    message: str


# =========================================================================
# DEPENDENCY: Get storage
# =========================================================================

async def get_storage():
    """Get storage instance from main app."""
    from app.main import storage
    if storage is None:
        raise HTTPException(
            status_code=503,
            detail="Storage not initialized"
        )
    return storage


# =========================================================================
# ENDPOINTS
# =========================================================================

@router.get("", response_model=SessionListResponse)
async def list_sessions(
    user_id: str = Query(..., description="User ID to list sessions for"),
    limit: int = Query(50, ge=1, le=100, description="Maximum sessions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    storage=Depends(get_storage)
):
    """
    List chat sessions for a user.

    Returns sessions ordered by most recently updated first.
    """
    try:
        sessions = await storage.list_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return SessionListResponse(
            sessions=[
                SessionSummary(
                    session_id=s["session_id"],
                    title=s.get("title"),
                    created_at=str(s.get("created_at")) if s.get("created_at") else None,
                    updated_at=str(s.get("updated_at")) if s.get("updated_at") else None
                )
                for s in sessions
            ],
            total=len(sessions),  # Could be enhanced with COUNT query
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    include_turns: bool = Query(True, description="Include conversation history"),
    storage=Depends(get_storage)
):
    """
    Get session details by ID.

    Optionally includes full conversation history.
    """
    try:
        session = await storage.get_session(session_id)

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )

        turns = []
        if include_turns:
            turn_data = await storage.get_turns(session_id)
            turns = [
                TurnResponse(
                    turn_number=t["turn_number"],
                    question=t["user_question"],
                    response=t["agent_response"],
                    created_at=str(t.get("created_at")) if t.get("created_at") else None
                )
                for t in turn_data
            ]

        return SessionDetail(
            session_id=session["session_id"],
            user_id=session["user_id"],
            title=session.get("title"),
            created_at=str(session.get("created_at")) if session.get("created_at") else None,
            updated_at=str(session.get("updated_at")) if session.get("updated_at") else None,
            turns=turns
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/history", response_model=List[TurnResponse])
async def get_session_history(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit number of turns"),
    storage=Depends(get_storage)
):
    """
    Get conversation history for a session.

    Returns turns in chronological order.
    """
    try:
        # Verify session exists
        session = await storage.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )

        turns = await storage.get_turns(session_id, limit=limit)

        return [
            TurnResponse(
                turn_number=t["turn_number"],
                question=t["user_question"],
                response=t["agent_response"],
                created_at=str(t.get("created_at")) if t.get("created_at") else None
            )
            for t in turns
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}", response_model=DeleteResponse)
async def delete_session(
    session_id: str,
    storage=Depends(get_storage)
):
    """
    Delete a session and all its conversation history.

    This action is irreversible.
    """
    try:
        # Verify session exists
        session = await storage.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )

        await storage.delete_session(session_id)

        return DeleteResponse(
            success=True,
            message=f"Session {session_id} deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/state")
async def get_session_state(
    session_id: str,
    storage=Depends(get_storage)
):
    """
    Get the full AgentState for a session.

    Useful for debugging or resuming workflows.
    """
    try:
        session = await storage.get_session(session_id)

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )

        return {
            "session_id": session_id,
            "state": session.get("state", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

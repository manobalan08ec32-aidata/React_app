"""
Workflow service that wraps the existing LangGraph workflow.
Provides streaming integration for WebSocket responses.
"""
import sys
import os
from pathlib import Path
from typing import Dict, Any, AsyncGenerator, Optional
from datetime import datetime, timezone

# Add the parent Agentic_view folder to path for imports
# Structure: Agentic_view/healthcare-api/app/services/workflow.py
#            ^^^^^^^^^^^^ This is what we need (3 levels up)
AGENTIC_VIEW_PATH = Path(__file__).parent.parent.parent.parent
if str(AGENTIC_VIEW_PATH) not in sys.path:
    sys.path.insert(0, str(AGENTIC_VIEW_PATH))


class WorkflowService:
    """
    Service layer for the Healthcare Finance LangGraph workflow.

    Handles workflow initialization, state management, and streaming.
    """

    def __init__(self):
        self._workflow = None
        self._db_client = None
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize the workflow and Databricks client.

        Returns True if successful, False otherwise.
        """
        if self._initialized:
            return True

        try:
            # Import from existing codebase
            from core.databricks_client import DatabricksClient
            from langraph_workflow import AsyncHealthcareFinanceWorkflow

            # Initialize Databricks client
            self._db_client = DatabricksClient()

            # Initialize workflow
            self._workflow = AsyncHealthcareFinanceWorkflow(self._db_client)

            self._initialized = True
            print("Workflow service initialized successfully")
            return True

        except ImportError as e:
            print(f"Could not import workflow components: {e}")
            print("Make sure Agentic_view is in the path")
            return False

        except Exception as e:
            print(f"Error initializing workflow: {e}")
            return False

    @property
    def is_initialized(self) -> bool:
        """Check if workflow is initialized."""
        return self._initialized

    def _build_initial_state(
        self,
        question: str,
        session_id: str,
        user_id: str,
        user_email: Optional[str] = None,
        existing_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build initial AgentState for workflow execution.

        Merges existing session state with new question.
        """
        # Start with existing state or empty dict
        state = dict(existing_state) if existing_state else {}

        # Required fields
        state["user_question"] = question
        state["current_question"] = question
        state["session_id"] = session_id
        state["user_id"] = user_id
        state["user_email"] = user_email

        # Set timestamp
        state["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Initialize lists if not present
        if "user_question_history" not in state:
            state["user_question_history"] = []
        if "errors" not in state:
            state["errors"] = []

        return state

    async def run_workflow(
        self,
        question: str,
        session_id: str,
        user_id: str,
        user_email: Optional[str] = None,
        existing_state: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run the main workflow and stream events.

        Yields events in the format:
        - {"type": "node_start", "name": "node_name", "data": {...}}
        - {"type": "node_end", "name": "node_name", "data": {...}}
        - {"type": "stream_token", "token": "...", "node": "..."}
        - {"type": "workflow_end", "data": {...}}
        - {"type": "error", "error": "..."}
        """
        if not self._initialized:
            success = await self.initialize()
            if not success:
                yield {
                    "type": "error",
                    "error": "Workflow not initialized. Check server logs."
                }
                return

        # Build initial state
        initial_state = self._build_initial_state(
            question=question,
            session_id=session_id,
            user_id=user_id,
            user_email=user_email,
            existing_state=existing_state
        )

        # Workflow config
        config = {
            "configurable": {
                "thread_id": thread_id or session_id
            }
        }

        try:
            # Yield start event
            yield {
                "type": "workflow_start",
                "session_id": session_id,
                "question": question
            }

            # Stream workflow events
            async for event in self._workflow.astream_events(initial_state, config):
                event_type = event.get("type", "unknown")
                node_name = event.get("name", "")
                node_data = event.get("data", {})

                if event_type == "node_end":
                    # Node completed - send status update
                    yield {
                        "type": "node_complete",
                        "node": node_name,
                        "status": self._get_node_status_message(node_name, node_data)
                    }

                    # Check for response content to stream
                    if node_name == "narrative_agent":
                        narrative = node_data.get("narrative_response", "")
                        if narrative:
                            yield {
                                "type": "narrative",
                                "content": narrative
                            }

                    # Check for SQL results
                    if "sql_result" in node_data and node_data["sql_result"]:
                        yield {
                            "type": "sql_result",
                            "data": node_data["sql_result"]
                        }

                    # Check for chart spec
                    if "chart_spec" in node_data and node_data["chart_spec"]:
                        yield {
                            "type": "chart",
                            "spec": node_data["chart_spec"]
                        }

                elif event_type == "workflow_end":
                    # Workflow completed
                    final_state = node_data

                    yield {
                        "type": "workflow_end",
                        "state": self._sanitize_state_for_response(final_state)
                    }

        except Exception as e:
            yield {
                "type": "error",
                "error": str(e)
            }

    async def run_followup_workflow(
        self,
        state_after_main: Dict[str, Any],
        session_id: str,
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the follow-up question generation workflow."""
        if not self._initialized:
            yield {"type": "error", "error": "Workflow not initialized"}
            return

        config = {
            "configurable": {
                "thread_id": thread_id or session_id
            }
        }

        try:
            async for step in self._workflow.astream_followup(state_after_main, config):
                for node_name, node_state in step.items():
                    if "followup_questions" in node_state:
                        yield {
                            "type": "followup_questions",
                            "questions": node_state["followup_questions"]
                        }

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    async def run_narrative_workflow(
        self,
        state_with_sql: Dict[str, Any],
        session_id: str,
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the narrative synthesis workflow."""
        if not self._initialized:
            yield {"type": "error", "error": "Workflow not initialized"}
            return

        config = {
            "configurable": {
                "thread_id": thread_id or session_id
            }
        }

        try:
            async for step in self._workflow.astream_narrative(state_with_sql, config):
                for node_name, node_state in step.items():
                    if "narrative_response" in node_state:
                        yield {
                            "type": "narrative",
                            "content": node_state["narrative_response"]
                        }

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    def _get_node_status_message(self, node_name: str, node_data: Dict) -> str:
        """Get user-friendly status message for a node."""
        status_messages = {
            "entry_router": "Analyzing your question...",
            "navigation_controller": "Understanding intent and context...",
            "router_agent": "Selecting relevant data sources...",
            "strategy_planner_agent": "Planning analysis strategy...",
            "drillthrough_planner_agent": "Performing detailed analysis...",
            "narrative_agent": "Generating response...",
            "followup_question_agent": "Suggesting follow-up questions..."
        }

        # Check for specific conditions
        if node_data.get("requires_domain_clarification"):
            return "Need clarification on which area to analyze..."
        if node_data.get("requires_dataset_clarification"):
            return "Need clarification on which dataset to use..."
        if node_data.get("greeting_response"):
            return "Responding to greeting..."

        return status_messages.get(node_name, f"Processing {node_name}...")

    def _sanitize_state_for_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize state for client response.
        Remove large/sensitive fields, keep useful info.
        """
        # Fields to include in response
        include_fields = {
            "session_id", "user_id", "current_question", "user_question",
            "question_type", "rewritten_question", "next_agent",
            "domain_selection", "selected_dataset", "functional_names",
            "greeting_response", "narrative_response", "followup_questions",
            "chart_spec", "report_found", "report_url", "report_name",
            "requires_domain_clarification", "domain_followup_question",
            "requires_dataset_clarification", "dataset_followup_question",
            "needs_followup", "sql_followup_question",
            "errors", "nav_error_msg", "user_friendly_message"
        }

        return {
            k: v for k, v in state.items()
            if k in include_fields and v is not None
        }


# Global workflow service instance
workflow_service = WorkflowService()


async def get_workflow_service() -> WorkflowService:
    """Dependency injection for workflow service."""
    if not workflow_service.is_initialized:
        await workflow_service.initialize()
    return workflow_service

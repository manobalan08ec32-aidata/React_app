"""
Abstract base class for storage backends.
Allows swapping between Databricks, Cosmos DB, or other storage implementations.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime


class StorageBackend(ABC):
    """
    Abstract storage interface for session and turn persistence.

    Implement this interface to support different storage backends:
    - DatabricksStorage (current)
    - CosmosDBStorage (future)
    - RedisStorage (if needed)
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the storage backend (create tables, connect, etc.).
        Called once at application startup.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Clean up resources (close connections, etc.).
        Called at application shutdown.
        """
        pass

    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================

    @abstractmethod
    async def save_session(
        self,
        session_id: str,
        user_id: str,
        state: Dict[str, Any],
        title: Optional[str] = None
    ) -> None:
        """
        Save or update a chat session.

        Args:
            session_id: Unique session identifier
            user_id: User who owns this session
            state: Current AgentState dictionary
            title: Optional session title (e.g., first question asked)
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID.

        Returns:
            Session dict with keys: session_id, user_id, state, title,
            created_at, updated_at. Returns None if not found.
        """
        pass

    @abstractmethod
    async def list_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List sessions for a user, ordered by most recent first.

        Returns:
            List of session dicts (without full state for efficiency)
        """
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its turns.

        Returns:
            True if deleted, False if not found
        """
        pass

    # =========================================================================
    # TURN OPERATIONS (Conversation History)
    # =========================================================================

    @abstractmethod
    async def save_turn(
        self,
        session_id: str,
        turn_number: int,
        user_question: str,
        agent_response: str,
        state_snapshot: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save a conversation turn.

        Args:
            session_id: Session this turn belongs to
            turn_number: Sequential turn number (1, 2, 3, ...)
            user_question: What the user asked
            agent_response: Full response from the agent
            state_snapshot: AgentState at end of this turn
            metadata: Optional metadata (timing, tokens used, etc.)
        """
        pass

    @abstractmethod
    async def get_turns(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation turns for a session, ordered by turn_number.

        Returns:
            List of turn dicts with keys: turn_number, user_question,
            agent_response, state_snapshot, metadata, created_at
        """
        pass

    @abstractmethod
    async def get_latest_turn(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent turn for a session.
        Useful for resuming conversations.

        Returns:
            Turn dict or None if no turns exist
        """
        pass

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if storage backend is healthy and connected.

        Returns:
            True if healthy, False otherwise
        """
        pass

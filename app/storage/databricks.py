"""
Databricks storage implementation for session and turn persistence.
Uses Databricks SQL Warehouse for storage operations.
"""
import json
import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.storage.base import StorageBackend
from config import settings


class DatabricksStorage(StorageBackend):
    """
    Databricks-based storage implementation.

    Stores sessions and turns in Delta tables for reliable persistence.
    Uses async HTTP calls to Databricks SQL Warehouse API.
    """

    def __init__(self):
        self.host = settings.databricks_host
        self.token = settings.databricks_token
        self.warehouse_id = settings.sql_warehouse_id
        self.sessions_table = settings.chat_sessions_table
        self.turns_table = settings.chat_turns_table

        self.sql_api_url = f"{self.host}/api/2.0/sql/statements/"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        self._http_session: Optional[aiohttp.ClientSession] = None
        self._http_timeout = aiohttp.ClientTimeout(
            total=180,
            connect=15,
            sock_read=90,
            sock_connect=15
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None or self._http_session.closed:
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=60,
                enable_cleanup_closed=True
            )
            self._http_session = aiohttp.ClientSession(
                timeout=self._http_timeout,
                connector=connector
            )
        return self._http_session

    async def _execute_sql(self, sql_query: str, timeout: int = 300) -> List[Dict]:
        """Execute SQL query against Databricks warehouse."""
        payload = {
            "warehouse_id": self.warehouse_id,
            "statement": sql_query,
            "disposition": "INLINE",
            "wait_timeout": "10s"
        }

        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                session = await self._get_session()
                async with session.post(
                    self.sql_api_url,
                    headers=self.headers,
                    json=payload
                ) as response:
                    result = await response.json()

                    if response.status != 200:
                        raise Exception(f"SQL API error: {result}")

                    state = result.get("status", {}).get("state", "")

                    # Poll for completion if pending
                    statement_id = result.get("statement_id")
                    poll_count = 0
                    max_polls = timeout // 2

                    while state in ("PENDING", "RUNNING") and poll_count < max_polls:
                        await asyncio.sleep(2)
                        poll_count += 1

                        async with session.get(
                            f"{self.sql_api_url}{statement_id}",
                            headers=self.headers
                        ) as poll_response:
                            result = await poll_response.json()
                            state = result.get("status", {}).get("state", "")

                    if state == "SUCCEEDED":
                        manifest = result.get("manifest", {})
                        columns = [col["name"] for col in manifest.get("schema", {}).get("columns", [])]
                        data = result.get("result", {}).get("data_array", [])
                        return [dict(zip(columns, row)) for row in data]

                    elif state == "FAILED":
                        error = result.get("status", {}).get("error", {})
                        raise Exception(f"SQL execution failed: {error}")

                    else:
                        raise Exception(f"Unexpected SQL state: {state}")

            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        return []

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        # Create sessions table
        create_sessions_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.sessions_table} (
            session_id STRING NOT NULL,
            user_id STRING NOT NULL,
            title STRING,
            state STRING,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        USING DELTA
        """

        # Create turns table
        create_turns_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.turns_table} (
            session_id STRING NOT NULL,
            turn_number INT NOT NULL,
            user_question STRING,
            agent_response STRING,
            state_snapshot STRING,
            metadata STRING,
            created_at TIMESTAMP
        )
        USING DELTA
        """

        await self._execute_sql(create_sessions_sql)
        await self._execute_sql(create_turns_sql)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================

    async def save_session(
        self,
        session_id: str,
        user_id: str,
        state: Dict[str, Any],
        title: Optional[str] = None
    ) -> None:
        """Save or update a chat session using MERGE."""
        now = datetime.now(timezone.utc).isoformat()
        state_json = json.dumps(state).replace("'", "''")
        title_escaped = (title or "").replace("'", "''")

        merge_sql = f"""
        MERGE INTO {self.sessions_table} AS target
        USING (SELECT '{session_id}' AS session_id) AS source
        ON target.session_id = source.session_id
        WHEN MATCHED THEN
            UPDATE SET
                state = '{state_json}',
                title = '{title_escaped}',
                updated_at = '{now}'
        WHEN NOT MATCHED THEN
            INSERT (session_id, user_id, title, state, created_at, updated_at)
            VALUES ('{session_id}', '{user_id}', '{title_escaped}', '{state_json}', '{now}', '{now}')
        """

        await self._execute_sql(merge_sql)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        sql = f"""
        SELECT session_id, user_id, title, state, created_at, updated_at
        FROM {self.sessions_table}
        WHERE session_id = '{session_id}'
        """

        results = await self._execute_sql(sql)
        if not results:
            return None

        row = results[0]
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "state": json.loads(row["state"]) if row["state"] else {},
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List sessions for a user."""
        sql = f"""
        SELECT session_id, user_id, title, created_at, updated_at
        FROM {self.sessions_table}
        WHERE user_id = '{user_id}'
        ORDER BY updated_at DESC
        LIMIT {limit} OFFSET {offset}
        """

        results = await self._execute_sql(sql)
        return [
            {
                "session_id": row["session_id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            for row in results
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its turns."""
        # Delete turns first
        await self._execute_sql(
            f"DELETE FROM {self.turns_table} WHERE session_id = '{session_id}'"
        )

        # Delete session
        await self._execute_sql(
            f"DELETE FROM {self.sessions_table} WHERE session_id = '{session_id}'"
        )

        return True

    # =========================================================================
    # TURN OPERATIONS
    # =========================================================================

    async def save_turn(
        self,
        session_id: str,
        turn_number: int,
        user_question: str,
        agent_response: str,
        state_snapshot: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a conversation turn."""
        now = datetime.now(timezone.utc).isoformat()
        question_escaped = user_question.replace("'", "''")
        response_escaped = agent_response.replace("'", "''")
        state_json = json.dumps(state_snapshot).replace("'", "''")
        metadata_json = json.dumps(metadata or {}).replace("'", "''")

        sql = f"""
        INSERT INTO {self.turns_table}
        (session_id, turn_number, user_question, agent_response, state_snapshot, metadata, created_at)
        VALUES ('{session_id}', {turn_number}, '{question_escaped}', '{response_escaped}', '{state_json}', '{metadata_json}', '{now}')
        """

        await self._execute_sql(sql)

    async def get_turns(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation turns for a session."""
        limit_clause = f"LIMIT {limit}" if limit else ""

        sql = f"""
        SELECT turn_number, user_question, agent_response, state_snapshot, metadata, created_at
        FROM {self.turns_table}
        WHERE session_id = '{session_id}'
        ORDER BY turn_number ASC
        {limit_clause}
        """

        results = await self._execute_sql(sql)
        return [
            {
                "turn_number": row["turn_number"],
                "user_question": row["user_question"],
                "agent_response": row["agent_response"],
                "state_snapshot": json.loads(row["state_snapshot"]) if row["state_snapshot"] else {},
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "created_at": row["created_at"]
            }
            for row in results
        ]

    async def get_latest_turn(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent turn for a session."""
        sql = f"""
        SELECT turn_number, user_question, agent_response, state_snapshot, metadata, created_at
        FROM {self.turns_table}
        WHERE session_id = '{session_id}'
        ORDER BY turn_number DESC
        LIMIT 1
        """

        results = await self._execute_sql(sql)
        if not results:
            return None

        row = results[0]
        return {
            "turn_number": row["turn_number"],
            "user_question": row["user_question"],
            "agent_response": row["agent_response"],
            "state_snapshot": json.loads(row["state_snapshot"]) if row["state_snapshot"] else {},
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"]
        }

    async def health_check(self) -> bool:
        """Check if Databricks connection is healthy."""
        try:
            results = await self._execute_sql("SELECT 1 AS health")
            return len(results) > 0 and results[0].get("health") == "1"
        except Exception:
            return False

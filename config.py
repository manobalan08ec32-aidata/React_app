"""
Configuration module for Healthcare API.
Loads environment variables and provides typed settings.
"""
import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache

# Load .env file if it exists
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # =============================================================
    # DATABRICKS CONFIGURATION
    # =============================================================
    databricks_host: str = os.getenv("DATABRICKS_HOST", "")
    databricks_llm_host: str = os.getenv("DATABRICKS_LLM_HOST", "")
    databricks_token: str = os.getenv("DATABRICKS_TOKEN", "")
    databricks_llm_token: str = os.getenv("DATABRICKS_LLM_TOKEN", "")
    sql_warehouse_id: str = os.getenv("SQL_WAREHOUSE_ID", "")

    # Databricks OAuth (for service principal auth)
    databricks_client_id: Optional[str] = os.getenv("DATABRICKS_CLIENT_ID")
    databricks_client_secret: Optional[str] = os.getenv("DATABRICKS_CLIENT_SECRET")
    databricks_tenant_id: Optional[str] = os.getenv("DATABRICKS_TENANT_ID")
    databricks_adb_id: Optional[str] = os.getenv("DATABRICKS_ADB_ID")

    # =============================================================
    # DATABRICKS TABLE/INDEX NAMES
    # =============================================================
    vector_table_index: str = "prd_optumrx_orxfdmprdsa.rag.table_chunks"
    session_table: str = "prd_optumrx_orxfdmprdsa.rag.session_state"
    rootcause_index: str = "prd_optumrx_orxfdmprdsa.rag.rootcause_chunks"
    llm_model: str = "databricks-claude-sonnet-4"

    # =============================================================
    # CLAUDE API CONFIGURATION
    # =============================================================
    claude_project_id: Optional[str] = os.getenv("CLAUDE_PROJECT_ID")
    claude_client_id: Optional[str] = os.getenv("CLAUDE_CLIENT_ID")
    claude_client_secret: Optional[str] = os.getenv("CLAUDE_CLIENT_SECRET")
    claude_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    claude_api_url: str = "https://api.uhg.com/api/cloud/api-management/ai-gateway/1.0"
    claude_auth_url: str = "https://api.uhg.com/oauth2/token"

    # =============================================================
    # OPENAI API CONFIGURATION
    # =============================================================
    openai_project_id: Optional[str] = os.getenv("OPENAI_PROJECT_ID", "d7b5ad10-4880-4f07-9495-ae0fcc5035b3")
    openai_model_id: str = "gpt-5_2025-08-07"
    openai_api_url: str = "https://api.uhg.com/api/cloud/api-management/ai-gateway-reasoning/1.0"
    openai_api_version: str = "2025-01-01-preview"

    # =============================================================
    # UHG API CONFIGURATION
    # =============================================================
    uhg_project_id: Optional[str] = os.getenv("UHG_PROJECT_ID")
    uhg_client_id: Optional[str] = os.getenv("UHG_CLIENT_ID")
    uhg_client_secret: Optional[str] = os.getenv("UHG_CLIENT_SECRET")
    uhg_auth_url: str = "https://api.uhg.com/oauth2/token"
    uhg_scope: str = "https://api.uhg.com/.default"
    uhg_deployment_name: str = "gpt-4o_2024-11-20"
    uhg_endpoint: str = "https://api.uhg.com/api/cloud/api-management/ai-gateway/1.0"
    uhg_api_version: str = "2025-01-01-preview"

    # =============================================================
    # API SERVER CONFIGURATION
    # =============================================================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS settings
    cors_origins: list = ["http://localhost:3000", "http://localhost:5173"]

    # =============================================================
    # SESSION STORAGE CONFIGURATION
    # =============================================================
    # Table for storing chat sessions (will be created in Databricks)
    chat_sessions_table: str = "prd_optumrx_orxfdmprdsa.rag.chat_sessions"
    chat_turns_table: str = "prd_optumrx_orxfdmprdsa.rag.chat_turns"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()

"""Application configuration, loaded from environment variables / .env.
Nothing here is secret by default — see ../../.env.example for the full list.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg2://contextiq:contextiq@localhost:5432/contextiq"
    )
    environment: str = "development"
    log_level: str = "INFO"

    openai_api_key: str | None = None

    # Agent LLM provider (Phase 6). Defaults to a local Ollama model since
    # no hosted API key was available when this was built -- see
    # docs/agent.md. Swapping providers is a config change, not a code
    # change, as long as the replacement exposes a LangChain chat model.
    llm_provider: str = "ollama"
    ollama_model: str = "qwen3:4b"
    ollama_base_url: str = "http://localhost:11434"

    # Phase 13 (security): run_sql tool stays read-only unless this is true.
    allow_destructive_sql: bool = False


settings = Settings()

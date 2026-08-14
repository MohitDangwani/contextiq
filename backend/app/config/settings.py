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

    # LM Studio (OpenAI-compatible local server) -- alternative to Ollama,
    # selected via LLM_PROVIDER=lmstudio. The API key is a non-secret
    # placeholder LM Studio's local server does not validate.
    lmstudio_model: str = "nvidia/nemotron-3-nano-4b"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_api_key: str = "lm-studio"

    # Applies to whichever provider is active. Reasoning models (e.g.
    # Nemotron) spend tokens on a hidden reasoning pass before emitting a
    # tool call or final answer, so this needs headroom beyond what a
    # plain chat model would require.
    llm_max_tokens: int = 2048

    # Phase 13 (security): run_sql tool stays read-only unless this is true.
    allow_destructive_sql: bool = False


settings = Settings()

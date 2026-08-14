"""LLM provider for the agent, entirely driven by app.config.settings --
no hardcoded model name, base URL, or API key.

Two providers are implemented: "ollama" (default) and "lmstudio" (an
OpenAI-compatible local server, e.g. LM Studio). Adding either later meant
adding a branch here that returns a different LangChain chat model --
nothing in app/agent/graph.py or app/agent/tools.py depends on which
provider produced the model, only that it's a LangChain BaseChatModel
supporting .bind_tools().
"""
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config.settings import settings


def get_chat_model(bind_tools_list: list | None = None) -> BaseChatModel:
    if settings.llm_provider == "ollama":
        model: BaseChatModel = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0,
        )
    elif settings.llm_provider == "lmstudio":
        model = ChatOpenAI(
            model=settings.lmstudio_model,
            base_url=settings.lmstudio_base_url,
            api_key=settings.lmstudio_api_key,
            temperature=0,
            max_tokens=settings.llm_max_tokens,
        )
    else:
        raise ValueError(
            f"Unsupported llm_provider={settings.llm_provider!r}. "
            "Expected 'ollama' or 'lmstudio'."
        )

    if bind_tools_list:
        model = model.bind_tools(bind_tools_list)
    return model

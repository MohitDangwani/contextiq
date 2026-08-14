"""LLM provider for the agent, entirely driven by app.config.settings --
no hardcoded model name, base URL, or API key.

Currently only "ollama" is implemented (see docs/agent.md for why: no
hosted LLM API key was available). Adding a hosted provider later means
adding a branch here that returns a different LangChain chat model --
nothing in app/agent/graph.py or app/agent/tools.py depends on which
provider produced the model, only that it's a LangChain BaseChatModel
supporting .bind_tools().
"""
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config.settings import settings


def get_chat_model(bind_tools_list: list | None = None) -> BaseChatModel:
    if settings.llm_provider != "ollama":
        raise ValueError(
            f"Unsupported llm_provider={settings.llm_provider!r}. Only 'ollama' is implemented."
        )

    model: BaseChatModel = ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )
    if bind_tools_list:
        model = model.bind_tools(bind_tools_list)
    return model

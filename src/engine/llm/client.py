"""LLM client abstract base + factory.

Four backends:
- DirectAPI: uses anthropic SDK directly (requires API key)
- AgentSDK: uses Claude Agent SDK (OAuth token or logged-in CLI session)
- OpenAIClient: uses openai SDK (any OpenAI-compatible API)

Priority (first match wins):
1. OPENAI_BASE_URL set         → OpenAI-compatible API
2. ANTHROPIC_API_KEY set       → DirectAPI (per-token billing)
3. ANTHROPIC_AUTH_TOKEN set    → AgentSDK with OAuth token (subscription billing)
4. Neither                     → AgentSDK with CLI session (subscription billing)
"""

import logging
from abc import ABC, abstractmethod

from engine.llm.types import LLMResponse, MessageResponse, ToolDef

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    def complete(self, prompt: str, model: str) -> LLMResponse:
        """Send a prompt, get a text response. Synchronous."""
        ...

    @abstractmethod
    async def acomplete(self, prompt: str, model: str) -> LLMResponse:
        """Async version of complete."""
        ...

    async def amessages_create(
        self,
        *,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        system: str = "",
        max_tokens: int = 4096,
    ) -> MessageResponse:
        """Single async API call with messages, tools, and system prompt.

        Returns structured content blocks (text + tool_use).
        Subclasses implement this; the tool-use loop is managed by callers.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support amessages_create"
        )

    def complete_with_tools(
        self,
        prompt: str,
        model: str,
        tools: list[ToolDef],
        max_turns: int = 5,
    ) -> LLMResponse:
        """Multi-turn tool-use loop. Default raises NotImplementedError."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support tool use"
        )


def create_client(
    api_key: str = "",
    auth_token: str = "",
    openai_api_key: str = "",
    openai_base_url: str = "",
) -> LLMClient:
    """Factory: pick the right backend based on available credentials.

    Priority:
    1. OpenAI base URL → OpenAIClient (any compatible API)
    2. Anthropic API key → DirectAPIClient (per-token billing)
    3. OAuth token → AgentSDKClient with token
    4. Neither → AgentSDKClient with CLI session (user must be logged in)
    """
    if openai_base_url:
        from engine.llm.adapters.openai import OpenAIClient
        logger.info("Using OpenAI-compatible API (%s)", openai_base_url)
        return OpenAIClient(openai_api_key, openai_base_url)
    if api_key:
        from engine.llm.adapters.anthropic import DirectAPIClient
        logger.info("Using direct Anthropic API (API key)")
        return DirectAPIClient(api_key)
    if auth_token:
        from engine.llm.adapters.agent_sdk import AgentSDKClient
        logger.info("Using Claude Agent SDK (OAuth token)")
        return AgentSDKClient(auth_token)
    from engine.llm.adapters.agent_sdk import AgentSDKClient
    logger.info("Using Claude Agent SDK (CLI session)")
    return AgentSDKClient()

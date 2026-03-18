"""AgentSDK LLM client — uses Claude Agent SDK.

Auth priority:
1. Explicit OAuth token → CLAUDE_CODE_OAUTH_TOKEN env var
2. No token → relies on CLI's own session (~/.claude.json)
"""

import asyncio
import logging
import os

from engine.llm.client import LLMClient
from engine.llm.helpers import _serialize_messages_to_prompt, _parse_tool_calls
from engine.llm.types import ContentBlock, LLMResponse, MessageResponse, ToolDef

logger = logging.getLogger(__name__)


class AgentSDKClient(LLMClient):
    """Uses Claude Agent SDK — works with OAuth token or logged-in CLI session."""

    def __init__(self, auth_token: str = ""):
        self._auth_token = auth_token

    def _build_env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        if self._auth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = self._auth_token
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
            env.pop("ANTHROPIC_API_KEY", None)
        return env

    def complete(self, prompt: str, model: str) -> LLMResponse:
        return asyncio.run(self.acomplete(prompt, model))

    async def acomplete(self, prompt: str, model: str) -> LLMResponse:
        from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

        result_text = ""
        cost_usd = None
        usage: dict = {}
        async for msg in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                model=model,
                max_turns=1,
                permission_mode="bypassPermissions",
                tools=[],
                env=self._build_env(),
            ),
        ):
            if isinstance(msg, ResultMessage):
                result_text = msg.result or ""
                cost_usd = msg.total_cost_usd
                usage = msg.usage or {}

        return LLMResponse(
            text=result_text,
            cost_usd=cost_usd,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    def complete_with_tools(
        self,
        prompt: str,
        model: str,
        tools: list[ToolDef],
        max_turns: int = 5,
    ) -> LLMResponse:
        """Multi-turn tool-use loop via text-based <tool_call> parsing."""
        import json

        api_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        tool_handlers = {t.name: t.handler for t in tools}

        messages: list[dict] = [{"role": "user", "content": prompt}]
        total_input = 0
        total_output = 0
        final_text = ""

        for _turn in range(max_turns):
            text_prompt = _serialize_messages_to_prompt(messages, api_tools)
            resp = self.complete(text_prompt, model)
            total_input += resp.input_tokens
            total_output += resp.output_tokens

            blocks = _parse_tool_calls(resp.text)
            text_blocks = [b for b in blocks if b.type == "text"]
            tool_uses = [b for b in blocks if b.type == "tool_use"]

            if text_blocks:
                final_text = text_blocks[-1].text

            if not tool_uses:
                break

            messages.append({"role": "assistant", "content": resp.text})
            tool_results = []
            for tu in tool_uses:
                handler = tool_handlers.get(tu.tool_name)
                if handler:
                    try:
                        result = handler(**(tu.tool_input or {}))
                        tool_results.append(
                            f"[Tool result for {tu.tool_name}: "
                            f"{json.dumps(result, default=str)[:2000]}]"
                        )
                    except Exception as e:
                        logger.warning("Tool %s failed: %s", tu.tool_name, e)
                        tool_results.append(f"[Tool {tu.tool_name} error: {e}]")
                else:
                    tool_results.append(f"[Unknown tool: {tu.tool_name}]")
            messages.append({"role": "user", "content": "\n".join(tool_results)})

        return LLMResponse(
            text=final_text,
            input_tokens=total_input,
            output_tokens=total_output,
        )

    async def amessages_create(
        self,
        *,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        system: str = "",
        max_tokens: int = 4096,
    ) -> MessageResponse:
        """Serialize to prompt, call query(), parse tool calls from response."""
        prompt = _serialize_messages_to_prompt(messages, tools, system)
        resp = await self.acomplete(prompt, model)
        blocks = _parse_tool_calls(resp.text) if tools else [
            ContentBlock(type="text", text=resp.text)
        ]
        has_tool_use = any(b.type == "tool_use" for b in blocks)
        return MessageResponse(
            content=blocks,
            stop_reason="tool_use" if has_tool_use else "end_turn",
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

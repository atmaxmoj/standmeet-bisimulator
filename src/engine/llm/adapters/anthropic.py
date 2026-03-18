"""DirectAPI LLM client — uses anthropic SDK directly (per-token billing)."""

import json
import logging
from typing import Any

from engine.llm.client import LLMClient
from engine.llm.types import ContentBlock, LLMResponse, MessageResponse, ToolDef

logger = logging.getLogger(__name__)


class DirectAPIClient(LLMClient):
    """Uses anthropic SDK directly — requires API key (per-token billing)."""

    def __init__(self, api_key: str):
        import anthropic
        self._sync = anthropic.Anthropic(api_key=api_key)
        self._async = anthropic.AsyncAnthropic(api_key=api_key)

    def complete(self, prompt: str, model: str) -> LLMResponse:
        response = self._sync.messages.create(
            model=model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        usage = response.usage
        return LLMResponse(
            text=raw,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    async def acomplete(self, prompt: str, model: str) -> LLMResponse:
        response = await self._async.messages.create(
            model=model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        usage = response.usage
        return LLMResponse(
            text=raw,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
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
        """Native Anthropic Messages API call with tool support."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if system:
            kwargs["system"] = system

        response = await self._async.messages.create(**kwargs)
        blocks = []
        for b in response.content:
            if b.type == "text":
                blocks.append(ContentBlock(type="text", text=b.text))
            elif b.type == "tool_use":
                blocks.append(ContentBlock(
                    type="tool_use",
                    tool_name=b.name,
                    tool_input=b.input,
                    tool_use_id=b.id,
                ))
        return MessageResponse(
            content=blocks,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def complete_with_tools(
        self,
        prompt: str,
        model: str,
        tools: list[ToolDef],
        max_turns: int = 5,
    ) -> LLMResponse:
        """Multi-turn tool-use loop using Anthropic SDK."""
        # Build tool definitions for the API
        api_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
        tool_handlers = {t.name: t.handler for t in tools}

        messages = [{"role": "user", "content": prompt}]
        total_input = 0
        total_output = 0
        final_text = ""

        for turn in range(max_turns):
            logger.debug(
                "complete_with_tools turn=%d model=%s max_tokens=8192 tools=%d msg_count=%d msg_roles=%s",
                turn, model, len(api_tools), len(messages),
                [m["role"] for m in messages],
            )
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "max_tokens": 16384,
                    "messages": messages,
                    "tools": api_tools,
                }
                # Opus 4.6 / Sonnet 4.6 require adaptive thinking
                if "opus-4-6" in model or "sonnet-4-6" in model:
                    kwargs["thinking"] = {"type": "adaptive"}
                response = self._sync.messages.create(**kwargs)
            except Exception as e:
                logger.error(
                    "complete_with_tools FAILED turn=%d model=%s tools=%s prompt_len=%d: %s",
                    turn, model, [t["name"] for t in api_tools],
                    sum(len(str(m.get("content", ""))) for m in messages), e,
                )
                raise

            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            # Check if the model wants to use tools
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if text_blocks:
                final_text = text_blocks[-1].text

            if not tool_uses or response.stop_reason == "end_turn":
                # No more tool calls, we're done
                if not final_text and text_blocks:
                    final_text = text_blocks[0].text
                break

            # Execute tool calls and build tool_result messages
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tool_use in tool_uses:
                handler = tool_handlers.get(tool_use.name)
                if handler:
                    try:
                        result = handler(**tool_use.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result, default=str),
                        })
                    except Exception as e:
                        logger.warning("Tool %s failed: %s", tool_use.name, e)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps({"error": str(e)}),
                            "is_error": True,
                        })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps({"error": f"Unknown tool: {tool_use.name}"}),
                        "is_error": True,
                    })
            messages.append({"role": "user", "content": tool_results})

        return LLMResponse(
            text=final_text,
            input_tokens=total_input,
            output_tokens=total_output,
        )

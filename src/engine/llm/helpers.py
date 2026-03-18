"""LLM helper utilities for serialization and parsing."""

import json
import logging
import re

from engine.llm.types import ContentBlock

logger = logging.getLogger(__name__)


def _serialize_messages_to_prompt(
    messages: list[dict],
    tools: list[dict] | None = None,
    system: str = "",
) -> str:
    """Serialize structured messages + tools into a text prompt for text-only backends."""
    parts: list[str] = []
    if system:
        parts.append(f"<system>\n{system}\n</system>\n")
    if tools:
        tool_desc = json.dumps(tools, indent=2)
        parts.append(
            f"<available_tools>\n{tool_desc}\n</available_tools>\n\n"
            "When you need to call a tool, respond with ONLY a JSON block in this exact format:\n"
            '<tool_call>\n{"name": "tool_name", "input": {...}}\n</tool_call>\n\n'
            "When you have your final answer, respond with plain text (no tool_call tags).\n"
        )
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(f"<{role}>\n{content}\n</{role}>")
        elif isinstance(content, list):
            # Tool results or multi-block content
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_result":
                        texts.append(f"[Tool result: {block.get('content', '')}]")
                    elif block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    else:
                        texts.append(json.dumps(block, default=str))
                else:
                    texts.append(str(block))
            parts.append(f"<{role}>\n{''.join(texts)}\n</{role}>")
    return "\n".join(parts)


def _parse_tool_calls(text: str) -> list[ContentBlock]:
    """Parse <tool_call> blocks from text response. Returns ContentBlocks."""
    blocks: list[ContentBlock] = []
    pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
    matches = re.findall(pattern, text, re.DOTALL)
    for i, match in enumerate(matches):
        try:
            parsed = json.loads(match)
            blocks.append(ContentBlock(
                type="tool_use",
                tool_name=parsed["name"],
                tool_input=parsed.get("input", {}),
                tool_use_id=f"text_tool_{i}",
            ))
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse tool_call: %s", match)
    # Also extract non-tool-call text
    clean = re.sub(pattern, "", text, flags=re.DOTALL).strip()
    if clean:
        blocks.insert(0, ContentBlock(type="text", text=clean))
    return blocks

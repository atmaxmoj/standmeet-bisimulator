"""AgentService — generic Agent SDK + MCP execution.

Shared agentic loop used by distill and compose pipelines.
"""

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from engine.config import MODEL_DEEP

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from an agentic MCP run."""
    result_text: str
    cost_usd: float
    input_tokens: int
    output_tokens: int


def run_agent_mcp(
    prompt: str,
    mcp_server: FastMCP,
    mcp_name: str,
    stage: str,
    conn: sqlite3.Connection,
    model: str = MODEL_DEEP,
    max_turns: int = 15,
) -> AgentResult:
    """Run Agent SDK query() with an in-process MCP server.

    Logs all messages at DEBUG level, records usage and pipeline log to DB.
    Returns AgentResult with text, cost, and token counts.
    """
    from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions, ResultMessage

    logger.info("%s: starting with MCP server", stage)

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        env.pop("ANTHROPIC_API_KEY", None)

    result_text = ""
    cost_usd = None
    usage: dict = {}

    async def _run():
        nonlocal result_text, cost_usd, usage
        async for msg in sdk_query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                model=model,
                max_turns=max_turns,
                permission_mode="bypassPermissions",
                mcp_servers={
                    mcp_name: {
                        "type": "sdk",
                        "name": f"{mcp_name}-tools",
                        "instance": mcp_server._mcp_server,
                    },
                },
                env=env,
            ),
        ):
            msg_type = type(msg).__name__
            logger.debug("%s msg: %s %s", stage, msg_type, str(msg)[:500])
            if isinstance(msg, ResultMessage):
                result_text = msg.result or ""
                cost_usd = msg.total_cost_usd
                usage = msg.usage or {}

    asyncio.run(_run())

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = cost_usd or 0

    from engine.storage.sync_db import SyncDB
    db = SyncDB(conn)
    db.record_usage(model, stage, input_tokens, output_tokens, cost)
    db.insert_pipeline_log(stage, prompt, result_text[:5000], model, input_tokens, output_tokens, cost)

    logger.info("%s: cost=$%.4f", stage, cost)
    return AgentResult(
        result_text=result_text,
        cost_usd=cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

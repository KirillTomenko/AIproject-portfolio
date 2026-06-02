import httpx
from config import MCP_SERVER_URL


async def call_tool(tool: str, arguments: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{MCP_SERVER_URL}/call",
            json={"tool": tool, "arguments": arguments},
        )
        r.raise_for_status()
        return r.json()

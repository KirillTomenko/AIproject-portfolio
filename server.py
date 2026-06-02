"""
Portfolio MCP Server
Запуск: python server.py
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import uvicorn

from db import init_db
from tools import (
    MCP_TOOLS,
    list_projects, find_project, add_project, update_project_status,
    get_stats, add_post_idea, list_post_ideas, safe_calculate, get_project_by_id
)

app = FastAPI(title="Portfolio MCP Server", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()
    print("✅ База данных инициализирована")


# ── MCP endpoints ─────────────────────────────────────────────────────────────

@app.get("/tools")
def get_tools():
    """Список доступных MCP-инструментов"""
    return {"tools": MCP_TOOLS}


class CallRequest(BaseModel):
    tool: str
    arguments: Optional[dict] = {}


@app.post("/call")
def call_tool(req: CallRequest):
    """Вызов MCP-инструмента"""
    t = req.tool
    a = req.arguments or {}

    try:
        if t == "list_projects":
            return list_projects(status=a.get("status"))
        elif t == "find_project":
            return find_project(query=a["query"])
        elif t == "add_project":
            return add_project(
                name=a["name"],
                description=a["description"],
                stack=a["stack"],
                status=a.get("status", "idea"),
                github_url=a.get("github_url", "")
            )
        elif t == "update_project_status":
            return update_project_status(project_id=a["project_id"], status=a["status"])
        elif t == "get_stats":
            return get_stats()
        elif t == "add_post_idea":
            return add_post_idea(idea=a["idea"], project_id=a.get("project_id"))
        elif t == "list_post_ideas":
            return list_post_ideas()
        elif t == "calculate":
            return safe_calculate(expression=a["expression"])
        elif t == "generate_post":
            project = get_project_by_id(a["project_id"]) if a.get("project_id") else None
            return {
                "topic": a["topic"],
                "project": project,
                "ready_for_generation": True
            }
        else:
            raise HTTPException(status_code=404, detail=f"Инструмент '{t}' не найден")
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Отсутствует параметр: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

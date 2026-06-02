import ast
import operator
from db import get_conn
from datetime import datetime

# ── Safe calculator ──────────────────────────────────────────────────────────

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"Операция {op_type.__name__} запрещена")
        return _ALLOWED_OPS[op_type](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Недопустимое выражение")


def safe_calculate(expression: str) -> dict:
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(tree.body)
        return {"result": result, "expression": expression}
    except Exception as e:
        return {"error": str(e), "expression": expression}


# ── Project tools ─────────────────────────────────────────────────────────────

def list_projects(status: str = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC", (status,))
    else:
        cur.execute("SELECT * FROM projects ORDER BY updated_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"projects": rows, "total": len(rows)}


def find_project(query: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{query}%"
    cur.execute(
        "SELECT * FROM projects WHERE name LIKE ? OR description LIKE ? OR stack LIKE ?",
        (like, like, like)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"projects": rows, "total": len(rows)}


def add_project(name: str, description: str, stack: str, status: str = "idea", github_url: str = "") -> dict:
    valid_statuses = {"idea", "in_progress", "done", "paused"}
    if status not in valid_statuses:
        return {"error": f"Статус должен быть одним из: {', '.join(valid_statuses)}"}
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO projects (name, description, stack, status, github_url) VALUES (?,?,?,?,?)",
        (name, description, stack, status, github_url)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"success": True, "id": new_id, "name": name}


def update_project_status(project_id: int, status: str) -> dict:
    valid_statuses = {"idea", "in_progress", "done", "paused"}
    if status not in valid_statuses:
        return {"error": f"Статус должен быть одним из: {', '.join(valid_statuses)}"}
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), project_id)
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    if affected == 0:
        return {"error": f"Проект с id={project_id} не найден"}
    return {"success": True, "id": project_id, "new_status": status}


def get_stats() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) as count FROM projects GROUP BY status")
    by_status = {row["status"]: row["count"] for row in cur.fetchall()}
    cur.execute("SELECT COUNT(*) as total FROM projects")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM post_ideas")
    ideas_count = cur.fetchone()["total"]
    conn.close()
    return {
        "total_projects": total,
        "by_status": by_status,
        "post_ideas_count": ideas_count,
    }


def add_post_idea(idea: str, project_id: int = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    if project_id:
        cur.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        if not cur.fetchone():
            conn.close()
            return {"error": f"Проект с id={project_id} не найден"}
    cur.execute(
        "INSERT INTO post_ideas (project_id, idea) VALUES (?,?)",
        (project_id, idea)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"success": True, "id": new_id, "idea": idea}


def list_post_ideas() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT pi.id, pi.idea, pi.created_at, p.name as project_name
        FROM post_ideas pi
        LEFT JOIN projects p ON pi.project_id = p.id
        ORDER BY pi.created_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"ideas": rows, "total": len(rows)}


def get_project_by_id(project_id: int) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"error": f"Proekt s id={project_id} ne najden"}
    return dict(row)


# ── MCP JSON Schema ───────────────────────────────────────────────────────────

MCP_TOOLS = [
    {
        "name": "list_projects",
        "description": "Возвращает список всех AI-проектов. Можно фильтровать по статусу: idea, in_progress, done, paused.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Фильтр по статусу (необязательно)"}
            },
            "required": []
        }
    },
    {
        "name": "find_project",
        "description": "Ищет проекты по названию, описанию или стеку технологий.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_project",
        "description": "Добавляет новый проект в портфолио.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "stack": {"type": "string"},
                "status": {"type": "string", "description": "idea | in_progress | done | paused"},
                "github_url": {"type": "string"}
            },
            "required": ["name", "description", "stack"]
        }
    },
    {
        "name": "update_project_status",
        "description": "Обновляет статус проекта по его ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "status": {"type": "string"}
            },
            "required": ["project_id", "status"]
        }
    },
    {
        "name": "get_stats",
        "description": "Возвращает статистику портфолио: сколько проектов по каждому статусу, количество идей для постов.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "add_post_idea",
        "description": "Сохраняет идею для поста в Telegram-канал.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idea": {"type": "string", "description": "Текст идеи для поста"},
                "project_id": {"type": "integer", "description": "ID связанного проекта (необязательно)"}
            },
            "required": ["idea"]
        }
    },
    {
        "name": "list_post_ideas",
        "description": "Возвращает список сохранённых идей для постов в канал.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "calculate",
        "description": "Безопасный калькулятор для математических выражений.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Математическое выражение, например '2 + 2 * 10'"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "generate_post",
        "description": "Генерирует черновик поста для Telegram-канала по теме или ID проекта. Возвращает данные для генерации — бот сам составит текст через LLM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Тема или идея поста"},
                "project_id": {"type": "integer", "description": "ID проекта из портфолио (необязательно)"}
            },
            "required": ["topic"]
        }
    }
]

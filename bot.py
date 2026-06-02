"""
Portfolio AI Bot
Запуск: venv\\Scripts\\python.exe bot.py
"""
import asyncio
import json
import logging
import ssl
import httpx

from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart, Command
from aiogram.types import Message


from config import TELEGRAM_TOKEN, OPENAI_API_KEY, MCP_SERVER_URL, OPENAI_BASE_URL, SOCKS5_PROXY
from mcp_client import call_tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Парсим порт из SOCKS5_PROXY строки (socks5://127.0.0.1:3067)
_proxy_port = int(SOCKS5_PROXY.split(":")[-1])

# Telegram Bot — через SOCKS5 (Karing), без SSL-ошибок
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

tg_session = AiohttpSession(proxy=f"socks5://127.0.0.1:{_proxy_port}")
bot = Bot(token=TELEGRAM_TOKEN, session=tg_session)
dp = Dispatcher()

# OpenAI — ProxyAPI base_url + SOCKS5 транспорт
_http_client = httpx.AsyncClient(proxy=SOCKS5_PROXY)
openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    http_client=_http_client,
)

# Per-user conversation history
user_history: dict[int, list] = {}

SYSTEM_PROMPT = """Ты — умный ассистент Кирилла, Python-разработчика, который ведёт Telegram-канал об AI-разработке.

Ты помогаешь управлять его портфолио AI-проектов: отслеживать проекты, их статусы, стек технологий, и сохранять идеи для постов в канал.

Доступные инструменты:
- list_projects — показать все проекты (можно с фильтром по статусу: idea, in_progress, done, paused)
- find_project — найти проект по названию или стеку
- add_project — добавить новый проект (name, description, stack, status, github_url)
- update_project_status — обновить статус проекта по ID
- get_stats — статистика портфолио
- add_post_idea — сохранить идею для поста в канал
- list_post_ideas — список сохранённых идей для постов
- calculate — посчитать математическое выражение
- generate_post — сгенерировать пост для Telegram-канала по теме или ID проекта

Когда нужен инструмент, отвечай ТОЛЬКО JSON без markdown:
{"tool": "название", "arguments": {"параметр": "значение"}}

Если инструмент не нужен — отвечай обычным текстом на русском.

Примеры:
"покажи все проекты" → {"tool": "list_projects", "arguments": {}}
"что в работе?" → {"tool": "list_projects", "arguments": {"status": "in_progress"}}
"найди проекты на FastAPI" → {"tool": "find_project", "arguments": {"query": "FastAPI"}}
"добавь идею для поста про MCP" → {"tool": "add_post_idea", "arguments": {"idea": "пост про MCP"}}
"статистика" → {"tool": "get_stats", "arguments": {}}
"переведи проект 3 в done" → {"tool": "update_project_status", "arguments": {"project_id": 3, "status": "done"}}
"напиши пост про MCP" → {"tool": "generate_post", "arguments": {"topic": "MCP-сервер для портфолио"}}
"напиши пост по проекту 6" → {"tool": "generate_post", "arguments": {"topic": "NexusAPI", "project_id": 6}}
"сгенерируй пост" → {"tool": "generate_post", "arguments": {"topic": "тема из последнего сообщения"}}

Форматируй ответы красиво, используй эмодзи умеренно. Отвечай дружелюбно и по делу."""

POST_GENERATION_PROMPT = """Ты — автор Telegram-канала о реальной Python-разработке. Пишешь от первого лица, как дневник разработчика.

СТРОГИЕ ПРАВИЛА:
- Используй ТОЛЬКО факты из сообщения. Ничего не выдумывай.
- Пиши живо: что конкретно сломалось, что попробовал, что сработало.
- Короткие абзацы, пустая строка между ними. Никаких списков и буллетов.
- 1 эмодзи в самом начале.
- В конце — короткий вывод или вопрос. Одна фраза.
- Длина: 120-180 слов.

Плохой стиль (так НЕ надо):
"Столкнулся с несколькими проблемами. Первая — X. Вторая — Y. Удалось найти решение."

Хороший стиль (вот так):
"Первым делом попытался создать venv — не вышло. Python 3.14 не мог скопировать лаунчер в папку окружения, молча падал с ошибкой. Погуглил, откатился на py -3.12 — заработало.

Дальше выяснилось, что aiogram требует pydantic<2.8, а fastapi тянет свежую. Пришлось явно фиксировать версию через pip install 'pydantic>=2.4.1,<2.8'."

Напиши пост в хорошем стиле про факты ниже:"""


def _format_projects(data: dict) -> str:
    projects = data.get("projects", [])
    if not projects:
        return "📭 Проектов не найдено."
    status_emoji = {"done": "✅", "in_progress": "🔨", "idea": "💡", "paused": "⏸"}
    lines = [f"📦 Найдено проектов: {len(projects)}\n"]
    for p in projects:
        emoji = status_emoji.get(p.get("status", ""), "•")
        lines.append(f"{emoji} <b>{p['name']}</b> (ID: {p['id']})")
        if p.get("description"):
            lines.append(f"   {p['description']}")
        if p.get("stack"):
            lines.append(f"   🛠 {p['stack']}")
        lines.append("")
    return "\n".join(lines)


def _format_stats(data: dict) -> str:
    by_status = data.get("by_status", {})
    lines = [
        "📊 <b>Статистика портфолио</b>\n",
        f"Всего проектов: <b>{data.get('total_projects', 0)}</b>",
        f"✅ Завершено: {by_status.get('done', 0)}",
        f"🔨 В работе: {by_status.get('in_progress', 0)}",
        f"💡 Идеи: {by_status.get('idea', 0)}",
        f"⏸ На паузе: {by_status.get('paused', 0)}",
        f"\n💬 Идей для постов: {data.get('post_ideas_count', 0)}",
    ]
    return "\n".join(lines)


def _format_post_ideas(data: dict) -> str:
    ideas = data.get("ideas", [])
    if not ideas:
        return "📭 Идей для постов пока нет."
    lines = [f"💬 <b>Идеи для постов ({len(ideas)})</b>\n"]
    for i in ideas:
        project = f" [{i['project_name']}]" if i.get("project_name") else ""
        lines.append(f"• {i['idea']}{project}")
    return "\n".join(lines)


def _format_tool_result(tool: str, result: dict) -> str:
    if "error" in result:
        return f"❌ Ошибка: {result['error']}"
    if tool in ("list_projects", "find_project"):
        return _format_projects(result)
    if tool == "get_stats":
        return _format_stats(result)
    if tool == "list_post_ideas":
        return _format_post_ideas(result)
    if tool == "calculate":
        if "result" in result:
            return f"🔢 {result['expression']} = <b>{result['result']}</b>"
        return f"❌ Ошибка вычисления: {result.get('error')}"
    if tool == "add_project" and result.get("success"):
        return f"✅ Проект <b>{result['name']}</b> добавлен (ID: {result['id']})"
    if tool == "update_project_status" and result.get("success"):
        return f"✅ Статус проекта ID={result['id']} обновлён на <b>{result['new_status']}</b>"
    if tool == "add_post_idea" and result.get("success"):
        return f"💡 Идея сохранена: «{result['idea']}»"
    return f"✅ Готово: {json.dumps(result, ensure_ascii=False)}"


async def _generate_post_text(topic: str, project: dict | None = None) -> str:
    project_context = ""
    if project and "error" not in project:
        project_context = (
            f"Название: {project.get('name')}\n"
            f"Описание: {project.get('description')}\n"
            f"Стек: {project.get('stack')}\n"
            f"Статус: {project.get('status')}"
        )

    user_content = f"Тема: {topic}\n"
    if project_context:
        user_content += f"\nДанные проекта (используй только их, ничего не придумывай):\n{project_context}"
    else:
        user_content += "\nДополнительного контекста нет — пиши только по теме."

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": POST_GENERATION_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()


async def process_with_llm(user_id: int, user_text: str) -> str:
    if user_id not in user_history:
        user_history[user_id] = []

    user_history[user_id].append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_history[user_id][-20:]

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
    )

    assistant_msg = response.choices[0].message.content.strip()
    user_history[user_id].append({"role": "assistant", "content": assistant_msg})

    # Пробуем распарсить как вызов инструмента
    try:
        cleaned = assistant_msg.strip().strip("```json").strip("```").strip()
        parsed = json.loads(cleaned)
        if "tool" in parsed:
            tool_name = parsed["tool"]
            arguments = parsed.get("arguments", {})
            result = await call_tool(tool_name, arguments)

            # generate_post — отдельная обработка через LLM
            if tool_name == "generate_post" and result.get("ready_for_generation"):
                post_text = await _generate_post_text(
                    topic=result["topic"],
                    project=result.get("project"),
                )
                user_history[user_id].append({
                    "role": "assistant",
                    "content": f"[Сгенерирован пост]: {post_text}",
                })
                return (
                    f"✍️ <b>Черновик поста:</b>\n\n"
                    f"{post_text}\n\n"
                    f"———\n"
                    f"Что можно улучшить? Напиши — и я доработаю."
                )

            formatted = _format_tool_result(tool_name, result)
            user_history[user_id].append({
                "role": "assistant",
                "content": f"[Результат инструмента {tool_name}]: {json.dumps(result, ensure_ascii=False)}",
            })
            return formatted
    except (json.JSONDecodeError, KeyError):
        pass

    return assistant_msg


# ── Handlers ──────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я ассистент для управления твоим портфолио AI-проектов.\n\n"
        "Что умею:\n"
        "• Показывать и искать проекты\n"
        "• Добавлять новые проекты\n"
        "• Обновлять статусы\n"
        "• Сохранять идеи для постов в канал\n"
        "• Считать что угодно\n\n"
        "Команды:\n"
        "/post [тема] — сгенерировать пост в твоём стиле\n"
        "Пример: /post поднимал FastAPI на VPS, nginx не видел порт...\n\n"
        "/stats — статистика портфолио\n"
        "/ideas — идеи для постов\n"
        "/clear — очистить историю диалога\n\n"
        "Для всего остального просто пиши обычным языком 👇",
        parse_mode="HTML",
    )


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    result = await call_tool("get_stats", {})
    await message.answer(_format_stats(result), parse_mode="HTML")


@dp.message(Command("ideas"))
async def cmd_ideas(message: Message) -> None:
    result = await call_tool("list_post_ideas", {})
    await message.answer(_format_post_ideas(result), parse_mode="HTML")

@dp.message(Command("post"))
async def cmd_post(message: Message) -> None:
    topic = message.text.replace("/post", "").strip()
    if not topic:
        await message.answer("Напиши тему после команды, например:\n/post поднимал MCP на Windows...")
        return
    await bot.send_chat_action(message.chat.id, "typing")
    post_text = await _generate_post_text(topic=topic)
    # Отправляем без parse_mode — plain text, никаких HTML-проблем
    await message.answer(
        f"✍️ Черновик поста:\n\n{post_text}\n\n———\nЧто улучшить?"
    )
@dp.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    user_history.pop(message.from_user.id, None)
    await message.answer("🗑 История диалога очищена.")


@dp.message()
async def handle_message(message: Message) -> None:
    if not message.text:
        return
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        answer = await process_with_llm(message.from_user.id, message.text)
        await message.answer(answer, parse_mode="HTML")
    except Exception as e:  # noqa: BLE001
        logging.error("Error: %s", e)
        await message.answer(f"⚠️ Ошибка: {e}")


async def main() -> None:
    logging.info("🤖 Бот запущен. MCP сервер: %s", MCP_SERVER_URL)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
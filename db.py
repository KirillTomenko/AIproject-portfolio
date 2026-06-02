import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "portfolio.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            stack TEXT,
            status TEXT DEFAULT 'idea',
            github_url TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS post_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            idea TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Seed with Kirill's real projects from his channel
    cur.execute("SELECT COUNT(*) FROM projects")
    if cur.fetchone()[0] == 0:
        seed_projects = [
            ("Lead Intake MVP", "Микросервис приёма заявок с уведомлениями в Telegram и Email", "FastAPI, SQLite, Docker", "done", "https://github.com/KirillTomenko"),
            ("UX Website Analyzer", "AI-аудит сайтов с рекомендациями по UX", "Python, OpenAI, BeautifulSoup", "done", "https://github.com/KirillTomenko"),
            ("Restaurant Feedback Bot", "Сбор обратной связи через Telegram-бот", "Python, aiogram, SQLite", "done", "https://github.com/KirillTomenko"),
            ("AI Sportdnevnik", "Персональный дневник тренировок с AI-анализом", "Python, OpenAI, Telegram", "done", "https://github.com/KirillTomenko"),
            ("Repo Analyzer", "Анализ GitHub-репозитория через AI", "Python, GitHub API, Claude", "done", "https://github.com/KirillTomenko"),
            ("NexusAPI", "FastAPI + CI/CD с Loki + Grafana на VPS", "FastAPI, Docker, GitHub Actions, Grafana", "done", "https://github.com/KirillTomenko"),
            ("Console AI Assistant", "Мультиагентный CLI с OpenAI и Claude Extended Thinking", "Python, Rich, OpenAI, Anthropic", "done", "https://github.com/KirillTomenko"),
            ("Client Challenger", "Тренажёр деловой коммуникации", "Flask, SQLite, VK OAuth", "in_progress", "https://github.com/KirillTomenko"),
            ("Portfolio MCP Server", "MCP-сервер для управления AI-портфолио через Telegram", "FastAPI, MCP, aiogram, OpenAI", "in_progress", "https://github.com/KirillTomenko"),
            ("Memory Bot — RAG", "Telegram-бот с тремя архитектурами памяти (buffer, RAG, combined)", "aiogram, ChromaDB, OpenAI, Docker", "done", "https://github.com/KirillTomenko"),
        ]
        cur.executemany(
            "INSERT INTO projects (name, description, stack, status, github_url) VALUES (?,?,?,?,?)",
            seed_projects
        )

        seed_ideas = [
            (1, "Как я автоматизировал приём заявок за выходные"),
            (3, "Почему обратная связь важнее фич: опыт ресторанного бота"),
            (9, "Что такое MCP и зачем это нужно разработчику"),
        ]
        cur.executemany(
            "INSERT INTO post_ideas (project_id, idea) VALUES (?,?)",
            seed_ideas
        )

    conn.commit()
    conn.close()

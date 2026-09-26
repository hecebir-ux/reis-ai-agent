from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import config


class SQLiteStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or config.SQLITE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def _init(self) -> None:
        with self._lock:
            con = self._connect()
            try:
                con.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        kind TEXT NOT NULL,
                        key TEXT,
                        content TEXT NOT NULL,
                        project TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
                    CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);

                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        description TEXT,
                        status TEXT,
                        priority INTEGER,
                        plan TEXT,
                        current_step TEXT,
                        progress REAL,
                        start_time TEXT,
                        end_time TEXT,
                        errors TEXT,
                        retries INTEGER,
                        result TEXT
                    );

                    CREATE TABLE IF NOT EXISTS projects (
                        name TEXT PRIMARY KEY,
                        path TEXT,
                        technology TEXT,
                        git TEXT,
                        dependencies TEXT,
                        settings TEXT,
                        updated_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT,
                        content TEXT,
                        created_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS knowledge (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        problem TEXT NOT NULL,
                        solution TEXT NOT NULL,
                        source TEXT,
                        project TEXT,
                        success INTEGER,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_knowledge_problem ON knowledge(problem);
                    """
                )
                con.commit()
            finally:
                con.close()

    def add_memory(self, kind: str, content: str, key: str | None = None, project: str | None = None) -> int:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            con = self._connect()
            try:
                cur = con.execute(
                    "INSERT INTO memories(kind, key, content, project, created_at) VALUES (?,?,?,?,?)",
                    (kind, key, content, project, now),
                )
                con.commit()
                return int(cur.lastrowid)
            finally:
                con.close()

    def search_memory(self, query: str, kind: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        q = f"%{query}%"
        sql = "SELECT * FROM memories WHERE content LIKE ?"
        args: list[Any] = [q]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            con = self._connect()
            try:
                rows = con.execute(sql, args).fetchall()
                return [dict(r) for r in rows]
            finally:
                con.close()

    def save_task(self, task: dict[str, Any]) -> None:
        fields = (
            "id", "title", "description", "status", "priority", "plan",
            "current_step", "progress", "start_time", "end_time", "errors",
            "retries", "result",
        )
        values = []
        for f in fields:
            v = task.get(f)
            if f in {"plan", "errors", "result"} and not isinstance(v, str):
                v = json.dumps(v or ([] if f == "errors" else {}), ensure_ascii=False)
            values.append(v)
        placeholders = ",".join("?" * len(fields))
        updates = ",".join(f"{f}=excluded.{f}" for f in fields if f != "id")
        sql = f"INSERT INTO tasks({','.join(fields)}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}"
        with self._lock:
            con = self._connect()
            try:
                con.execute(sql, values)
                con.commit()
            finally:
                con.close()

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM tasks"
        args: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            args.append(status)
        # rowid DESC breaks ties for tasks created within the same second.
        sql += " ORDER BY start_time DESC, rowid DESC"
        with self._lock:
            con = self._connect()
            try:
                return [dict(r) for r in con.execute(sql, args).fetchall()]
            finally:
                con.close()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            con = self._connect()
            try:
                row = con.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                return dict(row) if row else None
            finally:
                con.close()

    def add_conversation(self, role: str, content: str) -> None:
        with self._lock:
            con = self._connect()
            try:
                con.execute(
                    "INSERT INTO conversations(role, content, created_at) VALUES (?,?,?)",
                    (role, content, time.strftime("%Y-%m-%d %H:%M:%S")),
                )
                con.commit()
            finally:
                con.close()

    def recent_conversation(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            con = self._connect()
            try:
                rows = con.execute(
                    "SELECT * FROM conversations ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return list(reversed([dict(r) for r in rows]))
            finally:
                con.close()

    def upsert_project(self, name: str, path: str, technology: str = "python", **extra: Any) -> None:
        with self._lock:
            con = self._connect()
            try:
                con.execute(
                    """
                    INSERT INTO projects(name, path, technology, git, dependencies, settings, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        path=excluded.path,
                        technology=excluded.technology,
                        git=excluded.git,
                        dependencies=excluded.dependencies,
                        settings=excluded.settings,
                        updated_at=excluded.updated_at
                    """,
                    (
                        name,
                        path,
                        technology,
                        extra.get("git", ""),
                        json.dumps(extra.get("dependencies", []), ensure_ascii=False),
                        json.dumps(extra.get("settings", {}), ensure_ascii=False),
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                con.commit()
            finally:
                con.close()

    def ensure_knowledge_table(self) -> None:
        with self._lock:
            con = self._connect()
            try:
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        problem TEXT NOT NULL,
                        solution TEXT NOT NULL,
                        source TEXT,
                        project TEXT,
                        success INTEGER,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                con.commit()
            finally:
                con.close()

    def add_knowledge(
        self,
        problem: str,
        solution: str,
        source: str = "local",
        project: str | None = None,
        success: bool = True,
    ) -> int:
        self.ensure_knowledge_table()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            con = self._connect()
            try:
                cur = con.execute(
                    "INSERT INTO knowledge(problem, solution, source, project, success, created_at) VALUES (?,?,?,?,?,?)",
                    (problem, solution, source, project, 1 if success else 0, now),
                )
                con.commit()
                kid = int(cur.lastrowid)
            finally:
                con.close()
        self.add_memory("KNOWLEDGE", f"{problem} => {solution}", key=problem[:80], project=project)
        return kid

    def search_knowledge(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        self.ensure_knowledge_table()
        q = f"%{query}%"
        with self._lock:
            con = self._connect()
            try:
                rows = con.execute(
                    "SELECT * FROM knowledge WHERE problem LIKE ? OR solution LIKE ? ORDER BY id DESC LIMIT ?",
                    (q, q, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                con.close()

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            con = self._connect()
            try:
                return [dict(r) for r in con.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()]
            finally:
                con.close()

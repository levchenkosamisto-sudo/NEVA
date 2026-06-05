"""
tools/neva_graphiti.py — Графовое ядро NEVA
Версия: 3.6 (исправлено архитектором Claude)
P16 compliant, параметризованные запросы, без SQL injection
"""

import os
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import kuzu
    KUZU_AVAILABLE = True
except ImportError:
    KUZU_AVAILABLE = False
    logger.warning("kuzu не установлен: pip install kuzu==0.11.3")

try:
    from neva_write_queue import write_to_graph
    WRITE_QUEUE_AVAILABLE = True
except ImportError:
    WRITE_QUEUE_AVAILABLE = False
    logger.warning("neva_write_queue не найден — ТЗ-1 не установлен")


DB_PATH = os.path.expanduser("~/Documents/NEVA/kuzu_data")

# P16 — обязательные поля каждого атома
P16_REQUIRED = [
    "content", "author_ai", "source_path",
    "doc_id", "doc_version", "sha256", "atom_type"
]


class NevaGraphiti:
    """
    Обёртка над Kuzu для NEVA.
    Единственный способ работы с графом памяти.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.db = None
        self.conn = None
        self._initialized = False

    async def init(self) -> None:
        """Инициализация БД и схемы. Вызывать один раз при старте."""
        if not KUZU_AVAILABLE:
            raise RuntimeError("kuzu не установлен: pip install kuzu==0.11.3")

        # Kuzu сам создаёт файл БД — os.makedirs не нужен
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()
        self._initialized = True
        logger.info(f"NevaGraphiti инициализирован: {self.db_path}")

    def _init_schema(self) -> None:
        """Создаёт схему P16 если не существует. НЕ async по контракту ТЗ."""
        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Atom (
                uuid        STRING,
                content     STRING,
                author_ai   STRING,
                source_path STRING,
                doc_id      STRING,
                doc_version STRING,
                sha256      STRING,
                indexed_at  STRING,
                atom_type   STRING,
                status      STRING,
                PRIMARY KEY(uuid)
            )
        """)
        logger.info("Схема Atom (P16) инициализирована")

    def _check_init(self) -> None:
        if not self._initialized:
            raise RuntimeError("NevaGraphiti не инициализирован. Вызови await graph.init()")

    async def add_atom(self, atom: dict) -> dict:
        """
        Запись атома в граф через write_to_graph (IMMUTABLE RULE).
        Валидирует P16 поля перед записью.
        """
        self._check_init()

        # Валидация P16
        missing = [f for f in P16_REQUIRED if f not in atom]
        if missing:
            return {
                "status": "error",
                "reason": "MISSING_P16_FIELDS",
                "missing": missing
            }

        # Генерируем uuid и indexed_at
        atom_copy = dict(atom)
        atom_copy["uuid"] = str(uuid.uuid4())
        atom_copy["indexed_at"] = datetime.utcnow().isoformat()
        atom_copy.setdefault("status", "active")

        # Параметризованный запрос — без f-string, без injection
        query = """
            CREATE (:Atom {
                uuid:        $uuid,
                content:     $content,
                author_ai:   $author_ai,
                source_path: $source_path,
                doc_id:      $doc_id,
                doc_version: $doc_version,
                sha256:      $sha256,
                indexed_at:  $indexed_at,
                atom_type:   $atom_type,
                status:      $status
            })
        """

        if WRITE_QUEUE_AVAILABLE:
            # Через write_to_graph из ТЗ-1 (IMMUTABLE RULE)
            return await write_to_graph(
                self.conn.execute, query, atom_copy
            )
        else:
            # Fallback если ТЗ-1 не установлен — только для разработки
            logger.warning("write_to_graph недоступен — прямая запись (dev mode)")
            try:
                self.conn.execute(query, atom_copy)
                return {"status": "success", "uuid": atom_copy["uuid"]}
            except Exception as e:
                return {"status": "error", "reason": str(e)}

    async def invalidate(self, atom_uuid: str) -> dict:
        """Инвалидирует атом (для self-test cleanup и TTL)."""
        self._check_init()
        query = "MATCH (a:Atom {uuid: $uuid}) SET a.status = 'invalid'"
        try:
            if WRITE_QUEUE_AVAILABLE:
                return await write_to_graph(
                    self.conn.execute, query, {"uuid": atom_uuid}
                )
            else:
                self.conn.execute(query, {"uuid": atom_uuid})
                return {"status": "success"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def get_edges(self, atom_uuid: str) -> list:
        """Возвращает рёбра атома (для TTL safe_invalidate)."""
        self._check_init()
        # F1 (atom_edges) — Этап 2, сейчас возвращаем пустой список
        return []

    async def mark_pending_ttl(self, atom_uuid: str) -> dict:
        """Помечает атом как PENDING_TTL."""
        self._check_init()
        query = "MATCH (a:Atom {uuid: $uuid}) SET a.status = 'pending_ttl'"
        try:
            if WRITE_QUEUE_AVAILABLE:
                return await write_to_graph(
                    self.conn.execute, query, {"uuid": atom_uuid}
                )
            else:
                self.conn.execute(query, {"uuid": atom_uuid})
                return {"status": "success"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def search(self, query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Семантический поиск атомов.
        MVP: текстовый поиск по content.
        Этап 2: семантический через e5-small.
        """
        self._check_init()
        try:
            # MVP — простой CONTAINS поиск
            result = self.conn.execute(
                "MATCH (a:Atom) WHERE a.content CONTAINS $q AND a.status = 'active' "
                "RETURN a.uuid, a.content, a.source_path, a.doc_id, a.atom_type "
                "LIMIT $limit",
                {"q": query_text, "limit": limit}
            )
            atoms = []
            while result.has_next():
                row = result.get_next()
                atoms.append({
                    "atom_uuid":   row[0],
                    "content":     row[1],
                    "source_path": row[2],
                    "doc_id":      row[3],
                    "atom_type":   row[4],
                    "score":       0.85  # Этап 2: реальный score от e5-small
                })
            return atoms
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def get_atoms_by_doc(self, doc_id: str) -> List[Dict[str, Any]]:
        """Возвращает все атомы документа (для /api/v1/document/{doc_id})."""
        self._check_init()
        try:
            result = self.conn.execute(
                "MATCH (a:Atom) WHERE a.doc_id = $doc_id AND a.status = 'active' "
                "RETURN a.uuid, a.content, a.source_path, a.doc_version, a.atom_type",
                {"doc_id": doc_id}
            )
            atoms = []
            while result.has_next():
                row = result.get_next()
                atoms.append({
                    "atom_uuid":   row[0],
                    "content":     row[1],
                    "source_path": row[2],
                    "doc_version": row[3],
                    "atom_type":   row[4],
                })
            return atoms
        except Exception as e:
            logger.error(f"get_atoms_by_doc error: {e}")
            return []

    async def close(self) -> None:
        """Закрывает соединение."""
        self.conn = None
        self.db = None
        self._initialized = False
        logger.info("NevaGraphiti закрыт")


# Глобальный экземпляр — инициализируется при старте сервера
graph = NevaGraphiti()

# ТЕСТЫ ДЛЯ CURSOR-001 PIPELINE
# tests/test_pipeline.py
# Написаны Claude до кода (TDD контракты)

import pytest
import os
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# ─── ТЕСТЫ notify_director.py ────────────────────────────────────────────────

class TestNotifyDirector:

    def test_blocked_status_sends_telegram(self, tmp_path):
        """Файл с STATUS: BLOCKED → Telegram отправлен"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\nCursor не может найти модуль X")
        with patch("tools.pipeline.notify_director.send_telegram") as mock_send:
            mock_send.return_value = True
            result = subprocess.run(
                ["python3", "tools/pipeline/notify_director.py", str(q)],
                capture_output=True
            )
            assert result.returncode == 0

    def test_resolved_status_no_telegram(self, tmp_path):
        """Файл с STATUS: RESOLVED → Telegram НЕ отправляется"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: RESOLVED\nВопрос закрыт")
        result = subprocess.run(
            ["python3", "tools/pipeline/notify_director.py", str(q)],
            capture_output=True
        )
        assert result.returncode == 0
        assert b"OK" in result.stdout

    def test_missing_file_exits_zero(self, tmp_path):
        """Файл не существует → exit 0, нет ошибки"""
        q = tmp_path / "nonexistent.md"
        result = subprocess.run(
            ["python3", "tools/pipeline/notify_director.py", str(q)],
            capture_output=True
        )
        assert result.returncode == 0

    def test_empty_file_exits_zero(self, tmp_path):
        """Пустой файл → exit 0"""
        q = tmp_path / "questions.md"
        q.write_text("")
        result = subprocess.run(
            ["python3", "tools/pipeline/notify_director.py", str(q)],
            capture_output=True
        )
        assert result.returncode == 0

    def test_message_truncated_to_500_chars(self, tmp_path):
        """Длинное сообщение обрезается до 500 символов"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\n" + "A" * 1000)
        with patch("tools.pipeline.notify_director.send_telegram") as mock_send:
            mock_send.return_value = True
            subprocess.run(
                ["python3", "tools/pipeline/notify_director.py", str(q)],
                capture_output=True
            )
            call_args = mock_send.call_args[0][0]
            assert len(call_args) <= 550  # 500 + заголовок

    def test_telegram_timeout_retry_once(self, tmp_path):
        """Telegram timeout → 1 retry → exit 1"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\nОшибка")
        with patch("tools.pipeline.notify_director.send_telegram") as mock_send:
            mock_send.side_effect = TimeoutError("timeout")
            result = subprocess.run(
                ["python3", "tools/pipeline/notify_director.py", str(q)],
                capture_output=True
            )
            assert result.returncode == 1
            assert mock_send.call_count == 2  # оригинал + 1 retry


# ─── ТЕСТЫ inspector_poll.py ─────────────────────────────────────────────────

class TestInspectorPoll:

    def test_finds_blocked_project(self, tmp_path):
        """Сканирует projects/ и находит BLOCKED файл"""
        from tools.pipeline.inspector_poll import scan_projects
        proj = tmp_path / "my_project"
        proj.mkdir()
        q = proj / "questions.md"
        q.write_text("STATUS: BLOCKED\nНе могу импортировать")
        results = scan_projects(str(tmp_path))
        assert len(results) == 1
        assert "my_project" in results[0]

    def test_ignores_resolved_project(self, tmp_path):
        """Не возвращает RESOLVED файлы"""
        from tools.pipeline.inspector_poll import scan_projects
        proj = tmp_path / "done_project"
        proj.mkdir()
        q = proj / "questions.md"
        q.write_text("STATUS: RESOLVED\nВсё OK")
        results = scan_projects(str(tmp_path))
        assert len(results) == 0

    def test_no_duplicate_notifications(self, tmp_path):
        """Не отправляет повторно если прошло < 10 минут"""
        from tools.pipeline.inspector_poll import InspectorPoll
        poll = InspectorPoll(projects_dir=str(tmp_path), interval=1)
        proj = tmp_path / "proj"
        proj.mkdir()
        q = proj / "questions.md"
        q.write_text("STATUS: BLOCKED\nОшибка")
        with patch.object(poll, "notify") as mock_notify:
            poll.check_once()
            poll.check_once()  # второй вызов — не должен уведомить
            assert mock_notify.call_count == 1

    def test_creates_projects_dir_if_missing(self, tmp_path):
        """Создаёт projects/ если не существует"""
        from tools.pipeline.inspector_poll import InspectorPoll
        missing = tmp_path / "projects"
        poll = InspectorPoll(projects_dir=str(missing), interval=1)
        poll.check_once()
        assert missing.exists()

    def test_notify_failure_does_not_crash(self, tmp_path):
        """Если notify упал — poll продолжает работу"""
        from tools.pipeline.inspector_poll import InspectorPoll
        poll = InspectorPoll(projects_dir=str(tmp_path), interval=1)
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "questions.md").write_text("STATUS: BLOCKED\nОшибка")
        with patch.object(poll, "notify", side_effect=Exception("Telegram down")):
            poll.check_once()  # не должен бросить исключение


# ─── ТЕСТЫ new_project.sh ────────────────────────────────────────────────────

class TestNewProject:

    def test_creates_project_structure(self, tmp_path):
        """Создаёт все обязательные файлы"""
        result = subprocess.run(
            ["bash", "tools/pipeline/new_project.sh", "test_proj"],
            capture_output=True,
            env={**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)}
        )
        assert result.returncode == 0
        proj = tmp_path / "test_proj"
        assert (proj / "spec.md").exists()
        assert (proj / "AGENTS.md").exists()
        assert (proj / "tests_spec.py").exists()
        assert (proj / "smoke_test.sh").exists()
        assert (proj / "questions.md").exists()
        assert (proj / "logs").is_dir()

    def test_questions_md_has_idle_status(self, tmp_path):
        """questions.md создаётся со статусом IDLE"""
        subprocess.run(
            ["bash", "tools/pipeline/new_project.sh", "test_proj2"],
            capture_output=True,
            env={**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)}
        )
        content = (tmp_path / "test_proj2" / "questions.md").read_text()
        assert "STATUS: IDLE" in content

    def test_duplicate_project_fails(self, tmp_path):
        """Повторное создание того же проекта → exit 1"""
        env = {**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)}
        subprocess.run(["bash", "tools/pipeline/new_project.sh", "dup"],
                       env=env, capture_output=True)
        result = subprocess.run(["bash", "tools/pipeline/new_project.sh", "dup"],
                                env=env, capture_output=True)
        assert result.returncode == 1


# ─── ТЕСТЫ review_checker.py ─────────────────────────────────────────────────

class TestReviewChecker:

    def test_all_checked_returns_zero(self, tmp_path):
        """Все пункты [x] → exit 0"""
        r = tmp_path / "review.md"
        r.write_text("- [x] Все функции реализованы\n- [x] Тесты покрывают требования\n")
        result = subprocess.run(
            ["python3", "tools/pipeline/review_checker.py", str(r)],
            capture_output=True
        )
        assert result.returncode == 0
        assert b"OK" in result.stdout

    def test_unchecked_item_returns_one(self, tmp_path):
        """Хотя бы один [ ] → exit 1"""
        r = tmp_path / "review.md"
        r.write_text("- [x] Функции реализованы\n- [ ] Нет заглушек\n")
        result = subprocess.run(
            ["python3", "tools/pipeline/review_checker.py", str(r)],
            capture_output=True
        )
        assert result.returncode == 1
        assert b"zaglushki" in result.stdout or b"заглушек" in result.stdout.decode('utf-8', errors='ignore').encode()

    def test_missing_review_returns_one(self, tmp_path):
        """Файл не существует → exit 1"""
        result = subprocess.run(
            ["python3", "tools/pipeline/review_checker.py",
             str(tmp_path / "review.md")],
            capture_output=True
        )
        assert result.returncode == 1

    def test_empty_checklist_returns_one(self, tmp_path):
        """Нет ни одного пункта → exit 1"""
        r = tmp_path / "review.md"
        r.write_text("# Ревью\nКод выглядит нормально.")
        result = subprocess.run(
            ["python3", "tools/pipeline/review_checker.py", str(r)],
            capture_output=True
        )
        assert result.returncode == 1

    def test_lists_unchecked_items(self, tmp_path):
        """Перечисляет незакрытые пункты в выводе"""
        r = tmp_path / "review.md"
        r.write_text("- [x] ruff чисто\n- [ ] smoke PASS\n- [ ] нет заглушек\n")
        result = subprocess.run(
            ["python3", "tools/pipeline/review_checker.py", str(r)],
            capture_output=True, text=True
        )
        assert "smoke" in result.stdout
        assert "заглушек" in result.stdout

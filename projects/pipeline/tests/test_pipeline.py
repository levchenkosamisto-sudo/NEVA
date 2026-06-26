# ТЕСТЫ ДЛЯ CURSOR-001 PIPELINE
# tests/test_pipeline.py
# Написаны Claude до кода (TDD контракты)

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── ТЕСТЫ utils.py ──────────────────────────────────────────────────────────


class TestUtils:

    def test_load_env_reads_correctly(self, tmp_path):
        """load_env читает .env корректно"""
        from tools.pipeline.utils import load_env

        env_file = tmp_path / ".env"
        env_file.write_text(
            "NEVA_TELEGRAM_TOKEN=abc123\n"
            "# comment\n"
            'NEVA_TELEGRAM_CHAT_ID="999"\n'
            "EMPTY=\n",
            encoding="utf-8",
        )
        env = load_env(env_file)
        assert env["NEVA_TELEGRAM_TOKEN"] == "abc123"
        assert env["NEVA_TELEGRAM_CHAT_ID"] == "999"
        assert env["EMPTY"] == ""

    def test_get_required_raises_if_missing(self):
        """get_required бросает EnvironmentError если переменной нет"""
        from tools.pipeline.utils import get_required

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="NEVA_MISSING"):
                get_required("NEVA_MISSING", env={})

    def test_load_cache_returns_empty_if_missing(self, tmp_path):
        """load_cache возвращает пустой dict если файл не существует"""
        from tools.pipeline.utils import load_cache

        cache = load_cache(tmp_path / "missing_cache.json")
        assert cache == {}


# ─── ТЕСТЫ notify_director.py ────────────────────────────────────────────────


class TestNotifyDirector:

    def test_blocked_status_sends_telegram(self, tmp_path):
        """Файл с STATUS: BLOCKED → Telegram отправлен (mock)"""
        from unittest.mock import patch
        import tools.pipeline.notify_director as nd
        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\nCursor не может найти модуль X")
        with patch.object(nd, "send_telegram") as mock_send:
            mock_send.return_value = None
            original_argv = sys.argv
            sys.argv = ["notify_director.py", str(q)]
            try:
                result_code = nd.main()
            finally:
                sys.argv = original_argv
        assert result_code == 0
        mock_send.assert_called_once()

    def test_resolved_status_no_telegram(self, tmp_path):
        """Файл с STATUS: RESOLVED → Telegram НЕ отправляется"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: RESOLVED\nВопрос закрыт")
        result = subprocess.run(
            [sys.executable, "tools/pipeline/notify_director.py", str(q)],
            capture_output=True,
        )
        assert result.returncode == 0
        assert b"OK" in result.stdout

    def test_missing_file_exits_zero(self, tmp_path):
        """Файл не существует → exit 0, нет ошибки"""
        q = tmp_path / "nonexistent.md"
        result = subprocess.run(
            [sys.executable, "tools/pipeline/notify_director.py", str(q)],
            capture_output=True,
        )
        assert result.returncode == 0

    def test_empty_file_exits_zero(self, tmp_path):
        """Пустой файл → exit 0"""
        q = tmp_path / "questions.md"
        q.write_text("")
        result = subprocess.run(
            [sys.executable, "tools/pipeline/notify_director.py", str(q)],
            capture_output=True,
        )
        assert result.returncode == 0

    def test_message_truncated_to_500_chars(self, tmp_path):
        """Длинное сообщение обрезается до 500 символов"""
        from tools.pipeline.notify_director import main

        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\n" + "A" * 1000)
        with patch("tools.pipeline.notify_director.send_telegram") as mock_send:
            mock_send.return_value = None
            with patch("sys.argv", ["notify_director.py", str(q)]):
                main()
            call_args = mock_send.call_args[0][0]
            assert len(call_args) <= 550  # 500 + заголовок

    def test_telegram_timeout_retry_once(self, tmp_path):
        """Telegram timeout → 1 retry → exit 1"""
        from tools.pipeline.notify_director import main

        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\nОшибка")
        with patch("tools.pipeline.notify_director.send_telegram") as mock_send:
            mock_send.side_effect = TimeoutError("timeout")
            with patch("sys.argv", ["notify_director.py", str(q)]):
                assert main() == 1
            assert mock_send.call_count == 2  # оригинал + 1 retry

    def test_missing_token_exits_one(self, tmp_path):
        """NEVA_TELEGRAM_TOKEN отсутствует → exit 1 + сообщение в stderr"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\nПричина")
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("NEVA_TELEGRAM_TOKEN", "NEVA_TELEGRAM_CHAT_ID")
        }
        env["HOME"] = str(tmp_path)
        env["NEVA_TELEGRAM_CHAT_ID"] = "12345"
        result = subprocess.run(
            [sys.executable, "tools/pipeline/notify_director.py", str(q)],
            capture_output=True,
            env=env,
        )
        assert result.returncode == 1
        assert "NEVA_TELEGRAM_TOKEN" in result.stderr.decode("utf-8")

    def test_missing_chat_id_exits_one(self, tmp_path):
        """NEVA_TELEGRAM_CHAT_ID отсутствует → exit 1 + сообщение в stderr"""
        q = tmp_path / "questions.md"
        q.write_text("STATUS: BLOCKED\nПричина")
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("NEVA_TELEGRAM_TOKEN", "NEVA_TELEGRAM_CHAT_ID")
        }
        env["HOME"] = str(tmp_path)
        env["NEVA_TELEGRAM_TOKEN"] = "fake_token"
        result = subprocess.run(
            [sys.executable, "tools/pipeline/notify_director.py", str(q)],
            capture_output=True,
            env=env,
        )
        assert result.returncode == 1
        assert "NEVA_TELEGRAM_CHAT_ID" in result.stderr.decode("utf-8")


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

    def test_no_duplicate_after_restart(self, tmp_path):
        """Не дублирует после перезапуска (кэш с диска)"""
        from tools.pipeline.inspector_poll import InspectorPoll

        cache_file = tmp_path / "cache.json"
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "questions.md").write_text("STATUS: BLOCKED\nОшибка")

        poll1 = InspectorPoll(
            projects_dir=str(tmp_path), interval=1, cache_file=cache_file
        )
        with patch.object(poll1, "notify") as mock_notify:
            poll1.check_once()
            assert mock_notify.call_count == 1

        poll2 = InspectorPoll(
            projects_dir=str(tmp_path), interval=1, cache_file=cache_file
        )
        with patch.object(poll2, "notify") as mock_notify:
            poll2.check_once()
            assert mock_notify.call_count == 0

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


# ─── ТЕСТЫ new_project.py ────────────────────────────────────────────────────


class TestNewProject:

    def test_creates_project_structure(self, tmp_path):
        """Создаёт все обязательные файлы"""
        result = subprocess.run(
            [sys.executable, "tools/pipeline/new_project.py", "test_proj"],
            capture_output=True,
            env={**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)},
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
            [sys.executable, "tools/pipeline/new_project.py", "test_proj2"],
            capture_output=True,
            env={**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)},
        )
        content = (tmp_path / "test_proj2" / "questions.md").read_text()
        assert "STATUS: IDLE" in content

    def test_duplicate_project_fails(self, tmp_path):
        """Повторное создание того же проекта → exit 1"""
        env = {**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)}
        subprocess.run(
            [sys.executable, "tools/pipeline/new_project.py", "dup"],
            env=env,
            capture_output=True,
        )
        result = subprocess.run(
            [sys.executable, "tools/pipeline/new_project.py", "dup"],
            env=env,
            capture_output=True,
        )
        assert result.returncode == 1

    def test_empty_folder_reuses(self, tmp_path):
        """Если папка существует и ПУСТАЯ → создаёт файлы, exit 0"""
        proj = tmp_path / "empty_proj"
        proj.mkdir()
        result = subprocess.run(
            [sys.executable, "tools/pipeline/new_project.py", "empty_proj"],
            capture_output=True,
            env={**os.environ, "NEVA_PROJECTS_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert (proj / "spec.md").exists()
        assert (proj / "questions.md").read_text(encoding="utf-8") == "STATUS: IDLE\n"


# ─── ТЕСТЫ review_checker.py ─────────────────────────────────────────────────


class TestReviewChecker:

    def test_all_checked_returns_zero(self, tmp_path):
        """Все пункты [x] → exit 0"""
        r = tmp_path / "review.md"
        r.write_text(
            "- [x] Все функции реализованы\n- [x] Тесты покрывают требования\n"
        )
        result = subprocess.run(
            [sys.executable, "tools/pipeline/review_checker.py", str(r)],
            capture_output=True,
        )
        assert result.returncode == 0
        assert b"OK" in result.stdout

    def test_unchecked_item_returns_one(self, tmp_path):
        """Хотя бы один [ ] → exit 1"""
        r = tmp_path / "review.md"
        r.write_text("- [x] Функции реализованы\n- [ ] Нет заглушек\n")
        result = subprocess.run(
            [sys.executable, "tools/pipeline/review_checker.py", str(r)],
            capture_output=True,
        )
        assert result.returncode == 1
        assert b"zaglushki" in result.stdout or "заглушек" in result.stdout.decode(
            "utf-8"
        )

    def test_missing_review_returns_one(self, tmp_path):
        """Файл не существует → exit 1"""
        result = subprocess.run(
            [
                sys.executable,
                "tools/pipeline/review_checker.py",
                str(tmp_path / "review.md"),
            ],
            capture_output=True,
        )
        assert result.returncode == 1

    def test_empty_checklist_returns_one(self, tmp_path):
        """Нет ни одного пункта → exit 1"""
        r = tmp_path / "review.md"
        r.write_text("# Ревью\nКод выглядит нормально.")
        result = subprocess.run(
            [sys.executable, "tools/pipeline/review_checker.py", str(r)],
            capture_output=True,
        )
        assert result.returncode == 1

    def test_lists_unchecked_items(self, tmp_path):
        """Перечисляет незакрытые пункты в выводе"""
        r = tmp_path / "review.md"
        r.write_text("- [x] ruff чисто\n- [ ] smoke PASS\n- [ ] нет заглушек\n")
        result = subprocess.run(
            [sys.executable, "tools/pipeline/review_checker.py", str(r)],
            capture_output=True,
            text=True,
        )
        assert "smoke" in result.stdout
        assert "заглушек" in result.stdout

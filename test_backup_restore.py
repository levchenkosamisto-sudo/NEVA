"""
test_backup_restore.py — Этап 0 NEVA v2
Проверяет: export → удалить БД → restore → количество фактов совпадает
"""
import asyncio, shutil, json
from pathlib import Path
from graphiti_core.driver.kuzu_driver import KuzuDriver

BACKUP_DIR = Path("./test_backup_dir")
DB_PATH    = "./test_restore.db"

async def test():
    print("=== test_backup_restore.py ===")

    # ── 1. Создать БД и записать факты ───────────────────────────────
    driver = KuzuDriver(db=DB_PATH)
    driver.setup_schema()
    await driver.build_indices_and_constraints()

    for i in range(20):
        await driver.execute_query(
            f'CREATE (:Entity {{uuid: "fact_{i}", name: "Факт {i}", group_id: "g1"}})'
        )

    before = await driver.execute_query("MATCH (n:Entity) RETURN count(n)")
    count_before = before[0][0]["COUNT(n._ID)"]
    print(f"Записано фактов: {count_before}")

    # ── 2. Export в JSONL ─────────────────────────────────────────────
    result = await driver.execute_query(
        "MATCH (n:Entity) RETURN n.uuid, n.name, n.group_id"
    )
    await driver.close()

    BACKUP_DIR.mkdir(exist_ok=True)
    backup_file = BACKUP_DIR / "delta_test.jsonl"
    with open(backup_file, "w") as f:
        for row in result[0]:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Экспортировано строк: {len(result[0])}")

    # ── 3. Удалить БД ─────────────────────────────────────────────────
    shutil.rmtree(DB_PATH, ignore_errors=True)
    print("БД удалена")

    # ── 4. Restore — новая чистая БД, MERGE вместо CREATE ────────────
    driver3 = KuzuDriver(db=DB_PATH)
    driver3.setup_schema()
    await driver3.build_indices_and_constraints()

    lines = backup_file.read_text().splitlines()
    restored = 0
    for line in lines:
        row = json.loads(line)
        uuid = row.get("n.uuid", "")
        name = row.get("n.name", "").replace('"', '\\"')
        gid  = row.get("n.group_id", "")
        # MERGE: создать если нет, пропустить если есть
        await driver3.execute_query(
            f'MERGE (:Entity {{uuid: "{uuid}", name: "{name}", group_id: "{gid}"}})'
        )
        restored += 1

    after = await driver3.execute_query("MATCH (n:Entity) RETURN count(n)")
    count_after = after[0][0]["COUNT(n._ID)"]
    print(f"Восстановлено фактов: {count_after}")
    await driver3.close()

    # ── 5. Сравнить ───────────────────────────────────────────────────
    assert count_after == count_before, (
        f"ОШИБКА: было {count_before}, восстановлено {count_after}"
    )
    print(f"✓ Restore OK: {count_before} → {count_after} совпадает")

    # ── Очистка ───────────────────────────────────────────────────────
    shutil.rmtree(DB_PATH, ignore_errors=True)
    shutil.rmtree(BACKUP_DIR, ignore_errors=True)
    print("✓ test_backup_restore PASSED")

asyncio.run(test())

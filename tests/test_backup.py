import gzip
import json
import sqlite3
import asyncio
import pytest
from src.core.backup_manager import BackupManager
from src.models import db_manager, init_database
from conftest import FakeBot


def test_snapshot_and_download(app_client, config):
    client, fake, _ = app_client
    result = client.post("/api/backup", json={"group_id": 123}).json()
    assert result["success"] and result["member_count"] == 2
    response = client.get(f"/api/backups/{result['backup_id']}/download")
    assert response.status_code == 200
    data = json.loads(gzip.decompress(response.content))
    assert [m["user_id"] for m in data["members"]] == [11, 22]
    assert response.headers["cache-control"] == "no-store"


def test_history_count_is_independent_of_limit_and_offline_group_filter(app_client):
    client, bot, _ = app_client
    client.post("/api/backup", json={"group_id": 123})
    client.post("/api/backup", json={"group_id": 123})
    response = client.get("/api/backups?limit=1").json()
    assert len(response["backups"]) == 1 and response["total"] == 2
    bot.online = False
    assert client.get("/api/archived-groups").json()["groups"] == [
        {"group_id": 123, "group_name": "测试群"}
    ]


def test_empty_snapshot_preserves_members(app_client, config):
    client, fake, _ = app_client
    assert client.post("/api/backup", json={"group_id": 123}).status_code == 200
    fake.members = []
    assert client.post("/api/backup", json={"group_id": 123}).status_code == 500
    with sqlite3.connect(config.database.sqlite.path) as db:
        assert db.execute("select count(*) from members").fetchone()[0] == 2
        assert db.execute("select status from backups order by id").fetchall() == [
            ("success",),
            ("failed",),
        ]


def test_disk_error_rolls_back_member_replacement(app_client, config, monkeypatch):
    client, fake, web = app_client
    client.post("/api/backup", json={"group_id": 123})
    fake.members = [{"user_id": 33, "nickname": "丙", "role": "owner"}]

    async def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(web.state.backup_manager, "_save_backup_file", fail)
    assert client.post("/api/backup", json={"group_id": 123}).status_code == 500
    with sqlite3.connect(config.database.sqlite.path) as db:
        assert db.execute(
            "select user_id from members order by user_id"
        ).fetchall() == [(11,), (22,)]
        assert db.execute("select count(*) from backup_members").fetchone()[0] == 2


async def test_concurrent_group_backup_is_rejected(config):
    init_database(config.database)
    entered, finish = asyncio.Event(), asyncio.Event()
    fake = FakeBot()
    original = fake.get_group_member_list

    async def slow(*args, **kwargs):
        entered.set()
        await finish.wait()
        return await original(*args, **kwargs)

    fake.get_group_member_list = slow
    one = BackupManager(fake, config.backup.backup_dir)
    two = BackupManager(fake, config.backup.backup_dir)
    task = asyncio.create_task(one.backup_group(123))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        with pytest.raises(ValueError, match="正在备份"):
            await two.backup_group(123)
    finally:
        finish.set()
        await task
        await db_manager.close()


def test_encryption_cannot_silently_produce_plaintext(tmp_path):
    with pytest.raises(ValueError, match="不支持备份加密"):
        BackupManager(FakeBot(), str(tmp_path), encryption=True)

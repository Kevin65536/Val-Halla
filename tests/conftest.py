from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from src.utils.config import Config


class FakeBot:
    def __init__(self):
        self.online = True
        self.user_id = 12345
        self.members = [
            {"user_id": 11, "nickname": "甲", "role": "owner"},
            {"user_id": 22, "nickname": "乙", "role": "member"},
        ]

    async def get_login_info(self):
        return {"user_id": self.user_id, "nickname": "test"}

    async def get_status(self):
        return {"online": self.online, "good": self.online}

    async def get_version_info(self):
        return {"app_name": "test", "app_version": "test"}

    async def get_group_info(self, group_id, **kwargs):
        return {
            "group_id": group_id,
            "group_name": "测试群",
            "member_count": len(self.members),
        }

    async def get_group_member_list(self, group_id, **kwargs):
        return self.members

    async def get_group_list(self):
        return [await self.get_group_info(123)]

    async def close(self):
        pass


@pytest.fixture
def config(tmp_path):
    c = Config()
    c.database.sqlite.path = str(tmp_path / "test.db")
    c.backup.backup_dir = str(tmp_path / "backups")
    c.logging.file = str(tmp_path / "test.log")
    c.logging.console = False
    c.runtime.account = "12345"
    c.runtime.directory = str(tmp_path / "napcat")
    return c


@pytest.fixture
def app_client(config, monkeypatch):
    from src.web import app as web
    from src.utils.config import config_manager

    fake = FakeBot()
    monkeypatch.setattr(config_manager, "load", lambda: config)
    monkeypatch.setattr(web, "create_client", lambda config: fake)
    with TestClient(web.app) as client:
        yield client, fake, web

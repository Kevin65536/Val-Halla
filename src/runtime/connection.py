"""Single, bounded health check used by the UI and before online operations."""

import asyncio
import time


class ConnectionService:
    def __init__(self, config, client, runtime):
        self.config, self.client, self.runtime = config, client, runtime
        self.lock = asyncio.Lock()
        self.cached = None
        self.checked_at = 0
        self.version = {}

    async def check(self, force=False):
        async with self.lock:
            if not force and self.cached and time.monotonic() - self.checked_at < 2:
                return self.cached
            protocol, host, port = self.config.onebot.endpoint
            result = {
                "connected": False,
                "login_info": {},
                "version_info": self.version,
                "config": {"protocol": protocol, "host": host, "port": port},
                "mode": self.config.runtime.mode,
                "qr_available": False,
                "expected_account": self.config.runtime.account,
            }
            try:
                async with asyncio.timeout(5):
                    info = await self.client.get_login_info()
                    health = await self.client.get_status()
                if health.get("online") is not True or health.get("good") is False:
                    result.update(stage="offline", message="QQ 已离线，请重新登录。")
                    runtime_state = await self.runtime.status()
                    result.update(
                        qr_available=runtime_state.get("qr_available", False),
                        qr_key=runtime_state.get("qr_key", ""),
                    )
                elif (
                    self.config.runtime.account
                    and str(info.get("user_id")) != self.config.runtime.account
                ):
                    result.update(
                        stage="wrong_account",
                        message="当前登录账号与配置账号不同，请在 NapCat 面板核对。",
                    )
                else:
                    result.update(
                        connected=True,
                        login_info=info,
                        stage="ready",
                        message="已就绪，可以备份群成员。",
                    )
                    if not self.version:
                        try:
                            async with asyncio.timeout(2):
                                self.version = await self.client.get_version_info()
                        except Exception:
                            pass
                    result["version_info"] = self.version
            except Exception:
                result.update(await self.runtime.status())
            self.cached, self.checked_at = result, time.monotonic()
            return result

    def invalidate(self):
        self.cached = None

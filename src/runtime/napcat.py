"""Adapter for the pinned NapCat 4.18.38 WebUI API (credentials never sent to the browser)."""

import asyncio
import hashlib
import os
import time
from urllib.parse import urlparse

import httpx

from src.runtime.process import ManagedProcess
from src.utils.config import project_path


class ManagementError(RuntimeError):
    pass


class NapCatRuntime:
    def __init__(self, config):
        self.config = config.runtime
        self.onebot = config.onebot
        self.directory = project_path(self.config.directory).resolve()
        self.process = ManagedProcess(
            "napcat",
            self.directory / "node.exe",
            [str(self.directory / "index.js"), "-q", self.config.account],
            self.directory,
        )
        self.credential = None
        self.auth_time = 0
        self.lock = asyncio.Lock()
        self.client = httpx.AsyncClient(
            base_url=self.config.management_url, timeout=4, trust_env=False
        )
        self.started_at = 0
        self.last_error = ""

    async def close(self):
        await self.client.aclose()

    async def start(self):
        if self.config.mode != "native":
            raise ManagementError("外部服务模式下，请在服务所在环境启动 NapCat。")
        if os.name != "nt":
            raise ManagementError(
                "原生运行模式需要 Windows；其他环境请使用 external 模式。"
            )
        if not self.config.account.isdecimal():
            raise ManagementError("请先配置需要登录的 QQ 账号。")
        protocol, host, port = self.onebot.endpoint
        url = urlparse(self.config.management_url)
        if host != "127.0.0.1" or url.hostname != "127.0.0.1" or url.scheme != "http":
            raise ManagementError("本机原生组件必须使用 127.0.0.1。")
        env = os.environ.copy()
        env["NAPCAT_DISABLE_TIME_SYNC"] = "1"
        env["NAPCAT_WORKDIR"] = str(self.directory / "napcat")
        self.started_at = time.monotonic()
        try:
            pid = await asyncio.to_thread(
                self.process.start, [(host, port), (url.hostname, url.port)], env
            )
        except (OSError, RuntimeError) as error:
            self.last_error = str(error)
            raise ManagementError(self.last_error) from error
        self.last_error = ""
        self.credential = None
        return {"pid": pid, "message": "服务已启动，正在检查登录状态。"}

    async def _request(self, path, body=None):
        async with self.lock:
            if not self.config.management_token:
                raise ManagementError("缺少 NapCat 管理凭据，请检查本机配置。")
            for attempt in range(2):
                if not self.credential or time.monotonic() - self.auth_time > 3000:
                    digest = hashlib.sha256(
                        (self.config.management_token + ".napcat").encode()
                    ).hexdigest()
                    response = await self.client.post(
                        "/api/auth/login", json={"hash": digest}
                    )
                    response.raise_for_status()
                    auth = response.json()
                    self.credential = (auth.get("data") or {}).get("Credential")
                    if auth.get("code") != 0 or not self.credential:
                        raise ManagementError(
                            "NapCat 管理认证失败；请核对本机 Token 或在 NapCat 面板完成额外认证。"
                        )
                    self.auth_time = time.monotonic()
                response = await self.client.post(
                    "/api" + path,
                    json=body or {},
                    headers={"Authorization": "Bearer " + self.credential},
                )
                if response.status_code in (401, 403):
                    self.credential = None
                    continue
                response.raise_for_status()
                result = response.json()
                if result.get("code") == 0:
                    return result.get("data")
                if "Unauthorized" in str(result.get("message", "")) and attempt == 0:
                    self.credential = None
                    continue
                raise ManagementError(
                    "NapCat 拒绝该操作，请刷新登录状态或打开 NapCat 面板检查。"
                )
            raise ManagementError("NapCat 管理认证已过期，请重试。")

    async def status(self):
        if self.config.mode != "native":
            return {
                "stage": "external",
                "message": "等待外部 OneBot 服务连接。",
                "qr_available": False,
            }
        if not (self.directory / "node.exe").exists():
            return {
                "stage": "not_installed",
                "message": "尚未安装本机 NapCat。",
                "qr_available": False,
            }
        try:
            data = await self._request("/QQLogin/CheckLoginStatus")
            phase = data.get("loginPhase", "")
            if data.get("isLogin"):
                stage, message = "initializing", "QQ 已登录，正在连接群成员接口。"
            elif data.get("isOffline"):
                stage, message = "offline", "QQ 已离线，请重新登录。"
            elif data.get("qrLoginAccepted") or phase in (
                "qrcode_scanned",
                "initializing",
            ):
                stage, message = "initializing", "已收到扫码确认，正在初始化 QQ。"
            elif phase == "reconnecting":
                stage, message = "starting", "QQ 正在重新连接。"
            else:
                stage, message = "waiting_qr", "请使用手机 QQ 扫码并确认登录。"
            return {
                "stage": stage,
                "message": message,
                "qr_available": bool(data.get("qrcodeurl")) and not data.get("isLogin"),
                "qr_key": hashlib.sha256(
                    str(data.get("qrcodeurl", "")).encode()
                ).hexdigest()[:16],
            }
        except ManagementError as error:
            return {"stage": "auth_error", "message": str(error), "qr_available": False}
        except (httpx.HTTPError, ValueError, TypeError):
            running = await asyncio.to_thread(self.process.running)
            if running:
                stage = (
                    "starting"
                    if time.time() - running.create_time() < self.config.startup_timeout
                    else "unreachable"
                )
                message = (
                    "正在启动 NapCat…"
                    if stage == "starting"
                    else "NapCat 管理接口尚未就绪，请查看运行日志。"
                )
            else:
                stage, message = (
                    "stopped",
                    self.last_error or "NapCat 未运行，点击启动服务。",
                )
            return {"stage": stage, "message": message, "qr_available": False}

    async def qrcode(self):
        data = await self._request("/QQLogin/GetQQLoginQrcode")
        value = data.get("qrcode") if isinstance(data, dict) else None
        if not value or not isinstance(value, str) or len(value) > 8192:
            raise ManagementError("二维码暂不可用，请刷新登录状态。")
        return value

    async def refresh_qrcode(self):
        return await self._request("/QQLogin/RefreshQRcode")

    async def quick_login(self):
        if not self.config.account.isdecimal():
            raise ManagementError("未配置登录账号。")
        return await self._request(
            "/QQLogin/SetQuickLogin", {"uin": self.config.account}
        )

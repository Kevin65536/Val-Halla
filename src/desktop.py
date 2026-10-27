"""One entry point for local startup, status and shutdown; no Docker dependency."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from filelock import FileLock

from src.application import load_config
from src.runtime.napcat import NapCatRuntime
from src.runtime.process import ManagedProcess
from src.utils.config import PROJECT_ROOT


def web_process(config):
    return ManagedProcess(
        "webui",
        sys.executable,
        [
            "-X",
            "utf8",
            "-m",
            "src.main",
            "webui",
            "--host",
            config.web_api.host,
            "--port",
            str(config.web_api.port),
        ],
        PROJECT_ROOT,
    )


def base_url(config):
    return f"http://{config.web_api.host}:{config.web_api.port}"


def healthy(config):
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            response = client.get(base_url(config) + "/api/health")
            response.raise_for_status()
            data = response.json()
            return (
                data.get("app") == "Val-Halla"
                and data.get("project")
                == hashlib.sha256(str(PROJECT_ROOT).encode()).hexdigest()[:16]
            )
    except (httpx.HTTPError, ValueError):
        return False


def open_chrome(url):
    # Explicit Chrome profile; never fall back to a different browser.
    for base in (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ):
        if base:
            executable = Path(base) / "Google/Chrome/Application/chrome.exe"
            if executable.is_file():
                subprocess.Popen(
                    [str(executable), "--profile-directory=Default", url],
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return
    print(f"请在 Chrome 打开：{url}")


async def run(action, no_browser=False):
    config = load_config()
    if config.web_api.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("桌面启动器仅支持本机回环地址。")
    runtime = NapCatRuntime(config)
    web = web_process(config)
    try:
        if action == "stop":
            web.stop()
            if config.runtime.mode == "native":
                runtime.process.stop()
            print("已停止本项目管理的服务，外部 QQ、NapCat 和 Docker 不受影响。")
            return
        if action == "status":
            if healthy(config):
                async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                    data = (await client.get(base_url(config) + "/api/status")).json()
                    print(
                        json.dumps(
                            {
                                key: data.get(key)
                                for key in ("stage", "message", "connected", "mode")
                            },
                            ensure_ascii=False,
                        )
                    )
            else:
                print("Val-Halla 管理界面未运行。")
            return
        if config.runtime.mode == "native":
            try:
                await runtime.start()
            except Exception as error:
                # Keep offline history and the diagnostic/login page available.
                print(f"NapCat 尚未就绪：{error}")
        if not healthy(config):
            web.start([(config.web_api.host, config.web_api.port)])
            deadline = time.monotonic() + 20
            while not healthy(config):
                if time.monotonic() > deadline or not web.running():
                    raise RuntimeError(
                        "管理界面启动失败，请查看 runtime/processes/webui.log。"
                    )
                await asyncio.sleep(0.4)
        print(f"Val-Halla 已启动：{base_url(config)}")
        if not no_browser:
            open_chrome(base_url(config))
    finally:
        await runtime.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["start", "stop", "status"], nargs="?", default="start"
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    folder = PROJECT_ROOT / "runtime/processes"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(folder / "desktop.lock"), timeout=30):
            asyncio.run(run(args.action, args.no_browser))
    except Exception as error:
        print(f"操作未完成：{error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

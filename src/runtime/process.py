"""Manage only processes launched by this checkout; validate PID reuse before stopping."""

import json
import os
import socket
import subprocess
from pathlib import Path

import psutil
from filelock import FileLock

from src.utils.config import PROJECT_ROOT


class ManagedProcess:
    def __init__(self, name, executable, arguments, cwd, root=PROJECT_ROOT):
        self.name = name
        self.executable = Path(executable).resolve()
        self.arguments = [str(value) for value in arguments]
        self.cwd = Path(cwd).resolve()
        self.folder = Path(root) / "runtime/processes"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.record = self.folder / f"{name}.json"
        self.lock = FileLock(str(self.folder / f"{name}.lock"), timeout=10)

    def running(self):
        try:
            saved = json.loads(self.record.read_text(encoding="utf-8"))
            proc = psutil.Process(saved["pid"])
            expected_command = [str(self.executable), *self.arguments]
            if (
                abs(proc.create_time() - saved["created"]) > 0.01
                or Path(proc.exe()).resolve() != self.executable
                or Path(proc.cwd()).resolve() != self.cwd
                or proc.cmdline() != expected_command
            ):
                return None
            return proc if proc.is_running() else None
        except (OSError, ValueError, KeyError, psutil.Error):
            return None

    def start(self, ports=(), env=None):
        with self.lock:
            existing = self.running()
            if existing:
                return existing.pid
            if not self.executable.is_file():
                raise FileNotFoundError(
                    f"未安装运行组件：{self.executable.name}。请运行安装步骤。"
                )
            for host, port in ports:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind((host, port))
                    except OSError as error:
                        raise RuntimeError(
                            f"端口 {host}:{port} 被占用或被 Windows 保留，请检查配置。"
                        ) from error
            log = self.folder / f"{self.name}.log"
            if log.exists() and log.stat().st_size > 10 * 1024 * 1024:
                log.replace(log.with_suffix(".previous.log"))
            with log.open("ab") as stream:
                child = subprocess.Popen(
                    [str(self.executable), *self.arguments],
                    cwd=self.cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=stream,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt",
                )
            proc = psutil.Process(child.pid)
            saved = {"pid": child.pid, "created": proc.create_time()}
            self.record.write_text(json.dumps(saved), encoding="utf-8")
            return child.pid

    def stop(self):
        with self.lock:
            parent = self.running()
            if not parent:
                return False
            # Capture descendants before stopping the verified parent; never search by process name.
            children = parent.children(recursive=True)
            for proc in [*reversed(children), parent]:
                try:
                    proc.terminate()
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs([parent, *children], timeout=5)
            for proc in alive:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            self.record.unlink(missing_ok=True)
            return True

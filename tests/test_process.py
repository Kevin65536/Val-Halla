import json
import sys
from src.runtime.process import ManagedProcess


def test_duplicate_start_reuses_verified_process_and_pid_reuse_is_safe(tmp_path):
    process = ManagedProcess(
        "test",
        sys.executable,
        ["-c", "import time; time.sleep(60)"],
        tmp_path,
        root=tmp_path,
    )
    pid = process.start()
    try:
        assert process.start() == pid
        saved = process.record.read_text()
        corrupted = json.loads(saved)
        corrupted["created"] -= 10
        process.record.write_text(json.dumps(corrupted))
        assert process.running() is None
        assert process.stop() is False
        process.record.write_text(saved)
        assert process.running() is not None
    finally:
        process.stop()
    assert process.running() is None

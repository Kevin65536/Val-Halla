"""Switch local connection config after installing and validating the native runtime."""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.utils.config import config_manager, Config, RuntimeConfig  # noqa: E402

if __name__ == "__main__":
    connection = json.loads(
        (ROOT / "runtime/native-connection.json").read_text(encoding="utf-8")
    )
    if config_manager.config_path.exists():
        backup = ROOT / "work" / f"before-native-{datetime.now():%Y%m%d-%H%M%S}.yaml"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_manager.config_path, backup)
        config = config_manager.load()
    else:
        config = Config()
    config.runtime = RuntimeConfig(
        mode="native",
        account=connection["account"],
        management_url=f"http://127.0.0.1:{connection['management_port']}",
        management_token=connection["management_token"],
    )
    config.onebot.protocol = "http"
    config.onebot.http.host = "127.0.0.1"
    config.onebot.http.port = connection["onebot_port"]
    config.onebot.access_token = connection["onebot_token"]
    config.web_api.host, config.web_api.port = "127.0.0.1", 8080
    # Scheduling is intentionally opt-in and not implemented in this desktop launcher.
    config.backup.auto_backup = False
    config_manager.save(config)
    print("已切换到原生 NapCat。原配置已保留在 work/。")

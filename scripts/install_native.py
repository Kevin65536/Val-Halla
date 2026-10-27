"""Install the tested Windows Node runtime without importing another account's data."""

import argparse
import hashlib
import json
import secrets
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ARCHIVE_SHA256 = "b88007a373a30deefb387e7cf17911752ff900bce22c534b3da6b644f5c6d0ae"
VERSION = "4.18.38"


def install(archive: Path, account: str, root: Path = ROOT):
    if not account.isdecimal():
        raise ValueError("QQ account must contain digits only")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError(
            "Runtime archive hash differs from the tested release; installation refused"
        )
    target = root / "runtime/napcat"
    if target.exists():
        raise FileExistsError(
            "Runtime already exists; refusing to overwrite account data"
        )
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            if not (target / item.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError("Unsafe archive entry")
        bundle.extractall(target)
    cfg = target / "napcat/config"
    cfg.mkdir(parents=True, exist_ok=True)
    token, management_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    onebot = {
        "network": {
            "httpServers": [
                {
                    "name": "valhalla-local",
                    "enable": True,
                    "host": "127.0.0.1",
                    "port": 15701,
                    "enableCors": False,
                    "enableWebsocket": False,
                    "messagePostFormat": "array",
                    "token": token,
                    "debug": False,
                }
            ],
            "httpClients": [],
            "httpSseServers": [],
            "websocketClients": [],
            "websocketServers": [],
            "plugins": [],
        }
    }
    for name in ("onebot11.json", f"onebot11_{account}.json"):
        (cfg / name).write_text(json.dumps(onebot, indent=2), encoding="utf-8")
    (cfg / "webui.json").write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 16098,
                "token": management_token,
                "autoLoginAccount": account,
                "disableWebUI": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (cfg / "napcat.json").write_text(
        json.dumps(
            {
                "fileLog": False,
                "consoleLog": True,
                "consoleLogLevel": "warn",
                "o3HookMode": 1,
                "bypass": {
                    key: False
                    for key in (
                        "hook",
                        "window",
                        "module",
                        "process",
                        "container",
                        "js",
                    )
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Credentials remain local and ignored by Git; activate only after validation.
    (root / "runtime/native-connection.json").write_text(
        json.dumps(
            {
                "account": account,
                "onebot_token": token,
                "management_token": management_token,
                "onebot_port": 15701,
                "management_port": 16098,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (target / "valhalla-runtime.json").write_text(
        json.dumps(
            {
                "napcat": VERSION,
                "qq_runtime": "9.9.31-49738",
                "archive_sha256": ARCHIVE_SHA256,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Installed NapCat {VERSION} in {target}. Connection details saved locally.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--account", required=True)
    args = parser.parse_args()
    install(args.archive, args.account)

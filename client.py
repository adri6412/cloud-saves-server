import argparse
import io
import json
import zipfile
from pathlib import Path
import shutil

import requests

CONFIG_FILE = Path("client_config.json")


def ensure_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())

    nickname = input("Enter your nickname: ").strip()
    server_url = input("Server URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    save_paths = {}
    save_paths["mesen"] = input("Path to Mesen saves: ").strip()
    save_paths["duckstation"] = input("Path to DuckStation saves: ").strip()

    resp = requests.post(f"{server_url}/register", json={"nickname": nickname})
    resp.raise_for_status()
    api_key = resp.json()["api_key"]

    config = {
        "nickname": nickname,
        "api_key": api_key,
        "server_url": server_url,
        "save_paths": save_paths,
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    return config


def zip_directory(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in path.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(path))
    return buf.getvalue()


def unzip_to_directory(data: bytes, path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(path)


def upload(config: dict, emulator: str) -> None:
    path = Path(config["save_paths"][emulator])
    data = zip_directory(path)
    files = {"file": (f"{emulator}.zip", data)}
    headers = {"X-API-Key": config["api_key"]}
    url = f"{config['server_url']}/saves/{emulator}"
    resp = requests.post(url, files=files, headers=headers)
    resp.raise_for_status()


def download(config: dict, emulator: str) -> None:
    headers = {"X-API-Key": config["api_key"]}
    url = f"{config['server_url']}/saves/{emulator}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 404:
        print("No save on server")
        return
    resp.raise_for_status()
    path = Path(config["save_paths"][emulator])
    unzip_to_directory(resp.content, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud save client")
    parser.add_argument("action", choices=["upload", "download"])
    parser.add_argument("emulator", choices=["mesen", "duckstation"])
    args = parser.parse_args()

    config = ensure_config()
    if args.action == "upload":
        upload(config, args.emulator)
    else:
        download(config, args.emulator)


if __name__ == "__main__":
    main()

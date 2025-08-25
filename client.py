import argparse
import io
import json
import zipfile
from pathlib import Path
import shutil
import sys

import requests

CONFIG_FILE = Path("client_config.json")


def ensure_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())

    nickname = input("Enter your nickname: ").strip()
    server_url = input("Server URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    # Placeholder paths for emulator saves; edit the generated config file to point
    # to the real directories before using the client.
    save_paths = {
        "mesen": "/path/to/mesen/saves",
        "duckstation": "/path/to/duckstation/saves",
    }

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


def get_local_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    mtimes = [p.stat().st_mtime for p in path.rglob("*") if p.is_file()]
    if mtimes:
        return max(mtimes)
    return path.stat().st_mtime


def get_server_mtime(config: dict, emulator: str) -> float:
    headers = {"X-API-Key": config["api_key"]}
    url = f"{config['server_url']}/saves/{emulator}/info"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return 0.0
    return resp.json().get("modified", 0.0)


def read_key() -> str:
    try:
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            mapping = {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}
            return mapping.get(ch2, "")
        if ch == b"\r":
            return "ENTER"
        return ch.decode()
    except ImportError:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\n":
                return "ENTER"
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                mapping = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}
                return mapping.get(seq[1], "")
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def joystick_yes_no(prompt: str) -> bool:
    options = ["Yes", "No"]
    index = 0
    print(prompt)
    while True:
        for i, opt in enumerate(options):
            prefix = ">" if i == index else " "
            print(f"{prefix} {opt}")
        key = read_key()
        print("\033[F" * len(options), end="")
        if key in ("LEFT", "UP"):
            index = (index - 1) % len(options)
        elif key in ("RIGHT", "DOWN"):
            index = (index + 1) % len(options)
        elif key == "ENTER":
            print("\n", end="")
            return index == 0


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
    server_mtime = get_server_mtime(config, emulator)
    path = Path(config["save_paths"][emulator])
    local_mtime = get_local_mtime(path)
    if server_mtime and local_mtime > server_mtime:
        if joystick_yes_no("Local saves are newer than server. Upload them?"):
            upload(config, emulator)
            return
    url = f"{config['server_url']}/saves/{emulator}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 404:
        print("No save on server")
        return
    resp.raise_for_status()
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

import argparse
import io
import json
import zipfile
from pathlib import Path
import shutil

import pygame
import requests

CONFIG_FILE = Path("client_config.json")
SERVER_URL = "http://localhost:7000"


def ensure_config() -> dict:
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        created = False
    else:
        # Default skeleton with placeholder save paths; edit the paths manually.
        config = {
            "nickname": "",
            "api_key": "",
            "save_paths": {
                "mesen": "/path/to/mesen/saves",
                "duckstation": "/path/to/duckstation/saves",
            },
        }
        created = True

    changed = False
    if not config.get("nickname") or not config.get("api_key"):
        nickname = gamepad_prompt_text("Enter your nickname")
        resp = requests.post(f"{SERVER_URL}/register", json={"nickname": nickname})
        resp.raise_for_status()
        config.update({"nickname": nickname, "api_key": resp.json()["api_key"]})
        changed = True
    else:
        # Validate stored API key; if invalid, re-register.
        headers = {"X-API-Key": config["api_key"]}
        resp = requests.get(f"{SERVER_URL}/validate", headers=headers)
        if resp.status_code == 401:
            nickname = config.get("nickname") or gamepad_prompt_text("Enter your nickname")
            while True:
                resp = requests.post(f"{SERVER_URL}/register", json={"nickname": nickname})
                if resp.status_code == 400:
                    nickname = gamepad_prompt_text("Nickname exists. Choose another")
                    continue
                resp.raise_for_status()
                config.update({"nickname": nickname, "api_key": resp.json()["api_key"]})
                changed = True
                break

    if created or changed:
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
    url = f"{SERVER_URL}/saves/{emulator}/info"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return 0.0
    return resp.json().get("modified", 0.0)


def gamepad_prompt_text(prompt: str) -> str:
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        raise RuntimeError("No joystick connected")
    pygame.joystick.Joystick(0).init()
    font = pygame.font.Font(None, 36)
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") + ["<", "OK"]
    cols = 8
    index = 0
    text = ""
    screen = pygame.display.set_mode((640, 240))
    pygame.display.set_caption("Cloud Saves")
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.JOYHATMOTION:
                x, y = event.value
                if x == 1:
                    index = (index + 1) % len(letters)
                elif x == -1:
                    index = (index - 1) % len(letters)
                elif y == 1:
                    index = (index - cols) % len(letters)
                elif y == -1:
                    index = (index + cols) % len(letters)
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:  # A button
                    ch = letters[index]
                    if ch == "OK" and text:
                        pygame.quit()
                        return text
                    if ch == "<":
                        text = text[:-1]
                    else:
                        text += ch
        screen.fill((0, 0, 0))
        prompt_surf = font.render(prompt, True, (255, 255, 255))
        screen.blit(prompt_surf, (20, 20))
        text_surf = font.render(text, True, (255, 255, 255))
        screen.blit(text_surf, (20, 60))
        for i, ch in enumerate(letters):
            col = i % cols
            row = i // cols
            color = (255, 255, 0) if i == index else (200, 200, 200)
            surf = font.render(ch, True, color)
            screen.blit(surf, (20 + col * 70, 120 + row * 40))
        pygame.display.flip()
        clock.tick(30)


def gamepad_yes_no(prompt: str) -> bool:
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        raise RuntimeError("No joystick connected")
    pygame.joystick.Joystick(0).init()
    font = pygame.font.Font(None, 36)
    options = ["Yes", "No"]
    index = 0
    screen = pygame.display.set_mode((400, 200))
    pygame.display.set_caption("Cloud Saves")
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.JOYHATMOTION:
                x, _ = event.value
                if x == 1:
                    index = (index + 1) % len(options)
                elif x == -1:
                    index = (index - 1) % len(options)
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    pygame.quit()
                    return index == 0
        screen.fill((0, 0, 0))
        prompt_surf = font.render(prompt, True, (255, 255, 255))
        screen.blit(prompt_surf, (20, 20))
        for i, opt in enumerate(options):
            color = (255, 255, 0) if i == index else (200, 200, 200)
            surf = font.render(opt, True, color)
            screen.blit(surf, (60 + i * 150, 100))
        pygame.display.flip()
        clock.tick(30)


def upload(config: dict, emulator: str) -> None:
    path = Path(config["save_paths"][emulator])
    data = zip_directory(path)
    files = {"file": (f"{emulator}.zip", data)}
    headers = {"X-API-Key": config["api_key"]}
    url = f"{SERVER_URL}/saves/{emulator}"
    resp = requests.post(url, files=files, headers=headers)
    resp.raise_for_status()


def download(config: dict, emulator: str) -> None:
    headers = {"X-API-Key": config["api_key"]}
    server_mtime = get_server_mtime(config, emulator)
    path = Path(config["save_paths"][emulator])
    local_mtime = get_local_mtime(path)
    if server_mtime and local_mtime > server_mtime:
        if gamepad_yes_no("Local saves are newer than server. Upload them?"):
            upload(config, emulator)
            return
    url = f"{SERVER_URL}/saves/{emulator}"
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

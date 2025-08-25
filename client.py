import argparse
import io
import json
import zipfile
from pathlib import Path
import shutil
import logging

import pygame
import requests

CONFIG_FILE = Path("client_config.json")
SERVER_URL = "http://localhost:7000"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("client")


def ensure_config() -> dict:
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())
        created = False
        logger.info("Loaded config from %s", CONFIG_FILE)
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
        logger.info("Creating new config skeleton at %s", CONFIG_FILE)

    changed = False
    if not config.get("nickname") or not config.get("api_key"):
        # No credentials saved yet: register and handle already-taken names.
        nickname = config.get("nickname") or gamepad_prompt_text("Enter your nickname")
        while True:
            logger.info("Registering nickname %s", nickname)
            resp = requests.post(f"{SERVER_URL}/register", json={"nickname": nickname})
            if resp.status_code == 400:
                nickname = gamepad_prompt_text("Nickname exists. Choose another")
                continue
            resp.raise_for_status()
            config.update({"nickname": nickname, "api_key": resp.json()["api_key"]})
            changed = True
            break
    else:
        # Validate stored API key; if invalid, re-register.
        headers = {"X-API-Key": config["api_key"]}
        logger.info("Validating stored API key")
        resp = requests.get(f"{SERVER_URL}/validate", headers=headers)
        if resp.status_code == 401:
            logger.info("API key invalid; re-registering")
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
        logger.info("Wrote config to %s", CONFIG_FILE)
    return config


def zip_directory(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in path.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(path))
    logger.info("Zipped directory %s", path)
    return buf.getvalue()


def unzip_to_directory(data: bytes, path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(path)
    logger.info("Unzipped data to %s", path)


def get_local_mtime(path: Path) -> float:
    if not path.exists():
        logger.info("Save path %s does not exist", path)
        return 0.0
    files = [p for p in path.rglob("*") if p.is_file()]
    if not files:
        logger.info("No local save files in %s", path)
        return 0.0
    mtime = max(p.stat().st_mtime for p in files)
    logger.info("Local save mtime for %s: %s", path, mtime)
    return mtime


def get_server_mtime(config: dict, emulator: str) -> float:
    headers = {"X-API-Key": config["api_key"]}
    url = f"{SERVER_URL}/saves/{emulator}/info"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        logger.info("No server metadata for %s", emulator)
        return 0.0
    mtime = resp.json().get("modified", 0.0)
    logger.info("Server mtime for %s: %s", emulator, mtime)
    return mtime


def gamepad_prompt_text(prompt: str) -> str:
    pygame.init()
    pygame.joystick.init()
    use_joystick = pygame.joystick.get_count() > 0
    if use_joystick:
        pygame.joystick.Joystick(0).init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    width, height = screen.get_size()
    pygame.display.set_caption("Cloud Saves")
    font = pygame.font.Font(None, 72)
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") + ["<", "OK"]
    cols = 8
    index = 0
    text = ""
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if use_joystick and event.type == pygame.JOYHATMOTION:
                x, y = event.value
                if x == 1:
                    index = (index + 1) % len(letters)
                elif x == -1:
                    index = (index - 1) % len(letters)
                elif y == 1:
                    index = (index - cols) % len(letters)
                elif y == -1:
                    index = (index + cols) % len(letters)
            elif use_joystick and event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:  # A button
                    ch = letters[index]
                    if ch == "OK" and text:
                        pygame.quit()
                        return text
                    if ch == "<":
                        text = text[:-1]
                    else:
                        text += ch
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT:
                    index = (index + 1) % len(letters)
                elif event.key == pygame.K_LEFT:
                    index = (index - 1) % len(letters)
                elif event.key == pygame.K_DOWN:
                    index = (index + cols) % len(letters)
                elif event.key == pygame.K_UP:
                    index = (index - cols) % len(letters)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if text:
                        pygame.quit()
                        return text
                elif event.key == pygame.K_SPACE:
                    ch = letters[index]
                    if ch == "OK" and text:
                        pygame.quit()
                        return text
                    if ch == "<":
                        text = text[:-1]
                    else:
                        text += ch
                elif event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                else:
                    ch = event.unicode.upper()
                    if ch in letters[:-2]:
                        text += ch
        screen.fill((0, 0, 0))
        prompt_surf = font.render(prompt, True, (255, 255, 255))
        screen.blit(prompt_surf, (width // 2 - prompt_surf.get_width() // 2, height // 6))
        text_surf = font.render(text, True, (255, 255, 255))
        screen.blit(text_surf, (width // 2 - text_surf.get_width() // 2, height // 3))
        base_x = width // 2 - (cols * 70) // 2
        base_y = height // 2
        for i, ch in enumerate(letters):
            col = i % cols
            row = i // cols
            color = (255, 255, 0) if i == index else (200, 200, 200)
            surf = font.render(ch, True, color)
            screen.blit(surf, (base_x + col * 70, base_y + row * 40))
        pygame.display.flip()
        clock.tick(30)


def gamepad_yes_no(prompt: str) -> bool:
    pygame.init()
    pygame.joystick.init()
    use_joystick = pygame.joystick.get_count() > 0
    if use_joystick:
        pygame.joystick.Joystick(0).init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    width, height = screen.get_size()
    pygame.display.set_caption("Cloud Saves")
    font = pygame.font.Font(None, 72)
    options = ["Yes", "No"]
    index = 0
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if use_joystick and event.type == pygame.JOYHATMOTION:
                x, _ = event.value
                if x == 1:
                    index = (index + 1) % len(options)
                elif x == -1:
                    index = (index - 1) % len(options)
            elif use_joystick and event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    pygame.quit()
                    return index == 0
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RIGHT:
                    index = (index + 1) % len(options)
                elif event.key == pygame.K_LEFT:
                    index = (index - 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    pygame.quit()
                    return index == 0
        screen.fill((0, 0, 0))
        prompt_surf = font.render(prompt, True, (255, 255, 255))
        screen.blit(prompt_surf, (width // 2 - prompt_surf.get_width() // 2, height // 3))
        for i, opt in enumerate(options):
            color = (255, 255, 0) if i == index else (200, 200, 200)
            surf = font.render(opt, True, color)
            screen.blit(surf, (width // 2 - 100 + i * 200, height // 2))
        pygame.display.flip()
        clock.tick(30)


def upload(config: dict, emulator: str) -> None:
    path = Path(config["save_paths"][emulator])
    logger.info("Uploading saves for %s from %s", emulator, path)
    data = zip_directory(path)
    files = {"file": (f"{emulator}.zip", data)}
    headers = {"X-API-Key": config["api_key"]}
    url = f"{SERVER_URL}/saves/{emulator}"
    resp = requests.post(url, files=files, headers=headers)
    resp.raise_for_status()
    logger.info("Upload completed for %s", emulator)


def download(config: dict, emulator: str) -> None:
    headers = {"X-API-Key": config["api_key"]}
    server_mtime = get_server_mtime(config, emulator)
    path = Path(config["save_paths"][emulator])
    local_mtime = get_local_mtime(path)
    logger.info("Local mtime %s, server mtime %s", local_mtime, server_mtime)
    if server_mtime and local_mtime > server_mtime:
        logger.info("Local saves newer than server for %s", emulator)
        if gamepad_yes_no("Local saves are newer than server. Upload them?"):
            upload(config, emulator)
            return
    url = f"{SERVER_URL}/saves/{emulator}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 404:
        logger.info("No save on server for %s", emulator)
        return
    resp.raise_for_status()
    unzip_to_directory(resp.content, path)
    logger.info("Downloaded saves for %s to %s", emulator, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud save client")
    parser.add_argument("action", choices=["upload", "download"])
    parser.add_argument("emulator", choices=["mesen", "duckstation"])
    args = parser.parse_args()

    config = ensure_config()
    logger.info("Performing %s for %s", args.action, args.emulator)
    if args.action == "upload":
        upload(config, args.emulator)
    else:
        download(config, args.emulator)


if __name__ == "__main__":
    main()

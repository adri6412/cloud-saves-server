import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
import uvicorn

DATA_DIR = Path("server_data")
USERS_FILE = DATA_DIR / "users.json"
SAVES_DIR = DATA_DIR / "saves"

app = FastAPI(title="Cloud Save Server")


def load_users() -> list:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_users(users: list) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))


def find_user_by_key(api_key: str):
    for user in load_users():
        if user["api_key"] == api_key:
            return user
    return None


def find_user_by_nickname(nickname: str):
    for user in load_users():
        if user["nickname"] == nickname:
            return user
    return None


@app.post("/register")
async def register(payload: dict):
    nickname = payload.get("nickname")
    if not nickname:
        raise HTTPException(status_code=400, detail="nickname required")
    if find_user_by_nickname(nickname):
        raise HTTPException(status_code=400, detail="nickname already exists")
    api_key = uuid.uuid4().hex
    users = load_users()
    users.append({"nickname": nickname, "api_key": api_key})
    save_users(users)
    return {"nickname": nickname, "api_key": api_key}


@app.get("/validate")
async def validate(x_api_key: str = Header(...)):
    user = find_user_by_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="invalid api key")
    return {"status": "ok"}


@app.post("/saves/{emulator}")
async def upload_save(emulator: str, file: UploadFile = File(...), x_api_key: str = Header(...)):
    user = find_user_by_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="invalid api key")
    user_dir = SAVES_DIR / user["nickname"]
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / f"{emulator}.zip"
    content = await file.read()
    file_path.write_bytes(content)
    return {"status": "ok"}


@app.get("/saves/{emulator}")
async def download_save(emulator: str, x_api_key: str = Header(...)):
    user = find_user_by_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="invalid api key")
    file_path = SAVES_DIR / user["nickname"] / f"{emulator}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="save not found")
    headers = {"Last-Modified": str(file_path.stat().st_mtime)}
    return FileResponse(file_path, headers=headers)


@app.get("/saves/{emulator}/info")
async def save_info(emulator: str, x_api_key: str = Header(...)):
    user = find_user_by_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="invalid api key")
    file_path = SAVES_DIR / user["nickname"] / f"{emulator}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="save not found")
    return {"modified": file_path.stat().st_mtime}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=7000)

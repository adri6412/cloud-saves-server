# cloud-saves-server

This repository provides a small cloud save system with a Python server and a companion client.  The goal is to synchronize save files for the **Mesen** and **DuckStation** emulators.

## Server

The server uses [FastAPI](https://fastapi.tiangolo.com/) and stores data under the `server_data` directory.

### Install and run

```bash
pip install fastapi uvicorn
python server.py  # starts the server on http://0.0.0.0:8000
```

Available endpoints:

- `POST /register` – Register a nickname and receive an API key.
- `POST /saves/{emulator}` – Upload a zipped save file. Requires the `X-API-Key` header.
- `GET /saves/{emulator}` – Download the zipped save file for an emulator. Requires the `X-API-Key` header.
- `GET /saves/{emulator}/info` – Return the last modification timestamp for a save file.

## Client

The client synchronizes local save folders with the server. On first run it prompts
for a **nickname** and **server URL**. Placeholder save paths for Mesen and
DuckStation are written to the generated `client_config.json`; edit this file to
point to your actual save folders.

This information plus the API key returned by the server are stored in
`client_config.json`.

### Usage

```bash
# Download saves before starting an emulator
python client.py download mesen

# Upload saves after closing an emulator
python client.py upload mesen
```

Replace `mesen` with `duckstation` for PlayStation saves.

The client reads the paths from `client_config.json`, zips the save directory, and uploads it to the server or downloads and extracts it. When downloading, if the local saves are newer than the remote ones the client shows a joystick-controlled prompt asking whether to upload the local files instead.

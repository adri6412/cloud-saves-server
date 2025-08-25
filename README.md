# cloud-saves-server

This repository provides a small cloud save system with a Python server and a companion client.  The goal is to synchronize save files for the **Mesen** and **DuckStation** emulators.

## Server

The server uses [FastAPI](https://fastapi.tiangolo.com/) and stores data under the `server_data` directory.

### Install and run

```bash
pip install fastapi uvicorn
python server.py  # starts the server on http://0.0.0.0:7000
```

Available endpoints:

- `POST /register` – Register a nickname and receive an API key.
- `POST /saves/{emulator}` – Upload a zipped save file. Requires the `X-API-Key` header.
- `GET /saves/{emulator}` – Download the zipped save file for an emulator. Requires the `X-API-Key` header.
- `GET /saves/{emulator}/info` – Return the last modification timestamp for a save file.
- `GET /validate` – Confirm that an API key is valid.

## Client

The client synchronizes local save folders with the server. An example
`client_config.json` file is included with placeholder paths for Mesen and
DuckStation saves—edit these paths to your real directories. On first run a
GUI controlled by an Xbox gamepad asks for a **nickname**, registers with the
server to obtain an API key, and writes these details back to
`client_config.json`. The server URL is fixed inside `client.py`; edit the
`SERVER_URL` constant in the code if you need to change it.
If the server is reset and the stored API key becomes invalid, the client
automatically re-registers using the nickname in the config and updates the
API key.

### Usage

```bash
# Download saves before starting an emulator
python client.py download mesen

# Upload saves after closing an emulator
python client.py upload mesen
```

Replace `mesen` with `duckstation` for PlayStation saves.

The client reads the paths from `client_config.json`, zips the save directory,
and uploads it to the server or downloads and extracts it. When downloading,
if the local saves are newer than the remote ones the client displays a
gamepad-driven GUI asking whether to upload the local files instead.

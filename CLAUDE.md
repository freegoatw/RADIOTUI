# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
python main.py
```

No build step. Dependencies:

```bash
pip install -r requirements.txt
```

Requires VLC Media Player installed at the system level (`sudo apt install vlc` or equivalent).

## Architecture

**Entry point**: `main.py` — starts the welcome screen then drops into a REPL loop.

**Request flow**:
```
user input
  → core/parser.py      (tokenizes input into a dict: {sys, action, name, ...flags})
  → core/handleCMD.py   (routes by cmd['sys'] to the right service)
  → services/           (radio_service.py or youtube_service.py fetch data)
  → core/media_manager.py (stores results in global `data[]`, drives VLC playback)
```

**State lives in `media_manager.py` globals**: `data` (current result list), `index` (currently playing), `src` (`"radio"` or `"yt"`), `player` (VLC wrapper). There is no persistence — all state is lost on exit.

**Parser output format**: `{'sys': 'radio', 'action': 'search', 'name': 'lofi', 'tag': 'jazz', 'limit': '5'}`. Flags like `--tag=jazz` become `{'tag': 'jazz'}`; bare flags like `--no-postfix` become `{'no-postfix': True}`.

**Radio search** passes the parsed dict directly as query params to the Radio Browser API (`config.API_URL`). Any `--key=value` flag the user types is forwarded verbatim to the API, so all API parameters work automatically.

**YouTube flow** is two-step: `search_yt` uses `yt_dlp` with `extract_flat=True` (fast, no stream URL), then `get_stream_url` is called lazily at play time to resolve the actual audio URL.

**Loading spinners** use a shared `done` boolean + daemon thread pattern — set `done = False`, start the thread, do the blocking work, set `done = True`, join. This pattern is duplicated in `radio_service.py`, `youtube_service.py`, `media_manager.py`, and `ui.py`.

## Key config (`config.py`)

- `DEFAULT_RADIO_SEARCH_LIMIT = 10`
- `DEFAULT_TIMEOUT = 5` — seconds to wait for VLC to start playing before giving up
- `DEFAULT_QUERY_POSTFIX` — appended to YouTube queries by default
- `HIDE_ERR = True` — suppresses stderr (hides VLC noise)

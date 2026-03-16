# RADIOTUI

A lightweight **terminal radio player** with a full TUI (Text User Interface), written in Python. Search and stream thousands of internet radio stations or YouTube audio — without leaving your terminal.

Stations are fetched from the **[Radio Browser API](https://www.radio-browser.info/)**. Playback is handled by **VLC**. The interface is built with **[Textual](https://textual.textualize.io/)**.

---

## Features

- Full TUI — keyboard-driven, no typing commands
- Search radio stations by name, genre, country, language…
- Genre picker modal with curated list
- Favorites tab (persisted across sessions)
- ICY metadata display — shows the currently playing track
- YouTube audio streaming via `yt:` prefix
- All [Radio Browser API](https://www.radio-browser.info/) parameters supported

---

## Requirements

- Python 3.9+
- VLC Media Player (`sudo apt install vlc` or equivalent)

---

## Installation

```bash
git clone https://github.com/freegoatw/RADIOTUI.git
cd RADIOTUI
pip install -r requirements.txt
python main.py
```

---

## Usage

### Keyboard shortcuts

| Key       | Action                        |
|-----------|-------------------------------|
| `s`       | Open search bar               |
| `g`       | Open genre picker             |
| `Space`   | Play selected station         |
| `p`       | Pause / Resume                |
| `f`       | Toggle favorite               |
| `Tab`     | Switch between Results / Favorites |
| `q`       | Quit                          |
| `Escape`  | Close search / genre modal    |

### Search syntax

Type in the search bar and press `Enter`:

```
lofi                            # search by name
jazz --country=france           # filter by country
--tag=ambient --limit=50        # filter by tag
yt: joji                        # stream from YouTube
NRJ                             # exact name match
```

Any `--key=value` flag is forwarded directly to the Radio Browser API, so all API parameters work automatically.

### YouTube

Prefix your query with `yt:` to search YouTube instead of radio stations:

```
yt: bonobo
yt: the weeknd lofi one hour
```

By default a postfix is appended to improve audio-focused results. Disable it with `--no-postfix`:

```
yt: my query --no-postfix
```

---

## License

MIT — see [LICENSE](LICENSE).
Forked from [px7nn/px7-radio](https://github.com/px7nn/px7-radio).

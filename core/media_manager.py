import sys
import logging
from datetime import datetime
from services import youtube_service as ys

# ── Debug metadata ─────────────────────────────────────────────────────────────
# Passe DEBUG_META=True pour loguer tous les champs VLC dans /tmp/radio_meta.log
DEBUG_META = False

logging.basicConfig(
    filename="/tmp/radio_meta.log",
    level=logging.DEBUG,
    format="%(message)s",
)

_ALL_META = [
    "Title", "Artist", "Genre", "Copyright", "Album", "TrackNumber",
    "Description", "Rating", "Date", "Setting", "URL", "Language",
    "NowPlaying", "Publisher", "EncodedBy", "ArtworkURL", "TrackID",
    "TrackTotal", "Director", "Season", "Episode", "ShowName", "Actors",
    "AlbumArtist", "DiscNumber", "DiscTotal",
]

def _debug_meta(media) -> None:
    """Logue tous les champs vlc.Meta disponibles."""
    ts = datetime.now().strftime("%H:%M:%S")
    lines = [f"\n{'─'*50}", f"[{ts}] METADATA DUMP"]
    for name in _ALL_META:
        attr = getattr(vlc.Meta, name, None)
        if attr is None:
            continue
        val = media.get_meta(attr)
        if val:
            lines.append(f"  {name:<16} = {val}")
    logging.debug("\n".join(lines))


def check_vlc():
    try:
        import vlc
        vlc.Instance()
    except Exception:
        print("Error: VLC Media Player is not installed or not found in system PATH.")
        print("-" * 50)
        if sys.platform.startswith('win'):
            print("Download Windows version: https://www.videolan.org")
        elif sys.platform.startswith('darwin'):
            print("Download macOS version: https://www.videolan.org")
        else:
            print("Install via your package manager (e.g., sudo apt install vlc)")
        print("-" * 50)
        sys.exit(1)
    return vlc


vlc = check_vlc()


def _parse_stream_title(s: str) -> tuple[str, str]:
    """Tente de parser 'Artist - Title' depuis un StreamTitle ICY."""
    for sep in (" - ", " – ", " | ", " / "):
        if sep in s:
            artist, title = s.split(sep, 1)
            return artist.strip(), title.strip()
    return "", s.strip()


class Player:
    def __init__(self):
        self.Instance = vlc.Instance("--quiet --no-xlib --log-verbose=0 --no-video")
        self.Player = self.Instance.media_player_new()

    def play(self, url):
        self.stop()
        media = self.Instance.media_new(url)
        self.Player.set_media(media)
        self.Player.play()

    def pause(self):
        self.Player.pause()

    def resume(self):
        self.Player.play()

    def stop(self):
        self.Player.stop()

    def is_playing(self) -> bool:
        return self.Player.is_playing()

    def get_now_playing(self) -> dict:
        """Retourne les métadonnées ICY en cours sous forme de dict, ou {} si rien."""
        media = self.Player.get_media()
        if not media:
            return {}
        raw    = media.get_meta(vlc.Meta.NowPlaying) or ""
        title  = media.get_meta(vlc.Meta.Title) or ""
        artist = media.get_meta(vlc.Meta.Artist) or ""
        album  = media.get_meta(vlc.Meta.Album) or ""
        genre  = media.get_meta(vlc.Meta.Genre) or ""

        if DEBUG_META:
            _debug_meta(media)

        # NowPlaying vide ou juste un séparateur (ex: " - ") → on ignore
        if raw and not raw.strip(" -–|/"):
            raw = ""

        # Title seul sans NowPlaying ni Artist = nom du mountpoint/stream, pas un morceau
        if not raw and not artist:
            return {}

        # ICY streams: si VLC n'a pas splitté, on parse StreamTitle manuellement
        if raw and not artist and not title:
            artist, title = _parse_stream_title(raw)

        return {"raw": raw, "artist": artist, "title": title, "album": album, "genre": genre}


class MediaManager:
    def __init__(self):
        self.player = Player()
        self.data = []
        self.current_index = None
        self.src = ""  # "radio" ou "yt"

    def set_results(self, dat: list, src: str):
        """Stocke les résultats d'une recherche."""
        self.src = src
        if src == "radio":
            self.data = []
            for d in dat:
                station = {
                    "name": (d.get("name") or "")[:35].strip(),
                    "from": d.get("country") or "",
                    "countrycode": d.get("countrycode") or "",
                    "bitrate": d.get("bitrate") if d.get("bitrate") != 0 else "N.A.",
                    "url": d.get("url_resolved") or "",
                    "codec": d.get("codec") or "",
                    "language": d.get("language") or "",
                    "tags": d.get("tags") or "",
                    "votes": d.get("votes") or 0,
                    "homepage": d.get("homepage") or "",
                }
                self.data.append(station)
        else:  # yt
            self.data = dat

    def get_results(self) -> list[dict]:
        """Retourne les résultats courants."""
        return self.data

    def play(self, index: int, timeout: float = 5) -> dict:
        """Lance la lecture et retourne le résultat."""
        if not self.data:
            raise ValueError("List Empty")
        if index < 0 or index >= len(self.data):
            raise ValueError("Index Not in Range")

        if not self.data[index].get("url") and self.src == "yt":
            url = ys.get_stream_url(self.data[index].get("video_url"))
            if not url:
                raise ValueError("Stream URL not found")
            self.data[index]["url"] = url

        self.current_index = index
        self.player.play(self.data[index].get("url"))
        return {"status": "playing", "station": self.data[index]}

    def pause(self):
        """Met en pause."""
        self.player.pause()

    def resume(self):
        """Reprend la lecture."""
        self.player.resume()

    def stop(self):
        """Arrête la lecture."""
        self.player.stop()

    def is_playing(self) -> bool:
        """Retourne True si quelque chose est en lecture."""
        return self.player.is_playing()

    def get_current_station(self) -> dict | None:
        """Retourne la station en cours de lecture."""
        if self.current_index is None or not self.data:
            return None
        return self.data[self.current_index]
import threading

from textual.app import ComposeResult, App
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import (
    Footer, Input, Label, ListItem, ListView, Static, TabbedContent, TabPane
)
from rich.text import Text

from core.media_manager import MediaManager
from core.favorites import load_favorites, toggle_favorite, is_favorite
from core import parser
from services import radio_service as rs
from services import youtube_service as ys
import config


# ─── Widgets ──────────────────────────────────────────────────────────────────

class StationItem(ListItem):
    """Une ligne de la liste : nom | pays | bitrate | ★"""

    def __init__(self, station: dict, fav: bool = False):
        label = _fmt_station(station, fav)
        super().__init__(Label(label))
        self._station = station
        self._fav = fav

    @property
    def station(self) -> dict:
        return self._station

    def set_fav(self, fav: bool):
        self._fav = fav
        self.query_one(Label).update(_fmt_station(self._station, fav))


def _fmt_station(s: dict, fav: bool) -> str:
    name = (s.get("name") or "")[:38]
    country = (s.get("from") or "")[:14]
    bitrate = str(s.get("bitrate") or "N.A.")[:6]
    star = " ★" if fav else "  "
    return f"{name:<38} {country:<14} {bitrate:<6}{star}"


class StatusBar(Static):
    """Ligne de statut en bas."""

    status: reactive[str] = reactive("Ready")

    def render(self) -> Text:
        s = self.status
        if s.startswith("♪"):
            return Text(s, style="bold green")
        if s.startswith("!"):
            return Text(s[1:], style="bold red")
        if s.startswith("…"):
            return Text(s[1:], style="dim")
        return Text(s, style="dim")


# ─── App ──────────────────────────────────────────────────────────────────────

class RadioApp(App):
    TITLE = "PX7 Terminal Radio"

    # Désactive toutes les animations Textual
    ANIMATE_ON_SCROLL = False

    CSS = """
    Screen { layout: vertical; }

    TabbedContent { height: 1fr; }

    TabPane { padding: 0; }

    ListView { height: 1fr; }

    #search { height: 3; border: solid $accent; }

    #search Input { width: 100%; }

    #status { height: 1; background: $panel; padding: 0 1; }
    """

    BINDINGS = [
        Binding("f",       "favorite",     "★ Favori",  show=True),
        Binding("p",       "pause_resume", "Pause/▶",   show=True),
        Binding("s",       "stop",         "Stop",       show=True),
        Binding("/",       "focus_search", "Chercher",   show=True),
        Binding("t",       "switch_tab",   "Onglet",     show=True),
        Binding("ctrl+c",  "quit",         "Quitter",    show=True),
    ]

    def __init__(self):
        super().__init__()
        self.media = MediaManager()
        self.favs = load_favorites()

    # ── Layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with TabbedContent(id="tabs", initial="tab_results"):
            with TabPane("Résultats", id="tab_results"):
                yield ListView(id="results")
            with TabPane("Favoris", id="tab_favs"):
                yield ListView(id="favs")

        with Vertical(id="search"):
            yield Input(
                placeholder="radio search jazz  /  radio search --tag=lofi  /  yt search joji",
                id="search_input",
            )

        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self):
        self._reload_favs_list()
        self.query_one("#search_input", Input).focus()

    # ── Helpers ────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self.query_one(StatusBar).status = msg

    def _active_list(self) -> ListView:
        tab = self.query_one(TabbedContent).active
        return self.query_one("#favs" if tab == "tab_favs" else "#results", ListView)

    def _selected_station(self) -> dict | None:
        lv = self._active_list()
        idx = lv.index
        if idx is None or not lv._nodes:
            return None
        item = lv._nodes[idx]
        return item.station if isinstance(item, StationItem) else None

    def _reload_favs_list(self):
        fav_lv = self.query_one("#favs", ListView)
        fav_lv.clear()
        for s in self.favs:
            fav_lv.append(StationItem(s, fav=True))

    # ── Search ─────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted):
        query = event.value.strip()
        if not query:
            return
        self._status("… Recherche en cours…")
        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _search_thread(self, query: str):
        try:
            parsed = parser.parse(query)
            if not parsed or parsed == -1:
                self.call_from_thread(self._status, "! Commande invalide")
                return

            results = None
            sys_cmd = parsed.get("sys")

            if sys_cmd == "radio":
                params = {k: v for k, v in parsed.items() if k not in ("sys", "action")}
                if not params.get("name") and parsed.get("name"):
                    params["name"] = parsed["name"]
                results = rs.search(params)

            elif sys_cmd == "yt":
                params = {k: v for k, v in parsed.items() if k not in ("sys", "action")}
                results = ys.search_yt(parsed.get("name", ""), params)

            else:
                self.call_from_thread(self._status, f"! Commande inconnue: {sys_cmd}")
                return

            if not results:
                self.call_from_thread(self._status, "! Aucun résultat")
                return

            self.media.set_results(results, src=sys_cmd)
            self.call_from_thread(self._populate_results, results)
            self.call_from_thread(self._status, f"… {len(results)} résultat(s) – Enter pour jouer")

        except RuntimeError as e:
            self.call_from_thread(self._status, f"! {e}")

    def _populate_results(self, results: list):
        lv = self.query_one("#results", ListView)
        lv.clear()
        for s in results:
            lv.append(StationItem(s, fav=is_favorite(s, self.favs)))
        if lv._nodes:
            lv.index = 0
        self.query_one(TabbedContent).active = "tab_results"
        lv.focus()

    # ── Playback ───────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected):
        """Enter dans une ListView → jouer."""
        if not isinstance(event.item, StationItem):
            return
        station = event.item.station
        self._status(f"… Chargement de {station.get('name')}…")
        threading.Thread(target=self._play_thread, args=(station,), daemon=True).start()

    def _play_thread(self, station: dict):
        try:
            # Résout l'URL YT si nécessaire
            if not station.get("url") and station.get("video_url"):
                self.call_from_thread(self._status, "… Résolution URL YouTube…")
                from services.youtube_service import get_stream_url
                url = get_stream_url(station["video_url"])
                if not url:
                    raise RuntimeError("URL introuvable")
                station["url"] = url

            self.media.player.play(station["url"])
            import time
            deadline = config.DEFAULT_TIMEOUT
            while deadline > 0:
                time.sleep(0.2)
                deadline -= 0.2
                if self.media.player.is_playing():
                    break

            if self.media.player.is_playing():
                self.call_from_thread(self._status, f"♪ {station.get('name', '')}")
            else:
                self.media.player.stop()
                self.call_from_thread(self._status, "! Stream injoignable (timeout)")
        except Exception as e:
            self.call_from_thread(self._status, f"! {e}")

    def action_pause_resume(self):
        if self.media.player.is_playing():
            self.media.player.pause()
            self._status("⏸ Pause")
        else:
            self.media.player.resume()
            s = self.media.get_current_station()
            self._status(f"♪ {s['name']}" if s else "▶ Reprise")

    def action_stop(self):
        self.media.player.stop()
        self._status("Ready")

    # ── Favoris ────────────────────────────────────────────────────────────

    def action_favorite(self):
        station = self._selected_station()
        if not station:
            return
        self.favs = toggle_favorite(station, self.favs)
        self._reload_favs_list()
        # Met à jour le ★ dans la liste résultats
        results_lv = self.query_one("#results", ListView)
        for item in results_lv._nodes:
            if isinstance(item, StationItem):
                item.set_fav(is_favorite(item.station, self.favs))

    # ── Navigation ─────────────────────────────────────────────────────────

    def action_focus_search(self):
        self.query_one("#search_input", Input).focus()

    def action_switch_tab(self):
        tc = self.query_one(TabbedContent)
        tc.active = "tab_favs" if tc.active == "tab_results" else "tab_results"


if __name__ == "__main__":
    RadioApp().run()

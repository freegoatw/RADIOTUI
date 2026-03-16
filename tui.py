import threading
import time

from textual.app import ComposeResult, App
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static, TabbedContent, TabPane
from rich.text import Text

from core.media_manager import MediaManager
from core.favorites import load_favorites, toggle_favorite, is_favorite
from services import radio_service as rs
from services import youtube_service as ys
import config


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt(s: dict, fav: bool) -> str:
    name    = (s.get("name") or "")[:36]
    country = (s.get("from") or "")[:12]
    bitrate = str(s.get("bitrate") or "N.A.")[:6]
    star    = " ★" if fav else ""
    return f"{name:<36} {country:<12} {bitrate:<6}{star}"


# ─── Widgets ──────────────────────────────────────────────────────────────────

class StationItem(ListItem):
    def __init__(self, station: dict, fav: bool = False):
        super().__init__(Label(_fmt(station, fav)))
        self._station = station
        self._fav = fav

    @property
    def station(self) -> dict:
        return self._station

    def refresh_label(self, fav: bool):
        self._fav = fav
        self.query_one(Label).update(_fmt(self._station, fav))


class StatusBar(Static):
    msg: reactive[str] = reactive("Tape une recherche et appuie sur Entrée")

    def render(self) -> Text:
        m = self.msg
        if m.startswith("♪"):
            return Text(m, style="bold green")
        if m.startswith("✗"):
            return Text(m[1:].strip(), style="bold red")
        if m.startswith("⟳"):
            return Text(m[1:].strip(), style="italic dim")
        return Text(m, style="dim")


class StationList(ListView):
    """ListView avec ses propres bindings pour ne pas conflicuer avec l'Input."""

    BINDINGS = [
        Binding("f", "favorite", "★ Favori", show=True),
    ]

    def action_favorite(self):
        self.app.action_favorite()


# ─── App ──────────────────────────────────────────────────────────────────────

class RadioApp(App):
    TITLE = "PX7 Terminal Radio"
    ANIMATE_ON_SCROLL = False

    CSS = """
    Screen { layout: vertical; }

    TabbedContent { height: 1fr; }
    TabPane       { padding: 0; }
    StationList   { height: 1fr; }

    #search_bar {
        height: auto;
        border-top: solid $accent-darken-2;
    }
    #search_input { width: 100%; }

    #status {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    """

    # Bindings globaux avec priority=False : l'Input a la priorité sur ces touches
    BINDINGS = [
        Binding("p",      "pause_resume", "Pause/▶", show=True,  priority=False),
        Binding("s",      "stop",         "Stop",     show=True,  priority=False),
        Binding("t",      "switch_tab",   "Onglet",   show=True,  priority=False),
        Binding("escape", "focus_list",   "Liste",    show=False, priority=False),
        Binding("ctrl+c", "quit",         "Quitter",  show=True),
    ]

    def __init__(self):
        super().__init__()
        self.media = MediaManager()
        self.favs = load_favorites()

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with TabbedContent(id="tabs", initial="tab_results"):
            with TabPane("Résultats", id="tab_results"):
                yield StationList(id="results")
            with TabPane("Favoris", id="tab_favs"):
                yield StationList(id="favs")

        with Vertical(id="search_bar"):
            yield Input(
                placeholder="Chercher une radio…  (préfixe yt: pour YouTube)",
                id="search_input",
            )

        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self):
        self._reload_favs()
        self.query_one("#search_input", Input).focus()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self.query_one(StatusBar).msg = msg

    def _active_list(self) -> StationList:
        tab = self.query_one(TabbedContent).active
        return self.query_one("#favs" if tab == "tab_favs" else "#results", StationList)

    def _selected_station(self) -> dict | None:
        lv = self._active_list()
        if lv.index is None:
            return None
        nodes = list(lv._nodes)
        if not nodes:
            return None
        item = nodes[lv.index]
        return item.station if isinstance(item, StationItem) else None

    def _reload_favs(self):
        fav_lv = self.query_one("#favs", StationList)
        fav_lv.clear()
        for s in self.favs:
            fav_lv.append(StationItem(s, fav=True))

    # ── Recherche ─────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted):
        query = event.value.strip()
        if not query:
            return
        event.input.clear()
        self._set_status(f"⟳ Recherche « {query} »…")
        threading.Thread(target=self._search, args=(query,), daemon=True).start()

    def _search(self, query: str):
        try:
            if query.lower().startswith("yt:"):
                term = query[3:].strip()
                results = ys.search_yt(term, {})
                src = "yt"
            else:
                results = rs.search({"name": query})
                src = "radio"

            if not results:
                self.call_from_thread(self._set_status, "✗ Aucun résultat")
                return

            self.media.set_results(results, src)
            self.call_from_thread(self._populate, results)
            self.call_from_thread(
                self._set_status,
                f"{len(results)} résultat(s) – ↑↓ naviguer, Entrée jouer, f favori"
            )
        except RuntimeError as e:
            self.call_from_thread(self._set_status, f"✗ {e}")

    def _populate(self, results: list):
        lv = self.query_one("#results", StationList)
        lv.clear()
        for s in results:
            lv.append(StationItem(s, fav=is_favorite(s, self.favs)))
        if list(lv._nodes):
            lv.index = 0
        self.query_one(TabbedContent).active = "tab_results"
        lv.focus()

    # ── Lecture ───────────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected):
        if not isinstance(event.item, StationItem):
            return
        station = event.item.station
        self._set_status(f"⟳ Chargement de {station.get('name', '')}…")
        threading.Thread(target=self._play, args=(station,), daemon=True).start()

    def _play(self, station: dict):
        try:
            if not station.get("url") and station.get("video_url"):
                self.call_from_thread(self._set_status, "⟳ Résolution URL YouTube…")
                from services.youtube_service import get_stream_url
                url = get_stream_url(station["video_url"])
                if not url:
                    raise RuntimeError("URL introuvable")
                station["url"] = url

            self.media.player.play(station["url"])
            deadline = config.DEFAULT_TIMEOUT
            while deadline > 0:
                time.sleep(0.2)
                deadline -= 0.2
                if self.media.player.is_playing():
                    break

            if self.media.player.is_playing():
                self.call_from_thread(self._set_status, f"♪ {station.get('name', '')}")
            else:
                self.media.player.stop()
                self.call_from_thread(self._set_status, "✗ Stream injoignable (timeout)")
        except Exception as e:
            self.call_from_thread(self._set_status, f"✗ {e}")

    def action_pause_resume(self):
        if self.media.player.is_playing():
            self.media.player.pause()
            self._set_status("⏸ Pause — appuie sur p pour reprendre")
        else:
            self.media.player.resume()
            s = self.media.get_current_station()
            self._set_status(f"♪ {s['name']}" if s else "▶ Reprise")

    def action_stop(self):
        self.media.player.stop()
        self._set_status("Tape une recherche et appuie sur Entrée")

    # ── Favoris ───────────────────────────────────────────────────────────────

    def action_favorite(self):
        station = self._selected_station()
        if not station:
            return
        self.favs = toggle_favorite(station, self.favs)
        self._reload_favs()
        # Refresh ★ dans la liste résultats
        for item in list(self.query_one("#results", StationList)._nodes):
            if isinstance(item, StationItem):
                item.refresh_label(is_favorite(item.station, self.favs))
        name = station.get("name", "")
        added = is_favorite(station, self.favs)
        self._set_status(f"{'★ Ajouté aux' if added else '☆ Retiré des'} favoris : {name}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_focus_list(self):
        self._active_list().focus()

    def action_switch_tab(self):
        tc = self.query_one(TabbedContent)
        tc.active = "tab_favs" if tc.active == "tab_results" else "tab_results"


if __name__ == "__main__":
    RadioApp().run()

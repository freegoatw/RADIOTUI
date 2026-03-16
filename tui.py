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

    @property
    def station(self) -> dict:
        return self._station

    def refresh_label(self, fav: bool):
        self.query_one(Label).update(_fmt(self._station, fav))


class StatusBar(Static):
    msg: reactive[str] = reactive("s chercher  ·  tab changer d'onglet  ·  entrée/espace jouer  ·  f favori  ·  p pause  ·  q quitter")

    def render(self) -> Text:
        m = self.msg
        if m.startswith("♪"):
            return Text(m, style="bold green")
        if m.startswith("✗"):
            return Text(m[1:].strip(), style="bold red")
        if m.startswith("⟳"):
            return Text(m[1:].strip(), style="italic yellow")
        return Text(m, style="dim")


class StationList(ListView):
    """
    La zone centrale. Contient tous les bindings de navigation.
    L'utilisateur reste ici en permanence.
    """

    BINDINGS = [
        Binding("tab",    "switch_tab",   "Onglet",   show=True),
        Binding("t",      "switch_tab",   "",         show=False),
        Binding("s",      "open_search",  "Chercher", show=True),
        Binding("f",      "favorite",     "★ Favori", show=True),
        Binding("space",  "play",         "Jouer",    show=True),
        Binding("p",      "pause_resume", "Pause/▶",  show=True),
        Binding("q",      "quit_app",     "Quitter",  show=True),
    ]

    # Délègue tout à l'app
    def action_switch_tab(self):   self.app.action_switch_tab()
    def action_open_search(self):  self.app.action_open_search()
    def action_favorite(self):     self.app.action_favorite()
    def action_pause_resume(self): self.app.action_pause_resume()
    def action_quit_app(self):     self.app.exit()

    def action_play(self):
        """Space → jouer la sélection courante."""
        if self.index is not None:
            nodes = list(self._nodes)
            if nodes:
                item = nodes[self.index]
                if isinstance(item, StationItem):
                    self.app.play_station(item.station)


class SearchInput(Input):
    """Champ de recherche. Escape renvoie le focus sur la liste."""

    BINDINGS = [
        Binding("escape", "cancel", "Annuler", show=True),
    ]

    def action_cancel(self):
        self.clear()
        self.app.action_close_search()


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
        height: 0;          /* caché par défaut */
        border-top: solid $accent-darken-2;
    }
    #search_bar.visible {
        height: auto;
    }
    #search_input { width: 100%; }

    #status {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    """

    # Pas de bindings App-level : tout est dans StationList et SearchInput
    BINDINGS = []

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
            yield SearchInput(
                placeholder="Chercher une radio…  (préfixe yt: pour YouTube)",
                id="search_input",
            )

        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self):
        self._reload_favs()
        self._focus_list()

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

    def _focus_list(self):
        self._active_list().focus()

    # ── Recherche ─────────────────────────────────────────────────────────────

    def action_open_search(self):
        bar = self.query_one("#search_bar")
        bar.add_class("visible")
        self.query_one("#search_input", SearchInput).focus()

    def action_close_search(self):
        bar = self.query_one("#search_bar")
        bar.remove_class("visible")
        self._focus_list()

    def on_input_submitted(self, event: Input.Submitted):
        query = event.value.strip()
        self.action_close_search()
        if not query:
            return
        self._set_status(f"⟳ Recherche « {query} »…")
        threading.Thread(target=self._search, args=(query,), daemon=True).start()

    def _search(self, query: str):
        try:
            if query.lower().startswith("yt:"):
                results = ys.search_yt(query[3:].strip(), {})
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
                f"{len(results)} résultat(s)  ·  entrée/espace jouer  ·  f favori"
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
        """Enter dans la liste → jouer."""
        if isinstance(event.item, StationItem):
            self.play_station(event.item.station)

    def play_station(self, station: dict):
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
            self._set_status("⏸ Pause  ·  p pour reprendre")
        else:
            self.media.player.resume()
            s = self.media.get_current_station()
            self._set_status(f"♪ {s['name']}" if s else "▶ Reprise")

    # ── Favoris ───────────────────────────────────────────────────────────────

    def action_favorite(self):
        station = self._selected_station()
        if not station:
            return
        self.favs = toggle_favorite(station, self.favs)
        self._reload_favs()
        for item in list(self.query_one("#results", StationList)._nodes):
            if isinstance(item, StationItem):
                item.refresh_label(is_favorite(item.station, self.favs))
        added = is_favorite(station, self.favs)
        self._set_status(f"{'★ Ajouté' if added else '☆ Retiré'}  ·  {station.get('name', '')}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_switch_tab(self):
        tc = self.query_one(TabbedContent)
        tc.active = "tab_favs" if tc.active == "tab_results" else "tab_results"
        self._focus_list()


if __name__ == "__main__":
    RadioApp().run()

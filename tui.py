from textual.app import ComposeResult, App
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Input, Static, ListItem, ListView, TabbedContent, TabPane
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
import threading

from core.media_manager import MediaManager
from core.favorites import load_favorites, toggle_favorite, is_favorite
from core import parser
from services import radio_service as rs
from services import youtube_service as ys
import config


class StationListItem(ListItem):
    """Un élément de liste (station)."""

    def __init__(self, station: dict, is_fav: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.station = station
        self.is_fav = is_fav
        self._update_label()

    def _update_label(self):
        """Met à jour l'affichage du label."""
        name = self.station.get("name", "Unknown")
        from_str = self.station.get("from", "")
        bitrate = self.station.get("bitrate", "N.A.")
        fav_marker = " ★" if self.is_fav else ""

        # Format: name (40 chars) | country (10 chars) | bitrate (8 chars)
        label = f"{name:<40} {from_str:<15} {bitrate:<8}{fav_marker}"
        self.label = label

    @property
    def station(self):
        return self._station

    @station.setter
    def station(self, value):
        self._station = value
        if hasattr(self, "_update_label"):
            self._update_label()


class StatusBar(Static):
    """Barre de statut avec la station en cours."""

    playing = reactive("")

    def render(self) -> Text:
        if self.playing:
            return Text(f"♪ {self.playing}", style="bold cyan")
        return Text("Ready", style="dim")


class RadioApp(App):
    """Application TUI pour le lecteur radio."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main_content {
        height: 1fr;
        width: 100%;
    }

    #search_container {
        height: auto;
        border: solid $primary;
    }

    #search_input {
        width: 100%;
        margin: 0 1;
    }

    #status_bar {
        dock: bottom;
        height: 1;
        border-top: solid $primary;
        background: $panel;
    }

    StatusBar {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("up", "select_previous", "↑ Prev"),
        Binding("down", "select_next", "↓ Next"),
        Binding("enter", "play", "Play", show=True),
        Binding("f", "toggle_favorite", "Favorite", show=True),
        Binding("p", "pause_resume", "Pause", show=True),
        Binding("s", "stop", "Stop", show=True),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("tab", "switch_tab", "Tab", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.media_manager = MediaManager()
        self.favorites = load_favorites()

    def compose(self) -> ComposeResult:
        """Compose le layout de l'app."""
        yield Header(show_clock=False)

        with Vertical(id="main_content"):
            # Tabs Résultats / Favoris
            with TabbedContent(id="tabs"):
                with TabPane("Résultats", id="results_tab"):
                    yield ListView(id="results_list")
                with TabPane("Favoris", id="favorites_tab"):
                    yield ListView(id="favorites_list")

            # Search input
            with Container(id="search_container"):
                yield Input(
                    placeholder="radio search jazz | yt search joji",
                    id="search_input",
                )

        yield StatusBar(id="status_bar")
        yield Footer()

    def on_mount(self):
        """Initialise l'app et charge les favoris."""
        self.load_favorites_list()

    def load_favorites_list(self):
        """Charge la liste des favoris."""
        fav_list = self.query_one("#favorites_list", ListView)
        fav_list.clear()
        for station in self.favorites:
            item = StationListItem(station, is_fav=True)
            fav_list.append(item)

    def action_toggle_favorite(self):
        """Bascule le favori de la station sélectionnée."""
        if self.is_results_tab():
            list_view = self.query_one("#results_list", ListView)
        else:
            list_view = self.query_one("#favorites_list", ListView)

        if not list_view.children:
            return

        selected = list_view.index
        if selected is None:
            return

        station = list_view.children[selected].station
        self.favorites = toggle_favorite(station, self.favorites)
        self.load_favorites_list()

        # Met à jour le marker ★ dans la liste Résultats
        self.update_results_stars()

    def update_results_stars(self):
        """Met à jour les marqueurs ★ dans la liste Résultats."""
        results_list = self.query_one("#results_list", ListView)
        for item in results_list.children:
            item.is_fav = is_favorite(item.station, self.favorites)

    def action_play(self):
        """Lance la lecture de la station sélectionnée."""
        if self.is_results_tab():
            list_view = self.query_one("#results_list", ListView)
        else:
            list_view = self.query_one("#favorites_list", ListView)

        if not list_view.children:
            return

        selected = list_view.index
        if selected is None:
            return

        self.do_play(selected)

    def do_play(self, index: int):
        """Lance la lecture dans un thread."""
        def _play():
            try:
                timeout = config.DEFAULT_TIMEOUT
                self.media_manager.play(index, timeout)
                station = self.media_manager.get_current_station()
                if station:
                    self.call_from_thread(
                        setattr,
                        self.query_one(StatusBar),
                        "playing",
                        station.get("name", "")
                    )
            except Exception as e:
                self.call_from_thread(
                    setattr,
                    self.query_one(StatusBar),
                    "playing",
                    f"Error: {str(e)}"
                )

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()

    def action_pause_resume(self):
        """Bascule pause/reprendre."""
        if self.media_manager.is_playing():
            self.media_manager.pause()
            self.query_one(StatusBar).playing += " [Paused]"
        else:
            self.media_manager.resume()
            station = self.media_manager.get_current_station()
            if station:
                self.query_one(StatusBar).playing = station.get("name", "")

    def action_stop(self):
        """Arrête la lecture."""
        self.media_manager.stop()
        self.query_one(StatusBar).playing = ""

    def action_focus_search(self):
        """Focus sur le champ de recherche."""
        self.query_one("#search_input", Input).focus()

    def action_switch_tab(self):
        """Bascule entre les tabs Résultats et Favoris."""
        tabs = self.query_one(TabbedContent)
        # Déplace vers le prochain onglet
        current = tabs.active
        if current == "results_tab":
            tabs.active = "favorites_tab"
        else:
            tabs.active = "results_tab"

    def action_select_previous(self):
        """Sélectionne l'item précédent dans la liste."""
        if self.is_results_tab():
            list_view = self.query_one("#results_list", ListView)
        else:
            list_view = self.query_one("#favorites_list", ListView)

        if list_view.index is not None and list_view.index > 0:
            list_view.index = list_view.index - 1

    def action_select_next(self):
        """Sélectionne l'item suivant dans la liste."""
        if self.is_results_tab():
            list_view = self.query_one("#results_list", ListView)
        else:
            list_view = self.query_one("#favorites_list", ListView)

        if list_view.index is None:
            list_view.index = 0
        elif list_view.index < len(list_view.children) - 1:
            list_view.index = list_view.index + 1

    def is_results_tab(self) -> bool:
        """Retourne True si on est sur l'onglet Résultats."""
        tabs = self.query_one(TabbedContent)
        return tabs.active == "results_tab"

    def on_input_submitted(self, event: Input.Submitted):
        """Gère la soumission du formulaire de recherche."""
        query = event.value
        if query.strip():
            self.do_search(query)

    def do_search(self, query: str):
        """Lance la recherche dans un thread."""
        def _search():
            try:
                parsed = parser.parse(query)
                if not parsed or parsed == -1:
                    return

                results = None

                if parsed.get("sys") == "radio":
                    params = {k: v for k, v in parsed.items() if k not in ["sys", "action"]}
                    if "name" not in params and parsed.get("name"):
                        params["name"] = parsed.get("name")
                    if not params.get("limit"):
                        params["limit"] = config.DEFAULT_RADIO_SEARCH_LIMIT
                    results = rs.search(params)

                elif parsed.get("sys") == "yt":
                    params = {k: v for k, v in parsed.items() if k not in ["sys", "action"]}
                    query_str = parsed.get("name", "")
                    results = ys.search_yt(query_str, params)

                if results:
                    src = "radio" if parsed.get("sys") == "radio" else "yt"
                    self.media_manager.set_results(results, src)
                    self.call_from_thread(self.update_results_list)
            except Exception as e:
                # Silencieusement, la recherche s'est arrêtée
                pass

        thread = threading.Thread(target=_search, daemon=True)
        thread.start()

    def update_results_list(self):
        """Met à jour la liste des résultats."""
        results_list = self.query_one("#results_list", ListView)
        results_list.clear()

        for station in self.media_manager.get_results():
            is_fav = is_favorite(station, self.favorites)
            item = StationListItem(station, is_fav=is_fav)
            results_list.append(item)

        # Sélectionne le premier item
        if results_list.children:
            results_list.index = 0

        # Bascule vers l'onglet Résultats
        tabs = self.query_one(TabbedContent)
        tabs.active = "results_tab"


if __name__ == "__main__":
    app = RadioApp()
    app.run()

import threading
import time

from textual.app import ComposeResult, App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static, TabbedContent, TabPane
from rich.text import Text

from core.media_manager import MediaManager
from core.favorites import load_favorites, toggle_favorite, is_favorite
from services import radio_service as rs
from services import youtube_service as ys
import config


# ─── Genres ───────────────────────────────────────────────────────────────────

GENRES = [
    ("Lofi",        "lofi"),
    ("Jazz",        "jazz"),
    ("Techno",      "techno"),
    ("Electronic",  "electronic"),
    ("Ambient",     "ambient"),
    ("Classical",   "classical"),
    ("Rock",        "rock"),
    ("Metal",       "metal"),
    ("Pop",         "pop"),
    ("Hip-Hop",     "hip-hop"),
    ("R&B / Soul",  "rnb"),
    ("Blues",       "blues"),
    ("Reggae",      "reggae"),
    ("Folk",        "folk"),
    ("Country",     "country"),
    ("World",       "world"),
    ("News",        "news"),
    ("Talk",        "talk"),
    ("Sports",      "sports"),
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt(s: dict, fav: bool) -> str:
    name    = (s.get("name") or "")[:34]
    country = (s.get("from") or "")[:12]
    bitrate = str(s.get("bitrate") or "N.A.")[:6]
    star    = " ★" if fav else ""
    return f"{name:<34} {country:<12} {bitrate:<6}{star}"


def _meta_text(s: dict | None, now_playing: str = "") -> Text:
    """Construit le texte du panneau de métadonnées."""
    t = Text()
    if s is None:
        t.append("Sélectionne une station\npour voir les détails.", style="dim")
        return t

    name = s.get("name") or ""
    t.append(f"{name}\n", style="bold")
    t.append("─" * min(len(name) + 2, 28) + "\n", style="dim")

    country = s.get("from") or ""
    cc      = s.get("countrycode") or ""
    if country:
        label = f"{cc}  {country}" if cc else country
        t.append(f"  {label}\n")

    lang = s.get("language") or ""
    if lang:
        t.append(f"  {lang.title()}\n", style="dim")

    bitrate = s.get("bitrate")
    codec   = s.get("codec") or ""
    if bitrate and bitrate != "N.A.":
        spec = f"{bitrate} kbps"
        if codec:
            spec += f"  {codec.upper()}"
        t.append(f"\n  {spec}\n")

    tags = s.get("tags") or ""
    if tags:
        tag_list = [tg.strip() for tg in tags.split(",") if tg.strip()][:6]
        t.append("\n  " + "  ".join(tag_list) + "\n", style="dim italic")

    votes = s.get("votes")
    if votes:
        t.append(f"\n  ↑ {votes} votes\n", style="dim")

    homepage = s.get("homepage") or ""
    if homepage and not homepage.startswith("http://0"):
        disp = homepage.replace("https://", "").replace("http://", "")[:26]
        t.append(f"\n  {disp}\n", style="dim underline")

    # YT extras
    duration = s.get("duration")
    uploader = s.get("from") or ""
    if duration and not country:
        mins, secs = divmod(int(duration), 60)
        t.append(f"  {mins}:{secs:02d}\n")
    if uploader and not country:
        t.append(f"  {uploader}\n", style="dim")

    # ICY now playing
    if now_playing:
        t.append("\n♪ En cours\n", style="bold green")
        t.append(f"  {now_playing}\n", style="green")

    return t


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


class MetaPanel(Static):
    """Panneau latéral de métadonnées."""

    station:     reactive[dict | None] = reactive(None, layout=True)
    now_playing: reactive[str]         = reactive("", layout=True)

    def render(self) -> Text:
        return _meta_text(self.station, self.now_playing)


class StatusBar(Static):
    msg: reactive[str] = reactive(
        "s chercher  ·  g genres  ·  tab onglet  ·  entrée/espace jouer  ·  f favori  ·  p pause  ·  q quitter"
    )

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
    """Zone centrale — contient tous les raccourcis."""

    BINDINGS = [
        Binding("tab",   "switch_tab",   "Onglet",   show=True),
        Binding("t",     "switch_tab",   "",         show=False),
        Binding("s",     "open_search",  "Chercher", show=True),
        Binding("g",     "open_genres",  "Genres",   show=True),
        Binding("f",     "favorite",     "★ Favori", show=True),
        Binding("space", "play",         "Jouer",    show=True),
        Binding("p",     "pause_resume", "Pause/▶",  show=True),
        Binding("q",     "quit_app",     "Quitter",  show=True),
    ]

    def action_switch_tab(self):   self.app.action_switch_tab()
    def action_open_search(self):  self.app.action_open_search()
    def action_open_genres(self):  self.app.action_open_genres()
    def action_favorite(self):     self.app.action_favorite()
    def action_pause_resume(self): self.app.action_pause_resume()
    def action_quit_app(self):     self.app.exit()

    def action_play(self):
        if self.index is not None:
            nodes = list(self._nodes)
            if nodes and isinstance(nodes[self.index], StationItem):
                self.app.play_station(nodes[self.index].station)


def _parse_search(query: str) -> dict:
    """
    Parse le query de recherche en paramètres API.
    Supporte : jazz  /  NRJ  /  jazz --country=france  /  --tag=lofi --limit=50
    """
    params: dict = {}
    name_parts: list[str] = []

    for token in query.split():
        if token.startswith("--"):
            key, sep, val = token[2:].partition("=")
            params[key] = val if sep else "true"
        else:
            name_parts.append(token)

    if name_parts:
        params["name"] = " ".join(name_parts)

    # Tri par votes par défaut (les plus populaires d'abord)
    params.setdefault("order", "votes")
    params.setdefault("reverse", "true")

    return params


class SearchInput(Input):
    BINDINGS = [Binding("escape", "cancel", "Annuler", show=True)]

    def action_cancel(self):
        self.clear()
        self.app.action_close_search()


# ─── Genre Screen (modal) ─────────────────────────────────────────────────────

class GenreItem(ListItem):
    def __init__(self, label: str, tag: str):
        super().__init__(Label(label))
        self.tag = tag


class GenreScreen(ModalScreen):
    CSS = """
    GenreScreen {
        align: center middle;
    }
    #genre_dialog {
        width: 32;
        height: auto;
        max-height: 28;
        border: solid $accent;
        background: $surface;
        padding: 0 1;
    }
    #genre_title {
        text-align: center;
        padding: 1 0 0 0;
        color: $accent;
    }
    #genre_list {
        height: auto;
        max-height: 22;
    }
    """

    BINDINGS = [Binding("escape", "dismiss_screen", "Fermer", show=True)]

    def action_dismiss_screen(self):
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="genre_dialog"):
            yield Label("── Genres ──", id="genre_title")
            with ListView(id="genre_list"):
                for label, tag in GENRES:
                    yield GenreItem(label, tag)

    def on_mount(self):
        self.query_one("#genre_list", ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected):
        if isinstance(event.item, GenreItem):
            self.dismiss(event.item.tag)


# ─── App ──────────────────────────────────────────────────────────────────────

class RadioApp(App):
    TITLE = "PX7 Terminal Radio"
    ANIMATE_ON_SCROLL = False

    CSS = """
    Screen { layout: vertical; }

    #body {
        layout: horizontal;
        height: 1fr;
    }

    #left { width: 1fr; }

    TabbedContent { height: 1fr; }
    TabPane       { padding: 0; }
    StationList   { height: 1fr; }

    #meta {
        width: 30;
        border-left: solid $accent-darken-2;
        padding: 0 1;
        background: $panel;
    }

    #search_bar {
        height: 0;
        border-top: solid $accent-darken-2;
    }
    #search_bar.visible { height: auto; }
    #search_input       { width: 100%; }

    #status {
        height: 1;
        background: $panel-darken-1;
        padding: 0 1;
    }
    """

    BINDINGS = []

    def __init__(self):
        super().__init__()
        self.media = MediaManager()
        self.favs = load_favorites()
        self._icy_stop = threading.Event()

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="left"):
                with TabbedContent(id="tabs", initial="tab_results"):
                    with TabPane("Résultats", id="tab_results"):
                        yield StationList(id="results")
                    with TabPane("Favoris", id="tab_favs"):
                        yield StationList(id="favs")

            yield MetaPanel(id="meta")

        with Vertical(id="search_bar"):
            yield SearchInput(
                placeholder="NRJ  /  jazz --country=france  /  --tag=lofi --limit=50  /  yt: joji",
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

    # ── MetaPanel ─────────────────────────────────────────────────────────────

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if isinstance(event.item, StationItem):
            self.query_one(MetaPanel).station = event.item.station
        elif event.item is None:
            self.query_one(MetaPanel).station = None

    # ── Recherche ─────────────────────────────────────────────────────────────

    def action_open_search(self):
        self.query_one("#search_bar").add_class("visible")
        self.query_one("#search_input", SearchInput).focus()

    def action_close_search(self):
        self.query_one("#search_bar").remove_class("visible")
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
                results = rs.search(_parse_search(query))
                src = "radio"

            if not results:
                self.call_from_thread(self._set_status, "✗ Aucun résultat")
                return

            self.media.set_results(results, src)
            self.call_from_thread(self._populate, results)
            self.call_from_thread(
                self._set_status,
                f"{len(results)} résultat(s)  ·  entrée/espace jouer  ·  f favori",
            )
        except RuntimeError as e:
            self.call_from_thread(self._set_status, f"✗ {e}")

    def _search_by_tag(self, tag: str):
        self._set_status(f"⟳ Chargement du genre « {tag} »…")
        threading.Thread(target=self._search_tag_thread, args=(tag,), daemon=True).start()

    def _search_tag_thread(self, tag: str):
        try:
            results = rs.search({"tag": tag, "order": "votes", "reverse": "true"})
            if not results:
                self.call_from_thread(self._set_status, f"✗ Aucun résultat pour « {tag} »")
                return
            self.media.set_results(results, "radio")
            self.call_from_thread(self._populate, results)
            self.call_from_thread(
                self._set_status,
                f"{len(results)} résultat(s) — {tag}  ·  entrée/espace jouer  ·  f favori",
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

    # ── Genre screen ──────────────────────────────────────────────────────────

    def action_open_genres(self):
        def on_genre(tag: str | None):
            if tag:
                self._search_by_tag(tag)
        self.push_screen(GenreScreen(), on_genre)

    # ── Lecture ───────────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected):
        if isinstance(event.item, StationItem):
            self.play_station(event.item.station)

    def play_station(self, station: dict):
        self._icy_stop.set()
        self.query_one(MetaPanel).now_playing = ""
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
                self._start_icy_poll()
            else:
                self.media.player.stop()
                self.call_from_thread(self._set_status, "✗ Stream injoignable (timeout)")
        except Exception as e:
            self.call_from_thread(self._set_status, f"✗ {e}")

    def _start_icy_poll(self):
        """Démarre le polling des métadonnées ICY en arrière-plan."""
        self._icy_stop.set()          # Arrête un éventuel poll précédent
        self._icy_stop.clear()
        threading.Thread(target=self._icy_poll_loop, daemon=True).start()

    def _icy_poll_loop(self):
        """Boucle de polling : lit NowPlaying toutes les 5 s."""
        last = ""
        while not self._icy_stop.is_set():
            if not self.media.player.is_playing():
                break
            track = self.media.player.get_now_playing()
            if track != last:
                last = track
                self.call_from_thread(
                    setattr, self.query_one(MetaPanel), "now_playing", track
                )
            self._icy_stop.wait(5)

    def action_pause_resume(self):
        if self.media.player.is_playing():
            self.media.player.pause()
            self._icy_stop.set()
            self._set_status("⏸ Pause  ·  p pour reprendre")
        else:
            self.media.player.resume()
            self._start_icy_poll()
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

    # Nettoyage à la sortie
    def on_unmount(self):
        self._icy_stop.set()
        self.media.player.stop()


if __name__ == "__main__":
    RadioApp().run()

HELP_PAGE = """
════════════════════════════════════════════════════════════
                     PX7 TERMINAL RADIO
════════════════════════════════════════════════════════════

Stream internet radio directly from your terminal.

Basic workflow:
    1. Search stations
    2. Select station number
    3. Play and control playback

────────────────────────────────────────────────────────────
SEARCH
────────────────────────────────────────────────────────────

Search stations by name

    >> radio search <name>

Example
    >> radio search lofi
    >> radio search bbc


Search using API filters

    >> radio search [OPTIONS] <name>

Examples
    >> radio search --tag=lofi
    >> radio search --tag=jazz --limit=10
    >> radio search --country=Japan
    >> radio search --order=clickcount
    >> radio search --order=votes --reverse=true

────────────────────────────────────────────────────────────
SEARCH OPTIONS
────────────────────────────────────────────────────────────

--tag=TAG            Filter by tag / genre
--country=NAME       Filter by country
--language=LANG      Filter by language
--limit=N            Limit number of results
--reverse=true       Reverse order

Sort results

--order=name
--order=country
--order=language
--order=votes
--order=clickcount
--order=bitrate
--order=codec
--order=lastcheckok

Example

    >> radio search --tag=rock --order=clickcount --limit=10

────────────────────────────────────────────────────────────
PLAYBACK
────────────────────────────────────────────────────────────

Play a station

    >> play <number>

Pause playback

    >> pause

Resume playback

    >> resume

Stop playback

    >> stop

Show current station

    >> show

────────────────────────────────────────────────────────────
UTILITY
────────────────────────────────────────────────────────────

Check network ping

    >> ping

Exit application

    >> exit
    >> quit
    >> logout

────────────────────────────────────────────────────────────
EXAMPLE SESSION
────────────────────────────────────────────────────────────

>> radio search --tag=lofi --order=clickcount --limit=5

No.   Station name
1     Lofi Beats
2     Chillhop Radio
3     Sleepy Beats
4     Coffee Jazz
5     Tokyo Lofi

>> play 1
Playing
"""
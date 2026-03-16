import yt_dlp
from yt_dlp.utils import DownloadError
from config import YDL_OPTIONS, DEFAULT_YT_SEARCH_LIMIT, DEFAULT_QUERY_POSTFIX


def search_yt(query: str, params: dict):
    if not params.get("no-postfix"):
        query += DEFAULT_QUERY_POSTFIX
    limit = params.get("limit") or DEFAULT_YT_SEARCH_LIMIT
    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except DownloadError as e:
        raise RuntimeError(f"YouTube fetch failed: {e}")
    except Exception as e:
        raise RuntimeError(str(e))

    results = []
    for entry in info["entries"]:
        if not entry:
            continue
        duration = entry.get("duration")
        if not duration:
            continue
        results.append({
            "name": entry.get("title"),
            "video_url": f"https://youtube.com/watch?v={entry.get('id')}",
            "from": entry.get("uploader"),
            "duration": duration,
            "bitrate": "N.A.",
        })
    return results


def get_stream_url(video_url: str):
    ydl_opt = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opt) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info["url"] or None

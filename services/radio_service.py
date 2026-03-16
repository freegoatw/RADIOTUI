import requests as rq
import config


def search(params: dict):
    if params.get("name") is None and len(params) == 1:
        return None
    if not params.get("limit"):
        params["limit"] = config.DEFAULT_RADIO_SEARCH_LIMIT
    try:
        res = rq.get(config.API_URL, params=params, timeout=10)
        if not res.ok:
            raise RuntimeError(f"Server error {res.status_code}")
        return res.json()
    except Exception as e:
        raise RuntimeError(str(e))

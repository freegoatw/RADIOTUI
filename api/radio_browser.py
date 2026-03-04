import requests 
from . import DEFAULT_LIMIT, BASE_URL

def GetData(url):
    res = requests.get(url)
    if not res.ok:
        return None
    return res.json()

def GetByName(query):
    return GetData(f"{BASE_URL}search?name={query.lower()}")

def GetByTag(tag):
    return GetData(f"{BASE_URL}bytag/{tag.lower()}?limit={DEFAULT_LIMIT}&hidebroken=true&order=clickcount")
import requests
import json
import logging
import os
from enum import Enum, auto
from urllib.parse import quote, quote_plus
from time import sleep
from datetime import datetime

"""API Doc : https://scryfall.com/docs/api"""

date_fmt = "%Y-%m-%d"
url = "https://scryfall.com/"

class ScryfallTypes(Enum):
    UNIQUE_ART = "unique_artwork"


def get_content(url):
    """Extract data from API json file. If there is multiple pages, gather them."""
    if not url: return False
    # Time limit of scryfall API
    sleep(0.1)
    r = requests.get(url)
    data = {}
    if r.status_code == requests.codes.ok:
        data = json.loads(r.content.decode('utf-8'))
        if data.get("object", False) == "error": 
            logging.info("API respond an error to url : {0}".format(url))
            return False
        if data.get("has_more", None) and data.get("next_page", None):
            content = get_content(data["next_page"])
            data["data"] += content.get("data", [])
    return data


def get_card_url(card):
    return os.path.join(url, "card", card.get("id"))


def get_set_list():
    """Get list of all MTG set objects"""
    url = "https://api.scryfall.com/sets"
    content = get_content(url)
    return content.get("data", None)


def get_cards_list(edition):
    """Get list of cards from a set object"""
    url = edition.get("search_uri", False)
    content = get_content(url)
    return content.get("data", None)


def get_futur_sets():
    """Get list of all futur set objects until the last set with a past realease date"""
    present = datetime.now()
    set_list = get_set_list()
    futur_sets = []
    i = 0
    while datetime.strptime(set_list[i].get("released_at", "3000-01-01"), date_fmt) > present and i < len(set_list):
        # Doesn't include Magic Online sets
        if not set_list[i].get("digital", False):
            futur_sets.append(set_list[i])
        i += 1
    return futur_sets


def get_futur_cards():
    """
    Get cards released in the futur sorted by most futur date first
    :return: list of scryfall cards
    """
    url = f"https://api.scryfall.com/cards/search?order=released&q=date>{datetime.now().strftime(date_fmt)}"
    content = get_content(url)
    if not content.get("object", "error") == "error":
        return content.get("data", content)
    else:
        return None


def get_date(date: str):
    return datetime.strptime(date, date_fmt)


def get_image_urls(card, size="normal"):
    """Return a list of normal sized urls for a card object (up to 2 urls for double faced cards)
       Possible sizes: small, normal, large, png, art_crop, border_crop"""
    urls = []
    single_image = card.get("image_uris", {}).get(size, None)
    if single_image:
        urls.append(single_image)
    else:
        for face in card.get("card_faces", []):
            urls.append(face.get("image_uris", {}).get(size, None))
    return urls


def get_card_set(card):
    """Return Set object from a Card object"""
    set_code = card.get("code", None)
    if not set_code: return None
    
    url = "https://api.scryfall.com/sets/{}".format(set_code)
    return get_content(url)


def get_set(set_code):
    """Return set object from a set_code"""
    if not set_code: return None
    url = "https://api.scryfall.com/sets/{}".format(set_code)
    return get_content(url)


def get_card_by_id(scryfall_id):
    """Get card object by scryfall id"""
    url = "https://api.scryfall.com/cards/{}".format(scryfall_id)
    content = get_content(url)
    return content


def get_card_by_name(name, set="", exact=True):
    """Return a card object from a string cardname"""
    if set:
        set = "&set=" + quote_plus(set)
    if exact:
        exact = "exact"
    else:
        exact = "fuzzy"
    url = f"https://api.scryfall.com/cards/named?{exact}={quote(name)}{set}"
    content = get_content(url)
    if not content.get("object", "error") == "error": 
        return content
    else:
        return None


def search(**kwargs):
    """General search using scryfall search engine"""
    url = "https://api.scryfall.com/cards/search?q="
    url += "+".join(quote_plus(f"{key}:{value}") for key, value in kwargs.items())
    content = get_content(url)
    if not content.get("object", "error") == "error": 
        return content.get("data", content)
    else:
        return None


def get_random_card(query=None):
    url = "https://api.scryfall.com/cards/random"
    if query:
        url += "?" + quote(query)
    content = get_content(url)
    if not content.get("object", "error") == "error": 
        return content
    else:
        return {}


def get_card_color(card):
    """Get card color"""
    c = card.get("color_identity", None)
    if len(c) > 0:
        return ''.join(c)
    else:
        return "U"


def get_card_names(card):
    uri = card.get("uri", None)
    if uri:
        url = uri + "/fr"
        content = get_content(url)
    else:
        return None
    if not content.get("object", "error") == "error": 
        card_names = [card.get("name", None), content.get("printed_name", None)]
        return card_names
    else:
        card_names = [card.get("name", None)]
        return card_names


def get_related_tokens_id(card):
    ids = []
    for part in card.get("all_parts", []):
        if part.get("component", None) == "token":
            ids.append(part["id"])
    return ids


def get_bulk_data(bulk_type: ScryfallTypes):
    content = get_content("https://api.scryfall.com/bulk-data").get("data")
    for bulk_data in content:
        if bulk_data.get("type") == bulk_type.value:
            r = requests.get(bulk_data["download_uri"])
            if r.status_code == requests.codes.ok:
                return json.loads(r.content.decode('utf-8'))


def to_datetime(s: str):
    return datetime.strptime(s, "%Y-%m-%d")


if __name__ == "__main__":
    print([s.get("code") for s in get_futur_sets()])

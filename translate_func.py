import json

import requests

from token_keys import token

url = "https://dictionary.yandex.net/api/v1/dicservice.json/lookup"


def translate_to_en(word):
    word = word.lower()
    params = {
        "key": f"{token}",
        "lang": "ru-en",
        "text": f"{word}",
    }
    response = requests.get(url, params=params)
    data = response.json()
    try:
        return data["def"][0]["tr"][0]["text"]
    except (KeyError, IndexError):
        return None


def translate_to_ru(word):
    word = word.lower()
    params = {
        "key": f"{token}",
        "lang": "en-ru",
        "text": f"{word}",
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data["def"][0]["tr"][0]["text"]

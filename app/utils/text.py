import re


def sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
    return sanitized or "video"


def clean_text_for_narration(text: str) -> str:
    return re.sub(r"http\S+|www\.\S+", "", text, flags=re.MULTILINE).strip()


def expand_abbreviations_for_tts(text: str) -> str:
    abbreviations = {
        "TIFU": "Today I Fucked Up",
        "AITA": "Am I the Asshole",
        "TL;DR": "TLDR",
        "OP": "Original Poster",
        "IMO": "In My Opinion",
        "IMHO": "In My Humble Opinion",
        "ELI5": "Explain Like I'm Five",
        "NSFW": "Not Safe For Work",
        "SFW": "Safe For Work",
    }
    expanded = text
    for key, value in abbreviations.items():
        expanded = re.sub(rf"\b{re.escape(key)}\b", value, expanded, flags=re.IGNORECASE)
    return expanded

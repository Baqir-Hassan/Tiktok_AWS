import re


def sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
    return sanitized or "video"


def clean_text_for_narration(text: str) -> str:
    return re.sub(r"http\S+|www\.\S+", "", text, flags=re.MULTILINE).strip()


def sanitize_generated_script_for_tts(text: str) -> str:
    cleaned = clean_text_for_narration(text)
    if not cleaned:
        return ""

    # Remove common screenplay / stage-direction wrappers often produced by LLMs.
    cleaned = re.sub(r"\[(?:[^\]\n]{1,120})\]", " ", cleaned)

    stage_keywords = (
        "music|intro|outro|fade|sfx|sound effect|applause|cheer|laugh|laughter|"
        "sigh|gasp|whisper|pause|beat|breath|breathing|narrator|voiceover|vo"
    )
    cleaned = re.sub(
        rf"\((?=[^)]*(?:{stage_keywords}))[^)]{{1,120}}\)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Drop stage-direction labels at line starts.
    cleaned = re.sub(
        r"(?im)^\s*(narrator|voiceover|vo|sfx|fx|music)\s*:\s*",
        "",
        cleaned,
    )

    # Remove lightweight markdown styling that should not be spoken.
    cleaned = re.sub(r"[*_`>#~]+", "", cleaned)

    # Normalize whitespace and trim.
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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

import requests

from app.core.config import get_settings


class GeminiScriptService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_script(self, title: str, body: str) -> str:
        if not self.settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash-lite:generateContent?key={self.settings.google_api_key}"
        )
        prompt = (
            "Format the following Reddit story into a short-form narration script. "
            "Preserve the original meaning, remove formatting artifacts, and keep it engaging for voice narration. "
            "Output plain narration only. "
            "Do not include stage directions, speaker labels, production notes, bracketed cues, or parenthetical cues "
            "(for example: [intro music], (pause), Narrator:, SFX:). "
            "Return only the final narration text.\n\n"
            f"Title: {title}\n\nBody:\n{body}"
        )
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

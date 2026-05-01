import requests
from groq import Groq

from app.core.config import get_settings


class GroqScriptService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_script(self, title: str, body: str) -> str:
        if not self.settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        client = Groq(api_key=self.settings.groq_api_key)
        
        prompt = (
            "Format the following Reddit story into a short-form narration script. "
            "Preserve the original meaning, remove formatting artifacts, and keep it engaging for voice narration. "
            "Output plain narration only. "
            "Do not include stage directions, speaker labels, production notes, bracketed cues, or parenthetical cues "
            "(for example: [intro music], (pause), Narrator:, SFX:). "
            "Return only the final narration text.\n\n"
            f"Title: {title}\n\nBody:\n{body}"
        )
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=self.settings.groq_model,
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stop=None,
            stream=False,
        )
        
        return chat_completion.choices[0].message.content

import json
import time
from pathlib import Path

from groq import Groq
from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    client = Groq(api_key=settings.groq_api_key)
    
    try:
        # Test the Groq API
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "Health check: reply with exactly one word: healthy"
                }
            ],
            model=settings.groq_model,
            temperature=0.0,
            max_tokens=1024,
            top_p=1,
            stop=None,
            stream=False,
        )
        
        print(f"Groq API test response: {chat_completion.choices[0].message.content}")
        
    except Exception as e:
        print(f"Error testing Groq API: {e}")
        raise


if __name__ == "__main__":
    main()

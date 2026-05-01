import os
from app.core.config import get_settings

def main():
    settings = get_settings()
    print(f"GROQ_API_KEY: {settings.groq_api_key}")
    if settings.groq_api_key:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly one word: healthy"
                }
            ],
            model="llama3-70b-8192",
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stop=None,
            stream=False,
        )
        print(f"Groq API test response: {chat_completion.choices[0].message.content}")
    else:
        print("GROQ_API_KEY is not configured")

if __name__ == "__main__":
    main()
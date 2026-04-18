import json
import time

import requests

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash-lite:generateContent?key={settings.google_api_key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Reply with exactly one word: healthy"
                        )
                    }
                ]
            }
        ]
    }

    started_at = time.perf_counter()
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        elapsed = time.perf_counter() - started_at

        print(f"Status: {response.status_code}")
        print(f"Elapsed: {elapsed:.2f}s")

        if response.ok:
            try:
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                print(f"Reply: {text}")
            except Exception:
                print("Reply: <unable to parse success payload>")
                print(response.text[:1000])
        else:
            print("Error body:")
            try:
                print(json.dumps(response.json(), indent=2)[:2000])
            except Exception:
                print(response.text[:2000])
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - started_at
        print(f"Request failed after {elapsed:.2f}s")
        print(f"Error: {type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()

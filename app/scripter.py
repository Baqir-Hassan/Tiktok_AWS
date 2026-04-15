from app.services.script_service import GeminiScriptService


def generate_script_with_gemini(text):
    return GeminiScriptService().generate_script("Untitled", text)

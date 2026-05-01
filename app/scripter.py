from app.services.script_service import GroqScriptService


def generate_script_with_gemini(text):
    return GroqScriptService().generate_script("Untitled", text)

# ============================================================
# Sovereign AI Compliance Guard
# Government of India Data Residency — KB Tender RFB IN-KBL-543730-NC-RFB
#
# When KB_SOVEREIGN_MODE=1 (recommended for all KB content):
#   - All foreign cloud LLM API calls (Groq/Gemini/OpenRouter) are BLOCKED
#   - Only on-premise / India-hosted models are permitted
#   - Set KB_SOVEREIGN_MODE=0 only for non-KB / non-government content
# ============================================================
import os

_FOREIGN_PROVIDERS = ("groq", "gemini", "openrouter")

_DECLARATION = """
DATA RESIDENCY DECLARATION — KB Tender RFB IN-KBL-543730-NC-RFB
-----------------------------------------------------------------
All core AI processing (ASR, Translation, TTS) runs fully offline
on-premise using open-source models (faster-whisper, IndicTrans2,
Parler-TTS, MMS-TTS). No KB content is transmitted to foreign servers.

Optional LLM post-edit (Groq / Gemini / OpenRouter) is DISABLED
when KB_SOVEREIGN_MODE=1 in .env, ensuring full compliance with
Government of India data security and data residency requirements
(IT Act 2000, DPDP Act 2023, MeitY cloud policy).

Preferred sovereign alternatives: Sarvam AI (India-hosted),
BharatGPT, or any MeitY-empanelled cloud AI service.
"""


def sovereign_mode_enabled() -> bool:
    return os.environ.get("KB_SOVEREIGN_MODE", "1").strip() == "1"


def assert_sovereign_allowed(provider: str) -> None:
    """Raise if sovereign mode is on and provider is a foreign cloud API."""
    if sovereign_mode_enabled() and provider.lower() in _FOREIGN_PROVIDERS:
        raise PermissionError(
            f"[SOVEREIGN BLOCK] LLM provider '{provider}' is a foreign cloud API. "
            "KB_SOVEREIGN_MODE=1 prohibits sending government content to foreign servers. "
            "Set KB_SOVEREIGN_MODE=0 in .env only for non-KB content, or use a "
            "MeitY-empanelled India-hosted AI service."
        )


def get_compliance_declaration() -> str:
    return _DECLARATION.strip()

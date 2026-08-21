# ============================================================
# LLM Translation Enhancer
# Post-edit machine translations to meet KB tender 98% SLA.
# Optional — activates only when an API key is set in .env.
# Supports: Groq (free), Gemini, OpenRouter
# ============================================================
import os, json
from pathlib import Path
from .logger import get_logger
from .retry import retry
from .sovereign_guard import assert_sovereign_allowed, sovereign_mode_enabled

log = get_logger("llm")

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _groq_key():       return os.environ.get("GROQ_API_KEY", "")
def _gemini_key():     return os.environ.get("GEMINI_API_KEY", "")
def _openrouter_key(): return os.environ.get("OPENROUTER_API_KEY", "")

_ENHANCE_PROMPT = """\
You are a professional translator and language quality editor for Indian languages.

Task: Post-edit the machine translation below to make it natural, fluent, and accurate.
- Keep all proper nouns, scheme names, and numbers exactly as-is
- Fix grammar, word order, and unnatural phrasing
- Output ONLY the corrected translation, nothing else

Source ({src_lang}): {source}
Machine Translation ({tgt_lang}): {translation}
Corrected Translation:"""

_BATCH_PROMPT = """\
You are a professional translator for Indian languages.
Post-edit these machine translations to be natural and fluent.
Keep proper nouns and numbers unchanged.
Return a JSON array of corrected strings in the same order.

Source language: {src_lang}
Target language: {tgt_lang}
Translations: {translations_json}

Return only the JSON array, no explanation."""


class LLMEnhancer:
    def __init__(self):
        self._provider = self._detect_provider()
        if self._provider:
            log.info(f"LLM enhancer active: {self._provider}")
        else:
            log.info("No LLM API key found — enhancement disabled "
                     "(set GROQ_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY in .env)")

    def _detect_provider(self) -> str | None:
        if sovereign_mode_enabled():
            return None  # all foreign APIs blocked in sovereign mode
        if _groq_key():       return "groq"
        if _gemini_key():     return "gemini"
        if _openrouter_key(): return "openrouter"
        return None

    @property
    def available(self) -> bool:
        return self._detect_provider() is not None

    @retry(max_attempts=3, delay=1.0)
    def _call_groq(self, prompt: str) -> str:
        assert_sovereign_allowed("groq")
        import urllib.request
        payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1, "max_tokens": 1024,
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {_groq_key()}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()

    @retry(max_attempts=3, delay=1.0)
    def _call_gemini(self, prompt: str) -> str:
        assert_sovereign_allowed("gemini")
        import urllib.request
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        }).encode()
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
            data=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": _gemini_key()},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"].strip()

    @retry(max_attempts=3, delay=1.0)
    def _call_openrouter(self, prompt: str) -> str:
        assert_sovereign_allowed("openrouter")
        import urllib.request
        payload = json.dumps({
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {_openrouter_key()}",
                     "Content-Type": "application/json",
                     "HTTP-Referer": "https://kb-translation.local"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()

    def _call(self, prompt: str) -> str:
        provider = self._detect_provider()
        if provider == "groq":       return self._call_groq(prompt)
        if provider == "gemini":     return self._call_gemini(prompt)
        if provider == "openrouter": return self._call_openrouter(prompt)
        raise RuntimeError("No LLM provider available")

    def enhance(self, source: str, translation: str, src_lang: str, tgt_lang: str) -> str:
        """Enhance a single translation. Returns original if LLM unavailable or times out."""
        if not self.available or not translation.strip():
            return translation
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(self._call, _ENHANCE_PROMPT.format(
                    src_lang=src_lang, tgt_lang=tgt_lang,
                    source=source, translation=translation,
                ))
                result = fut.result(timeout=45)  # 45s hard cap — never stall pipeline
            log.debug(f"LLM enhanced [{tgt_lang}]: {translation[:60]} → {result[:60]}")
            return result
        except concurrent.futures.TimeoutError:
            log.warning(f"LLM enhance timed out after 45s [{tgt_lang}] — using raw translation")
            return translation
        except Exception as e:
            log.warning(f"LLM enhance failed: {e} — using raw translation")
            return translation

    def enhance_batch(self, sources: list[str], translations: list[str],
                      src_lang: str, tgt_lang: str) -> list[str]:
        """Enhance a batch of translations in one LLM call."""
        if not self.available or not translations:
            return translations
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(self._call, _BATCH_PROMPT.format(
                    src_lang=src_lang, tgt_lang=tgt_lang,
                    translations_json=json.dumps(translations, ensure_ascii=False),
                ))
                raw = fut.result(timeout=90)  # 90s for batch
            start, end = raw.find("["), raw.rfind("]") + 1
            if start >= 0 and end > start:
                enhanced = json.loads(raw[start:end])
                if isinstance(enhanced, list) and len(enhanced) == len(translations):
                    log.info(f"LLM batch enhanced {len(translations)} segments [{tgt_lang}]")
                    return enhanced
        except concurrent.futures.TimeoutError:
            log.warning(f"LLM batch enhance timed out after 90s [{tgt_lang}] — using raw")
        except Exception as e:
            log.warning(f"LLM batch enhance failed: {e} — using raw translations")
        return translations

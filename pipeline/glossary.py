# ============================================================
# Glossary Manager - Consistent terminology across all courses
# Ensures domain terms (govt, policy, AI etc.) are translated
# consistently throughout a course and across all courses.
# ============================================================

import json
import re
from pathlib import Path
from .lang_config import ALL_22, LANG_NAMES

GLOSSARY_DIR = Path(__file__).parent.parent / "glossary"
GLOSSARY_DIR.mkdir(exist_ok=True)


class GlossaryManager:
    """
    Manages per-language glossaries for consistent term translation.
    Glossary files stored as: glossary/<lang_code>.json
    Format: {"source_term": "translated_term", ...}
    """

    def __init__(self):
        self._glossaries: dict[str, dict] = {}  # lang -> {src: tgt}
        self._load_all()

    # ----------------------------------------------------------
    # Load / Save
    # ----------------------------------------------------------
    def _load_all(self):
        for lang in ALL_22 + ["eng"]:
            path = GLOSSARY_DIR / f"{lang}.json"
            if path.exists():
                self._glossaries[lang] = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._glossaries[lang] = {}

    def save(self, lang: str):
        path = GLOSSARY_DIR / f"{lang}.json"
        path.write_text(
            json.dumps(self._glossaries.get(lang, {}), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_all(self):
        for lang in self._glossaries:
            self.save(lang)

    # ----------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------
    def add_term(self, src_term: str, tgt_term: str, tgt_lang: str):
        """Add or update a glossary entry."""
        self._glossaries.setdefault(tgt_lang, {})[src_term.lower()] = tgt_term
        self.save(tgt_lang)

    def add_terms_bulk(self, terms: dict, tgt_lang: str):
        """Add multiple terms at once. terms = {src: tgt}"""
        g = self._glossaries.setdefault(tgt_lang, {})
        for src, tgt in terms.items():
            g[src.lower()] = tgt
        self.save(tgt_lang)

    def get_term(self, src_term: str, tgt_lang: str) -> str | None:
        return self._glossaries.get(tgt_lang, {}).get(src_term.lower())

    def get_glossary(self, tgt_lang: str) -> dict:
        return dict(self._glossaries.get(tgt_lang, {}))

    # ----------------------------------------------------------
    # Apply glossary to translated text
    # ----------------------------------------------------------
    # Matches any __GLOSS_N__ or _ _ GLOSS _ N _ artifacts (including chained)
    _GLOSS_ARTIFACT = re.compile(r"(?:_\s*)+GLOSS(?:\s*_\s*\d+\s*_\s*)+|__GLOSS_\d+__")
    # Stray script characters that leak at segment start (Gurmukhi, Malayalam, mixed)
    _STRAY_PREFIX   = re.compile(r"^[ੱਂ੍ൾ][ஸ்]*\s*")

    def apply(self, text: str, src_lang: str, tgt_lang: str, translated_text: str) -> str:
        """
        Post-process translated_text to enforce glossary terms.
        Only replaces source terms that literally leaked through unchanged.
        Cleans up any __GLOSS__ placeholder artifacts and stray characters.
        """
        # 1. Strip any GLOSS placeholder artifacts the model emitted literally
        result = self._GLOSS_ARTIFACT.sub("", translated_text).strip()
        # 2. Strip stray Gurmukhi prefix character
        result = self._STRAY_PREFIX.sub("", result).strip()

        glossary = self._glossaries.get(tgt_lang, {})
        if not glossary:
            return result

        # 3. Only replace source terms that literally leaked through (word-boundary match)
        for src_term, tgt_term in glossary.items():
            pattern = re.compile(r"(?<![\w])" + re.escape(src_term) + r"(?![\w])",
                                 re.IGNORECASE)
            result = pattern.sub(tgt_term, result)

        return result

    def protect_terms(self, text: str, tgt_lang: str) -> tuple[str, dict]:
        """
        Replace glossary source terms with placeholders before translation
        so the translation model doesn't alter them.
        Returns (modified_text, placeholder_map)
        """
        glossary = self._glossaries.get(tgt_lang, {})
        placeholder_map = {}
        result = text

        for i, (src_term, tgt_term) in enumerate(glossary.items()):
            placeholder = f"__GLOSS_{i}__"
            pattern = re.compile(re.escape(src_term), re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub(placeholder, result)
                placeholder_map[placeholder] = tgt_term

        return result, placeholder_map

    def restore_terms(self, text: str, placeholder_map: dict) -> str:
        """Restore placeholders with their glossary translations."""
        result = text
        for placeholder, tgt_term in placeholder_map.items():
            result = result.replace(placeholder, tgt_term)
        return result

    # ----------------------------------------------------------
    # Export glossary report
    # ----------------------------------------------------------
    def export_report(self, output_path: str):
        """Export full glossary as a readable report (for KB submission)."""
        lines = ["KB Translation Glossary Report", "=" * 60, ""]
        for lang in sorted(self._glossaries.keys()):
            g = self._glossaries[lang]
            if not g:
                continue
            lang_name = LANG_NAMES.get(lang, lang)
            lines.append(f"\n[{lang_name} ({lang})]")
            for src, tgt in sorted(g.items()):
                lines.append(f"  {src:<30} → {tgt}")
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
        print(f"[Glossary] Report saved → {output_path}")

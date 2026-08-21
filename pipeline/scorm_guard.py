# ============================================================
# SCORM Guard — KB Tender §3.1
# "All media includes only Non-SCORM content."
# Rejects SCORM packages before any pipeline processing.
# ============================================================

import zipfile
from pathlib import Path

# SCORM manifest filename (all versions: 1.1, 1.2, 2004)
_SCORM_MANIFEST = "imsmanifest.xml"

# SCORM namespace markers found inside imsmanifest.xml
_SCORM_NAMESPACES = (
    "adlcp:",
    "imscp:",
    "adlseq:",
    "adlnav:",
    "xmlns:adlcp",
    "xmlns:imscp",
    "schemaversion",
    "ADL SCORM",
)


def is_scorm_package(file_path: str) -> tuple[bool, str]:
    """
    Detect whether a file is a SCORM package.

    Checks (in order):
      1. File extension is .scorm
      2. File is a ZIP containing imsmanifest.xml at root
      3. imsmanifest.xml contains SCORM namespace markers

    Returns (is_scorm: bool, reason: str).
    reason is empty string when not SCORM.
    """
    p = Path(file_path)

    # 1. Explicit .scorm extension
    if p.suffix.lower() == ".scorm":
        return True, "File has .scorm extension (KB §3.1 — Non-SCORM content only)"

    # 2. ZIP-based check — most SCORM packages are ZIP files renamed to .zip or .mp4
    if not zipfile.is_zipfile(file_path):
        return False, ""

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names_lower = {n.lower() for n in zf.namelist()}

            # imsmanifest.xml must be at the ZIP root (not in a subfolder)
            if _SCORM_MANIFEST not in names_lower:
                return False, ""

            # 3. Confirm it's actually SCORM by checking namespace markers
            try:
                manifest_bytes = zf.read(_SCORM_MANIFEST).decode("utf-8", errors="replace")
                if any(marker in manifest_bytes for marker in _SCORM_NAMESPACES):
                    return (
                        True,
                        f"ZIP contains {_SCORM_MANIFEST} with SCORM namespace markers "
                        f"(KB §3.1 — Non-SCORM content only)",
                    )
                # imsmanifest.xml present but no SCORM markers — treat as SCORM anyway
                # (some stripped packages omit namespaces but are still SCORM)
                return (
                    True,
                    f"ZIP contains {_SCORM_MANIFEST} "
                    f"(KB §3.1 — Non-SCORM content only)",
                )
            except Exception:
                # Can't read manifest — flag conservatively
                return (
                    True,
                    f"ZIP contains {_SCORM_MANIFEST} (unreadable — flagged as SCORM per KB §3.1)",
                )
    except (zipfile.BadZipFile, OSError):
        return False, ""


def assert_non_scorm(file_path: str) -> None:
    """
    Raise ValueError if the file is a SCORM package.
    Call this at the start of any pipeline entry point.
    """
    detected, reason = is_scorm_package(file_path)
    if detected:
        raise ValueError(
            f"SCORM content rejected — {reason}. "
            f"The KB tender (§3.1) requires Non-SCORM content only. "
            f"Please provide the raw MP4/MP3/WAV source file."
        )

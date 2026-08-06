# ============================================================
# CBP Portal Uploader — KB Tender Section 4.2
# Uploads translated course assets to the iGOT Karmayogi
# Competency Building Product (CBP) portal.
# Portal: https://cbp.igotkarmayogi.gov.in
# ============================================================

import json
import time
from pathlib import Path
from .logger import get_logger

log = get_logger("cbp_uploader")


class CBPUploader:
    """
    Handles upload of translated course assets to the CBP portal.

    Credentials are provided by KB after contract signing.
    Set via environment variables or pass directly:
        CBP_USERNAME, CBP_PASSWORD, CBP_BASE_URL
    """

    BASE_URL = "https://cbp.igotkarmayogi.gov.in"

    def __init__(self, username: str = None, password: str = None, base_url: str = None):
        import os
        self.username = username or os.environ.get("CBP_USERNAME", "")
        self.password = password or os.environ.get("CBP_PASSWORD", "")
        self.base_url = (base_url or os.environ.get("CBP_BASE_URL", self.BASE_URL)).rstrip("/")
        self._session = None
        self._token = None

    def _get_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({"Content-Type": "application/json"})
        return self._session

    def login(self) -> bool:
        """Authenticate and store session token."""
        if not self.username or not self.password:
            log.warning("[CBP] No credentials set. Set CBP_USERNAME and CBP_PASSWORD.")
            return False
        try:
            session = self._get_session()
            resp = session.post(
                f"{self.base_url}/api/user/v1/login",
                json={"username": self.username, "password": self.password},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("result", {}).get("access_token") or data.get("access_token")
            if self._token:
                session.headers.update({"Authorization": f"Bearer {self._token}"})
                log.info("[CBP] Login successful")
                return True
            log.error("[CBP] Login failed: no token in response")
            return False
        except Exception as e:
            log.error(f"[CBP] Login error: {e}")
            return False

    def upload_video(self, video_path: str, course_id: str, lang: str) -> dict:
        return self._upload_asset(video_path, course_id, lang, asset_type="video")

    def upload_audio(self, audio_path: str, course_id: str, lang: str) -> dict:
        return self._upload_asset(audio_path, course_id, lang, asset_type="audio")

    def upload_metadata(self, metadata_path: str, course_id: str, lang: str) -> dict:
        return self._upload_asset(metadata_path, course_id, lang, asset_type="metadata")

    def upload_quiz(self, quiz_path: str, course_id: str, lang: str) -> dict:
        return self._upload_asset(quiz_path, course_id, lang, asset_type="assessment")

    def _upload_asset(self, file_path: str, course_id: str, lang: str, asset_type: str) -> dict:
        import requests
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        session = self._get_session()
        url = f"{self.base_url}/api/content/v1/upload"

        for attempt in range(1, 4):
            try:
                with open(file_path, "rb") as f:
                    resp = session.post(
                        url,
                        files={"file": (path.name, f)},
                        data={"courseId": course_id, "language": lang, "assetType": asset_type},
                        timeout=120,
                    )
                resp.raise_for_status()
                result = resp.json()
                log.info(f"[CBP] Uploaded {path.name} ({lang}/{asset_type})")
                return {"success": True, "response": result, "file": str(path)}
            except Exception as e:
                log.warning(f"[CBP] Upload attempt {attempt}/3 failed for {path.name}: {e}")
                if attempt < 3:
                    time.sleep(5 * attempt)

        return {"success": False, "error": f"Upload failed after 3 attempts: {file_path}"}

    def upload_course_package(self, package_dir: str, course_id: str, lang: str) -> dict:
        """
        Upload all assets for a translated course from a directory.
        Expects files matching: *_{lang}.mp4, *_{lang}.mp3,
        *_metadata_{lang}.xlsx, *_quiz_{lang}.docx
        """
        pkg = Path(package_dir)
        results = {"course_id": course_id, "lang": lang, "uploads": [], "errors": []}

        patterns = [
            (f"*_{lang}.mp4",   "video"),
            (f"*_{lang}.mp3",   "audio"),
            (f"*_{lang}*.xlsx", "metadata"),
            (f"*_{lang}*.docx", "assessment"),
            (f"*_{lang}.srt",   "subtitle"),
            (f"*_{lang}.vtt",   "subtitle"),
        ]

        for pattern, asset_type in patterns:
            for f in pkg.glob(pattern):
                r = self._upload_asset(str(f), course_id, lang, asset_type)
                if r["success"]:
                    results["uploads"].append(str(f))
                else:
                    results["errors"].append(r["error"])

        results["success"] = len(results["errors"]) == 0
        return results

    def generate_submission_report(self, upload_results: list[dict], output_path: str) -> str:
        """Generate a JSON submission report for KB records."""
        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "portal": self.base_url,
            "total_uploads": sum(len(r.get("uploads", [])) for r in upload_results),
            "total_errors": sum(len(r.get("errors", [])) for r in upload_results),
            "courses": upload_results,
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info(f"[CBP] Submission report saved → {output_path}")
        return output_path

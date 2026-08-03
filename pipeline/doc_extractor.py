"""Extract plain text from PDF / DOCX / TXT files."""

from pathlib import Path


def extract_text(file_path: str) -> str:
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix == ".txt":
        return p.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(p)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            raise ImportError("Install pdfplumber: pip install pdfplumber")

    if suffix in (".docx", ".doc"):
        try:
            from docx import Document
            doc = Document(str(p))
            return "\n".join(para.text for para in doc.paragraphs)
        except ImportError:
            raise ImportError("Install python-docx: pip install python-docx")

    raise ValueError(f"Unsupported file type: {suffix}")

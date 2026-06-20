from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from rag_engine.config import POLICY_DOCUMENTS_DIR


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def infer_category(file_name: str) -> str:
    lower_name = file_name.lower()

    if "leave" in lower_name:
        return "Leave"
    if "posh" in lower_name:
        return "POSH"
    if "conduct" in lower_name or "ethics" in lower_name:
        return "Conduct"
    if "remuneration" in lower_name or "salary" in lower_name:
        return "Compensation"
    if "policy" in lower_name:
        return "Policy"

    return "General"


def load_txt(file_path: Path) -> list[dict]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")

    return [
        {
            "text": text,
            "source": file_path.name,
            "page": 1,
            "category": infer_category(file_path.name),
        }
    ]


def load_pdf(file_path: Path) -> list[dict]:
    documents = []
    reader = PdfReader(str(file_path))

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()

        if not text:
            continue

        documents.append(
            {
                "text": text,
                "source": file_path.name,
                "page": page_number,
                "category": infer_category(file_path.name),
            }
        )

    return documents


def load_docx(file_path: Path) -> list[dict]:
    doc = DocxDocument(str(file_path))
    paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs]
    text = "\n".join(paragraph for paragraph in paragraphs if paragraph)

    return [
        {
            "text": text,
            "source": file_path.name,
            "page": 1,
            "category": infer_category(file_path.name),
        }
    ]


def load_document(file_path: Path) -> list[dict]:
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(file_path)

    if suffix == ".docx":
        return load_docx(file_path)

    if suffix == ".txt":
        return load_txt(file_path)

    return []


def load_policy_documents(policy_dir: Path = POLICY_DOCUMENTS_DIR) -> list[dict]:
    if not policy_dir.exists():
        raise FileNotFoundError(f"Policy documents folder not found: {policy_dir}")

    documents = []

    for file_path in sorted(policy_dir.iterdir()):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        documents.extend(load_document(file_path))

    return documents
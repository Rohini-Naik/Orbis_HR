from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from rag_engine.config import POLICY_DOCUMENTS_DIR


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# The bundled corpus is a set of publicly published policies from several real
# organisations, used as sample HR content. Attributing each document to its
# issuer keeps citations honest — a reader can see the answer came from, say,
# Bandhan's manual rather than from the demo employer's own handbook.
_COMPANY_KEYWORDS = (
    ("orbis", "Orbis"),
    ("bandhan", "Bandhan Financial Services"),
    ("ppl_", "Piramal Pharma"),
    ("pel ", "Piramal Enterprises"),
    ("pel-", "Piramal Enterprises"),
    ("pchfl", "Piramal Capital & Housing Finance"),
    ("smp", "Piramal Capital & Housing Finance"),
    ("posh", "Piramal Capital & Housing Finance"),
    ("remuneration-policy-new", "Piramal Housing Finance"),
)

UNKNOWN_COMPANY = "Unattributed"


def infer_company(file_name: str) -> str:
    """Best-effort issuer for a policy file, shown alongside citations.
    Uploaded files that match nothing are simply left unattributed."""
    name = file_name.lower()
    for keyword, company in _COMPANY_KEYWORDS:
        if keyword in name:
            return company
    return UNKNOWN_COMPANY


def infer_category(file_name: str) -> str:
    """Classify a policy file into the categories the UI filters by:
    Leave, Conduct, Benefits, Privacy, Work, General."""
    name = file_name.lower()

    if any(k in name for k in ("leave", "maternity", "paternity")):
        return "Leave"
    if any(k in name for k in ("posh", "harassment", "conduct", "ethics", "disciplin", "whistle")):
        return "Conduct"
    if any(k in name for k in ("benefit", "health", "wellness", "remuneration",
                               "salary", "travel", "expense", "reimburse")):
        return "Benefits"
    if any(k in name for k in ("privacy", "confidential", "data", "diba")):
        return "Privacy"
    if any(k in name for k in ("work", "hybrid", "remote", "wfh", "lifecycle",
                               "probation", "notice", "exit", "resignation",
                               "onboarding", "attendance")):
        return "Work"
    return "General"


def load_txt(file_path: Path) -> list[dict]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")

    return [
        {
            "text": text,
            "source": file_path.name,
            "page": 1,
            "category": infer_category(file_path.name),
            "company": infer_company(file_path.name),
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
                "company": infer_company(file_path.name),
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
            "company": infer_company(file_path.name),
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
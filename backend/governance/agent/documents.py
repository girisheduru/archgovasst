from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 160_000


def parse_document(filename: str, payload: bytes) -> dict[str, str]:
    extension = Path(filename).suffix.lower()
    stream = BytesIO(payload)
    if extension == ".pdf":
        reader = PdfReader(stream)
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("Use an unencrypted PDF of at most 100 pages.")
        sections = {
            f"Page {number}": page.extract_text() or ""
            for number, page in enumerate(reader.pages, 1)
        }
    elif extension == ".docx":
        with ZipFile(stream) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError("The expanded Word document exceeds 40 MB.")
        sections = {}
        for number, block in enumerate(Document(stream).iter_inner_content(), 1):
            if isinstance(block, Table):
                text = "\n".join(" | ".join(cell.text for cell in row.cells) for row in block.rows)
                sections[f"Table {number}"] = text
            else:
                sections[f"Paragraph {number}"] = block.text
    else:
        raise ValueError("Upload a PDF or Word (.docx) document.")

    sections = {label: " ".join(text.split()) for label, text in sections.items() if text.strip()}
    if not sections:
        raise ValueError("The document has no extractable text. Use a text-based PDF or Word document.")
    if sum(len(label) + len(text) for label, text in sections.items()) > MAX_TEXT_CHARS:
        raise ValueError("The document exceeds the 160,000-character review limit.")
    return sections

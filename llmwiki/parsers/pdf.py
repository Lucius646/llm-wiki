from pathlib import Path
from typing import Tuple, Dict, Any
from PyPDF2 import PdfReader

def parse_pdf(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text content from PDF file

    Args:
        file_path: Path to the PDF file

    Returns:
        Tuple of (content, metadata)
    """
    reader = PdfReader(file_path)
    content = ""

    for page in reader.pages:
        content += page.extract_text() + "\n\n"

    metadata = {
        "title": reader.metadata.get("/Title", file_path.stem) if reader.metadata else file_path.stem,
        "author": reader.metadata.get("/Author", "Unknown") if reader.metadata else "Unknown",
        "published_date": reader.metadata.get("/CreationDate", "Unknown") if reader.metadata else "Unknown",
        "source": str(file_path),
        "file_type": "pdf",
        "page_count": len(reader.pages)
    }

    # Clean up creation date format
    if metadata["published_date"].startswith("D:"):
        date_str = metadata["published_date"][2:10]
        try:
            metadata["published_date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except:
            pass

    return content, metadata

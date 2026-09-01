import os
import hashlib
import logging
import fitz  # PyMuPDF
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class IngestionService:
    @staticmethod
    def extract_text_from_pdf_bytes(file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract text from PDF bytes (avoids touching encrypted files on disk)."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages_content = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                lines = text.split("\n")
                section_title = None
                for line in lines:
                    line_strip = line.strip()
                    if line_strip.isupper() and 3 < len(line_strip) < 60:
                        section_title = line_strip
                        break
                pages_content.append({
                    "page_no": page_num + 1,
                    "text": text,
                    "section_title": section_title or f"Page {page_num + 1}",
                })
            doc.close()
            return pages_content
        except Exception as e:
            logger.warning("Error reading PDF stream: %s. Attempting text fallback.", e)
            return IngestionService.extract_text_from_txt_bytes(file_bytes)

    @staticmethod
    def extract_text_from_txt_bytes(file_bytes: bytes) -> List[Dict[str, Any]]:
        """Read plain-text bytes, splitting into page-like chunks of ~1500 chars."""
        content = file_bytes.decode("utf-8", errors="ignore")
        pages_content = []
        chunk_size = 1500
        chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
        for idx, chunk in enumerate(chunks):
            pages_content.append({
                "page_no": idx + 1,
                "text": chunk,
                "section_title": f"Section {idx + 1}",
            })
        return pages_content

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts text from a PDF page-by-page, returning a list of dictionaries
        with page numbers, text content, and section information.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        pages_content = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                # Simple heuristic to extract headers as potential section titles
                lines = text.split("\n")
                section_title = None
                for line in lines:
                    line_strip = line.strip()
                    # If line is bold or uppercase and reasonably short, treat as header
                    if line_strip.isupper() and 3 < len(line_strip) < 60:
                        section_title = line_strip
                        break

                pages_content.append({
                    "page_no": page_num + 1,
                    "text": text,
                    "section_title": section_title or f"Page {page_num + 1}",
                })
            doc.close()
        except Exception as e:
            logger.warning("Error reading PDF %s: %s. Attempting plain-text extraction fallback.", file_path, e)
            # Try to read it as text if PyMuPDF fails or if it's not a standard PDF
            return IngestionService.extract_text_from_txt(file_path)

        return pages_content

    @staticmethod
    def extract_text_from_txt(file_path: str) -> List[Dict[str, Any]]:
        """
        Reads a plain text file, splitting it into page-like chunks of roughly 1500 characters.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        pages_content = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Split into chunks of 1500 chars (approx a page)
            chunk_size = 1500
            chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]

            for idx, chunk in enumerate(chunks):
                pages_content.append({
                    "page_no": idx + 1,
                    "text": chunk,
                    "section_title": f"Section {idx + 1}",
                })
        except Exception as e:
            logger.error("Error reading txt file %s: %s", file_path, e)
            raise e

        return pages_content

    @classmethod
    def process_document(cls, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """
        Unified method to process a file depending on its type.
        """
        file_type = file_type.lower()
        if file_type == "pdf":
            return cls.extract_text_from_pdf(file_path)
        else:
            return cls.extract_text_from_txt(file_path)

    @classmethod
    def process_document_bytes(cls, file_bytes: bytes, file_type: str) -> List[Dict[str, Any]]:
        """
        Process a document from plaintext bytes (storage layer decrypts for us).
        Encryption-at-rest is transparent: parsing never touches ciphertext on disk.
        """
        file_type = file_type.lower()
        if file_type == "pdf":
            return cls.extract_text_from_pdf_bytes(file_bytes)
        else:
            return cls.extract_text_from_txt_bytes(file_bytes)

    @staticmethod
    def chunk_document_data(pages_content: List[Dict[str, Any]], chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, Any]]:
        """
        Splits pages into smaller contextual chunks for RAG embedding/matching.
        """
        chunks = []
        for page in pages_content:
            text = page["text"]
            page_no = page["page_no"]
            section = page["section_title"]

            # Tokenize roughly by words
            words = text.split()
            if not words:
                continue

            current_pos = 0
            while current_pos < len(words):
                chunk_words = words[current_pos:current_pos + chunk_size]
                chunk_text = " ".join(chunk_words)

                chunks.append({
                    "page_no": page_no,
                    "section_title": section,
                    "chunk_text": chunk_text,
                    "metadata": {
                        "page_no": page_no,
                        "section_title": section,
                        "word_count": len(chunk_words),
                    },
                })
                current_pos += (chunk_size - overlap)

        return chunks

    @staticmethod
    def verify_document_integrity(document_id: str, db) -> dict:
        """
        Verifies that the stored document file matches its initial SHA-256 hash.
        Reads through the storage backend so encryption-at-rest is transparent;
        AES-GCM decryption failure on a tampered file is also reported as TAMPERED.
        """
        from app.models import Document
        from app.services.storage import get_storage_backend

        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        file_path = doc.storage_url
        if not file_path or not os.path.exists(file_path):
            return {
                "document_id": document_id,
                "stored_hash": doc.file_hash,
                "current_hash": "",
                "integrity_status": "MISSING_FILE",
                "hashed_at": doc.hashed_at,
            }

        try:
            storage = get_storage_backend()
            if file_path.startswith("s3://"):
                current_bytes = storage.load(file_path.replace("s3://", ""))
            else:
                current_bytes = storage.load(file_path)
            current_hash = hashlib.sha256(current_bytes).hexdigest()
            is_intact = current_hash == doc.file_hash
            return {
                "document_id": document_id,
                "stored_hash": doc.file_hash,
                "current_hash": current_hash,
                "integrity_status": "INTACT" if is_intact else "TAMPERED",
                "hashed_at": doc.hashed_at,
            }
        except Exception as e:
            logger.error("Error checking integrity for document %s: %s", document_id, e)
            return {
                "document_id": document_id,
                "stored_hash": doc.file_hash,
                "current_hash": "",
                "integrity_status": "TAMPERED",
                "hashed_at": doc.hashed_at,
            }

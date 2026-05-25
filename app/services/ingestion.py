import os
import fitz  # PyMuPDF
from typing import List, Dict, Any

class IngestionService:
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
                    "section_title": section_title or f"Page {page_num + 1}"
                })
            doc.close()
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
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
            chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
            
            for idx, chunk in enumerate(chunks):
                pages_content.append({
                    "page_no": idx + 1,
                    "text": chunk,
                    "section_title": f"Section {idx + 1}"
                })
        except Exception as e:
            print(f"Error reading txt file {file_path}: {e}")
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
        elif file_type in ["txt", "csv", "md"]:
            return cls.extract_text_from_txt(file_path)
        else:
            # Fallback to txt parsing
            return cls.extract_text_from_txt(file_path)

    @classmethod
    def chunk_document_data(cls, pages_content: List[Dict[str, Any]], max_chunk_size: int = 500) -> List[Dict[str, Any]]:
        """
        Takes raw page contents and splits them into smaller, logically sound chunks of words
        to allow highly specific citations and context matching.
        """
        chunks = []
        for page in pages_content:
            page_no = page["page_no"]
            text = page["text"]
            section_title = page["section_title"]
            
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            
            current_chunk = []
            current_word_count = 0
            chunk_idx = 1
            
            for para in paragraphs:
                words = para.split()
                if current_word_count + len(words) > max_chunk_size and current_chunk:
                    # Output current chunk
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append({
                        "page_no": page_no,
                        "section_title": f"{section_title} - Part {chunk_idx}",
                        "chunk_text": chunk_text,
                        "metadata": {"paragraph_count": len(current_chunk)}
                    })
                    current_chunk = [para]
                    current_word_count = len(words)
                    chunk_idx += 1
                else:
                    current_chunk.append(para)
                    current_word_count += len(words)
                    
            if current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append({
                    "page_no": page_no,
                    "section_title": f"{section_title} - Part {chunk_idx}" if chunk_idx > 1 else section_title,
                    "chunk_text": chunk_text,
                    "metadata": {"paragraph_count": len(current_chunk)}
                })
                
        return chunks

import io

import pdfplumber
import pymupdf
import pymupdf.layout
import pymupdf4llm
import requests


def download_pdf(url):
    """Download PDF from URL and return as bytes"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading PDF from {url}: {e}")
        return None


def extract_text_from_pdf_bytes(pdf_bytes):
    """Extract text content from PDF bytes using in-memory approach"""
    if not pdf_bytes:
        return None

    try:
        # Use io.BytesIO to create an in-memory file object
        with io.BytesIO(pdf_bytes) as pdf_file:
            # Try using pymupdf4llm first for better text extraction
            try:
                doc = pymupdf.Document(stream=pdf_bytes, filetype="pdf")
                md_text = pymupdf4llm.to_markdown(doc)
                if md_text:
                    return md_text
            except Exception as e:
                print(f"pymupdf4llm extraction failed, falling back to pdfplumber: {e}")
            # If pymupdf4llm returns empty text, fall back to pdfplumber
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n\n"

        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

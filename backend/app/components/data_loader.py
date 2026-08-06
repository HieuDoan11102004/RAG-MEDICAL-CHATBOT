from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from .pdf_loader import create_text_chunks, load_pdf_files
from .vector_store import save_vector_store
from ..common.custom_exception import CustomException
from ..common.logger import get_logger

logger = get_logger(__name__)


def process_and_store_pdfs():
    try:
        logger.info("Making the vector store.....")

        documents = load_pdf_files()

        text_chunks = create_text_chunks(documents)
        logger.info(
            "Created %s text chunks. Starting embedding and FAISS indexing.",
            len(text_chunks),
        )

        save_vector_store(text_chunks)

        logger.info("Vector store created and saved successfully.")
    except Exception as e:
        error_message = CustomException(f"Error processing and storing PDFs: {str(e)}")
        logger.error(str(error_message))


if __name__ == "__main__":
    process_and_store_pdfs()

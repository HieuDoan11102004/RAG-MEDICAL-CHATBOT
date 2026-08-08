from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.common.custom_exception import CustomException
    from app.common.logger import get_logger
    from app.agents.rag_agent.components.pdf_loader import create_text_chunks, load_pdf_files
    from app.agents.rag_agent.components.vector_store import save_vector_store
else:
    from .pdf_loader import create_text_chunks, load_pdf_files
    from .vector_store import save_vector_store
    from ....common.custom_exception import CustomException
    from ....common.logger import get_logger

logger = get_logger(__name__)


def process_and_store_pdfs():
    try:
        logger.info("Making the vector store.....")

        documents = load_pdf_files()

        text_chunks = create_text_chunks(documents)
        logger.info(
            "Created %s text chunks. Starting embedding and Qdrant indexing.",
            len(text_chunks),
        )

        save_vector_store(text_chunks)

        logger.info("Qdrant collection created successfully.")
    except Exception as e:
        error_message = CustomException(f"Error processing and storing PDFs: {str(e)}")
        logger.error(str(error_message))


if __name__ == "__main__":
    process_and_store_pdfs()

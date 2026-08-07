import os
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..common.logger import get_logger
from ..common.custom_exception import CustomException

from ..config.config import DATA_PATH, CHUNK_SIZE, CHUNK_OVERLAP
from .gale_chunker import load_gale_pdf

logger = get_logger(__name__)


def load_pdf_files():
    try:
        if not os.path.exists(DATA_PATH):
            raise CustomException(f"Data path '{DATA_PATH}' does not exist.")
        logger.info(f"Loading PDF files from directory: {DATA_PATH}")

        documents = []
        for pdf_path in sorted(Path(DATA_PATH).glob("*.pdf")):
            normalized_name = pdf_path.name.upper().replace("_", " ").replace("-", " ")
            if "GALE" in normalized_name and "ENCYCLOPEDIA" in normalized_name:
                gale_documents = load_gale_pdf(pdf_path, max_chars=CHUNK_SIZE)
                documents.extend(gale_documents)
                logger.info("Loaded %s Gale semantic chunks from %s", len(gale_documents), pdf_path.name)
            else:
                documents.extend(PyPDFLoader(str(pdf_path)).load())

        if not documents:
            logger.warning(f"No PDF files found in directory: {DATA_PATH}")
        else:
            logger.info(
                f"Loaded {len(documents)} documents from directory: {DATA_PATH}"
            )
        return documents
    except Exception as e:
        error_message = CustomException(f"Error loading PDF files: {str(e)}")
        logger.error(str(error_message))
        return []


def create_text_chunks(documents):
    try:
        if not documents:
            raise CustomException("No documents to create text chunks from.")

        logger.info(f"Creating text chunks from {len(documents)} documents.")

        pre_chunked = [
            document for document in documents
            if document.metadata.get("chunk_strategy") == "gale_semantic"
        ]
        raw_documents = [document for document in documents if document not in pre_chunked]
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )

        text_chunks = pre_chunked + text_splitter.split_documents(raw_documents)

        return text_chunks
    except Exception as e:
        error_message = CustomException(f"Error creating text chunks: {str(e)}")
        logger.error(str(error_message))
        return []

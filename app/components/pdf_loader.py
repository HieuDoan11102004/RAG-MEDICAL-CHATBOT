import os
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.common.logger import get_logger
from app.common.custom_exception import CustomException

from app.config.config import DATA_PATH, CHUNK_SIZE, CHUNK_OVERLAP

logger = get_logger(__name__)


def load_pdf_files():
    try:
        if not os.path.exists(DATA_PATH):
            raise CustomException(f"Data path '{DATA_PATH}' does not exist.")
        logger.info(f"Loading PDF files from directory: {DATA_PATH}")

        loader = DirectoryLoader(DATA_PATH, glob="*.pdf", loader_cls=PyPDFLoader)

        documents = loader.load()

        if not documents:
            logger.warning(f"No PDF files found in directory: {DATA_PATH}")
        else:
            logger.info(
                f"Loaded {len(documents)} PDF files from directory: {DATA_PATH}"
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

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )

        text_chunks = text_splitter.split_documents(documents)

        return text_chunks
    except Exception as e:
        error_message = CustomException(f"Error creating text chunks: {str(e)}")
        logger.error(str(error_message))
        return []

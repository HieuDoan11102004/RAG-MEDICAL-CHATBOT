import time
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from .embeddings import get_embedding_model

from ....common.logger import get_logger
from ....common.custom_exception import CustomException

from ....config.config import (
    OPENAI_EMBEDDING_MODEL,
    QDRANT_COLLECTION,
    QDRANT_URL,
    get_qdrant_api_key,
)

logger = get_logger(__name__)


def _client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=get_qdrant_api_key())


def load_vector_store() -> QdrantVectorStore | None:
    try:
        embedding_model = get_embedding_model()
        client = _client()
        if not client.collection_exists(QDRANT_COLLECTION):
            logger.warning("Qdrant collection not found: %s", QDRANT_COLLECTION)
            return None
        collection = client.get_collection(QDRANT_COLLECTION)
        vector_config = collection.config.params.vectors
        if not isinstance(vector_config, models.VectorParams):
            raise CustomException("Qdrant collection must use a single dense vector configuration.")
        embedding_dimension = len(embedding_model.embed_query("medical question"))
        if vector_config.size != embedding_dimension:
            raise CustomException(
                "Qdrant collection dimension does not match the configured embedding model. "
                f"Collection dimension: {vector_config.size}, embedding dimension: {embedding_dimension}, "
                f"model: {OPENAI_EMBEDDING_MODEL}. Rebuild the collection with the current embedding model."
            )
        logger.info("Qdrant collection loaded successfully: %s", QDRANT_COLLECTION)
        return QdrantVectorStore.from_existing_collection(
            embedding=embedding_model,
            collection_name=QDRANT_COLLECTION,
            url=QDRANT_URL,
            api_key=get_qdrant_api_key(),
        )
    except Exception as e:
        error_message = CustomException(f"Error loading vector store: {str(e)}")
        logger.error(str(error_message))
        raise error_message


def save_vector_store(text_chunks) -> QdrantVectorStore:
    try:
        if not text_chunks:
            raise CustomException("No text chunks provided to save to vector store.")

        logger.info(
            "Creating Qdrant collection from %s text chunks.", len(text_chunks)
        )

        embedding_model = get_embedding_model()

        start_time = time.perf_counter()
        logger.info(
            "Creating the Qdrant collection and uploading embedded text chunks."
        )
        client = _client()
        embedding_dimension = len(embedding_model.embed_query("medical question"))
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=embedding_dimension, distance=models.Distance.COSINE
            ),
        )
        db = QdrantVectorStore.from_documents(
            text_chunks,
            embedding=embedding_model,
            url=QDRANT_URL,
            api_key=get_qdrant_api_key(),
            collection_name=QDRANT_COLLECTION,
        )
        logger.info(
            "Qdrant collection %s populated in %.2f seconds.",
            QDRANT_COLLECTION,
            time.perf_counter() - start_time,
        )

        return db

    except Exception as e:
        error_message = CustomException(f"Error saving vector store: {str(e)}")
        logger.error(str(error_message))
        raise error_message

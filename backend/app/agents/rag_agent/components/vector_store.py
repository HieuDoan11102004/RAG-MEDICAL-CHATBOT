from langchain_community.vectorstores import FAISS
import os
import time
from .embeddings import get_embedding_model

from ....common.logger import get_logger
from ....common.custom_exception import CustomException

from ....config.config import DB_FAISS_PATH, OPENAI_EMBEDDING_MODEL

logger = get_logger(__name__)


def load_vector_store():
    try:
        embedding_model = get_embedding_model()
        if os.path.exists(DB_FAISS_PATH):
            logger.info(f"Loading existing FAISS vector store from: {DB_FAISS_PATH}")
            vector_store = FAISS.load_local(
                DB_FAISS_PATH, embedding_model, allow_dangerous_deserialization=True
            )
            sample_vector = embedding_model.embed_query("medical question")
            index_dimension = vector_store.index.d
            embedding_dimension = len(sample_vector)
            if embedding_dimension != index_dimension:
                raise CustomException(
                    "Saved FAISS index dimension does not match the configured embedding model. "
                    f"Index dimension: {index_dimension}, embedding dimension: {embedding_dimension}, "
                    f"model: {OPENAI_EMBEDDING_MODEL}. Rebuild the vector store with the current embedding model "
                    "by running `uv run python -m app.agents.rag_agent.components.data_loader`."
                )
            logger.info("FAISS vector store loaded successfully.")
            return vector_store
        else:
            logger.warning("FAISS vector store not found.")
            return None
    except Exception as e:
        error_message = CustomException(f"Error loading vector store: {str(e)}")
        logger.error(str(error_message))
        raise error_message


def save_vector_store(text_chunks):
    try:
        if not text_chunks:
            raise CustomException("No text chunks provided to save to vector store.")

        logger.info(
            "Creating new FAISS vector store from %s text chunks.", len(text_chunks)
        )

        embedding_model = get_embedding_model()

        start_time = time.perf_counter()
        logger.info(
            "Embedding text chunks and building FAISS index. This can take a while on CPU."
        )
        db = FAISS.from_documents(text_chunks, embedding_model)
        logger.info(
            "Finished building FAISS index in %.2f seconds.",
            time.perf_counter() - start_time,
        )

        logger.info(f"Saving FAISS vector store to: {DB_FAISS_PATH}")
        os.makedirs(os.path.dirname(DB_FAISS_PATH), exist_ok=True)

        save_start_time = time.perf_counter()
        db.save_local(DB_FAISS_PATH)
        logger.info(
            "Saved FAISS vector store in %.2f seconds.",
            time.perf_counter() - save_start_time,
        )

        return db

    except Exception as e:
        error_message = CustomException(f"Error saving vector store: {str(e)}")
        logger.error(str(error_message))
        raise error_message

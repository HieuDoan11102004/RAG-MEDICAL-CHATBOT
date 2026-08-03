import os

from langchain_openai import OpenAIEmbeddings

from app.common.logger import get_logger
from app.common.custom_exception import CustomException
from app.config.config import OPENAI_EMBEDDING_MODEL

logger = get_logger(__name__)


def get_embedding_model():
    try:
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise CustomException(
                "OPENAI_API_KEY is not set. Add it to your environment or .env file before building or loading the vector store."
            )

        logger.info(
            "Initializing OpenAI embeddings model: %s",
            OPENAI_EMBEDDING_MODEL,
        )

        model = OpenAIEmbeddings(
            model=OPENAI_EMBEDDING_MODEL,
            api_key=openai_api_key,
        )

        logger.info(
            "OpenAI embeddings model initialized successfully: %s",
            OPENAI_EMBEDDING_MODEL,
        )

        return model
    except Exception as e:
        error_message = CustomException(f"Error initializing embedding model: {str(e)}")
        logger.error(str(error_message))
        raise error_message

from langchain_openai import ChatOpenAI

from ....config.config import OPENAI_MODEL, get_openai_api_key

from ....common.logger import get_logger
from ....common.custom_exception import CustomException

logger = get_logger(__name__)


def load_llm(
    model_name: str = OPENAI_MODEL,
    api_key: str | None = None,
    *,
    temperature: float = 0.3,
    max_tokens: int = 256,
):
    try:
        openai_api_key = api_key or get_openai_api_key()

        if not openai_api_key:
            raise CustomException(
                "OPENAI_API_KEY is not set. Add it to your environment or .env file before starting the app."
            )

        logger.info("Loading OpenAI chat model: %s", model_name)

        llm = ChatOpenAI(
            model=model_name,
            api_key=openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        logger.info("OpenAI chat model loaded successfully.")
        return llm
    except Exception as e:
        error_message = CustomException(f"Error loading LLM: {str(e)}")
        logger.error(str(error_message))
        raise error_message

from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate


from .llm import load_llm
from .vector_store import load_vector_store

from ..common.logger import get_logger
from ..common.custom_exception import CustomException
import os

logger = get_logger(__name__)

CUSTOM_PROMPT_TEMPLATE = """
Answer the following medical question in 2-3 lines maximum using only the information provided in the context.

Context:
{context}

Question:
{question}

Answer:
"""


def set_custom_prompt():
    return PromptTemplate(
        template=CUSTOM_PROMPT_TEMPLATE, input_variables=["context", "question"]
    )


def create_qa_chain():
    try:
        logger.info("Loading vector store for context...")
        db = load_vector_store()

        if db is None:
            raise CustomException(
                "Vector store not found. Please run the data processing script first."
            )

        llm = load_llm()

        if llm is None:
            raise CustomException(
                "LLM could not be loaded. Please check your OpenAI API key and model configuration."
            )

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=db.as_retriever(search_kwargs={"k": 1}),
            return_source_documents=False,
            chain_type_kwargs={"prompt": set_custom_prompt()},
        )

        logger.info("QA chain created successfully.")
        return qa_chain
    except Exception as e:
        error_message = CustomException(f"Error creating QA chain: {str(e)}")
        logger.error(str(error_message))
        raise error_message

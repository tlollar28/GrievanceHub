import os

from dotenv import load_dotenv
from openai import OpenAI

from app.retrieval_config import (
    RETRIEVAL_EMBEDDING_MAX_RETRIES,
    RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS,
)

load_dotenv()


class EmbeddingService:
    @staticmethod
    def create_embedding(
        text: str,
        *,
        timeout_seconds: float = RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS,
    ) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Embedding input must not be empty.")
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=timeout_seconds,
            max_retries=RETRIEVAL_EMBEDDING_MAX_RETRIES,
        )

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )

        return response.data[0].embedding
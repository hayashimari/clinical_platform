import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = (
    "You are a helpful clinical evidence assistant. "
    "Answer using only the provided context. "
    "If the context contains partial evidence, summarize what can be said from it instead of refusing."
)


def _get_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found")
    return api_key


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=_get_api_key())


def create_embedding(query: str) -> list[float]:
    response = get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    return response.data[0].embedding


def create_chat_completion(query: str, context: str) -> str:
    response = get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""
Question:
{query}

Context:
{context}
""",
            },
        ],
    )

    return response.choices[0].message.content or ""

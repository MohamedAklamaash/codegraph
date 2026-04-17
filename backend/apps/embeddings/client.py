from concurrent.futures import ThreadPoolExecutor, as_completed

import google.generativeai as genai
from django.conf import settings

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 3072
MAX_WORKERS = 20  # parallel requests; stay within Gemini rate limits


def _embed_one(text: str) -> list[float]:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    return genai.embed_content(model=EMBEDDING_MODEL, content=text)["embedding"]


def embed_texts(texts: list[str]) -> list[list[float]]:
    results: list[list[float] | None] = [None] * len(texts)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_embed_one, text): i for i, text in enumerate(texts)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results  # type: ignore[return-value]

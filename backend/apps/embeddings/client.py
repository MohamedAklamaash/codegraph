import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import google.generativeai as genai
from django.conf import settings
from google.api_core import exceptions as gax

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 3072
BATCH_SIZE = 50
MAX_PARALLEL_BATCHES = 4
MAX_TEXT_CHARS = 8000
MAX_RETRIES = 5
REQUEST_TIMEOUT = 30

_RETRYABLE = (gax.GoogleAPICallError, gax.RetryError)

_configured = False


def _configure_once():
    global _configured
    if not _configured:
        genai.configure(api_key=settings.GOOGLE_API_KEY, transport="rest")
        _configured = True


def _embed_batch(texts):
    _configure_once()
    for attempt in range(MAX_RETRIES):
        try:
            resp = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=texts,
                request_options={"timeout": REQUEST_TIMEOUT},
            )
            return resp["embedding"]
        except _RETRYABLE:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(min(2 ** attempt, 20))


def embed_texts(texts):
    if not texts:
        return []
    capped = [t[:MAX_TEXT_CHARS] for t in texts]
    batches = [(i, capped[i : i + BATCH_SIZE]) for i in range(0, len(capped), BATCH_SIZE)]
    results = [None] * len(capped)
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BATCHES) as pool:
        futures = {pool.submit(_embed_batch, chunk): start for start, chunk in batches}
        for future in as_completed(futures):
            start = futures[future]
            for offset, vec in enumerate(future.result()):
                results[start + offset] = vec
    return results

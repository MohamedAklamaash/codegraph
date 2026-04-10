import google.generativeai as genai
from django.conf import settings

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 3072

def embed_texts(texts: list[str]) -> list[list[float]]:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    results = []
    for text in texts:
        result = genai.embed_content(model=EMBEDDING_MODEL, content=text)
        results.append(result["embedding"])
    return results

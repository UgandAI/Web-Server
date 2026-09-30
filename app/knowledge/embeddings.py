import json
import math
from collections.abc import Sequence

from openai import OpenAI

from app.core.config import settings


def serialize_embedding(embedding: Sequence[float]) -> str:
    values = [float(value) for value in embedding]
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding must contain finite numeric values")
    return json.dumps(values, separators=(",", ":"))


def deserialize_embedding(value: str) -> list[float]:
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError
        result = [float(item) for item in parsed]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed embedding") from exc
    if not result or not all(math.isfinite(item) for item in result):
        raise ValueError("Malformed embedding")
    return result


class OpenAIEmbeddingService:
    def __init__(self, client=None, model: str | None = None):
        if client is None and not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        self.client = client or OpenAI(
            api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=1
        )
        self.model = model or settings.OPENAI_EMBEDDING_MODEL

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=list(texts))
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [[float(value) for value in item.embedding] for item in ordered]
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding service returned an unexpected vector count")
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1 or 0 in dimensions:
            raise RuntimeError("Embedding service returned inconsistent dimensions")
        return vectors

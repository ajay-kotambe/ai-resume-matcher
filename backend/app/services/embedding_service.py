"""Embedding service backed by sentence-transformers.

Loads the model lazily (first use only) and caches it process-wide. Cosine
similarity is used everywhere so scores are reproducible.
"""

from __future__ import annotations

import logging
import math
import threading
from functools import lru_cache

from app.core.config import get_settings
from app.core.errors import EmbeddingError

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class SentenceTransformerEmbedder:
    """Local embedding model + cosine similarity helpers."""

    def __init__(self, model_name: str, dimension: int) -> None:
        self.model_name = model_name
        self._dimension = dimension
        self._model = None

    # -- model ----------------------------------------------------------
    def _load(self):
        if self._model is None:
            with _lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:  # pragma: no cover
                        raise EmbeddingError(
                            "sentence-transformers is not installed. Run: "
                            "pip install -r requirements-ml.txt"
                        ) from exc

                    logger.info("Loading embedding model %s ...", self.model_name)
                    try:
                        self._model = SentenceTransformer(self.model_name)
                    except Exception as exc:  # noqa: BLE001
                        raise EmbeddingError(
                            f"Failed to load embedding model '{self.model_name}'.",
                            details={"reason": type(exc).__name__},
                        ) from exc
                    self._dimension = int(self._model.get_sentence_embedding_dimension())
                    logger.info("Embedding model ready (dim=%s)", self._dimension)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    # -- encoding -------------------------------------------------------
    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into unit-normalised vectors."""

        if not texts:
            return []
        model = self._load()
        try:
            vectors = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Embedding failed")
            raise EmbeddingError(
                "Failed to generate embeddings for text.",
                details={"reason": type(exc).__name__},
            ) from exc
        return [[float(v) for v in row] for row in vectors]

    def encode_one(self, text: str) -> list[float]:
        vectors = self.encode([text or " "])
        return vectors[0] if vectors else []


@lru_cache
def get_embedder() -> SentenceTransformerEmbedder:
    """Process-wide embedder instance (model loads on first encode)."""

    settings = get_settings()
    return SentenceTransformerEmbedder(
        model_name=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1], safe for zero vectors."""

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity between two texts, mapped to 0-100."""

    if not (text_a or "").strip() or not (text_b or "").strip():
        return 0.0
    embedder = get_embedder()
    vectors = embedder.encode([text_a, text_b])
    if len(vectors) != 2:
        return 0.0
    # Rescale from [-1, 1] to [0, 100].
    return round(max(0.0, min(1.0, (cosine_similarity(vectors[0], vectors[1]) + 1.0) / 2.0)) * 100, 2)


def batch_similarity(texts: list[str], target: str) -> list[float]:
    """Semantic similarity of many texts against one target (single encode pass)."""

    if not texts or not target.strip():
        return [0.0] * len(texts)
    embedder = get_embedder()
    vectors = embedder.encode(list(texts) + [target])
    target_vec = vectors[-1]
    return [
        round(max(0.0, min(1.0, (cosine_similarity(vec, target_vec) + 1.0) / 2.0)) * 100, 2)
        for vec in vectors[:-1]
    ]


def build_profile_text(candidate_data: dict) -> str:
    """Compose the text used for the semantic comparison.

    Structured fields are prioritised over free text so the embedding reflects
    what the candidate actually claims, not resume layout noise.
    """

    parts: list[str] = []
    if candidate_data.get("name"):
        parts.append(str(candidate_data["name"]))

    summary = str(candidate_data.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    skills = candidate_data.get("skills") or []
    if skills:
        parts.append("Skills: " + ", ".join(str(s) for s in skills))

    for entry in candidate_data.get("experience") or []:
        if isinstance(entry, dict):
            chunk = " ".join(
                str(entry.get(key, "")) for key in ("title", "company", "description")
            ).strip()
            if chunk:
                parts.append(chunk)
        elif entry:
            parts.append(str(entry))

    for entry in candidate_data.get("projects") or []:
        if isinstance(entry, dict):
            chunk = " ".join(
                str(entry.get(key, "")) for key in ("name", "description")
            ).strip()
            if chunk:
                parts.append(chunk)
        elif entry:
            parts.append(str(entry))

    for entry in candidate_data.get("education") or []:
        if isinstance(entry, dict):
            parts.append(" ".join(str(v) for v in entry.values()).strip())
        elif entry:
            parts.append(str(entry))

    return "\n".join(part for part in parts if part)[:8000]
"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True, slots=True)
class Settings:
    backend_dir: Path
    data_dir: Path
    groq_api_key: str | None
    groq_model: str | None
    generation_provider: str
    ollama_base_url: str | None
    ollama_model: str | None
    ollama_timeout_seconds: int
    ollama_api_key: str | None
    embedding_model: str
    reranker_model: str
    candidate_k: int
    context_k: int
    chunk_size: int
    chunk_overlap: int
    max_upload_bytes: int
    ocr_enabled: bool
    ocr_languages: str
    ocr_dpi: int
    ocr_min_characters: int
    render_max_dpi: int

    @classmethod
    def from_environment(cls, backend_dir: Path) -> Settings:
        configured_data_dir = os.getenv("RANKWISE_DATA_DIR")
        if configured_data_dir:
            configured_path = Path(configured_data_dir).expanduser()
            data_dir = (
                configured_path.resolve()
                if configured_path.is_absolute()
                else (backend_dir / configured_path).resolve()
            )
        else:
            data_dir = (backend_dir / "data").resolve()
        candidate_k = _positive_int("RANKWISE_CANDIDATE_K", 30)
        context_k = _positive_int("RANKWISE_CONTEXT_K", 5)
        if context_k > candidate_k:
            raise ValueError("RANKWISE_CONTEXT_K cannot exceed RANKWISE_CANDIDATE_K")

        chunk_size = _positive_int("RANKWISE_CHUNK_SIZE", 1200)
        chunk_overlap = _positive_int("RANKWISE_CHUNK_OVERLAP", 150)
        if chunk_overlap >= chunk_size:
            raise ValueError("RANKWISE_CHUNK_OVERLAP must be smaller than RANKWISE_CHUNK_SIZE")
        generation_provider = os.getenv("RANKWISE_GENERATION_PROVIDER", "auto").strip().casefold()
        if generation_provider not in {"auto", "groq", "ollama"}:
            raise ValueError("RANKWISE_GENERATION_PROVIDER must be auto, groq, or ollama")

        return cls(
            backend_dir=backend_dir,
            data_dir=data_dir,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL") or None,
            generation_provider=generation_provider,
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434") or None,
            ollama_model=os.getenv("OLLAMA_MODEL") or None,
            ollama_timeout_seconds=_positive_int("OLLAMA_TIMEOUT_SECONDS", 120),
            ollama_api_key=os.getenv("OLLAMA_API_KEY") or None,
            embedding_model=os.getenv(
                "RANKWISE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            reranker_model=os.getenv(
                "RANKWISE_RERANKER_MODEL",
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
            ),
            candidate_k=candidate_k,
            context_k=context_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_upload_bytes=_positive_int("RANKWISE_MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
            ocr_enabled=_boolean("RANKWISE_OCR_ENABLED", True),
            ocr_languages=os.getenv("RANKWISE_OCR_LANGUAGES", "eng"),
            ocr_dpi=_positive_int("RANKWISE_OCR_DPI", 200),
            ocr_min_characters=_positive_int("RANKWISE_OCR_MIN_CHARACTERS", 24),
            render_max_dpi=_positive_int("RANKWISE_RENDER_MAX_DPI", 300),
        )

"""Dependency container and production wiring."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import find_spec
from shutil import which

from .catalog import Catalog
from .chemistry_tools import ChemistryTools
from .config import Settings
from .jobs import BackgroundJobRunner, JobRunner
from .media import ImageService, MediaService
from .parsing import PdfParser
from .ports import Generator
from .product_services import CollectionService, NoteService
from .providers import (
    CrossEncoderReranker,
    GroqGenerator,
    OllamaGenerator,
    SentenceTransformerEmbedder,
)
from .science_tools import ScienceTools
from .services import IngestionService, QuestionService
from .storage import FaissIndexStore, LocalDocumentStore


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    ingestion: IngestionService
    questions: QuestionService
    catalog: Catalog | None = None
    jobs: JobRunner | None = None
    collections: CollectionService | None = None
    notes: NoteService | None = None
    media: MediaService | None = None
    images: ImageService | None = None
    science_tools: ScienceTools | None = None
    chemistry_tools: ChemistryTools | None = None
    generators: dict[str, Generator] = field(default_factory=dict)
    default_generation_provider: str = "groq"

    @property
    def ready(self) -> bool:
        return any(
            bool(getattr(provider, "configured", False))
            for provider in self.questions.generators.values()
        )

    @property
    def capabilities(self) -> dict[str, bool]:
        parser = self.ingestion.parser
        return {
            "generation": self.ready,
            "ocr": bool(getattr(parser, "ocr_enabled", False) and which("tesseract")),
            "symbolic_math": find_spec("sympy") is not None,
            "unit_conversion": find_spec("pint") is not None,
            "plotting": find_spec("matplotlib") is not None,
            "page_rendering": True,
            "reaction_balancing": find_spec("sympy") is not None,
            "molecule_analysis": find_spec("rdkit") is not None,
            "external_chemical_lookup": self.chemistry_tools is not None,
        }

    def provider_status(self) -> dict[str, object]:
        return {
            "default": self.default_generation_provider,
            "providers": self.questions.provider_status(),
        }


def build_default_container(settings: Settings) -> ServiceContainer:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    document_store = LocalDocumentStore(settings.data_dir)
    index_store = FaissIndexStore(settings.data_dir)
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    generator = GroqGenerator(api_key=settings.groq_api_key, model=settings.groq_model)
    ollama = OllamaGenerator(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        api_key=settings.ollama_api_key,
    )
    parser = PdfParser(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        ocr_enabled=settings.ocr_enabled,
        ocr_languages=settings.ocr_languages,
        ocr_dpi=settings.ocr_dpi,
        ocr_min_characters=settings.ocr_min_characters,
    )
    ingestion = IngestionService(
        parser=parser,
        embedder=embedder,
        index_store=index_store,
        document_store=document_store,
    )
    questions = QuestionService(
        embedder=embedder,
        reranker=reranker,
        generator=generator,
        generators={"groq": generator, "ollama": ollama},
        default_provider=settings.generation_provider,
        index_store=index_store,
        document_store=document_store,
        candidate_k=settings.candidate_k,
        context_k=settings.context_k,
    )
    catalog = Catalog(settings.data_dir / "catalog.sqlite3")
    jobs = BackgroundJobRunner(catalog)
    collections = CollectionService(
        catalog=catalog,
        jobs=jobs,
        ingestion=ingestion,
        questions=questions,
        document_store=document_store,
        data_dir=settings.data_dir,
    )
    science_tools = ScienceTools()
    chemistry_tools = ChemistryTools(cache_dir=settings.data_dir / "external-cache")
    media = MediaService(document_store, max_dpi=settings.render_max_dpi)
    images = ImageService(
        catalog=catalog,
        jobs=jobs,
        ingestion=ingestion,
        data_dir=settings.data_dir,
    )
    notes = NoteService(
        catalog=catalog,
        jobs=jobs,
        collections=collections,
        questions=questions,
        document_store=document_store,
        science_tools=science_tools,
        chemistry_tools=chemistry_tools,
    )
    return ServiceContainer(
        ingestion=ingestion,
        questions=questions,
        catalog=catalog,
        jobs=jobs,
        collections=collections,
        notes=notes,
        media=media,
        images=images,
        science_tools=science_tools,
        chemistry_tools=chemistry_tools,
        generators={"groq": generator, "ollama": ollama},
        default_generation_provider=settings.generation_provider,
    )

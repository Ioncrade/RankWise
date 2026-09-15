"""Phase 1 collection, job, and cited-note workflows."""

from __future__ import annotations

import copy
import json
import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .catalog import Catalog, CollectionRecord, JobRecord, NoteVersion
from .chemistry_tools import ChemistrySafetyPolicy, ChemistryTools
from .domain import Evidence
from .errors import AppError, NotFoundError, ValidationError
from .jobs import JobRunner
from .ports import DocumentStore
from .science_tools import ScienceTools
from .services import IngestionService, QuestionService

SECTION_PROFILES: dict[str, tuple[tuple[str, str], ...]] = {
    "comprehensive": (
        ("learning-objectives", "Learning objectives and major themes"),
        ("core-explanations", "Core explanations and processes"),
        ("definitions", "Definitions and terminology"),
        ("relationships", "Important equations, relationships, and examples"),
        ("misconceptions", "Misconceptions, exceptions, and boundary conditions"),
        ("source-differences", "Source differences and unresolved points"),
    ),
    "concise": (
        ("key-ideas", "Key ideas"),
        ("definitions", "Essential definitions and relationships"),
        ("review", "Quick review and unresolved points"),
    ),
    "formula_sheet": (
        ("symbols", "Symbols, definitions, and units"),
        ("formulas", "Formula sheet"),
        ("assumptions", "Assumptions, domains, and sign conventions"),
        ("worked-relations", "Worked relationships and rearrangements"),
    ),
    "reaction_sheet": (
        ("species", "Compounds, formulas, states, and charges"),
        ("verified-reactions", "Source reactions and verified balances"),
        ("conditions-safety", "Source-stated conditions, catalysts, yields, and safety"),
        ("reaction-review", "Reaction patterns and quick review"),
    ),
    "flashcards": (
        ("concept-cards", "Concept flashcards"),
        ("formula-reaction-cards", "Formula and reaction flashcards"),
        ("misconception-cards", "Misconception and boundary-condition flashcards"),
    ),
    "practice_questions": (
        ("recall-questions", "Recall questions"),
        ("application-questions", "Application and calculation questions"),
        ("answer-key", "Answer key with source-grounded explanations"),
    ),
}


class CollectionService:
    def __init__(
        self,
        *,
        catalog: Catalog,
        jobs: JobRunner,
        ingestion: IngestionService,
        questions: QuestionService,
        document_store: DocumentStore,
        data_dir: Path,
    ) -> None:
        self.catalog = catalog
        self.jobs = jobs
        self.ingestion = ingestion
        self.questions = questions
        self.document_store = document_store
        self.pending_dir = data_dir / "pending"
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self, tenant_id: str, title: str, subject: str, education_level: str
    ) -> CollectionRecord:
        return self.catalog.create_collection(tenant_id, title, subject, education_level)

    def list(self, tenant_id: str) -> list[dict[str, Any]]:
        return [self.view(item, tenant_id) for item in self.catalog.list_collections(tenant_id)]

    def get(self, collection_id: str, tenant_id: str) -> dict[str, Any]:
        return self.view(self.catalog.get_collection(collection_id, tenant_id), tenant_id)

    def view(self, collection: CollectionRecord, tenant_id: str) -> dict[str, Any]:
        documents = [
            self.document_store.get_document(version_id).to_dict()
            for version_id in self.catalog.document_versions(collection.collection_id, tenant_id)
        ]
        value = collection.to_dict()
        value["documents"] = documents
        value["document_count"] = len(documents)
        value["images"] = [
            item.public_dict()
            for item in self.catalog.list_images(collection.collection_id, tenant_id)
        ]
        value["image_count"] = len(value["images"])
        return value

    def enqueue_pdf(
        self, collection_id: str, tenant_id: str, source_path: Path, filename: str
    ) -> JobRecord:
        self.catalog.get_collection(collection_id, tenant_id)
        pending_path = self.pending_dir / f"{secrets.token_hex(16)}.pdf"
        shutil.copyfile(source_path, pending_path)

        def ingest() -> dict[str, Any]:
            try:
                record = self.ingestion.ingest_pdf(pending_path, filename, activate=False)
                self.catalog.add_document(collection_id, tenant_id, record.document_version_id)
                return {"document": record.to_dict(), "collection_id": collection_id}
            finally:
                pending_path.unlink(missing_ok=True)

        try:
            return self.jobs.submit(
                tenant_id,
                "document_ingestion",
                {"collection_id": collection_id, "filename": filename},
                ingest,
            )
        except Exception:
            pending_path.unlink(missing_ok=True)
            raise

    def scope(
        self,
        collection_id: str,
        tenant_id: str,
        requested_versions: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        available = tuple(self.catalog.document_versions(collection_id, tenant_id))
        if not available:
            raise NotFoundError("The collection has no ready documents", code="empty_collection")
        if requested_versions is None:
            return available
        selected = tuple(dict.fromkeys(requested_versions))
        if not selected:
            raise ValidationError("document_version_ids cannot be empty")
        if not set(selected).issubset(available):
            raise ValidationError(
                "One or more document versions are outside the collection",
                code="invalid_document_scope",
            )
        return selected

    def ask(
        self,
        collection_id: str,
        tenant_id: str,
        query: str,
        requested_versions: list[str] | None = None,
        generation_provider: str | None = None,
    ):
        versions = self.scope(collection_id, tenant_id, requested_versions)
        return self.questions.ask_versions(query, versions, generation_provider)


class NoteService:
    citation_pattern = re.compile(r"\[(E\d+)\]")

    def __init__(
        self,
        *,
        catalog: Catalog,
        jobs: JobRunner,
        collections: CollectionService,
        questions: QuestionService,
        document_store: DocumentStore,
        science_tools: ScienceTools | None = None,
        chemistry_tools: ChemistryTools | None = None,
        chemistry_safety: ChemistrySafetyPolicy | None = None,
    ) -> None:
        self.catalog = catalog
        self.jobs = jobs
        self.collections = collections
        self.questions = questions
        self.document_store = document_store
        self.science_tools = science_tools
        self.chemistry_tools = chemistry_tools
        self.chemistry_safety = chemistry_safety or ChemistrySafetyPolicy()

    def enqueue(
        self,
        *,
        collection_id: str,
        tenant_id: str,
        title: str,
        profile: str,
        document_version_ids: list[str] | None,
        generation_provider: str | None = None,
    ) -> JobRecord:
        versions = self.collections.scope(collection_id, tenant_id, document_version_ids)
        normalized_profile = profile.strip().casefold()
        if normalized_profile not in SECTION_PROFILES:
            raise ValidationError(
                "Unsupported note profile",
                code="invalid_note_profile",
            )
        normalized_title = title.strip()
        if not normalized_title:
            raise ValidationError("Note title is required")

        def generate() -> dict[str, Any]:
            note = self._generate(
                collection_id=collection_id,
                tenant_id=tenant_id,
                title=normalized_title,
                profile=normalized_profile,
                document_version_ids=versions,
                generation_provider=generation_provider,
            )
            return {"note_id": note.note_id, "note_version_id": note.note_version_id}

        return self.jobs.submit(
            tenant_id,
            "note_generation",
            {
                "collection_id": collection_id,
                "title": normalized_title,
                "profile": normalized_profile,
                "document_version_ids": list(versions),
                "generation_provider": generation_provider,
            },
            generate,
        )

    def _section(
        self,
        section_id: str,
        heading: str,
        versions: tuple[str, ...],
        extra_instruction: str = "",
        use_science_tools: bool = False,
        use_chemistry_tools: bool = False,
        artifact_profile: str | None = None,
        generation_provider: str | None = None,
    ) -> tuple[dict[str, Any], tuple[Evidence, ...], dict[str, Any]]:
        prompt = (
            f"Write the '{heading}' section of source-grounded science study notes. "
            "Be precise and concise. Cite every source-derived factual paragraph with "
            "the supplied evidence labels. Distinguish disagreement or missing evidence. "
            f"{extra_instruction}"
        ).strip()
        tool_observations: list[dict[str, Any]] = []
        if use_science_tools:
            tool_observations.extend(self._equation_observations(versions))
        if use_chemistry_tools:
            tool_observations.extend(self._reaction_observations(versions))
            prompt += (
                " Preserve each original source reaction. Show a computed balance only as a "
                "separate 'Verified calculation'. Never infer or invent a catalyst, solvent, "
                "temperature, yield, hazard, or laboratory procedure."
            )
        if artifact_profile == "flashcards":
            prompt += (
                " Format atomic study cards as 'Front' and 'Back'. Keep one testable concept "
                "per card, cite every source-derived back, and include misconception cards only "
                "when the evidence supports the correction."
            )
        elif artifact_profile == "practice_questions":
            prompt += (
                " Clearly label all questions as system-generated practice, not source content. "
                "Vary recall and application difficulty, do not require unstated data, and give "
                "the cited solution only in the answer-key section."
            )
        evidence = self.questions.retrieve_versions(prompt, versions)
        if tool_observations:
            prompt += (
                "\n\nUse these deterministic parser observations where relevant. A status of "
                "'parsed_not_proven' confirms syntax only, not that a physical law is true:\n"
                + json.dumps(tool_observations, ensure_ascii=False)
            )
        result = self.questions.answer_from_evidence(prompt, evidence, generation_provider)
        evidence_by_label = {item.label: item for item in result.evidence}
        cited_labels = set(self.citation_pattern.findall(result.answer))
        used: list[Evidence] = []

        def citation_link(match: re.Match[str]) -> str:
            evidence = evidence_by_label.get(match.group(1))
            if evidence is None:
                return "[invalid citation]"
            if evidence not in used:
                used.append(evidence)
            filename = evidence.document_filename or evidence.document_id
            url = (
                f"/v1/evidence/{evidence.evidence_id}"
                f"?document_version_id={evidence.document_version_id}"
            )
            display = (
                f"Image {filename}, region 1"
                if evidence.source_type == "image"
                else f"{filename}, p. {evidence.page_number}"
            )
            return f"[{display}]({url})"

        markdown = self.citation_pattern.sub(citation_link, result.answer)
        warnings = list(result.warnings)
        invalid_labels = sorted(cited_labels - evidence_by_label.keys())
        if invalid_labels:
            warnings.append("Invalid evidence labels were removed: " + ", ".join(invalid_labels))
        if not used:
            warnings.append("This section has no validated citation.")
        section = {
            "section_id": section_id,
            "heading": heading,
            "markdown": markdown,
            "citations": [item.evidence_id for item in used],
            "warnings": list(dict.fromkeys(warnings)),
            "tool_observations": tool_observations,
        }
        return section, tuple(used), result.generation

    def _equation_observations(self, versions: tuple[str, ...]) -> list[dict[str, Any]]:
        if self.science_tools is None:
            return []
        observations = []
        for version_id in versions:
            for chunk in self.document_store.get_chunks(version_id):
                if chunk.content_type != "equation":
                    continue
                observations.append(
                    {
                        "evidence_id": chunk.evidence_id,
                        "document_version_id": version_id,
                        "page_number": chunk.page_number,
                        "equation": chunk.text,
                        "observation": self.science_tools.inspect_equation(chunk.text),
                    }
                )
                if len(observations) >= 20:
                    return observations
        return observations

    def _reaction_observations(self, versions: tuple[str, ...]) -> list[dict[str, Any]]:
        if self.chemistry_tools is None:
            return []
        observations = []
        seen_equations: set[str] = set()
        for version_id in versions:
            for chunk in self.document_store.get_chunks(version_id):
                candidates = [line.strip() for line in chunk.text.splitlines()]
                for candidate in candidates:
                    equation = candidate.rsplit(":", 1)[-1].strip().rstrip(".;")
                    if not any(arrow in equation for arrow in ("->", "→", "⇌", "<=>")):
                        continue
                    if any(equation == seen or equation in seen for seen in seen_equations):
                        continue
                    seen_equations.add(equation)
                    try:
                        observation = self.chemistry_tools.balance_equation(equation)
                    except AppError as exc:
                        observation = {
                            "tool": "balance_chemical_equation",
                            "status": "not_verified",
                            "error": exc.code,
                        }
                    observations.append(
                        {
                            "evidence_id": chunk.evidence_id,
                            "document_version_id": version_id,
                            "page_number": chunk.page_number,
                            "equation": equation,
                            "observation": observation,
                        }
                    )
                    if len(observations) >= 20:
                        return observations
        return observations

    def _generate(
        self,
        *,
        collection_id: str,
        tenant_id: str,
        title: str,
        profile: str,
        document_version_ids: tuple[str, ...],
        generation_provider: str | None = None,
    ) -> NoteVersion:
        sections: list[dict[str, Any]] = []
        all_evidence: list[Evidence] = []
        generations: list[dict[str, Any]] = []
        for section_id, heading in SECTION_PROFILES[profile]:
            section, evidence, generation = self._section(
                section_id,
                heading,
                document_version_ids,
                use_science_tools=profile == "formula_sheet",
                use_chemistry_tools=profile == "reaction_sheet",
                artifact_profile=profile,
                generation_provider=generation_provider,
            )
            sections.append(section)
            all_evidence.extend(evidence)
            if generation not in generations:
                generations.append(generation)
        evidence = tuple({item.evidence_id: item for item in all_evidence}.values())
        content = {
            "schema_version": "rankwise.note.v1",
            "title": title,
            "artifact_type": (
                profile
                if profile in {"reaction_sheet", "flashcards", "practice_questions"}
                else "notes"
            ),
            "scope": {
                "collection_id": collection_id,
                "document_version_ids": list(document_version_ids),
                "sources": [
                    self.document_store.get_document(version_id).to_dict()
                    for version_id in document_version_ids
                ],
            },
            "sections": sections,
            "unresolved_items": [
                warning for section in sections for warning in section["warnings"]
            ],
            "provenance": {
                "pipeline_version": (
                    "phase3-v1"
                    if profile in {"reaction_sheet", "flashcards", "practice_questions"}
                    else "phase2-v1"
                    if profile == "formula_sheet"
                    else "phase1-v1"
                ),
                "generated_at": datetime.now(UTC).isoformat(),
                "generation": generations,
            },
        }
        markdown = self._render_markdown(content)
        return self.catalog.save_note(
            collection_id=collection_id,
            tenant_id=tenant_id,
            title=title,
            profile=profile,
            markdown=markdown,
            content=content,
            citations=tuple(item.public_dict() for item in evidence),
            document_version_ids=document_version_ids,
            warnings=tuple(content["unresolved_items"]),
            change_reason="initial_generation",
        )

    @staticmethod
    def _render_markdown(content: dict[str, Any]) -> str:
        scope = content["scope"]
        lines = [f"# {content['title']}", "", "## Sources", ""]
        lines.extend(
            f"- {source['filename']} (`{source['document_version_id']}`)"
            for source in scope["sources"]
        )
        for section in content["sections"]:
            lines.extend(["", f"## {section['heading']}", "", section["markdown"]])
            if section["warnings"]:
                lines.extend(["", *[f"> Warning: {warning}" for warning in section["warnings"]]])
            if section.get("tool_observations"):
                lines.extend(["", "### Deterministic checks", ""])
                for item in section["tool_observations"]:
                    observation = item["observation"]
                    source = f"source evidence `{item['evidence_id']}`"
                    if (
                        observation.get("tool") == "balance_chemical_equation"
                        and observation.get("status") == "verified"
                    ):
                        lines.append(f"- Original: `{observation['original_equation']}` ({source})")
                        lines.append(
                            "  - Verified calculation: "
                            f"`{observation['verified_balanced_equation']}`"
                        )
                    else:
                        lines.append(f"- `{item['equation']}` — {observation['status']} ({source})")
        return "\n".join(lines).strip() + "\n"

    def get(self, note_id: str, tenant_id: str) -> NoteVersion:
        return self.catalog.get_note(note_id, tenant_id)

    def regenerate_section(
        self,
        *,
        note_id: str,
        section_id: str,
        tenant_id: str,
        instruction: str,
        generation_provider: str | None = None,
    ) -> JobRecord:
        current = self.get(note_id, tenant_id)
        self.chemistry_safety.validate(instruction)
        matching = [
            section
            for section in current.content["sections"]
            if section["section_id"] == section_id
        ]
        if not matching:
            raise NotFoundError("Note section was not found", code="section_not_found")

        def regenerate() -> dict[str, Any]:
            section, section_evidence, generation = self._section(
                section_id,
                matching[0]["heading"],
                current.document_version_ids,
                instruction.strip(),
                use_science_tools=current.profile == "formula_sheet",
                use_chemistry_tools=current.profile == "reaction_sheet",
                artifact_profile=current.profile,
                generation_provider=generation_provider,
            )
            content = copy.deepcopy(current.content)
            content["sections"] = [
                section if item["section_id"] == section_id else item
                for item in content["sections"]
            ]
            content["provenance"] = {
                **content["provenance"],
                "generated_at": datetime.now(UTC).isoformat(),
                "generation": [
                    *content["provenance"].get("generation", []),
                    generation,
                ],
            }
            content["unresolved_items"] = [
                warning for item in content["sections"] for warning in item["warnings"]
            ]
            retained_ids = {
                evidence_id
                for item in content["sections"]
                if item["section_id"] != section_id
                for evidence_id in item["citations"]
            }
            citations = [item for item in current.citations if item["evidence_id"] in retained_ids]
            citations.extend(item.public_dict() for item in section_evidence)
            version = self.catalog.save_note(
                collection_id=current.collection_id,
                tenant_id=tenant_id,
                note_id=current.note_id,
                title=current.title,
                profile=current.profile,
                markdown=self._render_markdown(content),
                content=content,
                citations=tuple({item["evidence_id"]: item for item in citations}.values()),
                document_version_ids=current.document_version_ids,
                warnings=tuple(content["unresolved_items"]),
                change_reason=f"regenerated_section:{section_id}",
            )
            return {
                "note_id": version.note_id,
                "note_version_id": version.note_version_id,
            }

        return self.jobs.submit(
            tenant_id,
            "note_section_regeneration",
            {
                "note_id": note_id,
                "section_id": section_id,
                "generation_provider": generation_provider,
            },
            regenerate,
        )

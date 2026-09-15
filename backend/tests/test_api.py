from __future__ import annotations

import io
import re
from pathlib import Path

import pymupdf
from PIL import Image
from rankwise import create_app
from rankwise.catalog import Catalog
from rankwise.chemistry_tools import ChemistryTools
from rankwise.container import ServiceContainer
from rankwise.evaluation import CollectionRetrievalCase, collection_retrieval_metrics
from rankwise.jobs import InlineJobRunner
from rankwise.media import ImageService, MediaService
from rankwise.parsing import PdfParser
from rankwise.product_services import CollectionService, NoteService
from rankwise.science_tools import ScienceTools
from rankwise.services import IngestionService, QuestionService
from rankwise.storage import LocalDocumentStore

from .fakes import CitingGenerator, HashingEmbedder, LexicalReranker, MemoryIndexStore


def _app(tmp_path: Path):
    document_store = LocalDocumentStore(tmp_path / "data")
    index_store = MemoryIndexStore()
    embedder = HashingEmbedder()
    ingestion = IngestionService(
        parser=PdfParser(chunk_size=300, chunk_overlap=30),
        embedder=embedder,
        index_store=index_store,
        document_store=document_store,
    )
    questions = QuestionService(
        embedder=embedder,
        reranker=LexicalReranker(),
        generator=CitingGenerator(),
        index_store=index_store,
        document_store=document_store,
        candidate_k=10,
        context_k=5,
    )
    catalog = Catalog(tmp_path / "data" / "catalog.sqlite3")
    jobs = InlineJobRunner(catalog)
    collections = CollectionService(
        catalog=catalog,
        jobs=jobs,
        ingestion=ingestion,
        questions=questions,
        document_store=document_store,
        data_dir=tmp_path / "data",
    )
    science_tools = ScienceTools()
    chemistry_tools = ChemistryTools(cache_dir=tmp_path / "data" / "external-cache")
    media = MediaService(document_store)
    images = ImageService(
        catalog=catalog,
        jobs=jobs,
        ingestion=ingestion,
        data_dir=tmp_path / "data",
    )
    container = ServiceContainer(
        ingestion=ingestion,
        questions=questions,
        catalog=catalog,
        jobs=jobs,
        collections=collections,
        notes=NoteService(
            catalog=catalog,
            jobs=jobs,
            collections=collections,
            questions=questions,
            document_store=document_store,
            science_tools=science_tools,
            chemistry_tools=chemistry_tools,
        ),
        media=media,
        images=images,
        science_tools=science_tools,
        chemistry_tools=chemistry_tools,
    )
    return create_app({"TESTING": True}, services=container)


def test_vite_frontend_and_hashed_assets_are_served(tmp_path: Path) -> None:
    app = _app(tmp_path)
    client = app.test_client()

    root = client.get("/")
    assert root.status_code == 200
    html = root.get_data(as_text=True)
    assert "RankWise" in html

    asset_paths = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
    assert asset_paths
    for asset_path in asset_paths:
        asset = client.get(asset_path)
        assert asset.status_code == 200
        assert len(asset.data) > 100

    history_fallback = client.get("/notes")
    assert history_fallback.status_code == 200
    assert "RankWise" in history_fallback.get_data(as_text=True)


def test_generation_provider_status_and_validation(tmp_path: Path) -> None:
    client = _app(tmp_path).test_client()
    headers = {"X-Tenant-ID": "provider-test"}

    status = client.get("/v1/providers", headers=headers)
    assert status.status_code == 200
    payload = status.get_json()
    assert payload["default"] == "groq"
    assert payload["providers"]["groq"]["configured"] is True

    invalid = client.post(
        "/v1/collections/col_missing/queries",
        headers=headers,
        json={"query": "test", "generation_provider": "unknown"},
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "invalid_generation_provider"


def test_upload_ask_and_resolve_citation(tmp_path: Path, science_pdf_bytes: bytes) -> None:
    client = _app(tmp_path).test_client()

    upload = client.post(
        "/upload_pdf",
        data={"file": (io.BytesIO(science_pdf_bytes), "science.pdf")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    document = upload.get_json()["document"]
    assert document["document_id"].startswith("doc_")
    assert document["document_version_id"].startswith("dv_")
    assert document["page_count"] == 2

    answer = client.post(
        "/ask",
        json={
            "query": "What does Newton's second law say about force mass and acceleration?",
            "document_version_id": document["document_version_id"],
        },
    )
    assert answer.status_code == 200
    payload = answer.get_json()
    assert "[E1]" in payload["answer"]
    assert payload["citations"][0]["page_number"] == 2
    assert payload["warnings"] == []

    citation = payload["citations"][0]
    resolved = client.get(citation["url"])
    assert resolved.status_code == 200
    assert resolved.get_json()["evidence_id"] == citation["evidence_id"]
    assert "Newton" in resolved.get_json()["text"]


def test_upload_is_content_addressed_and_reproducible(
    tmp_path: Path, science_pdf_bytes: bytes
) -> None:
    client = _app(tmp_path).test_client()
    ids = []
    filenames = ("original.pdf", "renamed.pdf")
    returned_filenames = []
    for filename in filenames:
        response = client.post(
            "/upload_pdf",
            data={"file": (io.BytesIO(science_pdf_bytes), filename)},
            content_type="multipart/form-data",
        )
        ids.append(response.get_json()["document"]["document_version_id"])
        returned_filenames.append(response.get_json()["document"]["filename"])
    assert ids[0] == ids[1]
    assert returned_filenames == ["original.pdf", "original.pdf"]


def test_errors_are_typed(tmp_path: Path) -> None:
    client = _app(tmp_path).test_client()
    response = client.post("/ask", json={"query": "anything"})
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "no_document"

    response = client.post(
        "/upload_pdf",
        data={"file": (io.BytesIO(b"not a pdf"), "fake.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_pdf"


def test_readiness_is_separate_from_liveness(tmp_path: Path) -> None:
    client = _app(tmp_path).test_client()
    assert client.get("/health/live").status_code == 200
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["capabilities"]["symbolic_math"] is True
    assert response.get_json()["capabilities"]["reaction_balancing"] is True
    assert response.get_json()["capabilities"]["molecule_analysis"] is True
    assert response.get_json()["capabilities"]["external_chemical_lookup"] is True


def _pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    value = document.tobytes()
    document.close()
    return value


def test_phase1_five_pdf_notes_workflow_and_tenant_isolation(tmp_path: Path) -> None:
    client = _app(tmp_path).test_client()
    tenant_headers = {"X-Tenant-ID": "school-alpha"}
    create = client.post(
        "/v1/collections",
        headers=tenant_headers,
        json={
            "title": "Science revision",
            "subject": "general_science",
            "education_level": "secondary",
        },
    )
    assert create.status_code == 201
    collection_id = create.get_json()["collection_id"]

    sources = (
        ("mechanics.pdf", "Newton force mass acceleration mechanics. F = m*a"),
        ("biology.pdf", "Photosynthesis uses chlorophyll to capture light energy."),
        ("chemistry.pdf", "Atoms form chemical bonds by sharing or transferring electrons."),
        ("earth.pdf", "Tectonic plates move and can cause earthquakes."),
        ("energy.pdf", "Energy is conserved although it can change form."),
    )
    upload = client.post(
        f"/v1/collections/{collection_id}/documents",
        headers=tenant_headers,
        data={"files": [(io.BytesIO(_pdf(text)), name) for name, text in sources]},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 202
    jobs = upload.get_json()["jobs"]
    assert len(jobs) == 5
    assert all(job["status"] == "succeeded" for job in jobs)

    collection = client.get(f"/v1/collections/{collection_id}", headers=tenant_headers).get_json()
    assert collection["document_count"] == 5
    assert {item["filename"] for item in collection["documents"]} == {name for name, _ in sources}

    questions = (
        ("How does chlorophyll relate to photosynthesis?", "biology.pdf#1"),
        ("What equation relates force mass and acceleration?", "mechanics.pdf#1"),
        ("How do atoms form chemical bonds?", "chemistry.pdf#1"),
        ("What can moving tectonic plates cause?", "earth.pdf#1"),
        ("Can energy change form while remaining conserved?", "energy.pdf#1"),
    )
    retrieval_cases = []
    payload = None
    for query, relevant_location in questions:
        answer = client.post(
            f"/v1/collections/{collection_id}/queries",
            headers=tenant_headers,
            json={"query": query},
        )
        assert answer.status_code == 200
        current_payload = answer.get_json()
        locations = tuple(
            f"{item['document_filename']}#{item['page_number']}"
            for item in current_payload["retrieved_evidence"]
        )
        retrieval_cases.append(
            CollectionRetrievalCase(
                ranked_locations=locations,
                relevant_locations=frozenset({relevant_location}),
            )
        )
        if relevant_location == "biology.pdf#1":
            payload = current_payload
    assert collection_retrieval_metrics(retrieval_cases, k=1) == {
        "hit_rate@1": 1.0,
        "recall@1": 1.0,
        "mrr@1": 1.0,
        "ndcg@1": 1.0,
        "case_count": 5.0,
    }
    assert payload is not None
    assert payload["citations"][0]["document_filename"] == "biology.pdf"
    assert client.get(payload["citations"][0]["url"], headers=tenant_headers).status_code == 200
    biology_version = payload["citations"][0]["document_version_id"]
    biology_evidence = payload["citations"][0]["evidence_id"]
    assert (
        client.post(
            "/ask",
            json={"query": "photosynthesis", "document_version_id": biology_version},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/evidence/{biology_evidence}?document_version_id={biology_version}"
        ).status_code
        == 404
    )

    note_job = client.post(
        f"/v1/collections/{collection_id}/notes",
        headers=tenant_headers,
        json={"title": "Exam notes", "profile": "comprehensive"},
    )
    assert note_job.status_code == 202
    note_job_body = note_job.get_json()
    assert note_job_body["status"] == "succeeded"
    note_id = note_job_body["result"]["note_id"]

    note = client.get(f"/v1/notes/{note_id}", headers=tenant_headers)
    assert note.status_code == 200
    note_body = note.get_json()
    assert note_body["content"]["schema_version"] == "rankwise.note.v1"
    assert len(note_body["content"]["sections"]) == 6
    assert note_body["citations"]

    exported = client.get(f"/v1/notes/{note_id}/export.md", headers=tenant_headers)
    assert exported.status_code == 200
    assert exported.mimetype == "text/markdown"
    assert "## Learning objectives" in exported.get_data(as_text=True)
    assert "/v1/evidence/" in exported.get_data(as_text=True)

    regenerate = client.post(
        f"/v1/notes/{note_id}/sections/definitions/regenerate",
        headers=tenant_headers,
        json={"instruction": "Focus on terminology."},
    )
    assert regenerate.status_code == 202
    assert regenerate.get_json()["status"] == "succeeded"
    versions = client.get(f"/v1/notes/{note_id}/versions", headers=tenant_headers).get_json()[
        "versions"
    ]
    assert len(versions) == 2
    assert versions[0]["change_reason"] == "regenerated_section:definitions"

    other_tenant = {"X-Tenant-ID": "school-beta"}
    assert client.get(f"/v1/collections/{collection_id}", headers=other_tenant).status_code == 404
    assert client.get(f"/v1/notes/{note_id}", headers=other_tenant).status_code == 404
    job_id = jobs[0]["job_id"]
    assert client.get(f"/v1/jobs/{job_id}", headers=other_tenant).status_code == 404


def test_phase1_validates_tenant_upload_and_scope(tmp_path: Path) -> None:
    client = _app(tmp_path).test_client()
    assert client.get("/v1/collections").status_code == 400
    headers = {"X-Tenant-ID": "tenant-one"}
    collection_id = client.post(
        "/v1/collections", headers=headers, json={"title": "Test"}
    ).get_json()["collection_id"]

    invalid = client.post(
        f"/v1/collections/{collection_id}/documents",
        headers=headers,
        data={"files": (io.BytesIO(b"not-pdf"), "fake.pdf")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "invalid_pdf"

    empty = client.post(
        f"/v1/collections/{collection_id}/queries",
        headers=headers,
        json={"query": "question"},
    )
    assert empty.status_code == 404
    assert empty.get_json()["error"]["code"] == "empty_collection"


def test_phase2_render_formula_tools_and_image_storage(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-Tenant-ID": "physics-class"}
    collection_id = client.post(
        "/v1/collections",
        headers=headers,
        json={"title": "Physics", "subject": "physics"},
    ).get_json()["collection_id"]
    upload = client.post(
        f"/v1/collections/{collection_id}/documents",
        headers=headers,
        data={
            "files": (
                io.BytesIO(_pdf("Newton's second law. F = m*a")),
                "mechanics.pdf",
            )
        },
        content_type="multipart/form-data",
    )
    document = upload.get_json()["jobs"][0]["result"]["document"]
    version_id = document["document_version_id"]
    assert document["content_counts"]["equation"] == 1

    page = client.get(f"/v1/documents/{version_id}/pages/1/render?dpi=144", headers=headers)
    assert page.status_code == 200
    assert page.mimetype == "image/png"
    assert page.data.startswith(b"\x89PNG")
    region = client.get(
        f"/v1/documents/{version_id}/pages/1/render?x0=60&y0=50&x1=300&y1=100",
        headers=headers,
    )
    assert region.status_code == 200
    assert len(region.data) < len(page.data)
    services = app.extensions["rankwise_services"]
    equation = next(
        chunk
        for chunk in services.questions.document_store.get_chunks(version_id)
        if chunk.content_type == "equation"
    )
    evidence_region = client.get(
        f"/v1/evidence/{equation.evidence_id}/render?document_version_id={version_id}",
        headers=headers,
    )
    assert evidence_region.status_code == 200
    assert evidence_region.data.startswith(b"\x89PNG")

    formula_job = client.post(
        f"/v1/collections/{collection_id}/notes",
        headers=headers,
        json={"title": "Formula sheet", "profile": "formula_sheet"},
    ).get_json()
    assert formula_job["status"] == "succeeded"
    formula = client.get(
        f"/v1/notes/{formula_job['result']['note_id']}", headers=headers
    ).get_json()
    assert formula["content"]["provenance"]["pipeline_version"] == "phase2-v1"
    assert (
        formula["content"]["sections"][0]["tool_observations"][0]["observation"]["status"]
        == "parsed_not_proven"
    )

    math_result = client.post(
        "/v1/tools/math",
        headers=headers,
        json={
            "operation": "compare",
            "expression": "(x + 1)^2",
            "other_expression": "x^2 + 2*x + 1",
            "variables": ["x"],
        },
    )
    assert math_result.status_code == 200
    assert math_result.get_json()["equivalent"] is True

    conversion = client.post(
        "/v1/tools/units/convert",
        headers=headers,
        json={"value": 1000, "from_unit": "meter", "to_unit": "kilometer"},
    )
    assert conversion.status_code == 200
    assert conversion.get_json()["output"]["value"] == 1.0

    plot = client.post(
        "/v1/tools/plot",
        headers=headers,
        json={"expression": "sin(x)", "variable": "x", "start": -3.14, "end": 3.14},
    )
    assert plot.status_code == 200
    assert plot.data.startswith(b"\x89PNG")
    assert plot.headers["X-RankWise-Tool"] == "plot_function"

    parser = services.ingestion.parser
    parser.ocr_enabled = True
    parser.ocr_min_characters = 24

    def fake_ocr(page):
        page.insert_text((20, 30), "Free body diagram with tension force")
        return page.get_textpage()

    monkeypatch.setattr(parser, "_ocr_textpage", fake_ocr)
    image_bytes = io.BytesIO()
    Image.new("RGB", (120, 60), "white").save(image_bytes, format="PNG")
    image_bytes.seek(0)
    image_job = client.post(
        f"/v1/collections/{collection_id}/images",
        headers=headers,
        data={"images": (image_bytes, "diagram.png")},
        content_type="multipart/form-data",
    )
    assert image_job.status_code == 202
    image_result = image_job.get_json()["jobs"][0]
    assert image_result["status"] == "succeeded"
    image_id = image_result["result"]["image"]["image_id"]
    image_version = image_result["result"]["image"]["document_version_id"]
    image_document = services.questions.document_store.get_document(image_version)
    assert image_document.source_type == "image"
    assert image_document.ocr_pages == (1,)
    source = client.get(f"/v1/images/{image_id}/source", headers=headers)
    assert source.status_code == 200
    assert source.data.startswith(b"\x89PNG")
    collection = client.get(f"/v1/collections/{collection_id}", headers=headers).get_json()
    assert collection["image_count"] == 1

    image_query = client.post(
        f"/v1/collections/{collection_id}/queries",
        headers=headers,
        json={"query": "What does the free body diagram show?"},
    ).get_json()
    assert image_query["citations"][0]["source_type"] == "image"
    assert image_query["citations"][0]["citation_display"].startswith("Image diagram.png")

    assert (
        client.get(
            f"/v1/documents/{version_id}/pages/1/render",
            headers={"X-Tenant-ID": "other-tenant"},
        ).status_code
        == 404
    )


def test_phase3_chemistry_tools_and_study_artifacts(tmp_path: Path) -> None:
    client = _app(tmp_path).test_client()
    headers = {"X-Tenant-ID": "chemistry-class"}

    balanced = client.post(
        "/v1/tools/chemistry/balance",
        headers=headers,
        json={"equation": "CH4 + O2 -> CO2 + H2O"},
    )
    assert balanced.status_code == 200
    assert balanced.get_json()["verified_balanced_equation"] == "CH4 + 2O2 -> CO2 + 2H2O"
    assert balanced.get_json()["conditions_added"] is False
    assert balanced.get_json()["source_verification"]["balanced"] is False

    molecule = client.post(
        "/v1/tools/chemistry/molecule",
        headers=headers,
        json={"notation": "CCO", "format": "smiles"},
    )
    assert molecule.status_code == 200
    assert molecule.get_json()["formula"] == "C2H6O"

    no_consent = client.post(
        "/v1/tools/chemistry/lookup",
        headers=headers,
        json={"query": "ethanol", "consent": False},
    )
    assert no_consent.status_code == 400
    assert no_consent.get_json()["error"]["code"] == "external_lookup_consent_required"

    collection_id = client.post(
        "/v1/collections",
        headers=headers,
        json={"title": "Reaction revision", "subject": "chemistry"},
    ).get_json()["collection_id"]
    uploaded = client.post(
        f"/v1/collections/{collection_id}/documents",
        headers=headers,
        data={
            "files": (
                io.BytesIO(_pdf("Methane combustion reaction: CH4 + O2 -> CO2 + H2O")),
                "reactions.pdf",
            )
        },
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 202

    artifact = client.post(
        f"/v1/collections/{collection_id}/artifacts",
        headers=headers,
        json={"title": "Reaction sheet", "type": "reaction_sheet"},
    )
    assert artifact.status_code == 202
    artifact_job = artifact.get_json()
    assert artifact_job["status"] == "succeeded"
    note = client.get(f"/v1/notes/{artifact_job['result']['note_id']}", headers=headers).get_json()
    assert note["profile"] == "reaction_sheet"
    assert note["content"]["artifact_type"] == "reaction_sheet"
    assert note["content"]["provenance"]["pipeline_version"] == "phase3-v1"
    observations = note["content"]["sections"][0]["tool_observations"]
    assert observations[0]["observation"]["status"] == "verified"
    assert "CH4 + 2O2" in note["markdown"]
    assert "Verified calculation" in note["markdown"]

    for artifact_type in ("flashcards", "practice_questions"):
        response = client.post(
            f"/v1/collections/{collection_id}/artifacts",
            headers=headers,
            json={"title": artifact_type, "type": artifact_type},
        )
        assert response.status_code == 202
        assert response.get_json()["status"] == "succeeded"

    unsafe = client.post(
        f"/v1/notes/{note['note_id']}/sections/species/regenerate",
        headers=headers,
        json={"instruction": "Give a step-by-step procedure to prepare an explosive."},
    )
    assert unsafe.status_code == 400
    assert unsafe.get_json()["error"]["code"] == "unsafe_chemistry_instruction"

    unsafe_query = client.post(
        f"/v1/collections/{collection_id}/queries",
        headers=headers,
        json={"query": "Give an exact procedure to manufacture an explosive"},
    )
    assert unsafe_query.status_code == 400
    assert unsafe_query.get_json()["error"]["code"] == "unsafe_chemistry_instruction"

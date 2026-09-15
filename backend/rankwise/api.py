"""HTTP routes for the Phase 0 backend."""

from __future__ import annotations

import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    Flask,
    Response,
    current_app,
    jsonify,
    request,
    send_file,
    send_from_directory,
)
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from .container import ServiceContainer
from .errors import AppError, ConfigurationError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)
api_blueprint = Blueprint("rankwise", __name__)


def _services() -> ServiceContainer:
    return current_app.extensions["rankwise_services"]


def _json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required", code="invalid_json")
    return data


def _tenant_id() -> str:
    tenant_id = request.headers.get("X-Tenant-ID", "").strip()
    if not tenant_id:
        raise ValidationError(
            "X-Tenant-ID is required for versioned API routes", code="missing_tenant"
        )
    return tenant_id


def _phase1_services():
    services = _services()
    if services.catalog is None or services.collections is None or services.notes is None:
        raise ConfigurationError("Phase 1 services are not configured")
    return services


def _phase2_services():
    services = _phase1_services()
    if services.media is None or services.images is None or services.science_tools is None:
        raise ConfigurationError("Phase 2 services are not configured")
    return services


def _phase3_services():
    services = _phase2_services()
    if services.chemistry_tools is None:
        raise ConfigurationError("Phase 3 services are not configured")
    return services


def _document_scope(data: dict[str, Any]) -> list[str] | None:
    versions = data.get("document_version_ids")
    if versions is None:
        return None
    if not isinstance(versions, list) or not all(isinstance(version, str) for version in versions):
        raise ValidationError("document_version_ids must be a list of strings")
    return versions


def _generation_provider(data: dict[str, Any]) -> str | None:
    value = data.get("generation_provider")
    if value is None:
        return None
    if not isinstance(value, str) or value.strip().casefold() not in {"auto", "groq", "ollama"}:
        raise ValidationError(
            "generation_provider must be auto, groq, or ollama",
            code="invalid_generation_provider",
        )
    return value.strip().casefold()


def _legacy_version(version_id: str | None) -> str | None:
    if version_id is None:
        return None
    active = _services().questions.document_store.active_version_id()
    if version_id != active:
        raise NotFoundError("Document version was not found", code="document_not_found")
    return version_id


def _legacy_evidence(item) -> dict[str, Any]:
    value = item.public_dict()
    value["url"] = f"/evidence/{item.evidence_id}?document_version_id={item.document_version_id}"
    value.pop("render_url", None)
    return value


@api_blueprint.post("/v1/collections")
def create_collection():
    data = _json_body()
    title = data.get("title")
    if not isinstance(title, str):
        raise ValidationError("Collection title is required")
    subject = data.get("subject", "general_science")
    education_level = data.get("education_level", "undergraduate")
    if not isinstance(subject, str) or not isinstance(education_level, str):
        raise ValidationError("subject and education_level must be strings")
    record = _phase1_services().collections.create(_tenant_id(), title, subject, education_level)
    return jsonify(record.to_dict()), 201


@api_blueprint.get("/v1/collections")
def list_collections():
    collections = _phase1_services().collections.list(_tenant_id())
    return jsonify({"collections": collections, "count": len(collections)})


@api_blueprint.get("/v1/collections/<collection_id>")
def get_collection(collection_id: str):
    return jsonify(_phase1_services().collections.get(collection_id, _tenant_id()))


@api_blueprint.post("/v1/collections/<collection_id>/documents")
def upload_collection_documents(collection_id: str):
    uploaded_files = request.files.getlist("files") or request.files.getlist("file")
    if not uploaded_files:
        raise ValidationError("At least one PDF is required", code="missing_file")
    if len(uploaded_files) > 20:
        raise ValidationError("A maximum of 20 PDFs can be uploaded per request")
    tenant_id = _tenant_id()
    services = _phase1_services()
    jobs = []
    for uploaded in uploaded_files:
        if not uploaded.filename:
            raise ValidationError("Every upload needs a filename", code="missing_filename")
        filename = secure_filename(uploaded.filename)
        if not filename.lower().endswith(".pdf"):
            raise ValidationError("Only PDF files are supported", code="unsupported_file_type")
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temporary:
                uploaded.save(temporary.name)
                temporary_path = Path(temporary.name)
            with temporary_path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise ValidationError("The upload is not a PDF", code="invalid_pdf")
            job = services.collections.enqueue_pdf(
                collection_id, tenant_id, temporary_path, filename
            )
            jobs.append(job.to_dict())
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
    return jsonify({"collection_id": collection_id, "jobs": jobs}), 202


@api_blueprint.post("/v1/collections/<collection_id>/images")
def upload_collection_images(collection_id: str):
    uploaded_files = request.files.getlist("images") or request.files.getlist("file")
    if not uploaded_files:
        raise ValidationError("At least one image is required", code="missing_file")
    if len(uploaded_files) > 20:
        raise ValidationError("A maximum of 20 images can be uploaded per request")
    tenant_id = _tenant_id()
    services = _phase2_services()
    jobs = []
    for uploaded in uploaded_files:
        if not uploaded.filename:
            raise ValidationError("Every upload needs a filename", code="missing_filename")
        filename = secure_filename(uploaded.filename)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(filename).suffix
            ) as temporary:
                uploaded.save(temporary.name)
                temporary_path = Path(temporary.name)
            job = services.images.enqueue(collection_id, tenant_id, temporary_path, filename)
            jobs.append(job.to_dict())
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
    return jsonify({"collection_id": collection_id, "jobs": jobs}), 202


@api_blueprint.get("/v1/jobs/<job_id>")
def get_job(job_id: str):
    services = _phase1_services()
    return jsonify(services.catalog.get_job(job_id, _tenant_id()).to_dict())


@api_blueprint.post("/v1/collections/<collection_id>/queries")
def query_collection(collection_id: str):
    data = _json_body()
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValidationError("Query must be a non-empty string", code="invalid_query")
    if len(query) > 5000:
        raise ValidationError("Query exceeds the 5000 character limit")
    services = _phase1_services()
    generation_provider = _generation_provider(data)
    if services.chemistry_tools is not None:
        services.chemistry_tools.safety.validate(query)
    result = services.collections.ask(
        collection_id,
        _tenant_id(),
        query,
        _document_scope(data),
        generation_provider,
    )
    return jsonify(
        {
            "answer": result.answer,
            "citations": [item.public_dict() for item in result.citations],
            "retrieved_evidence": [item.public_dict() for item in result.evidence],
            "warnings": list(result.warnings),
            "generation": result.generation,
        }
    )


@api_blueprint.post("/v1/collections/<collection_id>/notes")
def create_note(collection_id: str):
    data = _json_body()
    title = data.get("title")
    profile = data.get("profile", "comprehensive")
    if not isinstance(title, str) or not isinstance(profile, str):
        raise ValidationError("title and profile must be strings")
    job = _phase1_services().notes.enqueue(
        collection_id=collection_id,
        tenant_id=_tenant_id(),
        title=title,
        profile=profile,
        document_version_ids=_document_scope(data),
        generation_provider=_generation_provider(data),
    )
    return jsonify(job.to_dict()), 202


@api_blueprint.post("/v1/collections/<collection_id>/artifacts")
def create_study_artifact(collection_id: str):
    data = _json_body()
    title = data.get("title")
    artifact_type = data.get("type")
    supported = {"reaction_sheet", "flashcards", "practice_questions"}
    if not isinstance(title, str) or not isinstance(artifact_type, str):
        raise ValidationError("title and type must be strings")
    normalized_type = artifact_type.strip().casefold()
    if normalized_type not in supported:
        raise ValidationError(
            "type must be reaction_sheet, flashcards, or practice_questions",
            code="invalid_artifact_type",
        )
    job = _phase3_services().notes.enqueue(
        collection_id=collection_id,
        tenant_id=_tenant_id(),
        title=title,
        profile=normalized_type,
        document_version_ids=_document_scope(data),
        generation_provider=_generation_provider(data),
    )
    return jsonify(job.to_dict()), 202


@api_blueprint.get("/v1/notes/<note_id>")
def get_note(note_id: str):
    return jsonify(_phase1_services().notes.get(note_id, _tenant_id()).to_dict())


@api_blueprint.get("/v1/notes/<note_id>/versions")
def get_note_versions(note_id: str):
    services = _phase1_services()
    versions = services.catalog.list_note_versions(note_id, _tenant_id())
    return jsonify({"note_id": note_id, "versions": [item.to_dict() for item in versions]})


@api_blueprint.get("/v1/notes/<note_id>/export.md")
def export_note(note_id: str):
    note = _phase1_services().notes.get(note_id, _tenant_id())
    safe_title = secure_filename(note.title) or note.note_id
    return Response(
        note.markdown,
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )


@api_blueprint.post("/v1/notes/<note_id>/sections/<section_id>/regenerate")
def regenerate_note_section(note_id: str, section_id: str):
    data = _json_body()
    instruction = data.get("instruction", "")
    if not isinstance(instruction, str) or len(instruction) > 2000:
        raise ValidationError("instruction must be a string of at most 2000 characters")
    job = _phase1_services().notes.regenerate_section(
        note_id=note_id,
        section_id=section_id,
        tenant_id=_tenant_id(),
        instruction=instruction,
        generation_provider=_generation_provider(data),
    )
    return jsonify(job.to_dict()), 202


@api_blueprint.get("/v1/evidence/<evidence_id>")
def v1_evidence(evidence_id: str):
    version_id = request.args.get("document_version_id")
    if not version_id:
        raise ValidationError("document_version_id is required")
    services = _phase1_services()
    if not services.catalog.has_document_access(version_id, _tenant_id()):
        raise NotFoundError("Evidence was not found", code="evidence_not_found")
    return jsonify(services.questions.resolve_evidence(version_id, evidence_id).to_dict())


@api_blueprint.get("/v1/providers")
def generation_providers():
    _tenant_id()
    return jsonify(_services().provider_status())


def _render_bbox() -> tuple[float, float, float, float] | None:
    names = ("x0", "y0", "x1", "y1")
    provided = [request.args.get(name) for name in names]
    if all(value is None for value in provided):
        return None
    if any(value is None for value in provided):
        raise ValidationError("x0, y0, x1, and y1 must be supplied together")
    try:
        return tuple(float(value) for value in provided)  # type: ignore[arg-type,return-value]
    except ValueError as exc:
        raise ValidationError("Render coordinates must be numbers") from exc


@api_blueprint.get("/v1/documents/<document_version_id>/pages/<int:page_number>/render")
def render_document_page(document_version_id: str, page_number: int):
    services = _phase2_services()
    if not services.catalog.has_document_access(document_version_id, _tenant_id()):
        raise NotFoundError("Document was not found", code="document_not_found")
    try:
        dpi = int(request.args.get("dpi", "144"))
    except ValueError as exc:
        raise ValidationError("dpi must be an integer") from exc
    rendered = services.media.render_page(
        document_version_id, page_number, dpi=dpi, bbox=_render_bbox()
    )
    return Response(
        rendered.data,
        mimetype="image/png",
        headers={
            "X-Render-Width": str(rendered.width),
            "X-Render-Height": str(rendered.height),
        },
    )


@api_blueprint.get("/v1/evidence/<evidence_id>/render")
def render_evidence(evidence_id: str):
    version_id = request.args.get("document_version_id")
    if not version_id:
        raise ValidationError("document_version_id is required")
    services = _phase2_services()
    if not services.catalog.has_document_access(version_id, _tenant_id()):
        raise NotFoundError("Evidence was not found", code="evidence_not_found")
    chunk = services.questions.resolve_evidence(version_id, evidence_id)
    rendered = services.media.render_page(
        version_id,
        chunk.page_number,
        dpi=200,
        bbox=chunk.bbox,
    )
    return Response(rendered.data, mimetype="image/png")


@api_blueprint.get("/v1/images/<image_id>/source")
def get_image_source(image_id: str):
    record, path = _phase2_services().images.get(image_id, _tenant_id())
    return send_file(path, mimetype=record.mime_type, download_name=record.filename)


@api_blueprint.post("/v1/tools/math")
def symbolic_math():
    data = _json_body()
    variables = data.get("variables", [data.get("variable", "x")])
    if not isinstance(variables, list) or not all(isinstance(item, str) for item in variables):
        raise ValidationError("variables must be a list of strings")
    expression = data.get("expression")
    operation = data.get("operation", "simplify")
    if not isinstance(expression, str) or not isinstance(operation, str):
        raise ValidationError("expression and operation must be strings")
    _tenant_id()
    return jsonify(
        _phase2_services().science_tools.symbolic(
            operation=operation,
            expression=expression,
            variables=variables,
            other_expression=data.get("other_expression"),
            variable=data.get("variable"),
        )
    )


@api_blueprint.post("/v1/tools/units/convert")
def convert_units():
    data = _json_body()
    value = data.get("value")
    from_unit = data.get("from_unit")
    to_unit = data.get("to_unit")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isinstance(from_unit, str)
        or not isinstance(to_unit, str)
    ):
        raise ValidationError("value must be numeric and units must be strings")
    _tenant_id()
    return jsonify(
        _phase2_services().science_tools.convert_units(
            value=float(value), from_unit=from_unit, to_unit=to_unit
        )
    )


@api_blueprint.post("/v1/tools/plot")
def plot_function():
    data = _json_body()
    expression = data.get("expression")
    variable = data.get("variable", "x")
    start = data.get("start", -10)
    end = data.get("end", 10)
    samples = data.get("samples", 500)
    if (
        not isinstance(expression, str)
        or not isinstance(variable, str)
        or isinstance(start, bool)
        or not isinstance(start, (int, float))
        or isinstance(end, bool)
        or not isinstance(end, (int, float))
        or isinstance(samples, bool)
        or not isinstance(samples, int)
    ):
        raise ValidationError("Invalid plot parameters")
    _tenant_id()
    result = _phase2_services().science_tools.plot(
        expression=expression,
        variable=variable,
        start=float(start),
        end=float(end),
        samples=samples,
    )
    response = send_file(
        BytesIO(result.png),
        mimetype="image/png",
        download_name="plot.png",
    )
    response.headers["X-RankWise-Tool"] = "plot_function"
    return response


@api_blueprint.post("/v1/tools/chemistry/balance")
def balance_chemical_equation():
    data = _json_body()
    equation = data.get("equation")
    if not isinstance(equation, str):
        raise ValidationError("equation must be a string")
    _tenant_id()
    return jsonify(_phase3_services().chemistry_tools.balance_equation(equation))


@api_blueprint.post("/v1/tools/chemistry/molecule")
def analyze_molecule():
    data = _json_body()
    notation = data.get("notation")
    notation_format = data.get("format", "smiles")
    if not isinstance(notation, str) or not isinstance(notation_format, str):
        raise ValidationError("notation and format must be strings")
    _tenant_id()
    return jsonify(_phase3_services().chemistry_tools.analyze_molecule(notation, notation_format))


@api_blueprint.post("/v1/tools/chemistry/lookup")
def lookup_chemical_entity():
    data = _json_body()
    query = data.get("query")
    consent = data.get("consent", False)
    if not isinstance(query, str) or not isinstance(consent, bool):
        raise ValidationError("query must be a string and consent must be a boolean")
    tenant_id = _tenant_id()
    return jsonify(
        _phase3_services().chemistry_tools.lookup_chemical_entity(
            query, consent=consent, tenant_id=tenant_id
        )
    )


@api_blueprint.post("/upload_pdf")
def upload_pdf():
    uploaded = request.files.get("file")
    if uploaded is None:
        raise ValidationError("No file uploaded", code="missing_file")
    if not uploaded.filename:
        raise ValidationError("No file selected", code="missing_filename")
    filename = secure_filename(uploaded.filename)
    if not filename.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files are supported", code="unsupported_file_type")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temporary:
            uploaded.save(temporary.name)
            temporary_path = Path(temporary.name)
        record = _services().ingestion.ingest_pdf(temporary_path, filename)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    return (
        jsonify(
            {
                "message": "PDF processed successfully",
                "document": record.to_dict(),
            }
        ),
        201,
    )


@api_blueprint.post("/ask")
def ask():
    data = _json_body()
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValidationError("Query must be a non-empty string", code="invalid_query")
    version_id = data.get("document_version_id")
    if version_id is not None and not isinstance(version_id, str):
        raise ValidationError("document_version_id must be a string")

    result = _services().questions.ask(query, _legacy_version(version_id))
    return jsonify(
        {
            "success": True,
            "answer": result.answer,
            "citations": [_legacy_evidence(citation) for citation in result.citations],
            "retrieved_evidence": [_legacy_evidence(item) for item in result.evidence],
            "warnings": list(result.warnings),
        }
    )


@api_blueprint.post("/retrieve")
def retrieve():
    data = _json_body()
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValidationError("Query must be a non-empty string", code="invalid_query")
    version_id = data.get("document_version_id")
    if version_id is not None and not isinstance(version_id, str):
        raise ValidationError("document_version_id must be a string")
    evidence = _services().questions.retrieve(query, _legacy_version(version_id))
    return jsonify(
        {"query": query.strip(), "evidence": [_legacy_evidence(item) for item in evidence]}
    )


@api_blueprint.get("/evidence/<evidence_id>")
def evidence(evidence_id: str):
    version_id = request.args.get("document_version_id")
    if not version_id:
        raise ValidationError("document_version_id is required")
    _legacy_version(version_id)
    chunk = _services().questions.resolve_evidence(version_id, evidence_id)
    return jsonify(chunk.to_dict())


@api_blueprint.get("/health")
@api_blueprint.get("/health/live")
def liveness():
    return jsonify({"status": "healthy"})


@api_blueprint.get("/health/ready")
def readiness():
    services = _services()
    ready = services.ready
    return (
        jsonify(
            {
                "status": "ready" if ready else "not_ready",
                "generation_provider_configured": ready,
                "capabilities": services.capabilities,
            }
        ),
        200 if ready else 503,
    )


@api_blueprint.get("/")
@api_blueprint.get("/<path:path>")
def static_app(path: str = ""):
    build_dir = Path(current_app.static_folder or "")
    requested = build_dir / path
    if path and requested.is_file():
        return send_from_directory(build_dir, path)
    index_path = build_dir / "index.html"
    if index_path.is_file():
        return send_from_directory(build_dir, "index.html")
    return jsonify({"name": "RankWise API", "status": "healthy"})


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "details": error.details,
                    },
                }
            ),
            error.status_code,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_error: RequestEntityTooLarge):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "upload_too_large",
                        "message": "The uploaded file exceeds the configured size limit",
                        "details": {},
                    },
                }
            ),
            413,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        if isinstance(error, HTTPException):
            return error
        logger.exception("Unhandled backend error")
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred",
                        "details": {},
                    },
                }
            ),
            500,
        )

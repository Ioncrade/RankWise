import type {
  Collection,
  Evidence,
  EvidenceChunk,
  GenerationProvider,
  Health,
  Job,
  NoteProfile,
  NoteVersion,
  QueryResponse,
  ToolResult,
} from "@/api/types";
import type { ProviderStatusResponse } from "@/api/types";

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  message?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, payload: ErrorEnvelope) {
    super(
      payload.error?.message ??
        payload.message ??
        `Request failed with status ${status}`,
    );
    this.name = "ApiError";
    this.status = status;
    this.code = payload.error?.code ?? "request_failed";
    this.details = payload.error?.details ?? {};
  }
}

function sleep(duration: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(resolve, duration);
    signal?.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout);
        reject(new DOMException("Request aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export class RankWiseApi {
  readonly baseUrl: string;
  readonly tenantId: string;

  constructor(
    tenantId: string,
    baseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
  ) {
    this.tenantId = tenantId;
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private headers(json = true): HeadersInit {
    return {
      ...(json ? { "Content-Type": "application/json" } : {}),
      "X-Tenant-ID": this.tenantId,
    };
  }

  private async parseError(response: Response): Promise<never> {
    let payload: ErrorEnvelope = {};
    try {
      payload = (await response.json()) as ErrorEnvelope;
    } catch {
      payload = { message: response.statusText };
    }
    throw new ApiError(response.status, payload);
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, init);
    if (!response.ok) await this.parseError(response);
    return (await response.json()) as T;
  }

  private post<T>(
    path: string,
    body: Record<string, unknown>,
    signal?: AbortSignal,
  ) {
    return this.request<T>(path, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(body),
      signal,
    });
  }

  async health() {
    const response = await fetch(`${this.baseUrl}/health/ready`);
    const payload = (await response.json()) as Health;
    return { ...payload, httpStatus: response.status };
  }

  listCollections(signal?: AbortSignal) {
    return this.request<{ collections: Collection[]; count: number }>(
      "/v1/collections",
      {
        headers: this.headers(false),
        signal,
      },
    );
  }

  getCollection(collectionId: string, signal?: AbortSignal) {
    return this.request<Collection>(`/v1/collections/${collectionId}`, {
      headers: this.headers(false),
      signal,
    });
  }

  providers(signal?: AbortSignal) {
    return this.request<ProviderStatusResponse>("/v1/providers", {
      headers: this.headers(false),
      signal,
    });
  }

  createCollection(body: {
    title: string;
    subject: string;
    education_level: string;
  }) {
    return this.post<Collection>("/v1/collections", body);
  }

  private async upload(path: string, field: string, files: File[]) {
    const data = new FormData();
    files.forEach((file) => data.append(field, file));
    return this.request<{ collection_id: string; jobs: Job[] }>(path, {
      method: "POST",
      headers: this.headers(false),
      body: data,
    });
  }

  uploadDocuments(collectionId: string, files: File[]) {
    return this.upload(
      `/v1/collections/${collectionId}/documents`,
      "files",
      files,
    );
  }

  uploadImages(collectionId: string, files: File[]) {
    return this.upload(
      `/v1/collections/${collectionId}/images`,
      "images",
      files,
    );
  }

  queryCollection(
    collectionId: string,
    query: string,
    generationProvider: GenerationProvider = "auto",
    signal?: AbortSignal,
  ) {
    return this.post<QueryResponse>(
      `/v1/collections/${collectionId}/queries`,
      { query, generation_provider: generationProvider },
      signal,
    );
  }

  getJob(jobId: string, signal?: AbortSignal) {
    return this.request<Job>(`/v1/jobs/${jobId}`, {
      headers: this.headers(false),
      signal,
    });
  }

  async waitForJob(initial: Job, signal?: AbortSignal): Promise<Job> {
    let job = initial;
    for (let attempt = 0; attempt < 150; attempt += 1) {
      if (job.status === "succeeded") return job;
      if (job.status === "failed") {
        throw new ApiError(422, {
          error: {
            code: job.error?.code ?? "job_failed",
            message: job.error?.message ?? "Background job failed",
          },
        });
      }
      await sleep(800, signal);
      job = await this.getJob(job.job_id, signal);
    }
    throw new ApiError(408, {
      message: "The job did not finish within two minutes",
    });
  }

  async waitForJobs(jobs: Job[], signal?: AbortSignal) {
    return Promise.all(jobs.map((job) => this.waitForJob(job, signal)));
  }

  createNote(
    collectionId: string,
    body: {
      title: string;
      profile: NoteProfile;
      document_version_ids?: string[];
      generation_provider?: GenerationProvider;
    },
  ) {
    const artifactProfiles = new Set<NoteProfile>([
      "reaction_sheet",
      "flashcards",
      "practice_questions",
    ]);
    if (artifactProfiles.has(body.profile)) {
      return this.post<Job>(`/v1/collections/${collectionId}/artifacts`, {
        title: body.title,
        type: body.profile,
        document_version_ids: body.document_version_ids,
        generation_provider: body.generation_provider,
      });
    }
    return this.post<Job>(`/v1/collections/${collectionId}/notes`, body);
  }

  getNote(noteId: string, signal?: AbortSignal) {
    return this.request<NoteVersion>(`/v1/notes/${noteId}`, {
      headers: this.headers(false),
      signal,
    });
  }

  listNoteVersions(noteId: string) {
    return this.request<{ note_id: string; versions: NoteVersion[] }>(
      `/v1/notes/${noteId}/versions`,
      { headers: this.headers(false) },
    );
  }

  regenerateNoteSection(
    noteId: string,
    sectionId: string,
    instruction: string,
    generationProvider: GenerationProvider = "auto",
  ) {
    return this.post<Job>(
      `/v1/notes/${noteId}/sections/${sectionId}/regenerate`,
      {
        instruction,
        generation_provider: generationProvider,
      },
    );
  }

  async exportNote(noteId: string) {
    const response = await fetch(
      `${this.baseUrl}/v1/notes/${noteId}/export.md`,
      {
        headers: this.headers(false),
      },
    );
    if (!response.ok) await this.parseError(response);
    return response.blob();
  }

  resolveEvidence(evidenceId: string, documentVersionId: string) {
    const query = new URLSearchParams({
      document_version_id: documentVersionId,
    });
    return this.request<EvidenceChunk>(`/v1/evidence/${evidenceId}?${query}`, {
      headers: this.headers(false),
    });
  }

  async renderEvidence(evidence: Pick<Evidence, "render_url">) {
    const response = await fetch(`${this.baseUrl}${evidence.render_url}`, {
      headers: this.headers(false),
    });
    if (!response.ok) await this.parseError(response);
    return response.blob();
  }

  symbolicMath(body: Record<string, unknown>) {
    return this.post<ToolResult>("/v1/tools/math", body);
  }

  convertUnits(body: { value: number; from_unit: string; to_unit: string }) {
    return this.post<ToolResult>("/v1/tools/units/convert", body);
  }

  async plot(body: Record<string, unknown>) {
    const response = await fetch(`${this.baseUrl}/v1/tools/plot`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(body),
    });
    if (!response.ok) await this.parseError(response);
    return response.blob();
  }

  balanceEquation(equation: string) {
    return this.post<ToolResult>("/v1/tools/chemistry/balance", { equation });
  }

  analyzeMolecule(notation: string, format: "smiles" | "inchi") {
    return this.post<ToolResult>("/v1/tools/chemistry/molecule", {
      notation,
      format,
    });
  }

  lookupChemical(query: string, consent: boolean) {
    return this.post<ToolResult>("/v1/tools/chemistry/lookup", {
      query,
      consent,
    });
  }
}

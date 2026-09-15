export type CapabilityMap = {
  generation: boolean;
  ocr: boolean;
  symbolic_math: boolean;
  unit_conversion: boolean;
  plotting: boolean;
  page_rendering: boolean;
  reaction_balancing: boolean;
  molecule_analysis: boolean;
  external_chemical_lookup: boolean;
};

export type Health = {
  status: "ready" | "not_ready";
  generation_provider_configured: boolean;
  capabilities: CapabilityMap;
};

export type GenerationProvider = "auto" | "groq" | "ollama";

export type ProviderStatus = {
  configured: boolean;
  reachable: boolean | null;
  model: string | null;
  model_available?: boolean;
  base_url_is_local?: boolean;
};

export type ProviderStatusResponse = {
  default: GenerationProvider;
  providers: Partial<
    Record<Exclude<GenerationProvider, "auto">, ProviderStatus>
  >;
};

export type GenerationMetadata = {
  requested_provider: GenerationProvider;
  provider_used?: "groq" | "ollama";
  model?: string | null;
  fallback?: boolean;
  fallback_reason?: string;
};

export type DocumentRecord = {
  document_id: string;
  document_version_id: string;
  filename: string;
  sha256: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
  parser_version: string;
  embedding_model: string;
  ocr_pages: number[];
  warnings: string[];
  content_counts: Record<string, number>;
  source_type: "pdf" | "image";
};

export type ImageRecord = {
  image_id: string;
  collection_id: string;
  filename: string;
  mime_type: string;
  sha256: string;
  document_version_id: string;
  warnings: string[];
  created_at: string;
};

export type Collection = {
  collection_id: string;
  tenant_id: string;
  title: string;
  subject: string;
  education_level: string;
  created_at: string;
  documents?: DocumentRecord[];
  document_count?: number;
  images?: ImageRecord[];
  image_count?: number;
};

export type Job = {
  job_id: string;
  tenant_id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed";
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: { code?: string; message?: string } | null;
  created_at: string;
  updated_at: string;
};

export type Evidence = {
  label: string;
  evidence_id: string;
  document_id: string;
  document_version_id: string;
  page_id: string;
  page_number: number;
  text: string;
  retrieval_score: number;
  reranker_score: number;
  content_type: string;
  extraction_method: string;
  bbox: [number, number, number, number] | null;
  document_filename: string | null;
  source_type: "pdf" | "image";
  citation_display: string;
  url: string;
  render_url: string;
};

export type EvidenceChunk = {
  chunk_id: string;
  evidence_id: string;
  document_id: string;
  document_version_id: string;
  page_id: string;
  page_number: number;
  char_start: number;
  char_end: number;
  text: string;
  content_type: string;
  extraction_method: string;
  bbox: [number, number, number, number] | null;
};

export type QueryResponse = {
  answer: string;
  citations: Evidence[];
  retrieved_evidence: Evidence[];
  warnings: string[];
  generation?: GenerationMetadata;
};

export type NoteSection = {
  section_id: string;
  heading: string;
  markdown: string;
  citations: string[];
  warnings: string[];
  tool_observations: Array<Record<string, unknown>>;
};

export type NoteVersion = {
  note_id: string;
  note_version_id: string;
  collection_id: string;
  title: string;
  profile: NoteProfile;
  markdown: string;
  content: {
    schema_version: string;
    title: string;
    artifact_type?: string;
    sections: NoteSection[];
    unresolved_items: string[];
    provenance: {
      pipeline_version: string;
      generated_at: string;
      generation?: GenerationMetadata[];
    };
    scope: {
      collection_id: string;
      document_version_ids: string[];
      sources: DocumentRecord[];
    };
  };
  citations: Evidence[];
  document_version_ids: string[];
  warnings: string[];
  change_reason: string;
  created_at: string;
};

export type NoteProfile =
  | "comprehensive"
  | "concise"
  | "formula_sheet"
  | "reaction_sheet"
  | "flashcards"
  | "practice_questions";

export type SavedNote = {
  note_id: string;
  collection_id: string;
  title: string;
  profile: NoteProfile;
  created_at: string;
};

export type ToolResult = Record<string, unknown>;

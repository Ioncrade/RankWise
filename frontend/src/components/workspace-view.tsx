import {
  ArrowUp,
  FileImage,
  FileText,
  ImagePlus,
  Layers3,
  Paperclip,
  Sparkles,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { RankWiseApi } from "@/api/client";
import type {
  Collection,
  Evidence,
  GenerationProvider,
  QueryResponse,
} from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";

type WorkspaceViewProps = {
  api: RankWiseApi;
  collection: Collection;
  generationReady: boolean;
  generationProvider: GenerationProvider;
  onRefresh: () => Promise<void>;
  onPreviewEvidence: (evidence: Evidence) => void;
};

type AnswerEntry = QueryResponse & { question: string };

export function WorkspaceView({
  api,
  collection,
  generationReady,
  generationProvider,
  onRefresh,
  onPreviewEvidence,
}: WorkspaceViewProps) {
  const pdfInput = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<"pdf" | "image" | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answers, setAnswers] = useState<AnswerEntry[]>([]);

  const uploadFiles = async (kind: "pdf" | "image", files: FileList | null) => {
    if (!files?.length) return;
    const selected = Array.from(files).slice(0, 20);
    setUploading(kind);
    try {
      const response =
        kind === "pdf"
          ? await api.uploadDocuments(collection.collection_id, selected)
          : await api.uploadImages(collection.collection_id, selected);
      await api.waitForJobs(response.jobs);
      await onRefresh();
      toast.success(
        `${selected.length} ${kind === "pdf" ? "document" : "image"} source(s) ready`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(null);
      if (pdfInput.current) pdfInput.current.value = "";
      if (imageInput.current) imageInput.current.value = "";
    }
  };

  const ask = async (event: FormEvent) => {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt) return;
    setAsking(true);
    try {
      const result = await api.queryCollection(
        collection.collection_id,
        prompt,
        generationProvider,
      );
      setAnswers((current) => [{ ...result, question: prompt }, ...current]);
      setQuestion("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Question failed");
    } finally {
      setAsking(false);
    }
  };

  const documents = collection.documents ?? [];
  const images = collection.images ?? [];

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-5">
        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-[#fbfbfa]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle>Ask your sources</CardTitle>
                <CardDescription className="mt-1">
                  Answers include evidence that resolves to the exact page or
                  image region.
                </CardDescription>
              </div>
              <Badge variant={generationReady ? "success" : "warning"}>
                {generationReady ? "Generation ready" : "Provider required"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-5">
            <form onSubmit={ask}>
              <div className="relative">
                <Textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder={
                    generationReady
                      ? "Ask for an explanation, comparison, derivation, or source detail…"
                      : "Configure the generation provider to ask questions"
                  }
                  className="min-h-28 pb-12 pr-14"
                  maxLength={5000}
                  disabled={
                    asking || documents.length === 0 || !generationReady
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <div className="absolute bottom-3 left-3 text-xs text-muted-foreground">
                  {documents.length} source{documents.length === 1 ? "" : "s"} ·
                  Shift + Enter for a new line
                </div>
                <Button
                  type="submit"
                  size="icon"
                  className="absolute bottom-2.5 right-2.5 rounded-lg"
                  disabled={
                    asking ||
                    !question.trim() ||
                    documents.length === 0 ||
                    !generationReady
                  }
                  aria-label="Ask question"
                >
                  {asking ? <Spinner /> : <ArrowUp />}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {answers.length === 0 ? (
          <div className="grid min-h-64 place-items-center rounded-xl border border-dashed bg-white/40 px-6 text-center">
            <div className="max-w-sm">
              <div className="mx-auto mb-3 grid size-10 place-items-center rounded-lg bg-accent text-accent-foreground">
                <Sparkles className="size-5" />
              </div>
              <h3 className="text-sm font-semibold">
                A clean slate for careful questions
              </h3>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Ask across all documents in this collection. The backend handles
                hybrid retrieval, reranking, and citation validation.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {answers.map((entry, index) => (
              <Card key={`${entry.question}-${index}`}>
                <CardHeader className="pb-3">
                  <div className="text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">
                    Question
                  </div>
                  <CardTitle className="text-base leading-6">
                    {entry.question}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap text-[15px] leading-7 text-[#34383f]">
                    {entry.answer}
                  </p>
                  {entry.generation?.provider_used && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      Answered by{" "}
                      <span className="font-medium">
                        {entry.generation.provider_used}
                      </span>
                      {entry.generation.model
                        ? ` · ${entry.generation.model}`
                        : ""}
                      {entry.generation.fallback &&
                      entry.generation.fallback_reason
                        ? ` · fallback: ${entry.generation.fallback_reason.replaceAll("_", " ")}`
                        : ""}
                    </p>
                  )}
                  {entry.citations.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2 border-t pt-4">
                      {entry.citations.map((citation) => (
                        <button
                          key={citation.evidence_id}
                          onClick={() => onPreviewEvidence(citation)}
                          className="inline-flex items-center gap-1.5 rounded-md border bg-white px-2.5 py-1.5 text-xs font-medium text-[#4e535b] hover:border-[#b7bac1] hover:text-foreground"
                        >
                          {citation.source_type === "image" ? (
                            <FileImage className="size-3.5" />
                          ) : (
                            <FileText className="size-3.5" />
                          )}
                          {citation.citation_display}
                        </button>
                      ))}
                    </div>
                  )}
                  {entry.warnings.map((warning) => (
                    <p
                      key={warning}
                      className="mt-3 text-xs leading-5 text-amber-700"
                    >
                      {warning}
                    </p>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Layers3 className="size-4 text-muted-foreground" /> Sources
            </CardTitle>
            <CardDescription>
              PDFs, scans, diagrams, and reference images in this collection.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              <input
                ref={pdfInput}
                type="file"
                accept="application/pdf,.pdf"
                multiple
                className="hidden"
                onChange={(event) =>
                  void uploadFiles("pdf", event.target.files)
                }
              />
              <input
                ref={imageInput}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/tiff"
                multiple
                className="hidden"
                onChange={(event) =>
                  void uploadFiles("image", event.target.files)
                }
              />
              <Button
                variant="outline"
                className="justify-start"
                disabled={uploading !== null}
                onClick={() => pdfInput.current?.click()}
              >
                {uploading === "pdf" ? <Spinner /> : <Paperclip />} Add PDFs
              </Button>
              <Button
                variant="outline"
                className="justify-start"
                disabled={uploading !== null}
                onClick={() => imageInput.current?.click()}
              >
                {uploading === "image" ? <Spinner /> : <ImagePlus />} Add images
              </Button>
            </div>

            <div className="mt-4 divide-y">
              {documents.length === 0 && (
                <div className="py-7 text-center text-xs leading-5 text-muted-foreground">
                  Upload up to 20 sources at a time to begin.
                </div>
              )}
              {documents.map((document) => (
                <div
                  key={document.document_version_id}
                  className="flex items-start gap-3 py-3"
                >
                  <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
                    {document.source_type === "image" ? (
                      <FileImage className="size-4" />
                    ) : (
                      <FileText className="size-4" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div
                      className="truncate text-sm font-medium"
                      title={document.filename}
                    >
                      {document.filename}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {document.page_count} page
                      {document.page_count === 1 ? "" : "s"} ·{" "}
                      {formatDate(document.created_at)}
                    </div>
                    {document.ocr_pages.length > 0 && (
                      <Badge variant="outline" className="mt-1.5 text-[10px]">
                        OCR · {document.ocr_pages.length} page
                        {document.ocr_pages.length === 1 ? "" : "s"}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-3 divide-x rounded-xl border bg-white py-4 text-center">
          <div>
            <div className="text-lg font-semibold">{documents.length}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Sources
            </div>
          </div>
          <div>
            <div className="text-lg font-semibold">
              {documents.reduce(
                (total, document) => total + document.page_count,
                0,
              )}
            </div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Pages
            </div>
          </div>
          <div>
            <div className="text-lg font-semibold">{images.length}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Images
            </div>
          </div>
        </div>

        {uploading && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
            Processing {uploading} sources. OCR and indexing may take a moment.
          </div>
        )}
      </div>
    </div>
  );
}

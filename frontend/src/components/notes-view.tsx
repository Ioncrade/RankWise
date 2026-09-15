import {
  Download,
  FileCheck2,
  History,
  NotebookPen,
  RefreshCw,
  WandSparkles,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type MouseEvent,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { RankWiseApi } from "@/api/client";
import type {
  Collection,
  Evidence,
  GenerationProvider,
  NoteProfile,
  NoteVersion,
  SavedNote,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { cn, formatDate } from "@/lib/utils";

const PROFILES: Array<{
  value: NoteProfile;
  label: string;
  description: string;
}> = [
  {
    value: "comprehensive",
    label: "Comprehensive notes",
    description: "Full cited study guide",
  },
  {
    value: "concise",
    label: "Concise revision",
    description: "Fast review of key ideas",
  },
  {
    value: "formula_sheet",
    label: "Formula sheet",
    description: "Symbols, units, and checks",
  },
  {
    value: "reaction_sheet",
    label: "Reaction sheet",
    description: "Original and verified reactions",
  },
  {
    value: "flashcards",
    label: "Flashcards",
    description: "Atomic front/back cards",
  },
  {
    value: "practice_questions",
    label: "Practice questions",
    description: "Questions with cited answers",
  },
];

type NotesViewProps = {
  api: RankWiseApi;
  collection: Collection;
  savedNotes: SavedNote[];
  generationReady: boolean;
  generationProvider: GenerationProvider;
  onSaveNote: (note: SavedNote) => void;
  onPreviewEvidence: (evidence: Evidence) => void;
};

export function NotesView({
  api,
  collection,
  savedNotes,
  generationReady,
  generationProvider,
  onSaveNote,
  onPreviewEvidence,
}: NotesViewProps) {
  const collectionNotes = useMemo(
    () =>
      savedNotes.filter(
        (note) => note.collection_id === collection.collection_id,
      ),
    [collection.collection_id, savedNotes],
  );
  const [selectedId, setSelectedId] = useState<string | null>(
    collectionNotes[0]?.note_id ?? null,
  );
  const [note, setNote] = useState<NoteVersion | null>(null);
  const [loadingNote, setLoadingNote] = useState(false);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [profile, setProfile] = useState<NoteProfile>("comprehensive");
  const [versionCount, setVersionCount] = useState(0);
  const [sectionId, setSectionId] = useState("");
  const [instruction, setInstruction] = useState("");
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    const first = collectionNotes[0]?.note_id ?? null;
    setSelectedId((current) =>
      current && collectionNotes.some((item) => item.note_id === current)
        ? current
        : first,
    );
  }, [collectionNotes]);

  useEffect(() => {
    if (!selectedId) {
      setNote(null);
      setVersionCount(0);
      return;
    }
    const controller = new AbortController();
    setLoadingNote(true);
    api
      .getNote(selectedId, controller.signal)
      .then((result) => {
        setNote(result);
        setSectionId(result.content.sections[0]?.section_id ?? "");
        return api.listNoteVersions(selectedId);
      })
      .then((result) => setVersionCount(result.versions.length))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        toast.error(
          error instanceof Error ? error.message : "Could not load artifact",
        );
      })
      .finally(() => setLoadingNote(false));
    return () => controller.abort();
  }, [api, selectedId]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    try {
      const initial = await api.createNote(collection.collection_id, {
        title: title.trim(),
        profile,
        generation_provider: generationProvider,
      });
      const job = await api.waitForJob(initial);
      const noteId = job.result?.note_id;
      if (typeof noteId !== "string")
        throw new Error("The note job returned no note ID");
      const result = await api.getNote(noteId);
      const saved: SavedNote = {
        note_id: result.note_id,
        collection_id: result.collection_id,
        title: result.title,
        profile: result.profile,
        created_at: result.created_at,
      };
      onSaveNote(saved);
      setSelectedId(result.note_id);
      setNote(result);
      setTitle("");
      toast.success("Study artifact generated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Generation failed");
    } finally {
      setCreating(false);
    }
  };

  const download = async () => {
    if (!note) return;
    try {
      const blob = await api.exportNote(note.note_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${note.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "notes"}.md`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    }
  };

  const regenerate = async (event: FormEvent) => {
    event.preventDefault();
    if (!note || !sectionId) return;
    setRegenerating(true);
    try {
      const initial = await api.regenerateNoteSection(
        note.note_id,
        sectionId,
        instruction.trim(),
        generationProvider,
      );
      await api.waitForJob(initial);
      const refreshed = await api.getNote(note.note_id);
      setNote(refreshed);
      setInstruction("");
      const versions = await api.listNoteVersions(note.note_id);
      setVersionCount(versions.versions.length);
      toast.success("Section regenerated as a new version");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Regeneration failed",
      );
    } finally {
      setRegenerating(false);
    }
  };

  const openMarkdownEvidence = async (
    event: MouseEvent<HTMLAnchorElement>,
    href?: string,
  ) => {
    if (!href?.startsWith("/v1/evidence/")) return;
    event.preventDefault();
    try {
      const url = new URL(href, window.location.origin);
      const evidenceId = url.pathname.split("/").at(-1);
      const versionId = url.searchParams.get("document_version_id");
      if (!evidenceId || !versionId)
        throw new Error("Citation link is incomplete");
      const citation = note?.citations.find(
        (item) =>
          item.evidence_id === evidenceId &&
          item.document_version_id === versionId,
      );
      if (!citation)
        throw new Error("Citation is not part of this note version");
      onPreviewEvidence(citation);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not open citation",
      );
    }
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <WandSparkles className="size-4 text-muted-foreground" /> Create
              artifact
            </CardTitle>
            <CardDescription>
              Generated only from the selected collection’s sources.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={create} className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="note-title">Title</Label>
                <Input
                  id="note-title"
                  value={title}
                  placeholder="Midterm revision"
                  onChange={(event) => setTitle(event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label>Format</Label>
                <Select
                  value={profile}
                  onValueChange={(value) => setProfile(value as NoteProfile)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PROFILES.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs leading-5 text-muted-foreground">
                  {PROFILES.find((item) => item.value === profile)?.description}
                </p>
              </div>
              {!generationReady && (
                <p className="rounded-md border border-amber-200 bg-amber-50 p-2.5 text-xs leading-5 text-amber-700">
                  Configure GROQ_API_KEY and GROQ_MODEL to generate artifacts.
                </p>
              )}
              <Button
                type="submit"
                disabled={
                  creating ||
                  !generationReady ||
                  !title.trim() ||
                  !(collection.documents?.length ?? 0)
                }
              >
                {creating ? <Spinner /> : <NotebookPen />} Generate
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Recent artifacts</CardTitle>
            <CardDescription>
              Saved in this browser for this API workspace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {collectionNotes.length === 0 && (
              <p className="py-5 text-center text-xs text-muted-foreground">
                Nothing generated yet.
              </p>
            )}
            {collectionNotes.map((item) => (
              <button
                key={item.note_id}
                onClick={() => setSelectedId(item.note_id)}
                className={cn(
                  "w-full rounded-lg px-3 py-2.5 text-left hover:bg-muted",
                  selectedId === item.note_id && "bg-muted",
                )}
              >
                <div className="truncate text-sm font-medium">{item.title}</div>
                <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                  <span>
                    {
                      PROFILES.find(
                        (profileItem) => profileItem.value === item.profile,
                      )?.label
                    }
                  </span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="min-h-[620px] min-w-0 overflow-hidden">
        {loadingNote ? (
          <div className="grid min-h-[620px] place-items-center">
            <Spinner className="size-5" />
          </div>
        ) : !note ? (
          <div className="grid min-h-[620px] place-items-center p-8 text-center">
            <div className="max-w-sm">
              <div className="mx-auto mb-3 grid size-10 place-items-center rounded-lg bg-muted text-muted-foreground">
                <FileCheck2 className="size-5" />
              </div>
              <h3 className="text-sm font-semibold">
                Your study artifacts live here
              </h3>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Choose a format and generate an immutable, cited artifact from
                the collection.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-start justify-between gap-4 border-b bg-[#fbfbfa] p-5">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-semibold tracking-tight">
                    {note.title}
                  </h2>
                  <Badge variant="outline">
                    {note.profile.replaceAll("_", " ")}
                  </Badge>
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <History className="size-3.5" /> {versionCount} version
                    {versionCount === 1 ? "" : "s"}
                  </span>
                  <span>{note.content.provenance.pipeline_version}</span>
                  {note.content.provenance.generation?.[0]?.provider_used && (
                    <span>
                      {note.content.provenance.generation[0].provider_used}
                    </span>
                  )}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void download()}
              >
                <Download /> Export Markdown
              </Button>
            </div>

            <div className="grid gap-5 p-5 2xl:grid-cols-[minmax(0,1fr)_280px]">
              <article className="prose-rankwise min-w-0">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children, ...props }) => (
                      <a
                        href={href}
                        {...props}
                        onClick={(event) =>
                          void openMarkdownEvidence(event, href)
                        }
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {note.markdown}
                </ReactMarkdown>
              </article>

              <aside className="h-fit rounded-lg border bg-[#fbfbfa] p-4">
                <div className="text-sm font-semibold">Refine one section</div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Creates a new immutable note version and preserves the rest.
                </p>
                <form onSubmit={regenerate} className="mt-4 grid gap-3">
                  <Select value={sectionId} onValueChange={setSectionId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Choose section" />
                    </SelectTrigger>
                    <SelectContent>
                      {note.content.sections.map((section) => (
                        <SelectItem
                          key={section.section_id}
                          value={section.section_id}
                        >
                          {section.heading}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Textarea
                    value={instruction}
                    maxLength={2000}
                    className="min-h-24 bg-white"
                    placeholder="Focus on common misconceptions…"
                    onChange={(event) => setInstruction(event.target.value)}
                  />
                  <Button
                    type="submit"
                    variant="outline"
                    disabled={regenerating || !sectionId || !generationReady}
                  >
                    {regenerating ? <Spinner /> : <RefreshCw />} Regenerate
                  </Button>
                </form>
              </aside>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

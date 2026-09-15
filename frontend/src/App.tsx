import {
  AlertTriangle,
  BookOpenCheck,
  Database,
  FlaskConical,
  LayoutDashboard,
} from "lucide-react";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Toaster, toast } from "sonner";

import { RankWiseApi } from "@/api/client";
import type {
  Collection,
  Evidence,
  GenerationProvider,
  Health,
  ProviderStatusResponse,
  SavedNote,
} from "@/api/types";
import { AppSidebar } from "@/components/app-sidebar";
import { EvidenceDialog } from "@/components/evidence-dialog";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkspaceView } from "@/components/workspace-view";

const NotesView = lazy(() =>
  import("@/components/notes-view").then((module) => ({
    default: module.NotesView,
  })),
);
const ToolsView = lazy(() =>
  import("@/components/tools-view").then((module) => ({
    default: module.ToolsView,
  })),
);

function LoadingView() {
  return (
    <div className="grid min-h-72 place-items-center rounded-xl border bg-white">
      <Spinner className="size-5" />
    </div>
  );
}

const DEFAULT_TENANT = "local-demo";
const NOTES_STORAGE_KEY = "rankwise.saved-notes.v1";
const PROVIDER_STORAGE_KEY = "rankwise.generation-provider.v1";

function readGenerationProvider(tenantId: string): GenerationProvider {
  const value = localStorage.getItem(`${PROVIDER_STORAGE_KEY}.${tenantId}`);
  return value === "groq" || value === "ollama" ? value : "auto";
}

function readSavedNotes(): SavedNote[] {
  try {
    const value = JSON.parse(
      localStorage.getItem(NOTES_STORAGE_KEY) ?? "[]",
    ) as unknown;
    return Array.isArray(value) ? (value as SavedNote[]) : [];
  } catch {
    return [];
  }
}

const offlineCapabilities: Health["capabilities"] = {
  generation: false,
  ocr: false,
  symbolic_math: false,
  unit_conversion: false,
  plotting: false,
  page_rendering: false,
  reaction_balancing: false,
  molecule_analysis: false,
  external_chemical_lookup: false,
};

export default function App() {
  const [tenantId, setTenantId] = useState(
    () => localStorage.getItem("rankwise.tenant-id") ?? DEFAULT_TENANT,
  );
  const api = useMemo(() => new RankWiseApi(tenantId), [tenantId]);
  const [generationProvider, setGenerationProvider] =
    useState<GenerationProvider>(() => readGenerationProvider(tenantId));
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collection, setCollection] = useState<Collection | null>(null);
  const [loadingCollections, setLoadingCollections] = useState(true);
  const [loadingCollection, setLoadingCollection] = useState(false);
  const [health, setHealth] = useState<
    (Health & { httpStatus: number }) | null
  >(null);
  const [providerStatus, setProviderStatus] =
    useState<ProviderStatusResponse | null>(null);
  const [providerLoading, setProviderLoading] = useState(true);
  const [apiError, setApiError] = useState("");
  const [savedNotes, setSavedNotes] = useState<SavedNote[]>(readSavedNotes);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [view, setView] = useState("workspace");

  const loadCollections = useCallback(
    async (signal?: AbortSignal) => {
      setLoadingCollections(true);
      try {
        const result = await api.listCollections(signal);
        setCollections(result.collections);
        setApiError("");
        setSelectedId((current) => {
          if (
            current &&
            result.collections.some((item) => item.collection_id === current)
          ) {
            return current;
          }
          return result.collections[0]?.collection_id ?? null;
        });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        setApiError(
          error instanceof Error
            ? error.message
            : "Could not reach the RankWise API",
        );
        setCollections([]);
        setSelectedId(null);
      } finally {
        setLoadingCollections(false);
      }
    },
    [api],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadCollections(controller.signal);
    api
      .health()
      .then(setHealth)
      .catch(() =>
        setHealth({
          status: "not_ready",
          generation_provider_configured: false,
          capabilities: offlineCapabilities,
          httpStatus: 0,
        }),
      );
    setProviderLoading(true);
    api
      .providers(controller.signal)
      .then(setProviderStatus)
      .catch(() => setProviderStatus(null))
      .finally(() => setProviderLoading(false));
    return () => controller.abort();
  }, [api, loadCollections]);

  const loadCollection = useCallback(
    async (signal?: AbortSignal) => {
      if (!selectedId) {
        setCollection(null);
        return;
      }
      setCollection(null);
      setLoadingCollection(true);
      try {
        const result = await api.getCollection(selectedId, signal);
        setCollection(result);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        toast.error(
          error instanceof Error ? error.message : "Could not load collection",
        );
      } finally {
        setLoadingCollection(false);
      }
    },
    [api, selectedId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadCollection(controller.signal);
    return () => controller.abort();
  }, [loadCollection]);

  const changeTenant = (value: string) => {
    localStorage.setItem("rankwise.tenant-id", value);
    setSelectedId(null);
    setCollection(null);
    setGenerationProvider(readGenerationProvider(value));
    setTenantId(value);
  };

  const changeGenerationProvider = (provider: GenerationProvider) => {
    localStorage.setItem(`${PROVIDER_STORAGE_KEY}.${tenantId}`, provider);
    setGenerationProvider(provider);
  };

  const createCollection = async (value: {
    title: string;
    subject: string;
    education_level: string;
  }) => {
    try {
      const created = await api.createCollection(value);
      await loadCollections();
      setSelectedId(created.collection_id);
      toast.success("Collection created");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not create collection",
      );
      throw error;
    }
  };

  const saveNote = (saved: SavedNote) => {
    setSavedNotes((current) => {
      const next = [
        saved,
        ...current.filter((item) => item.note_id !== saved.note_id),
      ].slice(0, 100);
      localStorage.setItem(NOTES_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  };

  const previewEvidence = (item: Evidence) => {
    setEvidence(item);
    setEvidenceOpen(true);
  };

  const capabilities = health?.capabilities ?? offlineCapabilities;

  return (
    <>
      <div className="app-grid">
        <AppSidebar
          tenantId={tenantId}
          collections={collections}
          selectedId={selectedId}
          health={health}
          generationProvider={generationProvider}
          providerStatus={providerStatus}
          providerLoading={providerLoading}
          loading={loadingCollections}
          onTenantChange={changeTenant}
          onSelect={setSelectedId}
          onCreate={createCollection}
          onGenerationProviderChange={changeGenerationProvider}
        />

        <main className="workspace-shell">
          <div className="workspace-width">
            {apiError && (
              <div className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <div>
                  <div className="font-medium">Backend unavailable</div>
                  <div className="mt-0.5 text-xs leading-5">{apiError}</div>
                </div>
              </div>
            )}

            {collection ? (
              <>
                <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
                      {collection.subject.replaceAll("_", " ")} ·{" "}
                      {collection.education_level}
                    </div>
                    <h1 className="text-2xl font-semibold tracking-[-0.025em]">
                      {collection.title}
                    </h1>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {collection.document_count ??
                      collection.documents?.length ??
                      0}{" "}
                    indexed sources
                  </div>
                </header>

                <Tabs value={view} onValueChange={setView}>
                  <TabsList className="mb-1">
                    <TabsTrigger value="workspace" className="gap-1.5">
                      <LayoutDashboard className="size-3.5" /> Workspace
                    </TabsTrigger>
                    <TabsTrigger value="notes" className="gap-1.5">
                      <BookOpenCheck className="size-3.5" /> Notes
                    </TabsTrigger>
                    <TabsTrigger value="tools" className="gap-1.5">
                      <FlaskConical className="size-3.5" /> Tools
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="workspace">
                    <WorkspaceView
                      key={collection.collection_id}
                      api={api}
                      collection={collection}
                      generationReady={Boolean(
                        health?.generation_provider_configured,
                      )}
                      generationProvider={generationProvider}
                      onRefresh={() => loadCollection()}
                      onPreviewEvidence={previewEvidence}
                    />
                  </TabsContent>
                  <TabsContent value="notes">
                    <Suspense fallback={<LoadingView />}>
                      <NotesView
                        key={collection.collection_id}
                        api={api}
                        collection={collection}
                        savedNotes={savedNotes.filter(
                          (item) =>
                            item.collection_id === collection.collection_id,
                        )}
                        generationReady={Boolean(
                          health?.generation_provider_configured,
                        )}
                        generationProvider={generationProvider}
                        onSaveNote={saveNote}
                        onPreviewEvidence={previewEvidence}
                      />
                    </Suspense>
                  </TabsContent>
                  <TabsContent value="tools">
                    <Suspense fallback={<LoadingView />}>
                      <ToolsView api={api} capabilities={capabilities} />
                    </Suspense>
                  </TabsContent>
                </Tabs>
              </>
            ) : (
              <div className="grid min-h-[80vh] place-items-center">
                <div className="max-w-md text-center">
                  <div className="mx-auto mb-4 grid size-12 place-items-center rounded-xl border bg-white shadow-xs">
                    <Database className="size-5 text-muted-foreground" />
                  </div>
                  <h1 className="text-xl font-semibold tracking-tight">
                    {loadingCollections || loadingCollection
                      ? "Opening your workspace…"
                      : "Start with a collection"}
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Collections keep PDFs, images, questions, and generated
                    study artifacts within one explicit source scope. Create one
                    from the sidebar to begin.
                  </p>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      <EvidenceDialog
        api={api}
        evidence={evidence}
        open={evidenceOpen}
        onOpenChange={setEvidenceOpen}
      />
      <Toaster richColors position="bottom-right" />
    </>
  );
}

import {
  BookOpen,
  Check,
  ChevronsUpDown,
  CirclePlus,
  Cloud,
  Cpu,
  Library,
  Settings2,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import type {
  Collection,
  GenerationProvider,
  Health,
  ProviderStatusResponse,
} from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

type NewCollection = {
  title: string;
  subject: string;
  education_level: string;
};

type AppSidebarProps = {
  tenantId: string;
  collections: Collection[];
  selectedId: string | null;
  health: (Health & { httpStatus: number }) | null;
  generationProvider: GenerationProvider;
  providerStatus: ProviderStatusResponse | null;
  providerLoading: boolean;
  loading: boolean;
  onTenantChange: (tenantId: string) => void;
  onSelect: (collectionId: string) => void;
  onCreate: (value: NewCollection) => Promise<void>;
  onGenerationProviderChange: (provider: GenerationProvider) => void;
};

export function AppSidebar({
  tenantId,
  collections,
  selectedId,
  health,
  generationProvider,
  providerStatus,
  providerLoading,
  loading,
  onTenantChange,
  onSelect,
  onCreate,
  onGenerationProviderChange,
}: AppSidebarProps) {
  const [tenantDraft, setTenantDraft] = useState(tenantId);
  const [tenantOpen, setTenantOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<NewCollection>({
    title: "",
    subject: "general_science",
    education_level: "undergraduate",
  });

  const submitCollection = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      await onCreate(form);
      setCreateOpen(false);
      setForm({
        title: "",
        subject: "general_science",
        education_level: "undergraduate",
      });
    } finally {
      setCreating(false);
    }
  };

  const applyTenant = (event: FormEvent) => {
    event.preventDefault();
    const normalized = tenantDraft.trim();
    if (!normalized) return;
    onTenantChange(normalized);
    setTenantOpen(false);
  };

  const groq = providerStatus?.providers.groq;
  const ollama = providerStatus?.providers.ollama;
  const autoAvailable = Boolean(groq?.configured || ollama?.configured);
  const providerLabel = (provider: GenerationProvider) =>
    provider === "auto"
      ? "Auto · Groq → local fallback"
      : provider === "groq"
        ? "Groq"
        : "Local Ollama";

  return (
    <aside className="flex min-h-screen flex-col border-r border-border bg-[#f0f0ed] px-3 py-4 max-[900px]:min-h-0 max-[900px]:border-b max-[900px]:border-r-0">
      <div className="flex h-11 items-center gap-3 px-2">
        <div className="grid size-8 place-items-center rounded-lg bg-[#191b1f] text-white">
          <BookOpen className="size-4" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight">RankWise</div>
          <div className="text-[11px] text-muted-foreground">
            Grounded study workspace
          </div>
        </div>
      </div>

      <Dialog open={tenantOpen} onOpenChange={setTenantOpen}>
        <DialogTrigger asChild>
          <button className="mt-4 flex w-full items-center justify-between rounded-lg border border-border bg-white px-3 py-2 text-left shadow-xs hover:bg-muted/50">
            <span className="min-w-0">
              <span className="block text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                Workspace
              </span>
              <span className="block truncate text-sm font-medium">
                {tenantId}
              </span>
            </span>
            <ChevronsUpDown className="size-4 text-muted-foreground" />
          </button>
        </DialogTrigger>
        <DialogContent>
          <form onSubmit={applyTenant}>
            <DialogHeader>
              <DialogTitle>Change workspace</DialogTitle>
              <DialogDescription>
                This development identifier is sent as the X-Tenant-ID header.
                Production must replace it with authenticated identity.
              </DialogDescription>
            </DialogHeader>
            <div className="my-5 grid gap-2">
              <Label htmlFor="tenant-id">Workspace ID</Label>
              <Input
                id="tenant-id"
                value={tenantDraft}
                maxLength={100}
                onChange={(event) => setTenantDraft(event.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={!tenantDraft.trim()}>
                Apply workspace
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <div className="mt-6 flex items-center justify-between px-2">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Library className="size-3.5" /> Collections
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label="New collection"
            >
              <CirclePlus />
            </Button>
          </DialogTrigger>
          <DialogContent>
            <form onSubmit={submitCollection}>
              <DialogHeader>
                <DialogTitle>New collection</DialogTitle>
                <DialogDescription>
                  Group PDFs and images for one course, topic, or revision goal.
                </DialogDescription>
              </DialogHeader>
              <div className="my-5 grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="collection-title">Name</Label>
                  <Input
                    id="collection-title"
                    autoFocus
                    placeholder="Quantum mechanics"
                    value={form.title}
                    onChange={(event) =>
                      setForm({ ...form, title: event.target.value })
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="collection-subject">Subject</Label>
                  <Input
                    id="collection-subject"
                    placeholder="physics"
                    value={form.subject}
                    onChange={(event) =>
                      setForm({ ...form, subject: event.target.value })
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="collection-level">Education level</Label>
                  <Input
                    id="collection-level"
                    placeholder="undergraduate"
                    value={form.education_level}
                    onChange={(event) =>
                      setForm({ ...form, education_level: event.target.value })
                    }
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setCreateOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={creating || !form.title.trim()}>
                  {creating && <Spinner />} Create collection
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <nav className="mt-2 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto max-[900px]:max-h-36">
        {loading && (
          <div className="flex items-center gap-2 px-3 py-3 text-xs text-muted-foreground">
            <Spinner /> Loading collections
          </div>
        )}
        {!loading && collections.length === 0 && (
          <button
            className="rounded-lg border border-dashed border-border px-3 py-5 text-left text-xs leading-relaxed text-muted-foreground hover:border-[#b8bab4] hover:text-foreground"
            onClick={() => setCreateOpen(true)}
          >
            No collections yet. Create your first workspace.
          </button>
        )}
        {collections.map((collection) => {
          const active = selectedId === collection.collection_id;
          return (
            <button
              key={collection.collection_id}
              onClick={() => onSelect(collection.collection_id)}
              className={cn(
                "group flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                active
                  ? "bg-white font-medium shadow-xs"
                  : "text-[#555960] hover:bg-white/60",
              )}
            >
              <span
                className={cn(
                  "grid size-6 shrink-0 place-items-center rounded-md text-[10px] font-semibold",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "bg-[#e2e3df] text-[#666a71]",
                )}
              >
                {collection.title.slice(0, 1).toUpperCase()}
              </span>
              <span className="min-w-0 flex-1 truncate">
                {collection.title}
              </span>
              {active && <Check className="size-3.5 text-primary" />}
            </button>
          );
        })}
      </nav>

      <Separator className="my-3" />
      <div className="rounded-lg border border-border bg-white p-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold">Generation</div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              Choose how answers are generated
            </div>
          </div>
          <Cpu className="size-4 text-muted-foreground" />
        </div>
        <Select
          value={generationProvider}
          onValueChange={(value) =>
            onGenerationProviderChange(value as GenerationProvider)
          }
          disabled={providerLoading}
        >
          <SelectTrigger className="mt-3 h-9 bg-[#fbfbfa] text-xs">
            <SelectValue>{providerLabel(generationProvider)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="auto" disabled={!autoAvailable}>
              Auto · Groq → local fallback
            </SelectItem>
            <SelectItem value="groq" disabled={!groq?.configured}>
              Groq{groq?.model ? ` · ${groq.model}` : ""}
            </SelectItem>
            <SelectItem
              value="ollama"
              disabled={!ollama?.configured || ollama.model_available === false}
            >
              Local Ollama{ollama?.model ? ` · ${ollama.model}` : ""}
            </SelectItem>
          </SelectContent>
        </Select>
        <div className="mt-3 grid gap-1.5 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Cloud className="size-3" />
            <span>Groq</span>
            <Badge
              variant={groq?.configured ? "success" : "warning"}
              className="ml-auto px-1.5 py-0 text-[10px] font-normal"
            >
              {groq?.configured ? "Ready" : "Not configured"}
            </Badge>
          </div>
          <div className="flex items-center gap-1.5">
            <Cpu className="size-3" />
            <span>Ollama</span>
            <Badge
              variant={
                ollama?.configured && ollama.model_available !== false
                  ? "success"
                  : "warning"
              }
              className="ml-auto px-1.5 py-0 text-[10px] font-normal"
            >
              {ollama?.model_available === true
                ? "Ready"
                : ollama?.configured
                  ? "Unavailable"
                  : "Not configured"}
            </Badge>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between px-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Settings2 className="size-3.5" /> API
        </span>
        <Badge
          variant={
            health?.generation_provider_configured ? "success" : "warning"
          }
          className="font-normal"
        >
          <span className="size-1.5 rounded-full bg-current" />
          {health?.generation_provider_configured ? "Ready" : "Limited"}
        </Badge>
      </div>
    </aside>
  );
}

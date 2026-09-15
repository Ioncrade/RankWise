import { FileImage, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { RankWiseApi } from "@/api/client";
import type { Evidence } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

type EvidenceDialogProps = {
  api: RankWiseApi;
  evidence: Evidence | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function EvidenceDialog({
  api,
  evidence,
  open,
  onOpenChange,
}: EvidenceDialogProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !evidence) return;
    let active = true;
    let objectUrl: string | null = null;
    setPreviewUrl(null);
    setError("");
    api
      .renderEvidence(evidence)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not render evidence",
          );
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [api, evidence, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <div className="flex items-center gap-2 pr-8">
            {evidence?.source_type === "image" ? (
              <FileImage className="size-5" />
            ) : (
              <FileText className="size-5" />
            )}
            <DialogTitle>
              {evidence?.citation_display ?? "Evidence"}
            </DialogTitle>
          </div>
          <DialogDescription>
            Exact source region used by the retrieval and citation pipeline.
          </DialogDescription>
        </DialogHeader>
        {evidence && (
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{evidence.content_type}</Badge>
              <Badge variant="outline">{evidence.extraction_method}</Badge>
              <Badge variant="outline">page {evidence.page_number}</Badge>
            </div>
            <div className="grid min-h-64 place-items-center overflow-hidden rounded-lg border bg-muted/40">
              {!previewUrl && !error && <Spinner className="size-5" />}
              {error && (
                <p className="max-w-sm p-6 text-center text-sm text-red-600">
                  {error}
                </p>
              )}
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt={`Rendered evidence from ${evidence.citation_display}`}
                  className="max-h-[55vh] w-full object-contain"
                />
              )}
            </div>
            <div className="rounded-lg border bg-white p-4">
              <div className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">
                Extracted text
              </div>
              <p className="whitespace-pre-wrap text-sm leading-6 text-[#3d4148]">
                {evidence.text}
              </p>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

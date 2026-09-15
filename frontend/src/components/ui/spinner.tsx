import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/utils";

function Spinner({ className }: { className?: string }) {
  return (
    <LoaderCircle
      aria-label="Loading"
      className={cn("size-4 animate-spin", className)}
    />
  );
}

export { Spinner };

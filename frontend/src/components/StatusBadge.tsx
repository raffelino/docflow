import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

const variants = {
  success: {
    className: "bg-success/10 text-success border-success/20",
    icon: CheckCircle2,
    label: "Erfolgreich",
  },
  error: {
    className: "bg-destructive/10 text-destructive border-destructive/20",
    icon: XCircle,
    label: "Fehler",
  },
  running: {
    className: "bg-warning/10 text-warning border-warning/20",
    icon: Loader2,
    label: "Laeuft",
  },
} as const;

export function StatusBadge({ status }: { status: string }) {
  const v = variants[status as keyof typeof variants] ?? variants.running;
  const Icon = v.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
        v.className,
      )}
    >
      <Icon
        className={cn("h-3 w-3", status === "running" && "animate-spin")}
      />
      {v.label}
    </span>
  );
}

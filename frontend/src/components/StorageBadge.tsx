import { cn } from "@/lib/utils";
import { HardDrive, Cloud, Database } from "lucide-react";

const config: Record<string, { icon: typeof HardDrive; className: string }> = {
  local: { icon: HardDrive, className: "bg-gray-100 text-gray-600" },
  icloud: { icon: Cloud, className: "bg-cyan-100 text-cyan-700" },
  s3: { icon: Database, className: "bg-orange-100 text-orange-700" },
};

export function StorageBadge({ backend }: { backend: string | null }) {
  if (!backend) return null;
  const c = config[backend] ?? config.local;
  const Icon = c.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
        c.className,
      )}
    >
      <Icon className="h-3 w-3" />
      {backend}
    </span>
  );
}

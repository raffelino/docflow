import { cn } from "@/lib/utils";
import { Camera, Mail } from "lucide-react";

export function SourceBadge({ source }: { source: string }) {
  const isEmail = source === "email";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
        isEmail
          ? "bg-purple-100 text-purple-700"
          : "bg-blue-100 text-blue-700",
      )}
    >
      {isEmail ? <Mail className="h-3 w-3" /> : <Camera className="h-3 w-3" />}
      {isEmail ? "Email" : "Photos"}
    </span>
  );
}

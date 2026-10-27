import Link from "next/link";
import { Layers } from "lucide-react";

export function Brand({ light = false, href = "/" }: { light?: boolean; href?: string }) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-2.5 text-xl font-bold tracking-tight transition-colors ${
        light ? "text-white" : "text-slate-900 dark:text-white"
      }`}
      aria-label="DOCTool home"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-teal-700 to-emerald-600 text-white shadow-sm shadow-emerald-950/20">
        <Layers size={20} strokeWidth={2.4} />
      </span>
      <span>DOCTool</span>
      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-emerald-500" />
    </Link>
  );
}

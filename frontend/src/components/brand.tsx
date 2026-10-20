import Link from "next/link";
import { Layers } from "lucide-react";
export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-2.5 text-xl font-semibold tracking-tight ${light ? "text-white" : "text-[#192d35]"}`}
      aria-label="DocuChat home"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#087f74] text-white">
        <Layers size={21} strokeWidth={2.2} />
      </span>
      DocuChat
      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#55c5a6]" />
    </Link>
  );
}

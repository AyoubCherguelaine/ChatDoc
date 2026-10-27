"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertCircle, RotateCcw, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ProtectedWorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Protected workspace error:", error);
  }, [error]);

  return (
    <div className="mx-auto my-12 max-w-lg rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-xs">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-amber-600">
        <AlertCircle size={26} />
      </div>
      <h2 className="text-lg font-semibold text-slate-900">
        Something went wrong in your workspace
      </h2>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        {error?.message || "Could not render this section. Your files and active sessions are safe."}
      </p>
      {error?.digest && (
        <p className="mt-1 font-mono text-[10px] text-slate-400">
          Ref: {error.digest}
        </p>
      )}
      <div className="mt-6 flex flex-col justify-center gap-2.5 sm:flex-row">
        <Button
          onClick={() => reset()}
          className="flex items-center justify-center gap-2"
        >
          <RotateCcw size={15} /> Try again
        </Button>
        <Button
          variant="outline"
          asChild
          className="flex items-center justify-center gap-2"
        >
          <Link href="/advanced-ocr">
            <LayoutDashboard size={15} /> Back to Dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}


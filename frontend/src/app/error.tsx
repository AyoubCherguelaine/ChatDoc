"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertCircle, RotateCcw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log client error to browser console
    console.error("Application runtime error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#f7faf8] px-4 text-center">
      <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600">
          <AlertCircle size={26} />
        </div>
        <h2 className="text-xl font-semibold text-slate-900">
          Unable to load this page
        </h2>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          {error?.message || "An unexpected issue occurred while rendering the page."}
        </p>
        {error?.digest && (
          <p className="mt-1 font-mono text-[10px] text-slate-400">
            Digest: {error.digest}
          </p>
        )}
        <div className="mt-6 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
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
            <Link href="/drive">
              <Home size={15} /> Go to Dashboard
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}


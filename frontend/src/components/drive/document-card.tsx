"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes, formatDate } from "@/lib/utils";
import { fetchDocumentSessions, createSession } from "@/lib/api";
import { useRouter } from "next/navigation";
import { type Document } from "@/lib/types";
import {
  FileText,
  FileSpreadsheet,
  MessageCircle,
  Plus,
  ArrowUpRight,
} from "lucide-react";
import { ApiError } from "@/lib/api";

interface DocumentCardProps {
  doc: Document;
  onSaved: () => void;
}

export function DocumentCard({ doc, onSaved }: DocumentCardProps) {
  const router = useRouter();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [sessions, setSessions] = useState<
    Awaited<ReturnType<typeof fetchDocumentSessions>>
  >([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const openPicker = async () => {
    setPickerOpen(true);
    setLoading(true);
    setError("");
    try {
      const s = await fetchDocumentSessions(doc.id);
      setSessions(s);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load sessions",
      );
    } finally {
      setLoading(false);
    }
  };

  const startNew = async () => {
    setCreating(true);
    setError("");
    try {
      const s = await createSession(
        doc.id,
        `Chat about ${doc.originalFilename}`,
      );
      setPickerOpen(false);
      onSaved();
      router.push(`/chat/${s.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to create session",
      );
    } finally {
      setCreating(false);
    }
  };

  const openExisting = (sessionId: string) => {
    setPickerOpen(false);
    router.push(`/chat/${sessionId}`);
  };

  return (
    <>
      <Card className="group !rounded-2xl !border-slate-200 !bg-white !shadow-none transition hover:!border-emerald-500/50 dark:!border-slate-800 dark:!bg-[#121820]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base text-slate-900 dark:text-white">
            <span
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${/\.(xls|xlsx|csv)$/i.test(doc.originalFilename) ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400" : "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400"}`}
            >
              {/\.(xls|xlsx|csv)$/i.test(doc.originalFilename) ? (
                <FileSpreadsheet size={20} />
              ) : (
                <FileText size={20} />
              )}
            </span>
            <span className="min-w-0 truncate" title={doc.originalFilename}>
              {doc.originalFilename || doc.filename}
            </span>
          </CardTitle>
          <p className="text-sm text-zinc-500 ">
            {formatBytes(doc.fileSize)} • {doc.pageCount}{" "}
            {/\.pdf$/i.test(doc.originalFilename)
              ? doc.pageCount === 1
                ? "page"
                : "pages"
              : doc.pageCount === 1
                ? "section"
                : "sections"}
          </p>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-zinc-400">
            Uploaded {formatDate(doc.createdAt)}
          </p>
          <Button
            size="sm"
            variant="outline"
            className="mt-4 w-full !border-[#dce8e0] text-teal-700"
            onClick={openPicker}
          >
            <MessageCircle size={14} className="mr-1" />
            Chat with document <ArrowUpRight size={14} className="ml-auto" />
          </Button>
        </CardContent>
      </Card>

      <Dialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        title="Pick a conversation"
        description="Start a new chat or continue an existing one."
      >
        {loading ? (
          <div className="py-6 text-center">
            <Spinner size={24} />
            <p className="mt-2 text-sm text-zinc-500">Loading sessions…</p>
          </div>
        ) : (
          <div className="space-y-2">
            <Button
              className="w-full justify-start"
              onClick={startNew}
              disabled={creating}
            >
              {creating ? (
                <Spinner size={14} />
              ) : (
                <Plus size={14} className="mr-1" />
              )}
              New conversation
            </Button>
            {sessions.length === 0 ? (
              <p className="text-center text-sm text-zinc-500">
                No previous conversations.
              </p>
            ) : (
              <div className="max-h-56 overflow-y-auto">
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-zinc-100 "
                    onClick={() => openExisting(s.id)}
                  >
                    <span className="block font-medium">{s.title}</span>
                    <span className="text-xs text-zinc-500">
                      {formatDate(s.createdAt)}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {error && <p className="text-sm text-rose-600">{error}</p>}
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPickerOpen(false)}
          >
            Cancel
          </Button>
        </div>
      </Dialog>
    </>
  );
}

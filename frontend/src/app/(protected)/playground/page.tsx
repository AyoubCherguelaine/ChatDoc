"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  Play,
  Copy,
  Check,
  Download,
  RotateCcw,
  Upload,
  FileText,
  Clock,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  Layers,
  Code2,
  FileCheck,
  X,
  ExternalLink,
  ShieldCheck,
  Terminal,
  Zap,
} from "lucide-react";
import {
  fetchPlaygroundPresets,
  runPlayground,
  fetchDocuments,
  uploadDocument,
  fetchCompanyAccount,
  type PlaygroundPreset,
  type PlaygroundRunResult,
  type CompanyAccountInfo,
} from "@/lib/api";
import type { Document } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export default function PlaygroundPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const serviceKey = searchParams.get("service") || "invoice";
  const initialShowCode = searchParams.get("code") === "true";

  const [preset, setPreset] = useState<PlaygroundPreset | null>(null);
  const [defaultEnvModel, setDefaultEnvModel] = useState<string>("gpt-6-luna");
  const [docs, setDocs] = useState<Document[]>([]);
  const [account, setAccount] = useState<CompanyAccountInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Input Context States
  const [sourceType, setSourceType] = useState<"document" | "text">("document");
  const [textContent, setTextContent] = useState<string>("");
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string>("");

  // Prompt & Schema
  const [systemPrompt, setSystemPrompt] = useState<string>("");
  const [userPrompt, setUserPrompt] = useState<string>("");
  const [schemaText, setSchemaText] = useState<string>("");

  // Execution & Output
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<PlaygroundRunResult | null>(null);
  const [error, setError] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"json" | "blocks" | "rendered" | "steps">("json");
  const [configTab, setConfigTab] = useState<"schema" | "system">("schema");
  const [copied, setCopied] = useState<boolean>(false);

  // API Code Modal States
  const [showApiModal, setShowApiModal] = useState<boolean>(initialShowCode);
  const [apiModalTab, setApiModalTab] = useState<"curl" | "python" | "typescript" | "full_workflow">("curl");
  const [apiModalAsync, setApiModalAsync] = useState<boolean>(false);
  const [codeCopied, setCodeCopied] = useState<boolean>(false);

  // Load preset, documents, and company account
  useEffect(() => {
    let active = true;
    Promise.all([
      fetchPlaygroundPresets(),
      fetchDocuments().catch(() => []),
      fetchCompanyAccount().catch(() => null),
    ])
      .then(([presetData, docList, accData]) => {
        if (!active) return;
        const envModel = presetData.defaultModel || "gpt-6-luna";
        setDefaultEnvModel(envModel);
        setDocs(docList);
        if (accData) {
          setAccount(accData);
        }
        const targetDocId = searchParams.get("doc");
        if (targetDocId && docList.some((d) => d.id === targetDocId)) {
          setSelectedDocId(targetDocId);
          setSourceType("document");
        } else if (docList.length > 0) {
          setSelectedDocId(docList[0].id);
          setSourceType("document");
        }

        const current = presetData.presets[serviceKey] || presetData.presets["invoice"];
        if (current) {
          setPreset(current);
          setSystemPrompt(current.default_system_prompt || "");
          setUserPrompt(current.default_query || "");
          setSchemaText(
            current.default_schema ? JSON.stringify(current.default_schema, null, 2) : ""
          );
          setTextContent(current.sample_text || "");
        }
      })
      .catch((err) => {
        console.error("Failed to load playground:", err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [serviceKey]);

  const selectedDoc = useMemo(() => {
    return docs.find((d) => d.id === selectedDocId) || docs[0] || null;
  }, [docs, selectedDocId]);

  const processUploadedFile = async (file: File) => {
    setIsUploading(true);
    setUploadError("");
    try {
      const up = await uploadDocument(file);
      const newDoc: Document = {
        id: up.id,
        userId: "",
        filename: up.filename,
        originalFilename: up.filename,
        pageCount: up.pageCount,
        fileSize: file.size,
        mimeType: file.type || "application/pdf",
        createdAt: new Date().toISOString(),
      };
      setDocs((prev) => [newDoc, ...prev.filter((d) => d.id !== newDoc.id)]);
      setSelectedDocId(up.id);
      setSourceType("document");
    } catch (err: any) {
      setUploadError(err.message || "File upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processUploadedFile(file);
    }
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      await processUploadedFile(file);
    }
  };

  const handleRun = async () => {
    setIsRunning(true);
    setError("");

    let parsedSchema = undefined;
    if (schemaText.trim()) {
      try {
        parsedSchema = JSON.parse(schemaText);
      } catch {
        parsedSchema = schemaText;
      }
    }

    const payload: any = {
      service: serviceKey,
      model: defaultEnvModel,
      system_prompt: systemPrompt || undefined,
      user_prompt: userPrompt || undefined,
      schema_override: parsedSchema,
      output_format: "json",
    };

    if (sourceType === "document" && selectedDocId) {
      payload.document_id = selectedDocId;
    } else {
      payload.text_content = textContent;
    }

    runPlayground(payload)
      .then((res) => {
        setResult(res);
      })
      .catch((err) => {
        setError(err.message || "Execution failed");
      })
      .finally(() => {
        setIsRunning(false);
      });
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = (data: any) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${serviceKey}_result.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isSchemaValid = useMemo(() => {
    if (!schemaText.trim()) return true;
    try {
      JSON.parse(schemaText);
      return true;
    } catch {
      return false;
    }
  }, [schemaText]);

  const apiKey = account?.rawApiKey || account?.apiKey || "docu_live_your_api_key_here";

  // Dynamic code generators for current state
  const curlCode = useMemo(() => {
    const isDoc = sourceType === "document" && selectedDocId;
    let inputSnippet = "";
    if (isDoc) {
      inputSnippet = `    "document_id": "${selectedDocId}",\n`;
    } else {
      const truncated = (textContent || "").slice(0, 300);
      inputSnippet = `    "text_content": ${JSON.stringify(truncated)},\n`;
    }

    let schemaSnippet = "";
    if (schemaText.trim()) {
      try {
        const obj = JSON.parse(schemaText);
        schemaSnippet = `    "schema_override": ${JSON.stringify(obj, null, 4).replace(/\n/g, "\n    ")},\n`;
      } catch {
        schemaSnippet = `    "schema_override": ${JSON.stringify(schemaText)},\n`;
      }
    }

    let promptSnippet = "";
    if (userPrompt.trim()) {
      promptSnippet = `    "user_prompt": ${JSON.stringify(userPrompt)},\n`;
    }

    let systemSnippet = "";
    if (systemPrompt.trim()) {
      systemSnippet = `    "system_prompt": ${JSON.stringify(systemPrompt)},\n`;
    }

    let asyncSnippet = "";
    if (apiModalAsync) {
      asyncSnippet = `    "async": true,\n    "webhook_url": "https://your-api.company.com/webhooks/doctool",\n`;
    }

    return `# 1. Direct Pipeline Run Endpoint
curl -X POST "http://localhost:8000/api/v1/pipeline/run" \\
  -H "X-API-Key: ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "service": "${serviceKey}",
${inputSnippet}${promptSnippet}${systemSnippet}${schemaSnippet}${asyncSnippet}    "output_format": "json"
  }'`;
  }, [apiKey, serviceKey, sourceType, selectedDocId, textContent, schemaText, userPrompt, systemPrompt, apiModalAsync]);

  const pythonCode = useMemo(() => {
    const isDoc = sourceType === "document" && selectedDocId;
    const body: any = {
      service: serviceKey,
      output_format: "json",
    };
    if (isDoc) {
      body.document_id = selectedDocId;
    } else {
      body.text_content = (textContent || "").slice(0, 300);
    }
    if (userPrompt.trim()) body.user_prompt = userPrompt;
    if (systemPrompt.trim()) body.system_prompt = systemPrompt;
    if (schemaText.trim()) {
      try {
        body.schema_override = JSON.parse(schemaText);
      } catch {
        body.schema_override = schemaText;
      }
    }
    if (apiModalAsync) {
      body.async = true;
      body.webhook_url = "https://your-api.company.com/webhooks/doctool";
    }

    return `import requests

url = "http://localhost:8000/api/v1/pipeline/run"
headers = {
    "X-API-Key": "${apiKey}",
    "Content-Type": "application/json"
}

payload = ${JSON.stringify(body, null, 4)}

response = requests.post(url, headers=headers, json=payload)
data = response.json()

if response.status_code == 200:
    print(f"Status: {data.get('status')}")
    print(f"Credits Remaining: {data.get('creditsRemaining')}")
    print("Structured Extraction:", data.get("data"))
else:
    print(f"Error {response.status_code}:", data.get("detail"))`;
  }, [apiKey, serviceKey, sourceType, selectedDocId, textContent, schemaText, userPrompt, systemPrompt, apiModalAsync]);

  const typescriptCode = useMemo(() => {
    const isDoc = sourceType === "document" && selectedDocId;
    const body: any = {
      service: serviceKey,
      output_format: "json",
    };
    if (isDoc) {
      body.document_id = selectedDocId;
    } else {
      body.text_content = (textContent || "").slice(0, 300);
    }
    if (userPrompt.trim()) body.user_prompt = userPrompt;
    if (systemPrompt.trim()) body.system_prompt = systemPrompt;
    if (schemaText.trim()) {
      try {
        body.schema_override = JSON.parse(schemaText);
      } catch {
        body.schema_override = schemaText;
      }
    }
    if (apiModalAsync) {
      body.async = true;
      body.webhook_url = "https://your-api.company.com/webhooks/doctool";
    }

    return `// In Node.js 18+ or modern backend worker
async function runDocumentPipeline() {
  const url = "http://localhost:8000/api/v1/pipeline/run";
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "X-API-Key": "${apiKey}",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(${JSON.stringify(body, null, 2)}),
  });

  const json = await response.json();
  if (!response.ok) {
    throw new Error(json.detail || "Pipeline execution failed");
  }

  console.log("Status:", json.status);
  console.log("Structured JSON Output:", json.data);
  return json.data;
}

runDocumentPipeline().catch(console.error);`;
  }, [apiKey, serviceKey, sourceType, selectedDocId, textContent, schemaText, userPrompt, systemPrompt, apiModalAsync]);

  const workflowCode = useMemo(() => {
    return `# End-to-End Enterprise Document AI Workflow:
# Step 1: Ingest and OCR PDF/Scan
UPLOAD_RES=$(curl -s -X POST "http://localhost:8000/api/v1/documents/upload" \\
  -H "X-API-Key: ${apiKey}" \\
  -F "file=@./invoice_or_contract.pdf")

DOCUMENT_ID=$(echo "$UPLOAD_RES" | jq -r '.id')
echo "Ingested Document ID: $DOCUMENT_ID"

# Step 2: Trigger AI Pipeline (${serviceKey})
curl -X POST "http://localhost:8000/api/v1/pipeline/run" \\
  -H "X-API-Key: ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "service": "${serviceKey}",
    "document_id": "'"$DOCUMENT_ID"'",
    "output_format": "json"
  }' | jq .`;
  }, [apiKey, serviceKey]);

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  };

  // Keyboard shortcut listener: Cmd+Enter or Ctrl+Enter to execute
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (!isRunning) {
          handleRun();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isRunning, sourceType, selectedDocId, textContent, schemaText, userPrompt, systemPrompt]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner size={28} />
      </div>
    );
  }

  const serviceTitle = preset?.name || serviceKey;

  return (
    <div className="mx-auto max-w-7xl animate-enter space-y-4">
      {/* Studio Header & Breadcrumb */}
      <div className="border-b border-slate-200 pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
              <Link href="/services" className="hover:text-slate-800 transition flex items-center gap-1">
                <ArrowLeft size={13} />
                <span>AI Services</span>
              </Link>
              <span>/</span>
              <span className="font-mono text-slate-700 uppercase tracking-wider text-[11px] font-semibold">{serviceKey}</span>
            </div>

            <div className="mt-1 flex items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-slate-900">
                {serviceTitle}
              </h1>
              <span className="rounded-md bg-slate-900 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-200">
                {defaultEnvModel}
              </span>
              <span className="hidden sm:inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-medium text-slate-600 border border-slate-200">
                REST API Sandbox
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden lg:inline-flex text-[11px] font-mono text-slate-400">
              Press <kbd className="rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 font-mono">⌘+↵</kbd>
            </span>

            <Button
              onClick={() => setShowApiModal(true)}
              variant="outline"
              className="h-9 gap-1.5 border-slate-300 bg-white font-medium text-slate-700 hover:bg-slate-50 text-xs shadow-2xs"
            >
              <Code2 size={14} className="text-[#087f74]" />
              <span>&lt;/&gt; Get API Code</span>
            </Button>

            <Button
              onClick={handleRun}
              disabled={isRunning}
              className="h-9 gap-2 bg-[#087f74] hover:bg-[#06675e] text-white font-semibold px-4 text-xs shadow-xs transition"
            >
              {isRunning ? (
                <Spinner size={13} className="text-white" />
              ) : (
                <Play size={13} className="fill-current" />
              )}
              <span>{isRunning ? "Executing..." : `Run ${serviceTitle}`}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Main Studio Two-Column Workbench */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 items-start">
        {/* Left Panel: Inputs & Configuration Workbench (5 cols on lg) */}
        <div className="lg:col-span-5 flex flex-col rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          {/* Top Panel Header: Segmented Source Selector */}
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-4 py-2">
            <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
              Input Source
            </span>
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs shadow-2xs font-medium">
              <button
                type="button"
                onClick={() => setSourceType("document")}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition ${
                  sourceType === "document"
                    ? "bg-slate-900 text-white font-semibold shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <FileText size={12} />
                <span>Document ({docs.length})</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setSourceType("text");
                  if (!textContent && preset?.sample_text) {
                    setTextContent(preset.sample_text);
                  }
                }}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition ${
                  sourceType === "text"
                    ? "bg-slate-900 text-white font-semibold shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Code2 size={12} />
                <span>Direct Text</span>
              </button>
            </div>
          </div>

          <div className="p-4 space-y-4 flex-1">
            {/* Document Source View */}
            {sourceType === "document" ? (
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <select
                      value={selectedDocId}
                      onChange={(e) => setSelectedDocId(e.target.value)}
                      className="h-9 w-full appearance-none rounded-lg border border-slate-300 bg-white px-3 pr-8 text-xs font-semibold text-slate-900 shadow-2xs hover:border-slate-400 focus:border-teal-600 focus:outline-none"
                    >
                      {docs.length === 0 && <option value="">No files uploaded yet</option>}
                      {docs.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.filename} ({d.pageCount} {d.pageCount === 1 ? "page" : "pages"})
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      size={14}
                      className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                  </div>

                  {/* Compact Upload Action */}
                  <label className="relative flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-3 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 shadow-2xs transition">
                    <input
                      type="file"
                      accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.png,.jpg,.jpeg"
                      onChange={handleFileUpload}
                      disabled={isUploading}
                      className="hidden"
                    />
                    <Upload size={13} className="text-slate-500" />
                    <span>{isUploading ? "Uploading..." : "Upload File"}</span>
                  </label>
                </div>

                {/* Drag and Drop Minimal Dropzone */}
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`rounded-lg border border-dashed px-3 py-2 text-center transition ${
                    isDragging
                      ? "border-teal-600 bg-teal-50/60"
                      : "border-slate-200 bg-slate-50/40 hover:border-slate-300"
                  }`}
                >
                  <p className="text-[11px] text-slate-500">
                    Drag &amp; drop PDF or document here • Automatic layout OCR enabled
                  </p>
                </div>

                {uploadError && (
                  <p className="text-xs text-rose-600 flex items-center gap-1">
                    <AlertCircle size={12} /> {uploadError}
                  </p>
                )}

                {/* Selected File Status Strip */}
                {selectedDoc && (
                  <div className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-slate-50/80 px-3 py-1.5 text-xs">
                    <div className="flex items-center gap-2 truncate">
                      <FileText size={13} className="text-teal-700 shrink-0" />
                      <span className="font-semibold text-slate-800 truncate text-[11px]">{selectedDoc.filename}</span>
                    </div>
                    <span className="shrink-0 font-mono text-[10px] text-slate-500">
                      {selectedDoc.pageCount} {selectedDoc.pageCount === 1 ? "page" : "pages"} • OCR Ready
                    </span>
                  </div>
                )}
              </div>
            ) : (
              /* Text Source View */
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>Direct text context:</span>
                  {preset?.sample_text && (
                    <button
                      type="button"
                      onClick={() => setTextContent(preset.sample_text)}
                      className="text-teal-700 hover:underline flex items-center gap-1 font-medium"
                    >
                      <RotateCcw size={10} /> Reset Sample
                    </button>
                  )}
                </div>
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  rows={4}
                  placeholder="Paste document text or invoice OCR output..."
                  className="w-full rounded-lg border border-slate-200 bg-[#fafbfc] p-3 font-mono text-xs text-slate-900 focus:border-teal-600 focus:bg-white focus:outline-none"
                />
              </div>
            )}

            {/* Task Prompt / Instruction */}
            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                Task Query / Prompt
              </label>
              <input
                type="text"
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                placeholder="e.g. Extract structured invoice data, itemized rows, and calculate VAT."
                className="h-9 w-full rounded-lg border border-slate-300 px-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none shadow-2xs font-medium"
              />
            </div>

            {/* Studio Advanced Configuration: JSON Schema & System Prompt Tabs */}
            <div className="space-y-2 pt-1 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <div className="inline-flex rounded-md border border-slate-200 bg-slate-100 p-0.5 text-xs font-medium">
                  <button
                    type="button"
                    onClick={() => setConfigTab("schema")}
                    className={`rounded px-2.5 py-1 text-xs transition ${
                      configTab === "schema"
                        ? "bg-white text-slate-900 font-semibold shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Target JSON Schema
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfigTab("system")}
                    className={`rounded px-2.5 py-1 text-xs transition ${
                      configTab === "system"
                        ? "bg-white text-slate-900 font-semibold shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    System Instructions
                  </button>
                </div>

                {configTab === "schema" ? (
                  <div className="flex items-center gap-2 text-[11px]">
                    <span
                      className={`font-mono text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        isSchemaValid
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}
                    >
                      {isSchemaValid ? "Valid JSON" : "Invalid JSON"}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        try {
                          setSchemaText(JSON.stringify(JSON.parse(schemaText), null, 2));
                        } catch {}
                      }}
                      disabled={!isSchemaValid}
                      className="text-slate-600 hover:text-slate-900 disabled:opacity-40"
                    >
                      Format
                    </button>
                    <span className="text-slate-300">•</span>
                    <button
                      type="button"
                      onClick={() =>
                        setSchemaText(
                          preset?.default_schema ? JSON.stringify(preset.default_schema, null, 2) : ""
                        )
                      }
                      className="text-teal-700 hover:underline"
                    >
                      Reset
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setSystemPrompt(preset?.default_system_prompt || "")}
                    className="text-[11px] text-teal-700 hover:underline flex items-center gap-1 font-medium"
                  >
                    <RotateCcw size={10} /> Reset
                  </button>
                )}
              </div>

              {configTab === "schema" ? (
                <textarea
                  value={schemaText}
                  onChange={(e) => setSchemaText(e.target.value)}
                  rows={6}
                  placeholder="Target JSON schema template..."
                  className="w-full rounded-lg border border-slate-800 bg-[#0c1222] p-3 font-mono text-[11px] leading-relaxed text-emerald-400 focus:outline-none"
                />
              ) : (
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={6}
                  placeholder="System prompt instructions..."
                  className="w-full rounded-lg border border-slate-200 bg-[#fafbfc] p-3 font-mono text-[11px] leading-relaxed text-slate-800 focus:border-teal-600 focus:outline-none"
                />
              )}
            </div>
          </div>
        </div>

        {/* Right Panel: Execution Output & Inspector (7 cols on lg) */}
        <div className="lg:col-span-7 flex flex-col rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          {/* Header Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50/80 px-4 py-2">
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs font-medium shadow-2xs">
              <button
                onClick={() => setActiveTab("json")}
                className={`rounded px-2.5 py-1 text-xs transition ${
                  activeTab === "json"
                    ? "bg-slate-900 text-white font-semibold shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Structured JSON
              </button>
              <button
                onClick={() => setActiveTab("blocks")}
                className={`rounded px-2.5 py-1 text-xs transition ${
                  activeTab === "blocks"
                    ? "bg-slate-900 text-white font-semibold shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Layout Blocks
              </button>
              <button
                onClick={() => setActiveTab("rendered")}
                className={`rounded px-2.5 py-1 text-xs transition ${
                  activeTab === "rendered"
                    ? "bg-slate-900 text-white font-semibold shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Raw Text
              </button>
              <button
                onClick={() => setActiveTab("steps")}
                className={`rounded px-2.5 py-1 text-xs transition ${
                  activeTab === "steps"
                    ? "bg-slate-900 text-white font-semibold shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Agent Steps ({result?.steps?.length || 0})
              </button>
            </div>

            <div className="flex items-center gap-2">
              {result && (
                <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-500">
                  <span className="flex items-center gap-1 rounded bg-slate-200/70 px-2 py-0.5 font-semibold text-slate-700">
                    <Clock size={11} className="text-teal-700" /> {result.latencyMs} ms
                  </span>
                  <span className="rounded bg-teal-50 px-2 py-0.5 font-semibold text-teal-800 border border-teal-200">
                    {result.model}
                  </span>
                </div>
              )}

              {result?.data && (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleCopy(JSON.stringify(result.data, null, 2))}
                    className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 transition shadow-2xs"
                  >
                    {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </button>
                  <button
                    onClick={() => handleDownload(result.data)}
                    className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 transition shadow-2xs"
                  >
                    <Download size={12} />
                    <span>Export</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Viewport Content */}
          <div className="flex-1 p-4 overflow-auto min-h-[460px]">
            {/* Running State */}
            {isRunning && (
              <div className="flex h-96 flex-col items-center justify-center text-center">
                <Spinner size={24} className="text-teal-700" />
                <p className="mt-3 text-xs font-semibold text-slate-800">
                  Executing {serviceTitle} Pipeline...
                </p>
                <p className="mt-1 font-mono text-[11px] text-slate-400">
                  Running model {defaultEnvModel} with layout verification
                </p>
              </div>
            )}

            {/* Error State */}
            {error && !isRunning && (
              <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-800">
                <AlertCircle size={15} className="shrink-0 text-red-600 mt-0.5" />
                <div>
                  <p className="font-semibold">Pipeline Execution Failed</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed font-mono">{error}</p>
                </div>
              </div>
            )}

            {/* Output View */}
            {result && !isRunning && (
              <div>
                {/* Structured JSON Tab */}
                {activeTab === "json" && (
                  <pre className="max-h-[560px] overflow-auto rounded-lg border border-slate-800 bg-[#0a0f1d] p-4 font-mono text-[12px] leading-relaxed text-emerald-400 shadow-inner">
                    {JSON.stringify(result.data || result.result, null, 2)}
                  </pre>
                )}

                {/* Layout Blocks Tab */}
                {activeTab === "blocks" && (
                  <div className="max-h-[560px] overflow-auto space-y-3">
                    {Array.isArray(result.data?.blocks) && result.data.blocks.length > 0 ? (
                      result.data.blocks.map((blk: any, idx: number) => (
                        <div key={idx} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-xs space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-[10px] font-bold uppercase rounded bg-slate-200 px-1.5 py-0.5 text-slate-700">
                              Block #{blk.metadata?.reading_order || idx + 1} • {blk.type}
                            </span>
                            <span className="font-mono text-[10px] text-slate-400">
                              page {blk.metadata?.page_number || 1}
                            </span>
                          </div>
                          {blk.title && (
                            <p className="font-bold text-slate-900 text-sm">{blk.title}</p>
                          )}
                          {blk.table?.content_md ? (
                            <pre className="font-mono text-[11px] bg-white p-2 rounded border border-slate-200 overflow-x-auto text-slate-800">
                              {blk.table.content_md}
                            </pre>
                          ) : blk.image?.description ? (
                            <p className="italic text-teal-800 bg-teal-50 p-2 rounded border border-teal-200">
                              Image: {blk.image.description}
                            </p>
                          ) : (
                            <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{blk.content}</p>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500">
                        <p>Direct JSON payload received.</p>
                        <p className="mt-1 text-[11px] text-slate-400 font-mono">
                          Inspect the Structured JSON tab to view extracted fields.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Formatted Text Tab */}
                {activeTab === "rendered" && (
                  <div className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50/50 p-4 font-mono text-xs leading-relaxed text-slate-800">
                    {result.result}
                  </div>
                )}

                {/* Agent Steps Tab */}
                {activeTab === "steps" && (
                  <div className="max-h-[560px] overflow-auto space-y-2">
                    {result.steps && result.steps.length > 0 ? (
                      result.steps.map((st, idx) => (
                        <div
                          key={idx}
                          className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-2xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-teal-800 font-mono text-[11px]">
                              Step {idx + 1}: {st.action || "Agent Reasoning"}
                            </span>
                          </div>
                          {st.thought && <p className="italic text-slate-600 text-[11px]">{st.thought}</p>}
                          {st.observation && (
                            <pre className="max-h-24 overflow-auto rounded bg-slate-50 p-2 font-mono text-[10px] text-slate-700 border border-slate-100">
                              {st.observation}
                            </pre>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="p-4 text-xs text-slate-500 text-center">
                        Single-pass direct model execution completed without multi-step iterations.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Empty State */}
            {!result && !isRunning && !error && (
              <div className="flex h-96 flex-col items-center justify-center text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-500 mb-3 border border-slate-200">
                  <Code2 size={22} />
                </div>
                <p className="text-sm font-semibold text-slate-800">Ready to execute</p>
                <p className="text-xs text-slate-400 mt-1 max-w-xs">
                  Click <span className="font-semibold text-slate-700">Run</span> or press{" "}
                  <kbd className="rounded border border-slate-300 bg-slate-100 px-1 py-0.5 text-[10px] font-mono text-slate-600">
                    ⌘+Enter
                  </kbd>{" "}
                  to execute pipeline with <span className="font-mono text-teal-700 font-semibold">{defaultEnvModel}</span>.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* API Code Integration Modal */}
      {showApiModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setShowApiModal(false)}
        >
          <div
            className="relative w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 bg-slate-50/60">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-[#087f74]">
                  <Code2 size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Integrate {serviceTitle} API
                  </h3>
                  <p className="text-xs text-slate-500">
                    Production REST endpoint with your current playground parameters and API key.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowApiModal(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200/60 hover:text-slate-700 transition"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="overflow-y-auto p-6 space-y-4 flex-1">
              {/* Tab Selector & Mode Switch */}
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-3">
                <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-medium">
                  <button
                    onClick={() => setApiModalTab("curl")}
                    className={`rounded-md px-3 py-1 transition ${
                      apiModalTab === "curl"
                        ? "bg-white text-slate-900 font-semibold shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    cURL
                  </button>
                  <button
                    onClick={() => setApiModalTab("python")}
                    className={`rounded-md px-3 py-1 transition ${
                      apiModalTab === "python"
                        ? "bg-white text-slate-900 font-semibold shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Python (requests)
                  </button>
                  <button
                    onClick={() => setApiModalTab("typescript")}
                    className={`rounded-md px-3 py-1 transition ${
                      apiModalTab === "typescript"
                        ? "bg-white text-slate-900 font-semibold shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Node / TypeScript
                  </button>
                  <button
                    onClick={() => setApiModalTab("full_workflow")}
                    className={`rounded-md px-3 py-1 transition ${
                      apiModalTab === "full_workflow"
                        ? "bg-white text-slate-900 font-semibold shadow-2xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Upload + Process
                  </button>
                </div>

                {/* Async Toggle */}
                {apiModalTab !== "full_workflow" && (
                  <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-700 select-none">
                    <input
                      type="checkbox"
                      checked={apiModalAsync}
                      onChange={(e) => setApiModalAsync(e.target.checked)}
                      className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    />
                    <span className="font-medium">Async Background Job</span>
                    <span className="text-[10px] text-slate-400 font-normal">
                      (returns job_id immediately)
                    </span>
                  </label>
                )}
              </div>

              {/* Code Snippet Container */}
              <div className="relative rounded-xl border border-slate-800 bg-[#0b1320] p-4 text-xs font-mono text-emerald-400 shadow-inner">
                <div className="absolute right-3 top-3">
                  <button
                    onClick={() => {
                      const code =
                        apiModalTab === "curl"
                          ? curlCode
                          : apiModalTab === "python"
                          ? pythonCode
                          : apiModalTab === "typescript"
                          ? typescriptCode
                          : workflowCode;
                      handleCopyCode(code);
                    }}
                    className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition"
                  >
                    {codeCopied ? (
                      <>
                        <Check size={13} className="text-emerald-400" />
                        <span className="text-emerald-400">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy size={13} />
                        <span>Copy Code</span>
                      </>
                    )}
                  </button>
                </div>

                <pre className="max-h-80 overflow-auto pt-7 leading-relaxed whitespace-pre font-mono text-[12px] text-emerald-300">
                  {apiModalTab === "curl" && curlCode}
                  {apiModalTab === "python" && pythonCode}
                  {apiModalTab === "typescript" && typescriptCode}
                  {apiModalTab === "full_workflow" && workflowCode}
                </pre>
              </div>

              {/* API Information Bar */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-xs">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-1">
                  <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                    <ShieldCheck size={14} className="text-emerald-600" />
                    <span>Authentication Header</span>
                  </div>
                  <p className="text-[11px] text-slate-500 font-mono">
                    X-API-Key: {account?.apiKeyPrefix || "docu_live_"}••••••••••
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-1">
                  <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                    <Zap size={14} className="text-[#087f74]" />
                    <span>Free Trial Credits</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    {account ? `${account.remainingCredits.toLocaleString()} credits remaining` : "1,200 starting credits included"}
                  </p>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/70 px-6 py-3.5 text-xs">
              <Link
                href="/usage"
                className="flex items-center gap-1 font-semibold text-[#087f74] hover:underline"
              >
                <span>Manage API Keys &amp; View Quota in Usage</span>
                <ExternalLink size={12} />
              </Link>
              <Button
                onClick={() => setShowApiModal(false)}
                className="bg-slate-900 text-white hover:bg-slate-800 font-semibold px-4 text-xs h-8"
              >
                Done
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

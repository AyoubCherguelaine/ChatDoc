export type Role = "user" | "assistant";

export interface User {
  id: string;
  email: string;
  name: string | null;
  createdAt: string;
}

export interface Document {
  id: string;
  userId: string;
  filename: string;
  originalFilename: string;
  fileSize: number;
  mimeType: string;
  pageCount: number;
  createdAt: string;
}

export interface ChatSession {
  id: string;
  userId: string;
  documentId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount?: number;
}

export interface Message {
  id: string;
  sessionId: string;
  role: Role;
  content: string;
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  user: User;
}

export type ChatMode =
  | "conversational"
  | "agent"
  | "summary"
  | "research"
  | "extraction"
  | "comparison"
  | "factcheck"
  | "invoice"
  | "contract"
  | "google_ai"
  | "receipt"
  | "resume"
  | "compliance"
  | "form_parser"
  | "coordinator"
  | "redaction"
  | "classifier"
  | "financial_statement"
  | "translation"
  | "anomaly_audit";

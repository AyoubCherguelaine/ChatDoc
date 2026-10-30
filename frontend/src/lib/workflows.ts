export interface Workflow {
  id: string;
  title: string;
  description: string;
  prompt: string;
  mode:
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
  color: string;
}

export const workflows: Workflow[] = [
  {
    id: "summary",
    title: "Executive summary",
    description: "Summarize the main findings, figures and recommendations.",
    prompt:
      "Write an executive summary of this document. Cover its purpose, key findings, important numbers, and recommended next steps. Cite the source page or section for each key finding.",
    mode: "summary",
    color: "sage",
  },
  {
    id: "research",
    title: "Deep research",
    description: "Review claims and supporting passages with source references.",
    prompt:
      "Investigate the main claims in this document. Search relevant sections, read the supporting pages, identify evidence and gaps, and produce a research brief with source citations. Clearly distinguish facts from inferences.",
    mode: "research",
    color: "blue",
  },
  {
    id: "extract",
    title: "Extract key data",
    description: "Extract names, dates and figures into a table.",
    prompt:
      "Extract the key metrics, dates, names, and financial figures from this document into a Markdown table. Include the source page or worksheet section for every row. Preserve units and currency, and mark missing values as not provided. Do not invent or calculate figures without showing the inputs.",
    mode: "extraction",
    color: "peach",
  },
  {
    id: "actions",
    title: "Find action items",
    description: "List stated tasks, owners and deadlines.",
    prompt:
      "Identify action items, decisions, deadlines, and responsible people explicitly mentioned in this document. Present them in a table with source citations. If an owner or deadline is absent, say not specified. Separate suggested actions from explicit commitments.",
    mode: "conversational",
    color: "violet",
  },
  {
    id: "factcheck",
    title: "Fact-check claims",
    description: "Check whether the document supports its claims.",
    prompt:
      "Verify the key factual claims in this document against the evidence. For each claim, state whether it is SUPPORTED, CONTRADICTED, or UNDETERMINED, and cite the source page. If the document contains no evidence for a claim, say so.",
    mode: "factcheck",
    color: "red",
  },
  {
    id: "auto",
    title: "Auto-routing agent",
    description: "Let the coordinator pick the best specialist.",
    prompt:
      "Analyse the document comprehensively. Produce an executive summary, identify key data and metrics, highlight any comparisons or contradictions, and verify any claims you can find. Use all specialist agents as needed.",
    mode: "coordinator",
    color: "indigo",
  },
  {
    id: "invoice",
    title: "Invoice processing",
    description: "Extract structured invoice data as JSON.",
    prompt:
      "Extract all invoice data from this document: vendor, client, invoice number, dates, line items with quantities and prices, subtotal, taxes, and total. Present as JSON with source citations. Verify that subtotal + tax equals the grand total.",
    mode: "invoice",
    color: "emerald",
  },
  {
    id: "contract",
    title: "Contract analysis",
    description: "Analyse clauses, obligations, and risks.",
    prompt:
      "Analyse this contract: identify parties, effective and expiration dates, governing law, key clauses (termination, indemnification, confidentiality, force majeure), payment terms, and flag any risk or unusual clauses. Present as JSON with source citations.",
    mode: "contract",
    color: "amber",
  },
  {
    id: "google_ai",
    title: "Google AI Document",
    description: "Extract document structure, fields and tables.",
    prompt:
      "Analyse this document using Google AI Document Intelligence. Perform layout and structural analysis, extract key entities, form fields, tables, and summarize the core information into structured sections with citations.",
    mode: "google_ai",
    color: "blue",
  },
  {
    id: "receipt",
    title: "Receipt & Expense Processing",
    description: "Itemized receipts, tax breakdowns, tips, and financial verification.",
    prompt:
      "Extract all receipt and expense data: merchant name and address, date, time, currency, payment method, itemized products/services, subtotal, taxes, tips, and grand total. Validate that mathematical sums match and present as structured JSON.",
    mode: "receipt",
    color: "emerald",
  },
  {
    id: "resume",
    title: "Resume reading",
    description: "Candidate profiling, skills taxonomy, work history, and experience scoring.",
    prompt:
      "Parse this resume/CV: extract candidate contact info, executive summary, technical/soft skills taxonomy, chronological work history with key accomplishments, educational background, certifications, and provide a seniority assessment.",
    mode: "resume",
    color: "violet",
  },
  {
    id: "compliance",
    title: "PII & Compliance Audit",
    description: "Detect sensitive PII, GDPR/HIPAA risks, and secret leaks with redaction guidance.",
    prompt:
      "Audit this document for Personally Identifiable Information (PII), confidential credentials, and compliance vulnerabilities under GDPR and HIPAA. Provide a risk score (0-100), itemize detected data with citations, and provide redaction recommendations.",
    mode: "compliance",
    color: "red",
  },
  {
    id: "form_parser",
    title: "Form reading",
    description: "Extract form fields, checkbox states, selection groups, and signatures.",
    prompt:
      "Parse all form fields from this document: identify form title and metadata, extract key-value field pairs, check-box selection states ([X] or [ ]), and signature blocks (signatory name, signed status, date signed). Highlight any missing required fields.",
    mode: "form_parser",
    color: "peach",
  },
  {
    id: "redaction",
    title: "Bilingual PII & Tax Redaction",
    description: "Mask Saudi National IDs, GCC IBANs, ZATCA VAT IDs, and sensitive data.",
    prompt:
      "Perform deterministic and LLM-assisted PII and sensitive tax data redaction on this document for both Arabic and English text. Mask Saudi National IDs, GCC IBANs, ZATCA 15-digit Tax IDs, Commercial Registrations, emails, and phone numbers with [REDACTED_...] tokens. Provide a structured audit report of all redacted entities.",
    mode: "redaction",
    color: "red",
  },
  {
    id: "classifier",
    title: "Document Classification & Routing",
    description: "Categorize documents, detect language (EN/AR), urgency, and target department.",
    prompt:
      "Classify this document: identify document type (invoice, contract, financial statement, resume, commercial registration, or official letter), detected language (ar, en, or mixed), urgency level, and target department. Provide JSON summary with confidence scores.",
    mode: "classifier",
    color: "indigo",
  },
  {
    id: "financial_statement",
    title: "Financial Statement Analysis",
    description: "Analyze Income Statement and Balance Sheet metrics and calculate key ratios.",
    prompt:
      "Analyze the financial statements in this document. Extract Revenue, Gross Profit, EBIT, Net Income, Total Assets, Total Liabilities, and Total Equity in both Arabic and English formats. Compute Gross Margin, Net Margin, and Debt-to-Equity ratios. Provide an executive financial health diagnosis.",
    mode: "financial_statement",
    color: "emerald",
  },
  {
    id: "translation",
    title: "Bilingual Legal & Financial Translation",
    description: "High-fidelity translation between Arabic and English preserving terminology.",
    prompt:
      "Translate this document with high fidelity between English and Arabic. Preserve all legal, financial, and technical terminology accurately, retain table layouts and numbering, and provide bilingual alignment notes.",
    mode: "translation",
    color: "blue",
  },
  {
    id: "anomaly_audit",
    title: "Anomaly & Tax Audit",
    description: "Audit financial math, ZATCA 15% VAT compliance, and date chronology.",
    prompt:
      "Perform a rigorous audit on this document: verify mathematical integrity (subtotal + tax = total), check ZATCA 15% VAT compliance, and detect date inversions or chronological anomalies. Flag any discrepancy with severity and remediation guidance.",
    mode: "anomaly_audit",
    color: "amber",
  },
];

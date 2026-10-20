export const workflows = [
  {
    id: "summary",
    title: "Executive summary",
    description: "The big picture, without the long read.",
    prompt:
      "Write an executive summary of this document. Cover its purpose, key findings, important numbers, and recommended next steps. Cite the source page or section for each key finding.",
    mode: "conversational" as const,
    color: "sage",
  },
  {
    id: "research",
    title: "Deep research",
    description: "Follow the evidence. Connect the details.",
    prompt:
      "Investigate the main claims in this document. Search relevant sections, read the supporting pages, identify evidence and gaps, and produce a research brief with source citations. Clearly distinguish facts from inferences.",
    mode: "agent" as const,
    color: "blue",
  },
  {
    id: "extract",
    title: "Extract key data",
    description: "Turn buried details into a clear table.",
    prompt:
      "Extract the key metrics, dates, names, and financial figures from this document into a Markdown table. Include the source page or worksheet section for every row. Preserve units and currency, and mark missing values as not provided. Do not invent or calculate figures without showing the inputs.",
    mode: "agent" as const,
    color: "peach",
  },
  {
    id: "actions",
    title: "Find action items",
    description: "Move from what it says to what comes next.",
    prompt:
      "Identify action items, decisions, deadlines, and responsible people explicitly mentioned in this document. Present them in a table with source citations. If an owner or deadline is absent, say not specified. Separate suggested actions from explicit commitments.",
    mode: "conversational" as const,
    color: "violet",
  },
];

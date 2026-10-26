GLOBAL_RESPONSE_POLICY = """
- Transcribe only what is visible.
- Never invent missing lines.
- Keep Arabic exactly as written.
- Preserve numbering, bullets, headings, and tables.
- Output Markdown only, with no extra commentary.
""".strip()


def normalize_model_markdown(md_text: str) -> str:
    """Remove fenced wrappers that models sometimes add around Markdown."""
    cleaned = md_text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned

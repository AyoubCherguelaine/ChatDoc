"""
GPT Chat & OpenAI Tool Calling Integration Example.

Shows how to connect DocuChat tools into OpenAI GPT chat completions
(e.g., GPT-4o, Custom GPTs, or LangChain agents).
"""

from __future__ import annotations

import json
import os
import httpx

DOCUCHAT_API_KEY = os.getenv("DOCUCHAT_API_KEY", "docu_live_enterprise_demo_key")
DOCUCHAT_URL = os.getenv("DOCUCHAT_BASE_URL", "http://127.0.0.1:8000")


def get_docuchat_tools():
    """Fetch OpenAI-formatted function calling schemas directly from DocuChat server."""
    with httpx.Client() as client:
        resp = client.get(f"{DOCUCHAT_URL}/api/v1/openai/tools")
        return resp.json().get("tools", [])


def handle_tool_call(tool_name: str, arguments: dict):
    """Execute the tool on DocuChat API."""
    headers = {"X-API-Key": DOCUCHAT_API_KEY}
    with httpx.Client() as client:
        if tool_name == "docuchat_list_documents":
            r = client.get(f"{DOCUCHAT_URL}/api/v1/documents", headers=headers, params=arguments)
            return r.json()
        elif tool_name == "docuchat_search_chunks":
            doc_id = arguments.get("document_id")
            r = client.get(f"{DOCUCHAT_URL}/api/v1/documents/{doc_id}/search", headers=headers, params=arguments)
            return r.json()
        elif tool_name == "docuchat_extract_invoice":
            payload = {"document_id": arguments.get("document_id"), "service": "invoice", "query": arguments.get("query")}
            r = client.post(f"{DOCUCHAT_URL}/api/v1/pipeline/run", headers=headers, json=payload)
            return r.json()
        elif tool_name == "docuchat_analyze_contract":
            payload = {"document_id": arguments.get("document_id"), "service": "contract", "query": arguments.get("query")}
            r = client.post(f"{DOCUCHAT_URL}/api/v1/pipeline/run", headers=headers, json=payload)
            return r.json()
        elif tool_name == "docuchat_audit_compliance":
            payload = {"document_id": arguments.get("document_id"), "service": "compliance"}
            r = client.post(f"{DOCUCHAT_URL}/api/v1/pipeline/run", headers=headers, json=payload)
            return r.json()
        elif tool_name == "docuchat_summarize_document":
            payload = {"document_id": arguments.get("document_id"), "service": "summary", "query": arguments.get("query")}
            r = client.post(f"{DOCUCHAT_URL}/api/v1/pipeline/run", headers=headers, json=payload)
            return r.json()
        return {"error": f"Unknown tool {tool_name}"}


if __name__ == "__main__":
    tools = get_docuchat_tools()
    print(f"Loaded {len(tools)} DocuChat tools ready for GPT chat completions:")
    for t in tools:
        print(f" - {t['function']['name']}: {t['function']['description']}")

    print("\nTo use with OpenAI Python SDK:")
    print("```python")
    print("from openai import OpenAI")
    print("client = OpenAI()")
    print("response = client.chat.completions.create(")
    print("    model='gpt-4o',")
    print("    messages=[{'role': 'user', 'content': 'Audit contract doc-123 for PII and GDPR compliance'}],")
    print("    tools=tools,")
    print(")")
    print("```")


"""
B2B Data Pipeline Integration Example using DocuChat Enterprise SDK.

Demonstrates how B2B companies integrate DocuChat into automated pipelines
(e.g., Apache Airflow, Prefect, Celery, or scheduled cron jobs).
"""

from __future__ import annotations

import os
from backend.sdk.client import DocuChatClient, DocuChatError

# 1. Initialize client with your company API key (issued on registration / dashboard)
API_KEY = os.getenv("DOCUCHAT_API_KEY", "docu_live_enterprise_demo_key")
BASE_URL = os.getenv("DOCUCHAT_BASE_URL", "http://127.0.0.1:8000")

client = DocuChatClient(api_key=API_KEY, base_url=BASE_URL)


def run_enterprise_invoice_pipeline():
    print("--- [1] Checking Enterprise Credit Balance ---")
    account = client.get_account()
    print(f"Company: {account.get('companyName')}")
    print(f"Plan Tier: {account.get('planTier')}")
    print(f"Remaining Credits: {account.get('remainingCredits')}\n")

    print("--- [2] Ingesting Document into Pipeline ---")
    # You can upload a file directly or pass raw document text:
    sample_invoice = """
    GLOBAL CLOUD SERVICES LLC
    742 Evergreen Terrace, Springfield, OR 97477
    TAX ID: 94-8849201 | INVOICE #: INV-2026-8812
    Date: October 26, 2026 | Due Date: November 25, 2026

    Bill To:
    Acme Enterprise Solutions
    100 Industrial Parkway, Suite 400

    ITEMS:
    1. Dedicated GPU Cluster (H100 x 8) - 1 Month:      $18,400.00
    2. Enterprise Vector DB Storage (10 TB):             $1,200.00
    3. 24/7 Dedicated Support SLA:                       $2,500.00

    Subtotal:                                           $22,100.00
    Sales Tax (8.25%):                                   $1,823.25
    TOTAL DUE:                                          $23,923.25

    Payment Terms: Net 30 days via Wire Transfer.
    """
    upload_res = client.upload_text(sample_invoice, filename="cloud_invoice_oct2026.txt")
    doc_id = upload_res["documentId"]
    print(f"Document Ingested! ID: {doc_id}, Chunks: {upload_res['chunkCount']}, Pages: {upload_res['pageCount']}\n")

    print("--- [3] Executing Automated Invoice AI Agent ---")
    invoice_data = client.extract_invoice(doc_id)
    print("Service Status:", invoice_data.get("status"))
    print("Credits Deducted:", invoice_data.get("creditsDeducted"))
    print("Credits Remaining:", invoice_data.get("creditsRemaining"))
    print("Extracted Structured Data:")
    print(invoice_data.get("data") or invoice_data.get("raw"))
    print("\n")

    print("--- [4] Hybrid RAG Search across Documents ---")
    search_res = client.search(doc_id, query="What are the payment terms?", top_k=2)
    for idx, match in enumerate(search_res.get("results", [])):
        print(f"Match #{idx+1} [Page {match['page']}]: {match['content'][:120]}...")

    print("\n--- Pipeline Run Completed Successfully! ---")


if __name__ == "__main__":
    try:
        run_enterprise_invoice_pipeline()
    except DocuChatError as e:
        print(f"Pipeline error: {e}")


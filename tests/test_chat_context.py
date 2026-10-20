from langchain_core.documents import Document

from backend.chat.chatWithVSDB import ConversationChain


def test_context_preserves_evidence_beyond_old_snippet_limit():
    chain = ConversationChain(retriever=None, llm=None)
    result = chain._format_docs(
        [
            Document(
                page_content="x" * 600 + "Total: 42000 USD",
                metadata={"doc_name": "budget.xlsx", "start_page": 2, "end_page": 2},
            )
        ]
    )
    assert "42000 USD" in result
    assert "budget.xlsx (section 2)" in result


def test_context_is_bounded_and_pdf_citations_use_pages():
    chain = ConversationChain(retriever=None, llm=None)
    docs = [
        Document(page_content="a" * 20000, metadata={"doc_name": "report.pdf", "start_page": i, "end_page": i + 1})
        for i in range(20)
    ]
    result = chain._format_docs(docs)
    assert result.count("a") <= 24020
    assert "report.pdf (page 0-1)" in result
    assert len(result) < 25000

from app.components.gale_chunker import Article, Line, articles_to_documents, build_articles


class FakePage:
    width = 600
    rects = []

    def __init__(self, words):
        self._words = words

    def extract_words(self, **_kwargs):
        return self._words


class FakePdf:
    def __init__(self, pages):
        self.pages = pages


def word(text, x0, top, size):
    return {"text": text, "x0": x0, "x1": x0 + 20, "top": top, "bottom": top + size, "size": size, "upright": True}


def test_key_terms_are_page_local_and_do_not_capture_body_text():
    page = FakePage([
        word("Anemia", 20, 10, 15),
        word("Definition", 20, 35, 11),
        word("Body", 20, 50, 10),
        word("text", 45, 50, 10),
        word("KEY", 330, 20, 12),
        word("TERMS", 360, 20, 12),
        word("Term", 330, 35, 10),
        word("definition", 360, 35, 10),
        # A clear vertical gap ends the fallback sidebar region.
        word("Continuing", 330, 70, 10),
        word("body", 390, 70, 10),
    ])
    articles = list(build_articles(FakePdf([page]), range(1)))

    assert articles[0].key_terms == ["Term definition"]
    assert "Continuing body" in articles[0].sections["Definition"]


def test_semantic_documents_have_citation_metadata_and_respect_limit():
    article = Article(
        title="Example",
        start_page=4,
        end_page=5,
        sections={"Definition": ["x" * 300]},
        key_terms=["Term — definition"],
    )
    documents = articles_to_documents([article], "data/gale.pdf", max_chars=100)

    assert {document.metadata["type"] for document in documents} == {"section", "glossary"}
    assert all(document.metadata["source"] == "data/gale.pdf" for document in documents)
    assert all(document.metadata["page_start"] == 5 for document in documents)
    assert all(len(document.page_content) <= 100 for document in documents)

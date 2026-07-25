from scripts.rank_candidates import (
    build_training_set,
    train_model,
    rank_candidates,
    select_flexible_slots,
    MIN_LABELED_EXAMPLES,
)


def make_paper(id, title, summary="Summary text", category="neuroscience"):
    return {"id": id, "title": title, "summary": summary, "category": category}


def test_build_training_set_only_includes_explicit_marks():
    papers = [make_paper("a", "A"), make_paper("b", "B"), make_paper("c", "C")]
    marks = {"a": "used", "b": "not_interested"}  # c is unmarked, must be excluded
    texts, labels = build_training_set(papers, marks)
    assert len(texts) == 2
    assert labels == [1, 0]


def test_build_training_set_skips_marks_for_unknown_papers():
    papers = [make_paper("a", "A")]
    marks = {"a": "used", "ghost-paper": "not_interested"}
    texts, labels = build_training_set(papers, marks)
    assert len(texts) == 1


def test_train_model_returns_none_below_threshold():
    papers = [make_paper(str(i), f"Title {i}") for i in range(MIN_LABELED_EXAMPLES - 1)]
    marks = {str(i): "used" if i % 2 == 0 else "not_interested" for i in range(MIN_LABELED_EXAMPLES - 1)}
    assert train_model(papers, marks) is None


def test_train_model_returns_none_with_only_one_class():
    papers = [make_paper(str(i), f"Title {i}") for i in range(MIN_LABELED_EXAMPLES)]
    marks = {str(i): "used" for i in range(MIN_LABELED_EXAMPLES)}
    assert train_model(papers, marks) is None


def test_train_model_trains_at_threshold():
    papers = []
    marks = {}
    for i in range(MIN_LABELED_EXAMPLES):
        pid = str(i)
        label = "used" if i % 2 == 0 else "not_interested"
        papers.append(make_paper(pid, f"Title {i}", summary=f"Summary about topic {i % 2}"))
        marks[pid] = label
    model = train_model(papers, marks)
    assert model is not None
    assert "vectorizer" in model and "classifier" in model


def test_rank_candidates_returns_unchanged_order_when_model_is_none():
    candidates = [make_paper("a", "A"), make_paper("b", "B")]
    result = rank_candidates(None, candidates)
    assert result == candidates


def test_select_flexible_slots_returns_requested_count():
    candidates = [make_paper(str(i), f"Title {i}") for i in range(12)]
    result = select_flexible_slots(None, candidates, slot_count=6)
    assert len(result) == 6

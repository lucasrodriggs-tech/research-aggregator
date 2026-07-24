from scripts.site_data import group_by_date, latest_date, category_counts


def make_paper(id, date, category="neuroscience"):
    return {"id": id, "date_surfaced": date, "category": category}


def test_group_by_date_splits_papers_by_date():
    papers = [make_paper("a", "2026-07-24"), make_paper("b", "2026-07-25"), make_paper("c", "2026-07-25")]
    groups = group_by_date(papers)
    assert set(groups.keys()) == {"2026-07-24", "2026-07-25"}
    assert len(groups["2026-07-25"]) == 2


def test_latest_date_returns_max_date():
    papers = [make_paper("a", "2026-07-24"), make_paper("b", "2026-07-25")]
    assert latest_date(papers) == "2026-07-25"


def test_latest_date_returns_none_for_empty_list():
    assert latest_date([]) is None


def test_category_counts_counts_per_category_for_given_date():
    papers = [
        make_paper("a", "2026-07-25", "neuroscience"),
        make_paper("b", "2026-07-25", "cell_therapy"),
        make_paper("c", "2026-07-25", "cell_therapy"),
        make_paper("d", "2026-07-24", "cell_therapy"),
    ]
    counts = category_counts(papers, "2026-07-25")
    assert counts == {"neuroscience": 1, "cell_therapy": 2}

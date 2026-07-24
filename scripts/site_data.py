def group_by_date(papers):
    groups = {}
    for paper in papers:
        date = paper["date_surfaced"]
        groups.setdefault(date, []).append(paper)
    return groups


def latest_date(papers):
    dates = {paper["date_surfaced"] for paper in papers}
    return max(dates) if dates else None


def category_counts(papers, date):
    counts = {}
    for paper in papers:
        if paper["date_surfaced"] == date:
            counts[paper["category"]] = counts.get(paper["category"], 0) + 1
    return counts

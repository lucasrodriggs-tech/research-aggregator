import json

MIN_LABELED_EXAMPLES = 15


def build_training_text(paper):
    return f"{paper['title']} {paper['summary']} {paper['category']}"


def build_training_set(papers, marks):
    texts = []
    labels = []
    papers_by_id = {p["id"]: p for p in papers}
    for paper_id, mark in marks.items():
        if mark not in ("used", "not_interested"):
            continue
        paper = papers_by_id.get(paper_id)
        if paper is None:
            continue
        texts.append(build_training_text(paper))
        labels.append(1 if mark == "used" else 0)
    return texts, labels


def train_model(papers, marks):
    texts, labels = build_training_set(papers, marks)
    if len(texts) < MIN_LABELED_EXAMPLES:
        return None
    if len(set(labels)) < 2:
        return None

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
    X = vectorizer.fit_transform(texts)
    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(X, labels)
    return {"vectorizer": vectorizer, "classifier": classifier}


def rank_candidates(model, candidates):
    if model is None:
        return candidates
    texts = [build_training_text(c) for c in candidates]
    X = model["vectorizer"].transform(texts)
    scores = model["classifier"].predict_proba(X)[:, 1]
    scored = list(zip(candidates, scores))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [c for c, _ in scored]


def select_flexible_slots(model, candidates, slot_count=6):
    ranked = rank_candidates(model, candidates)
    return ranked[:slot_count]


if __name__ == "__main__":
    with open("data/papers.json", encoding="utf-8") as f:
        papers = json.load(f)
    with open("data/marks.json", encoding="utf-8") as f:
        marks = json.load(f)
    model = train_model(papers, marks)
    texts, _ = build_training_set(papers, marks)
    if model is None:
        print(f"Cold start: {len(texts)} labeled examples (need {MIN_LABELED_EXAMPLES}), skipping training")
    else:
        print(f"Model trained on {len(texts)} labeled examples")

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_papers import validate_papers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "papers.json"
TEMPLATE_PATH = ROOT / "site" / "artifact_template.html"
OUTPUT_PATH = ROOT / "docs" / "index.html"
PLACEHOLDER = "__PAPERS_DATA__"


def load_papers(path=DATA_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_html(papers, template_path=TEMPLATE_PATH):
    template = Path(template_path).read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise ValueError(f"Template is missing the {PLACEHOLDER} placeholder")
    data_json = json.dumps(papers, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, data_json)


def build(data_path=DATA_PATH, template_path=TEMPLATE_PATH, output_path=OUTPUT_PATH):
    papers = load_papers(data_path)
    errors = validate_papers(papers)
    if errors:
        raise ValueError("papers.json failed validation:\n" + "\n".join(errors))
    html = render_html(papers, template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    written_path = build()
    print(f"Wrote {written_path}")

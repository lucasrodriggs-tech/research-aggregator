import json

from scripts.build_site import render_html, build, PLACEHOLDER

SAMPLE_TEMPLATE = '<html><body><script id="papers-data" type="application/json">__PAPERS_DATA__</script></body></html>'


def make_valid_paper():
    return {
        "id": "test-1", "title": "Test Paper", "link": "https://example.com/paper",
        "summary": "A test summary.", "journal": "Test Journal", "year": 2026,
        "category": "neuroscience", "date_surfaced": "2026-07-25",
        "retraction_status": "No retraction found.", "citation_count": 10,
        "citation_source": "Semantic Scholar", "citation_checked_date": "2026-07-24",
        "contradicting_papers": [],
    }


def test_render_html_embeds_papers_as_valid_json(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    papers = [make_valid_paper()]

    html = render_html(papers, template_path)

    assert PLACEHOLDER not in html
    start = html.index('type="application/json">') + len('type="application/json">')
    end = html.index("</script>", start)
    embedded = json.loads(html[start:end])
    assert embedded == papers


def test_render_html_raises_if_placeholder_missing(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text("<html>no placeholder here</html>", encoding="utf-8")

    try:
        render_html([], template_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert PLACEHOLDER in str(e)


def test_render_html_escapes_script_close_tags_in_data(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    paper = make_valid_paper()
    paper["summary"] = "Contains a literal </script> tag in the text."

    html = render_html([paper], template_path)

    assert html.count("</script>") == 1
    assert "<\\/script>" in html


def test_build_writes_output_file_for_valid_data(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    data_path = tmp_path / "papers.json"
    data_path.write_text(json.dumps([make_valid_paper()]), encoding="utf-8")
    output_path = tmp_path / "dist" / "index.html"

    result_path = build(data_path=data_path, template_path=template_path, output_path=output_path)

    assert result_path == output_path
    assert output_path.exists()
    assert PLACEHOLDER not in output_path.read_text(encoding="utf-8")


def test_build_raises_on_invalid_data(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    data_path = tmp_path / "papers.json"
    bad_paper = make_valid_paper()
    del bad_paper["title"]
    data_path.write_text(json.dumps([bad_paper]), encoding="utf-8")
    output_path = tmp_path / "dist" / "index.html"

    try:
        build(data_path=data_path, template_path=template_path, output_path=output_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "title" in str(e)

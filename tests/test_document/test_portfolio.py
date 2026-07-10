from alteryx2dbx.document.portfolio import generate_portfolio_report


def test_portfolio_report_generated(tmp_path):
    results = [
        {
            "name": "wf_a",
            "tools_total": 10,
            "avg_confidence": 0.95,
            "supported": 10,
            "unsupported": 0,
            "readiness": "Ready",
        },
        {
            "name": "wf_b",
            "tools_total": 25,
            "avg_confidence": 0.65,
            "supported": 20,
            "unsupported": 5,
            "readiness": "Significant Manual Work",
        },
        {
            "name": "wf_c",
            "tools_total": 5,
            "avg_confidence": 0.82,
            "supported": 4,
            "unsupported": 1,
            "readiness": "Needs Review",
        },
    ]
    generate_portfolio_report(tmp_path, results)
    report_path = tmp_path / "portfolio_report.md"
    assert report_path.exists()
    content = report_path.read_text()
    assert "## Summary" in content
    assert "wf_a" in content
    assert "wf_b" in content


def test_portfolio_sorted_by_confidence(tmp_path):
    results = [
        {
            "name": "good",
            "tools_total": 5,
            "avg_confidence": 0.95,
            "supported": 5,
            "unsupported": 0,
            "readiness": "Ready",
        },
        {
            "name": "bad",
            "tools_total": 10,
            "avg_confidence": 0.40,
            "supported": 4,
            "unsupported": 6,
            "readiness": "Significant Manual Work",
        },
    ]
    generate_portfolio_report(tmp_path, results)
    content = (tmp_path / "portfolio_report.md").read_text()
    bad_pos = content.index("bad")
    good_pos = content.index("good")
    assert bad_pos < good_pos

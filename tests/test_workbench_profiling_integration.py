"""Exercise the optional profiling dependency used by the workbench."""

import pytest


def test_profile_report_renders_html() -> None:
    pytest.importorskip("data_profiling")
    pandas = pytest.importorskip("pandas")
    frame = pandas.DataFrame({"id": [1, 2, 3], "label": ["a", "b", "c"]})
    report = frame.profile_report(minimal=True, progress_bar=False)
    assert "<html" in report.to_html().lower()

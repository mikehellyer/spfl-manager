from spfl_manager.__main__ import self_test


def test_self_test_passes_and_counts_cup_matches(tmp_path):
    report = tmp_path / "selftest.txt"
    assert self_test(str(report)) == 0
    text = report.read_text()
    assert "SELF-TEST PASSED" in text
    assert "played League Cup Group Matchday 1: 16 matches" in text

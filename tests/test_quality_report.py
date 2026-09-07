from src.data.quality_report import parse_blocks


def test_parse_blocks_splits_on_name_markers():
    sql = """-- header comment
-- name: total_rows
SELECT count(*) FROM t;

-- name: hard_dupes
SELECT a FROM t GROUP BY a HAVING count(*) > 1;
"""
    blocks = parse_blocks(sql)
    names = [n for n, _ in blocks]
    assert names == ["total_rows", "hard_dupes"]
    assert blocks[0][1] == "SELECT count(*) FROM t"
    assert "HAVING" in blocks[1][1]
    assert not blocks[1][1].endswith(";")


def test_parse_blocks_ignores_unnamed_preamble():
    assert parse_blocks("SELECT 1;\n") == []

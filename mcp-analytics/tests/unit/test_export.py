import pytest

from mcp_analytics.export import new_export_id, resolve_export_path, write_csv


def test_write_and_resolve_roundtrip(tmp_path):
    eid = new_export_id()
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    path = write_csv(tmp_path, eid, ["a", "b"], rows)
    assert path.exists()
    resolved = resolve_export_path(tmp_path, eid)
    assert resolved == path
    # CSV header + 2 rows
    content = path.read_text().strip().splitlines()
    assert content[0] == "a,b"
    assert len(content) == 3


@pytest.mark.parametrize(
    "bad_id",
    ["../etc/passwd", "/absolute/path", "a/b", "a\\b", "..", ""],
)
def test_resolve_rejects_path_traversal(tmp_path, bad_id):
    with pytest.raises(ValueError):
        resolve_export_path(tmp_path, bad_id)


def test_resolve_errors_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_export_path(tmp_path, "deadbeef")


def test_new_export_id_is_random():
    a = new_export_id()
    b = new_export_id()
    assert a != b
    assert len(a) == 16  # 8 bytes hex

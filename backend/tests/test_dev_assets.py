"""app.dev.assets.write_snapshot — path containment and hostile-input handling.

Mirrors the containment pattern in app.services.snapshots.resolve(), which
write_snapshot's docstring explicitly calls out as reachable from Package B's
injector with a caller-supplied snapshot_key, not just the seeder's own
well-formed ones.
"""

from pathlib import Path

from app.dev.assets import write_snapshot


def test_writes_a_placeholder_under_the_root(tmp_path: Path):
    assert write_snapshot("2026/08/12/camera_1/abc.jpg", snapshot_root=tmp_path)
    target = tmp_path / "2026" / "08" / "12" / "camera_1" / "abc.jpg"
    assert target.is_file()
    assert target.read_bytes()


def test_refuses_to_overwrite_an_existing_file(tmp_path: Path):
    key = "camera_1/abc.jpg"
    assert write_snapshot(key, snapshot_root=tmp_path)
    assert not write_snapshot(key, snapshot_root=tmp_path)


def test_rejects_a_traversal_key(tmp_path: Path):
    assert not write_snapshot("../../etc/passwd", snapshot_root=tmp_path)
    assert not (tmp_path.parent / "etc").exists()


def test_rejects_an_absolute_path_key(tmp_path: Path):
    outside = tmp_path.parent / "outside.jpg"
    assert not write_snapshot(str(outside), snapshot_root=tmp_path)
    assert not outside.exists()


def test_rejects_a_null_byte_key_instead_of_raising(tmp_path: Path):
    # .resolve() raises ValueError/OSError on an embedded null byte rather
    # than returning — this must reject cleanly, not propagate as a 500.
    assert not write_snapshot("camera_1/ab\x00c.jpg", snapshot_root=tmp_path)

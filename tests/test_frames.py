import csv
import json
import subprocess
from pathlib import Path

import pytest

from extract.frames import extract


@pytest.fixture()
def synthetic_video(tmp_path: Path) -> Path:
    """2 s of 29.97 fps lossless test pattern."""
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=30000/1001:duration=2",
         "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", str(src)],
        check=True)
    return src


def test_frame_count_matches_ffprobe(synthetic_video: Path, tmp_path: Path):
    idx = extract(synthetic_video, "synthetic", frames_root=tmp_path / "frames",
                  derived_root=tmp_path / "derived")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(synthetic_video)],
        capture_output=True, text=True, check=True)
    assert idx.n_frames == int(out.stdout.strip())
    assert abs(idx.fps - 29.97) < 0.01
    rows = list(csv.DictReader((tmp_path / "derived" / "synthetic" / "frames.csv").open()))
    assert len(rows) == idx.n_frames
    meta = json.loads((tmp_path / "derived" / "synthetic" / "frames_meta.json").read_text())
    assert meta["n_frames"] == idx.n_frames and len(meta["source_sha256"]) == 64


def test_duplicates_detected(tmp_path: Path):
    """A clip built from a still image is all duplicates after the first frame."""
    src = tmp_path / "still.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:size=64x48:rate=10:duration=1",
         "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", str(src)], check=True)
    idx = extract(src, "still", frames_root=tmp_path / "frames", derived_root=tmp_path / "derived")
    assert idx.n_frames == 10
    assert idx.n_dups == 9


def test_extraction_is_deterministic(synthetic_video: Path, tmp_path: Path):
    a = extract(synthetic_video, "a", frames_root=tmp_path / "f", derived_root=tmp_path / "d")
    b = extract(synthetic_video, "b", frames_root=tmp_path / "f", derived_root=tmp_path / "d")
    assert a.frame_set_sha256 == b.frame_set_sha256

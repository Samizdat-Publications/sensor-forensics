"""The app's playback videos (tools/build_app_data.py export_video) are frame-exact: decoded frame i of
app/data/video/<case>.mp4 is the extracted frame i (data/frames/<folder>/f<i>.png), not a neighbour. The app reads
the frame on screen from the video's clock (app/js/player.js), so an off-by-one here would put the re-render one
frame away from the footage. Also: the per-variant prediction files the app loads equal predictions.json."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "data"
CASES = {"gimbal": "gimbal", "gofast": "gofast", "flir1": "flir1_navy"}


def _decode(video: Path, frames: list[int], w: int, h: int) -> dict[int, np.ndarray]:
    expr = "+".join(f"eq(n\\,{i})" for i in frames)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select={expr}", "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(float)
    assert len(arr) == len(frames), f"decoded {len(arr)} of {len(frames)} frames"
    return dict(zip(frames, arr))


def _png(folder: str, i: int) -> np.ndarray:
    return np.asarray(Image.open(ROOT / "data" / "frames" / folder / f"f{i:06d}.png").convert("L"), float)


@pytest.mark.parametrize("cid", list(CASES))
def test_video_frames_match_the_extracted_frames(cid):
    assert shutil.which("ffmpeg"), "ffmpeg is needed"
    video = APP / "video" / f"{cid}.mp4"
    assert video.exists(), f"{video} missing: run tools/build_app_data.py"
    meta = json.loads((APP / cid / "meta.json").read_text(encoding="utf-8"))
    n = meta["n_frames"]
    folder = CASES[cid]
    h, w = _png(folder, 0).shape
    sample = sorted({1, n // 5, n // 2, (4 * n) // 5, n - 2})
    got = _decode(video, sample, w, h)
    for i in sample:
        err = {j: float(np.mean(np.abs(got[i] - _png(folder, j)))) for j in (i - 1, i, i + 1)}
        # a tie is a match: the source repeats some frames (FLIR1's first two are identical)
        assert err[i] <= min(err.values()) + 1e-9, f"{cid} frame {i}: closest extracted frame is {min(err, key=err.get)} ({err})"
        assert err[i] < 4.0, f"{cid} frame {i}: mean abs error {err[i]:.2f} grey levels"
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=nb_read_frames,r_frame_rate", "-of", "json", str(video)], capture_output=True, check=True, text=True)
    st = json.loads(probe.stdout)["streams"][0]
    assert int(st["nb_read_frames"]) == n, f"{cid}: {st['nb_read_frames']} frames in the video, {n} extracted"
    num, den = (int(x) for x in st["r_frame_rate"].split("/"))
    assert abs(num / den - meta["fps"]) < 1e-6, f"{cid}: video rate {num}/{den}, frames at {meta['fps']}"


@pytest.mark.parametrize("cid", list(CASES))
def test_per_variant_predictions_equal_the_full_export(cid):
    meta = json.loads((APP / cid / "meta.json").read_text(encoding="utf-8"))
    full = json.loads((APP / cid / "predictions.json").read_text(encoding="utf-8"))
    assert set(meta["predictions_files"]) == set(full["variants"])
    for vn, name in meta["predictions_files"].items():
        part = json.loads((APP / cid / name).read_text(encoding="utf-8"))
        assert part["picture"] == full["picture"] and part["measured"] == full["measured"]
        for h, fits in full["variants"][vn]["hypotheses"].items():
            for fn, f in fits.items():
                slim = {k: x for k, x in f.items() if k not in ("img_x", "img_y")}
                assert part["data"]["hypotheses"][h][fn] == slim, f"{cid} {vn} {h} {fn}"

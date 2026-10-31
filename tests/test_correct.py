"""Tests for the symbology correction tool (M1.5): extract/merge.py and extract/correct/server.py.

Everything runs on a tiny fake case in a temporary directory; the real data/derived is never written.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import cv2
import numpy as np
import pandas as pd
import pytest

from extract import merge as mg
from extract.correct import server as srvmod

CASE = "fake"
LAYOUT = """\
video: fake
size: [64, 48]
fields:
  azimuth: {box: [10, 5, 40, 15], kind: text}
  zoom:    {box: [10, 20, 30, 30], kind: text}
"""
SYMBOLOGY = (
    "frame,field,value,raw,confidence,method\n"
    "0,azimuth,54L,54°L,0.5000,template\n"
    "0,zoom,2.0,2.0,0.9000,template\n"
    "1,azimuth,53L,53°L,0.1000,template\n"
    "1,zoom,2.0,2.0,0.0800,template\n"
    "2,azimuth,52L,52°L,0.9500,template\n"
    "2,zoom,blank,___,0.2000,blank\n"
)


@pytest.fixture()
def fake(tmp_path):
    """A fake data root: derived/fake/symbology.csv, frames/fake/f00000N.png (3 frames), and a layout."""
    derived = tmp_path / "derived" / CASE
    frames = tmp_path / "frames" / CASE
    derived.mkdir(parents=True)
    frames.mkdir(parents=True)
    (derived / "symbology.csv").write_text(SYMBOLOGY, encoding="utf-8")
    for i in range(3):
        img = np.full((48, 64, 3), 20 * (i + 1), np.uint8)
        cv2.rectangle(img, (12, 7), (20, 12), (255, 255, 255), -1)
        assert cv2.imwrite(str(frames / f"f{i:06d}.png"), img)
    layout = tmp_path / "fake.yaml"
    layout.write_text(LAYOUT, encoding="utf-8")
    return tmp_path, derived, layout


# --------------------------------------------------------------------------- merge

def test_merge_without_corrections_equals_symbology(fake):
    _, derived, _ = fake
    df = mg.merge(CASE, derived)
    base = pd.read_csv(derived / "symbology.csv", dtype=str, keep_default_na=False)
    assert list(df.columns) == mg.FINAL_COLUMNS
    assert len(df) == len(base)
    assert df["value"].tolist() == base["value"].tolist()
    assert (df["method"] == base["method"]).all()
    assert (df["previous_value"] == "").all()


def test_merge_correction_overrides_and_keeps_previous(fake):
    _, derived, _ = fake
    (derived / "corrections.json").write_text(json.dumps([
        {"frame": 1, "field": "azimuth", "value": "54L", "previous_value": "53L", "note": "",
         "source": "manual", "when": "2026-10-30T12:00:00-04:00"},
    ]), encoding="utf-8")
    df = mg.merge(CASE, derived)
    row = df[(df.frame == 1) & (df.field == "azimuth")].iloc[0]
    assert row["value"] == "54L"
    assert row["method"] == "manual"
    assert row["previous_value"] == "53L"
    assert row["confidence"] == 1.0
    assert float(row["previous_confidence"]) == pytest.approx(0.1)
    other = df[(df.frame == 1) & (df.field == "zoom")].iloc[0]
    assert other["method"] == "template" and other["previous_value"] == ""


def test_merge_removal_restores_machine_value(fake):
    _, derived, _ = fake
    path = derived / "corrections.json"
    path.write_text(json.dumps([{"frame": 0, "field": "zoom", "value": "3.0"}]), encoding="utf-8")
    assert mg.merge(CASE, derived).query("frame == 0 and field == 'zoom'").iloc[0]["value"] == "3.0"
    path.write_text("[]", encoding="utf-8")
    row = mg.merge(CASE, derived).query("frame == 0 and field == 'zoom'").iloc[0]
    assert row["value"] == "2.0" and row["method"] == "template" and row["previous_value"] == ""


def test_merge_cli_writes_final_csv(fake):
    root, derived, _ = fake
    (derived / "corrections.json").write_text(json.dumps([{"frame": 2, "field": "zoom", "value": "2.0"}]),
                                              encoding="utf-8")
    mg.main([CASE, "--data-root", str(root)])
    final = pd.read_csv(derived / "symbology_final.csv", dtype=str, keep_default_na=False)
    row = final[(final.frame == "2") & (final.field == "zoom")].iloc[0]
    assert row["value"] == "2.0" and row["method"] == "manual" and row["previous_value"] == "blank"


# --------------------------------------------------------------------------- server API

class Running:
    def __init__(self, root, layout):
        self.srv = srvmod.make_server(srvmod.Config.for_case(CASE, root, layout), port=0)
        self.port = self.srv.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.status, r.headers.get("Content-Type"), r.read()

    def post(self, body, ctype="application/json"):
        req = urllib.request.Request(self.base + "/api/correct", data=json.dumps(body).encode(),
                                     headers={"Content-Type": ctype}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


def test_server_binds_loopback_only(fake):
    root, _, layout = fake
    with Running(root, layout) as s:
        assert s.srv.server_address[0] == "127.0.0.1"


def test_server_items_and_filters(fake):
    root, _, layout = fake
    with Running(root, layout) as s:
        _, _, body = s.get("/api/items?filter=lowconf&threshold=0.3")
        items = json.loads(body)
        assert [(i["frame"], i["field"]) for i in items] == [(1, "azimuth"), (1, "zoom"), (2, "zoom")]
        assert all(i["corrected"] is False for i in items)
        assert len(json.loads(s.get("/api/items?filter=all")[2])) == 6
        zoom = json.loads(s.get("/api/items?filter=field=zoom")[2])
        assert {i["field"] for i in zoom} == {"zoom"} and len(zoom) == 3
        assert len(json.loads(s.get("/api/items?filter=lowconf&threshold=0.09")[2])) == 1
        with pytest.raises(urllib.error.HTTPError) as e:
            s.get("/api/items?filter=field=nope")
        assert e.value.code == 400


def test_server_images(fake):
    root, _, layout = fake
    with Running(root, layout) as s:
        status, ctype, png = s.get("/api/crop?frame=0&field=azimuth&scale=4")
        assert status == 200 and ctype == "image/png"
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        # box 30 x 10 plus 2 px margin on each side, enlarged 4x
        assert img.shape[:2] == ((10 + 4) * 4, (30 + 4) * 4)
        _, _, png = s.get("/api/context?frame=1&field=azimuth")
        ctx = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        assert ctx.shape[:2] == (96, 128)
        with pytest.raises(urllib.error.HTTPError) as e:
            s.get("/api/crop?frame=99&field=azimuth")
        assert e.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as e:
            s.get("/api/crop?frame=0&field=nope")
        assert e.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as e:
            s.get("/api/crop?frame=0&field=azimuth&scale=1000")
        assert e.value.code == 400
        assert b"<title>" in s.get("/")[2]


def test_server_correct_add_replace_remove(fake):
    root, derived, layout = fake
    path = derived / "corrections.json"
    with Running(root, layout) as s:
        status, res = s.post({"frame": 1, "field": "azimuth", "value": "54L", "note": "read at 8x"})
        assert status == 200 and res["ok"]
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1
        c = data[0]
        assert (c["frame"], c["field"], c["value"], c["previous_value"], c["note"], c["source"]) == \
               (1, "azimuth", "54L", "53L", "read at 8x", "manual")
        assert "T" in c["when"]
        # a second correction for the same item replaces the first; previous_value stays the machine read
        assert s.post({"frame": 1, "field": "azimuth", "value": "55L"})[0] == 200
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1 and data[0]["value"] == "55L" and data[0]["previous_value"] == "53L"
        items = json.loads(s.get("/api/items?filter=all")[2])
        hit = [i for i in items if (i["frame"], i["field"]) == (1, "azimuth")][0]
        assert hit["corrected"] is True and hit["correction"] == "55L" and hit["value"] == "53L"
        # null removes
        status, res = s.post({"frame": 1, "field": "azimuth", "value": None})
        assert status == 200 and res["removed"] is True
        assert json.loads(path.read_text(encoding="utf-8")) == []
        # removing something that does not exist is harmless
        assert s.post({"frame": 0, "field": "zoom", "value": None})[1]["removed"] is False
    # the merge sees what the server wrote
    path.write_text(json.dumps([{"frame": 0, "field": "azimuth", "value": "55L"}]), encoding="utf-8")
    assert mg.merge(CASE, derived).query("frame == 0 and field == 'azimuth'").iloc[0]["value"] == "55L"


@pytest.mark.parametrize("body", [
    {"frame": 99, "field": "azimuth", "value": "1"},            # frame out of range
    {"frame": -1, "field": "azimuth", "value": "1"},
    {"frame": "0", "field": "azimuth", "value": "1"},           # not an integer
    {"frame": True, "field": "azimuth", "value": "1"},
    {"frame": 0, "field": "../evil", "value": "1"},             # field not in the layout
    {"frame": 0, "field": "nope", "value": "1"},
    {"frame": 0, "field": "azimuth", "value": "x" * 33},        # too long
    {"frame": 0, "field": "azimuth", "value": ""},
    {"frame": 0, "field": "azimuth", "value": "a\nb"},
    {"frame": 0, "field": "azimuth", "value": 5},
    {"frame": 0, "field": "azimuth", "value": "1", "note": "n" * 501},
])
def test_server_rejects_bad_input(fake, body):
    root, derived, layout = fake
    with Running(root, layout) as s:
        status, res = s.post(body)
        assert status == 400 and "error" in res
    assert not (derived / "corrections.json").exists()


def test_server_rejects_wrong_content_type_and_stays_inside_case_dir(fake):
    root, derived, layout = fake
    with Running(root, layout) as s:
        assert s.post({"frame": 0, "field": "azimuth", "value": "1"}, ctype="text/plain")[0] == 415
        assert s.post({"frame": 0, "field": "azimuth", "value": "1"})[0] == 200
    written = sorted(p.name for p in root.rglob("*") if p.is_file() and p.suffix in {".json", ".tmp"})
    assert written == ["corrections.json"]
    assert (derived / "corrections.json").exists()


# --------------------------------------------------------------------------- browser

def test_browser_types_correction_and_presses_enter(fake):
    """Headless Chromium: load the page, type a correction, press Enter, check corrections.json."""
    from playwright.sync_api import sync_playwright

    root, derived, layout = fake
    with Running(root, layout) as s:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 800})
                page.goto(s.base + "/")
                page.wait_for_function("document.getElementById('progress').textContent.startsWith('Item 1 of 3')")
                assert page.input_value("#value") == "53L"        # first low-confidence item: frame 1 azimuth
                # The crop loads asynchronously and focus lands after render: wait for both
                # instead of asserting immediately (this race made the test intermittent).
                page.wait_for_function("(() => { const i = document.getElementById('img'); return i.complete && i.naturalWidth > 0; })()")
                page.wait_for_function("document.activeElement && document.activeElement.id === 'value'")
                # typing replaces the selected value, Enter saves and advances
                page.keyboard.type("55L")
                page.wait_for_function("document.getElementById('value').value === '55L'")
                page.keyboard.press("Enter")
                page.wait_for_function("document.getElementById('progress').textContent.startsWith('Item 2 of 3')")
                data = json.loads((derived / "corrections.json").read_text(encoding="utf-8"))
                assert len(data) == 1
                assert (data[0]["frame"], data[0]["field"], data[0]["value"], data[0]["previous_value"]) ==                        (1, "azimuth", "55L", "53L")
                assert data[0]["source"] == "manual"
                # Enter with no change records nothing and moves on
                assert page.input_value("#value") == "2.0"        # frame 1 zoom
                page.keyboard.press("Enter")
                page.wait_for_function("document.getElementById('progress').textContent.startsWith('Item 3 of 3')")
                assert len(json.loads((derived / "corrections.json").read_text(encoding="utf-8"))) == 1
                # Left twice goes back and shows the saved correction; F toggles the context view
                page.keyboard.press("ArrowLeft")
                page.keyboard.press("ArrowLeft")
                page.wait_for_function("document.getElementById('progress').textContent.startsWith('Item 1 of 3')")
                assert page.input_value("#value") == "55L"
                page.keyboard.press("f")
                assert "/api/context" in page.get_attribute("#img", "src")
                page.keyboard.press("F")
                assert "/api/crop" in page.get_attribute("#img", "src")
                page.keyboard.press("ArrowRight")
                page.wait_for_function("document.getElementById('progress').textContent.startsWith('Item 2 of 3')")
                # the page never shows an em dash
                assert chr(0x2014) not in page.content()
            finally:
                browser.close()

"""Manual correction tool for the per-frame symbology readings (M1.5).

    python -m extract.correct.server <case> --port 8765

Standard-library HTTP server bound to 127.0.0.1 only. Serves one page (index.html) and a small
JSON/PNG API; corrections are written to data/derived/<case>/corrections.json and applied by
`python -m extract.merge <case>`.

    GET  /                                  the page
    GET  /api/info                          case name, field names, frame count
    GET  /api/items?filter=lowconf|all|field=<name>&threshold=0.3
    GET  /api/crop?frame=N&field=F&scale=4  field box enlarged (nearest neighbor), 2 px margin
    GET  /api/context?frame=N[&field=F]     whole frame, field box outlined
    POST /api/correct  {frame, field, value, note}   value null removes the correction
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import yaml

from extract.merge import ROOT, read_corrections, read_symbology

HERE = Path(__file__).resolve().parent
HOST = "127.0.0.1"
CASE_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_VALUE_LEN = 32
MAX_NOTE_LEN = 500
MAX_BODY = 20_000
MARGIN = 2
DEFAULT_THRESHOLD = 0.3


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Config:
    case: str
    derived: Path          # data/derived/<case>, the only place this server writes
    frames: Path           # data/frames/<case>
    layout: Path           # extract/layouts/<case>.yaml

    @classmethod
    def for_case(cls, case: str, data_root: Path | None = None, layout: Path | None = None) -> "Config":
        if not CASE_RE.match(case):
            raise ValueError(f"bad case name: {case!r}")
        dr = Path(data_root) if data_root is not None else ROOT / "data"
        return cls(
            case=case,
            derived=dr / "derived" / case,
            frames=dr / "frames" / case,
            layout=Path(layout) if layout is not None else ROOT / "extract" / "layouts" / f"{case}.yaml",
        )


class Store:
    """Everything the handlers need, loaded once; corrections are re-read on every request."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()
        lay = yaml.safe_load(cfg.layout.read_text(encoding="utf-8"))
        self.boxes: dict[str, tuple[int, int, int, int]] = {
            n: tuple(int(v) for v in f["box"]) for n, f in lay["fields"].items()
        }
        self.sym = read_symbology(cfg.derived / "symbology.csv")
        self.frames = set(int(f) for f in self.sym["frame"])
        self.corr_path = cfg.derived / "corrections.json"

    # -- corrections --------------------------------------------------------
    def corrections(self) -> list[dict]:
        return read_corrections(self.corr_path)

    def _write_corrections(self, items: list[dict]) -> None:
        target = self.corr_path.resolve()
        if target.parent != self.cfg.derived.resolve():
            raise ApiError("refusing to write outside the case directory", 500)
        self.cfg.derived.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".corrections.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(items, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, target)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def machine_value(self, frame: int, field: str) -> str:
        m = self.sym[(self.sym["frame"] == frame) & (self.sym["field"] == field)]
        return str(m.iloc[0]["value"]) if len(m) else ""

    def correct(self, body: dict) -> dict:
        frame = body.get("frame")
        field = body.get("field")
        if isinstance(frame, bool) or not isinstance(frame, int):
            raise ApiError("frame must be an integer")
        if frame not in self.frames:
            raise ApiError(f"frame {frame} out of range")
        if not isinstance(field, str) or field not in self.boxes:
            raise ApiError("unknown field")
        value = body.get("value")
        note = body.get("note", "")
        if note is None:
            note = ""
        if not isinstance(note, str) or len(note) > MAX_NOTE_LEN:
            raise ApiError("note must be a string of at most %d characters" % MAX_NOTE_LEN)
        if value is not None:
            if not isinstance(value, str):
                raise ApiError("value must be a string or null")
            value = value.strip()
            if not value or len(value) > MAX_VALUE_LEN or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise ApiError("value must be 1 to %d printable characters" % MAX_VALUE_LEN)
        with self.lock:
            items = self.corrections()
            kept = [c for c in items if not (c["frame"] == frame and c["field"] == field)]
            if value is None:
                removed = len(kept) != len(items)
                if removed:
                    self._write_corrections(kept)
                return {"ok": True, "removed": removed, "count": len(kept)}
            kept.append({
                "frame": frame,
                "field": field,
                "value": value,
                "previous_value": self.machine_value(frame, field),
                "note": note,
                "source": "manual",
                "when": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            kept.sort(key=lambda c: (c["frame"], c["field"]))
            self._write_corrections(kept)
            return {"ok": True, "removed": False, "count": len(kept)}

    # -- items --------------------------------------------------------------
    def items(self, flt: str, threshold: float) -> list[dict]:
        df = self.sym
        if flt == "lowconf":
            df = df[df["confidence"] < threshold]
        elif flt.startswith("field="):
            name = flt[len("field="):]
            if name not in self.boxes:
                raise ApiError("unknown field")
            df = df[df["field"] == name]
        elif flt != "all":
            raise ApiError("filter must be lowconf, all or field=<name>")
        cmap = {(c["frame"], c["field"]): c for c in self.corrections()}
        out = []
        for r in df.itertuples(index=False):
            c = cmap.get((int(r.frame), r.field))
            out.append({
                "frame": int(r.frame), "field": r.field, "value": r.value,
                "confidence": round(float(r.confidence), 4), "method": r.method,
                "corrected": c is not None,
                "correction": c["value"] if c else None,
            })
        return out

    # -- images -------------------------------------------------------------
    def frame_image(self, frame: int):
        if frame not in self.frames:
            raise ApiError(f"frame {frame} out of range", 404)
        p = self.cfg.frames / f"f{frame:06d}.png"
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            raise ApiError(f"frame image missing: {p.name}", 404)
        return img

    def crop_png(self, frame: int, field: str, scale: int) -> bytes:
        img = self.frame_image(frame)
        h, w = img.shape[:2]
        x0, y0, x1, y1 = self.boxes[field]
        x0, y0 = max(0, x0 - MARGIN), max(0, y0 - MARGIN)
        x1, y1 = min(w, x1 + MARGIN), min(h, y1 + MARGIN)
        c = img[y0:y1, x0:x1]
        c = cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        return encode_png(c)

    def context_png(self, frame: int, field: str | None) -> bytes:
        img = self.frame_image(frame).copy()
        boxes = [self.boxes[field]] if field else list(self.boxes.values())
        for x0, y0, x1, y1 in boxes:
            cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 255) if field else (0, 160, 255), 1)
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        return encode_png(img)


def encode_png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ApiError("png encode failed", 500)
    return buf.tobytes()


def make_handler(store: Store):
    page = (HERE / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        server_version = "SymbologyCorrect/1"

        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status: int = 200) -> None:
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

        def _int(self, q, name: str, default=None, lo=None, hi=None) -> int:
            raw = q.get(name, [None])[0]
            if raw is None:
                if default is None:
                    raise ApiError(f"missing {name}")
                return default
            try:
                v = int(raw)
            except ValueError:
                raise ApiError(f"{name} must be an integer")
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                raise ApiError(f"{name} out of range")
            return v

        def _field(self, q) -> str:
            f = q.get("field", [None])[0]
            if f not in store.boxes:
                raise ApiError("unknown field")
            return f

        def do_GET(self):
            try:
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path in ("/", "/index.html"):
                    self._send(200, page, "text/html; charset=utf-8")
                elif u.path == "/api/info":
                    self._json({"case": store.cfg.case, "fields": list(store.boxes),
                                "frames": len(store.frames),
                                "boxes": {n: list(b) for n, b in store.boxes.items()}})
                elif u.path == "/api/items":
                    flt = q.get("filter", ["lowconf"])[0]
                    try:
                        thr = float(q.get("threshold", [DEFAULT_THRESHOLD])[0])
                    except ValueError:
                        raise ApiError("threshold must be a number")
                    self._json(store.items(flt, thr))
                elif u.path == "/api/crop":
                    frame = self._int(q, "frame")
                    scale = self._int(q, "scale", default=4, lo=1, hi=16)
                    self._send(200, store.crop_png(frame, self._field(q), scale), "image/png")
                elif u.path == "/api/context":
                    frame = self._int(q, "frame")
                    field = self._field(q) if "field" in q else None
                    self._send(200, store.context_png(frame, field), "image/png")
                else:
                    raise ApiError("not found", 404)
            except ApiError as e:
                self._json({"error": str(e)}, e.status)

        def do_POST(self):
            try:
                u = urlparse(self.path)
                if u.path != "/api/correct":
                    raise ApiError("not found", 404)
                if not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise ApiError("Content-Type must be application/json", 415)
                origin = self.headers.get("Origin")
                if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                    raise ApiError("cross-origin request refused", 403)
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise ApiError("bad Content-Length")
                if n <= 0 or n > MAX_BODY:
                    raise ApiError("body missing or too large", 413 if n > MAX_BODY else 400)
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    raise ApiError("body is not valid JSON")
                if not isinstance(body, dict):
                    raise ApiError("body must be a JSON object")
                self._json(store.correct(body))
            except ApiError as e:
                self._json({"error": str(e)}, e.status)

    return Handler


def make_server(cfg: Config, port: int = 8765) -> ThreadingHTTPServer:
    """Bound to 127.0.0.1 only. port=0 picks a free port (server.server_address[1])."""
    store = Store(cfg)
    srv = ThreadingHTTPServer((HOST, port), make_handler(store))
    srv.daemon_threads = True
    srv.store = store  # type: ignore[attr-defined]
    return srv


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data-root", type=Path, default=None, help="default: <repo>/data")
    a = ap.parse_args(argv)
    srv = make_server(Config.for_case(a.case, a.data_root), a.port)
    print(f"Symbology correction tool for {a.case}: http://{HOST}:{srv.server_address[1]}/  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()

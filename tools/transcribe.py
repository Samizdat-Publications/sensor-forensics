"""Transcribe cockpit audio with faster-whisper, keeping word timings and confidences.

Output: data/derived/<case>/audio.json, labeled as inferred. Each word carries its
start and end time (seconds from the start of the clip), the frame index at that
time, and the model's probability. Low-probability words are what a human checks.

Usage:
    python tools/transcribe.py data/audio/gimbal.wav gimbal --model medium.en
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FPS = 30000 / 1001


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", type=Path)
    ap.add_argument("case")
    ap.add_argument("--model", default="medium.en")
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()

    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(a.model, device=a.device, compute_type="float16" if a.device != "cpu" else "int8")
    except Exception:  # no usable CUDA runtime: fall back to CPU
        model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(a.wav), language="en", word_timestamps=True,
                                      vad_filter=False, beam_size=5, temperature=0.0)
    segs = []
    for s in segments:
        segs.append({
            "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "avg_logprob": round(s.avg_logprob, 3), "no_speech_prob": round(s.no_speech_prob, 3),
            "words": [{"w": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2),
                       "frame": int(round(w.start * FPS)), "p": round(w.probability, 3)}
                      for w in (s.words or [])],
        })
    out = {
        "case": a.case,
        "status": "inferred (machine transcription, not checked by a person)",
        "source_audio": str(a.wav.as_posix()),
        "model": f"faster-whisper {a.model}",
        "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "language_prob": round(info.language_probability, 3),
        "segments": segs,
    }
    dest = ROOT / "data" / "derived" / a.case / "audio.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for s in segs:
        flag = "" if min((w["p"] for w in s["words"]), default=1) > 0.5 else "  [low-confidence words]"
        print(f"{s['start']:6.2f}-{s['end']:6.2f}  {s['text']}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

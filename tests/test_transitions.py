import cv2
import numpy as np

from extract.transitions import split_ratio


def glyph(text: str) -> np.ndarray:
    img = np.full((24, 60, 3), 40, np.uint8)
    cv2.putText(img, text, (4, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (235, 235, 235), 2)
    return img


def test_interlaced_mix_scores_high():
    prev, nxt = glyph("47"), glyph("48")
    mixed = prev.copy()
    mixed[1::2] = nxt[1::2]  # odd rows from the next value: an interlaced transition
    assert split_ratio(prev, mixed, nxt) > 2.0


def test_clean_frames_score_low():
    prev, nxt = glyph("47"), glyph("48")
    assert split_ratio(prev, nxt.copy(), nxt) < 1.3
    assert split_ratio(prev, prev.copy(), nxt) < 1.3

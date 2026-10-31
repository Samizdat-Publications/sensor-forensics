"""Golden test: Sitrec's default GOFAST result reproduced from Sitrec's own inputs.

Tolerances were stated in _PLAN.md before the first run: altitude within 300 ft and
speed within 5 kt of Sitrec's observed output (13,151 / 13,208 ft, about 64 kt toward
about 93 deg; docs/prior-work/sitrec.md).
"""

import pytest

from solve.repro_gofast import sitrec_way


def test_sitrec_gofast_reproduced_within_tolerance():
    r = sitrec_way()
    assert r["alt_ft_at_375"] == pytest.approx(13151, abs=300)
    assert r["alt_ft_at_1030"] == pytest.approx(13208, abs=300)
    assert r["ground_speed_kt"] == pytest.approx(64, abs=5)
    assert r["ground_track_deg"] == pytest.approx(93, abs=10)
    # Sitrec's reading: the object drifts with a 65 kt wind from 274 deg (air speed near zero).
    assert r["air_speed_kt_vs_65kt_from_274"] < 10

import numpy as np
import pytest

from solve import atmosphere as A
from solve.frames import FT, KT


def test_isa_reference_values():
    t, p, rho = A.isa(0.0)
    assert t == pytest.approx(288.15) and p == pytest.approx(101_325) and rho == pytest.approx(1.225, abs=1e-3)
    t, p, _ = A.isa(11_000.0)
    assert t == pytest.approx(216.65) and p == pytest.approx(22_632, rel=1e-3)
    t, p, _ = A.isa(25_000 * FT)
    assert t - 273.15 == pytest.approx(-34.5, abs=0.1)
    assert p == pytest.approx(37_600, rel=5e-3)


def test_cas_equals_tas_at_sea_level():
    assert A.cas_to_tas(150.0, 0.0) == pytest.approx(150.0, rel=1e-6)


def test_cas_to_tas_textbook_value():
    # E6B / standard tables: 250 KCAS at FL250 on a standard day is Mach 0.603, about 363 KTAS.
    assert A.cas_to_mach(250 * KT, 25_000 * FT) == pytest.approx(0.603, abs=0.002)
    assert A.cas_to_tas(250 * KT, 25_000 * FT) / KT == pytest.approx(363, abs=1.5)


def test_gimbal_airspeed_is_lower_than_2023_paper():
    # Peings and von Rennenkampff quote IAS 238 to 242 kt at 25,000 ft and -25 C as
    # TAS 363 to 369 kt. Standard compressible conversion gives about 354 to 360 kt
    # (ISA is -34.5 C there, so dT = +9.5 K). Logged as a disagreement for M0/M2.
    tas = A.cas_to_tas(np.array([238, 242]) * KT, 25_000 * FT, dT=9.5) / KT
    assert tas[0] == pytest.approx(353.6, abs=0.5)
    assert tas[1] == pytest.approx(359.6, abs=0.5)


def test_mach_round_trip():
    h = 25_000 * FT
    m = A.cas_to_mach(240 * KT, h)
    assert A.mach_to_tas(m, h) == pytest.approx(A.cas_to_tas(240 * KT, h), rel=1e-12)


def test_turn_rate_standard_rate_check():
    # 360 kt at 30 deg bank turns at about 1.75 deg/s.
    assert np.degrees(A.turn_rate(360 * KT, np.radians(30))) == pytest.approx(1.75, abs=0.03)

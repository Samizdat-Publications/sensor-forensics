"""Golden tests: the two published GIMBAL reconstructions reproduced from their own inputs (M2.7).

Tolerances were stated before the first run (work item M2.7, docs/reproductions/gimbal.md):
positions within 0.2 nmi, the frame of minimum ground speed within 60 frames, speeds within
15 percent at start and end. Where the reproduction misses, the test locks the miss and the
input that explains it, so a change in either is noticed.
"""

from dataclasses import replace

import numpy as np
import pytest

from solve import repro_gimbal as G


@pytest.fixture(scope="module")
def a_repro():
    return G.run_a(G.pvr_inputs())


@pytest.fixture(scope="module")
def sitrec_cloud_rate():
    return G.cloud_turn_rate(G.sitrec_inputs().az_deg)


def test_pvr_jet_track_matches_fig3(a_repro):
    # P&vR Fig. 3: no-wind end near (-1.65, 2.87) nmi, with 120 kt wind from -35 deg near (-1.0, 1.9).
    assert np.hypot(*(np.array(a_repro["jet_end_air_nmi"]) - [-1.65, 2.87])) < 0.2
    assert np.hypot(*(np.array(a_repro["jet_end_ground_nmi"]) - [-1.0, 1.9])) < 0.2


def test_pvr_close_path_positions_and_speeds(a_repro):
    c = G.check_a(a_repro)
    assert a_repro["start_range_nmi"] == pytest.approx(8.0, abs=1e-6)
    assert c["end_range_nmi"]["pass"]                      # 6.64 vs 6.8
    assert c["air_speed_start_kt"]["pass"]                 # about 373 vs 400
    assert c["ground_speed_start_kt"]["pass"]              # about 259 vs 300
    assert c["ground_speed_end_kt_over_120"]["pass"]
    assert c["air_speed_under_50_frame"]["pass"]           # air velocity reverses at about f880 vs f900
    assert a_repro["all_intersections_in_front"]
    assert 150 < a_repro["alt_change_ft"] < 450            # P&vR: about +250 ft (+300 in their Sitrec comparison)


def test_pvr_ground_speed_minimum_frame_is_the_known_miss(a_repro):
    # Locked miss: minimum ground speed at about f830 (published about f720), outside 60 frames.
    c = G.check_a(a_repro)
    assert not c["ground_speed_min_frame"]["pass"]
    assert 790 <= a_repro["ground_speed_min_frame"] <= 860


def test_cloud_matched_turn_rate_moves_the_minimum_into_tolerance(sitrec_cloud_rate):
    # P&vR correct the line of sight with cloud motion (unquantified, omitted here). Steering
    # the jet with Sitrec's cloud-matched turn rate instead moves the minimum to about f690.
    d = G.load_sitrec()
    rate = G.cloud_turn_rate(-d["5 gaussian_smoothed_azimuth"].to_numpy(float))
    r = G.run_a(replace(G.pvr_inputs(), turn_override=rate))
    assert abs(r["ground_speed_min_frame"] - 720) <= 60


def test_pvr_fig_a7_level_path_start_and_known_end_miss():
    r = G.run_a7(G.pvr_inputs())
    c = G.check_a7(r)
    assert c["range_near_30_nmi"]["pass"]                  # 29.7 to 30.5 nmi at 18,700 ft (flat Earth)
    assert c["air_speed_start_kt"]["pass"]                 # about 318 vs 300
    assert not c["air_speed_end_kt"]["pass"]               # about 530 vs 450: the last 150 frames
    assert 480 < r["air_speed_end_kt"] < 580


def test_fig_a7_reproduced_with_cloud_matched_turn_rate():
    d = G.load_sitrec()
    rate = G.cloud_turn_rate(-d["5 gaussian_smoothed_azimuth"].to_numpy(float))
    r = G.run_a7(replace(G.pvr_inputs(), turn_override=rate))
    assert G.check_a7(r)["all_pass"]                       # about 319 rising to 461 kt


def test_sitrec_far_path_bank_turn_rate_fails_its_premise():
    # "From Bank and Speed": the 340 kt constant-air-speed path from 32 nmi has no solution on
    # about 14 percent of frames; level and near 32 nmi where it exists.
    r = G.run_b(G.sitrec_inputs())
    c = G.check_b(r)
    assert not c["path_exists_bad_frames_under_5pct"]["pass"]
    assert 120 <= r["n_no_intersection_frames"] <= 170
    assert c["range_within_30_34_nmi"]["pass"] and c["level_within_500_ft"]["pass"]


def test_sitrec_far_path_with_match_clouds_is_straight_level_and_steady(sitrec_cloud_rate):
    r = G.run_b(G.sitrec_inputs(), turn_rate=sitrec_cloud_rate)
    assert G.check_b(r)["all_pass"]
    assert r["n_no_intersection_frames"] <= 2
    assert r["end_range_nmi"] == pytest.approx(32.8, abs=0.2)
    assert r["straightness_top_view"]["max_dev_nmi"] < 0.1
    assert r["air_heading_span_deg"] < 15
    lo, hi = r["ground_speed_kt_min_max"]
    assert hi - lo < 15
    a0, a1 = r["alt_min_max_ft"]
    assert 18_900 < a0 and a1 < 19_200


def test_cloud_port_and_bank_turn_rate_agree_on_total_heading_change(sitrec_cloud_rate):
    bank = G.turn_rate_deg_s(G.sitrec_inputs())
    assert np.sum(bank[:-1]) / G.FPS == pytest.approx(np.sum(sitrec_cloud_rate[:-1]) / G.FPS, abs=2.5)


def test_lab_azimuth_fit_stays_inside_every_readout_interval():
    az, info = G.interval_azimuth(G.lab_azimuth_readings())
    assert info["max_constraint_violation_deg"] <= 0.5 + 1e-9
    assert info["n_centers"] >= 55
    assert az[0] == pytest.approx(-54.2, abs=0.3) and az[-1] == pytest.approx(6.7, abs=0.5)

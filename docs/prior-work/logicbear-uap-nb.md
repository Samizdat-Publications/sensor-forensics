# logicbear / 0x1beef `uap_nb`: GIMBAL cloud-motion, object-geometry and GOFAST passive-ranging notebooks

- **Title:** `uap_nb` (Jupyter notebooks on UAP videos; no README in the repo)
- **Author:** GitHub user `0x1beef`; the notebooks name the Hugging Face account `logicbear` as the data host (`logicbear/gimbal`, `logicbear/gimbal_clouds`, `logicbear/gimbal_cloud_means`, `logicbear/uap`), so "logicbear" and "0x1beef" are the same author by the code's own references (inference, not stated in a profile).
- **Created / last push:** 06/01/2024 / 01/16/2026 (GitHub API)
- **URL:** https://github.com/0x1beef/uap_nb
- **Commit read:** `7c8852df564ad6090d7d362ca1427eb590a005b0` (01/16/2026, "Added transmittance experiments with LOWTRAN"). Raw URLs: `https://raw.githubusercontent.com/0x1beef/uap_nb/7c8852df564ad6090d7d362ca1427eb590a005b0/src/<file>`.
- **License:** MIT. The `LICENSE` file is the standard MIT text with the line "Copyright (c) 2024" and no named copyright holder. GitHub reports `license.spdx_id = MIT`.
- **Prepared:** 10/30/2026 by reading the notebook cells (code, markdown and printed text output; image outputs were not viewed). Cell numbers below are 0-based indices in the .ipynb.
- **Files in `src/`:** `common.py`, `utils.py`, `import_ipynb.py`, `opencv_cuda_installer.py`, `gimbal_clouds.ipynb`, `gimbal_adjust_clouds.ipynb`, `gimbal_object_data.ipynb`, `gofast_ranging.ipynb`, `interlacing.ipynb`, `opencv_cuda.ipynb`, `transmittance_lowtran.ipynb`. The intermediate datasets (`object_data.parquet`, `cloud_motion.parquet`, `cloud_means.parquet`) live on Hugging Face and were NOT downloaded in this task (not needed for the summary).

## What each notebook does (one line each)

| Notebook | Purpose |
|---|---|
| `gimbal_object_data.ipynb` | Per-frame object geometry (glare angle, centre of mass) from the Gimbal video, plus the "human horizon" series computed by running Sitrec headless |
| `gimbal_clouds.ipynb` | Optical-flow tracking of the cloud background per frame (magnitude, direction, rotation), saved to parquet |
| `gimbal_adjust_clouds.ipynb` | Corrects the cloud motion for the camera's own rotation and for the object's centre-of-mass motion |
| `gofast_ranging.ipynb` | Passive ranging for GOFAST: least-squares range and speed from the camera path and line of sight, assuming a constant-velocity target, with a simulated tracking-error model |
| `interlacing.ipynb` | Simulates the WMV/interlacing artifacts seen in Gimbal on a synthetic video (not read in detail) |
| `transmittance_lowtran.ipynb` | LOWTRAN IR transmittance experiments for a distant jet and for the cloud tops (Gimbal "distant jet" scenario, midlatitude winter atmosphere, clouds at 11,740 ft as in Sitrec); read only at heading level |
| `opencv_cuda.ipynb`, `opencv_cuda_installer.py` | Build helper for OpenCV with CUDA |

## Inputs

| Quantity | Value | Source location |
|---|---|---|
| Video | Navy FOIA `2 - GIMBAL.wmv` (13.5 MB), 1031 frames at 29.97 fps, fetched from Hugging Face `logicbear/uap` | gimbal_object_data cell 3 output; `common.gimbal_from_huggingface` (common.py) |
| Crop | ffmpeg `crop=428:428:104:27` (428 x 428 px, grayscale) for the Navy 2015 videos; FLIR1 crop 240:238:54:15 | common.py (`navy_2015_extract_frames`, `flir1_extract_frames`) |
| White-hot to black-hot switch | last white-hot frame 370, first black-hot frame 372 (frames in between are interpolated in plots) | gimbal_object_data cell 6; common.py `gimbal_fix_wh_to_bh` |
| WH to BH grey-level map | fitted curve y = a (x/255)^g 255 + b, (g, a, b) = (4.041, 0.434, -2.670), from ROI rows 166-250, cols 201-228 of frames 370 and 372 | gimbal_object_data cell 7 output |
| Object segmentation | central ROI (1/12 of height and width each side of centre), threshold at 0.2 x 255, largest contour with area under 0.7 x ROI | gimbal_object_data cell 9 |
| Human horizon | Sitrec `get_real_horizon_angle_for_frame(frame)` for each of 1031 frames, obtained by cloning Sitrec (shallow, HEAD at the time) and running `horizon.js` under bun | gimbal_object_data cells 12-17 |
| Cloud-top height above the object centre | piecewise-linear (time s, pixels): (0,25), (2,30), (4,30), (6,30), (8,50), (10,45), (12,40), (14,55), (16,45), (18,40), (20,40), (22,45), (24,50), (28,55), (30,60), (35,60); used only to build a "below the cloud top" mask | gimbal_clouds cell 9 |
| Overlay masks (pixel boxes excluded from flow) | (0,373,115,427), (194,412,243,427), (317,393,391,427), (369,256,426,323), (34,194,69,207), (384,346,426,359), (413,318,426,386) in (x0,y0,x1,y1) | gimbal_clouds cell 9 |
| GOFAST jet and target path | `jetTrack` and `LOSTraverseSelect` (default traverse) positions and `jetRollFromFrame` per frame, from Sitrec `gofast` sitch run headless | gofast_ranging cells 2-8 |

## Conventions and assumptions

- Image coordinates (x right, y down). `human_horizon` is Sitrec's horizon angle in degrees (negative values in the data: -16.62 at frame 0, -29.59 at frame 1030).
- The `glare_angle` here is the principal-axis orientation of the thresholded object blob, from image moments: `0.5 atan2(2 mu11, mu20 - mu02)` in degrees (frame 0: 44.75; frame 1030: -63.48). It is an image-based measure, not Sitrec's glare series (Sitrec's GimbalData.csv col 13 runs -48.72 to 65.46); the two were not compared in the notebooks and their sign and zero conventions are not reconciled.
- Sitrec geometry is the one in the Sitrec repo at the time of the run (HEAD circa 06/2024 to 11/2024); a lab reproduction of Sitrec outputs should pin a commit.
- In `adjust_cloud_motion`, the image centre is hard-coded `C = (213, 211)` px (the centre of the 428 x 428 crop, near the object's mean centre of mass of about (213, 211)).
- Frame difference used for optical flow is variable in time: `frame_diff = int(frame_diff_from + frame (frame_diff_to + 1 - frame_diff_from) / num_frames)`, so 6 at frame 0 rising to 10 at the end by default (common.py `get_frame_diff`; params 6 and 10).
- Cloud-only mask: pixels above the cloud line are discarded; the cloud line is derived from the human horizon rotated about the object's centre of mass, offset by the keyed "height above clouds" (gimbal_clouds cell 9).
- Constant-velocity target assumption in the GOFAST ranging (explicit in the comment of `constant_velocity_ranging`).

## Method

### Cloud motion (`gimbal_clouds.ipynb`)

1. Extract grayscale frames (428 x 428).
2. Build a mask: exclude the overlay boxes, the border, everything above the cloud line, then erode by 19 px so the 31-px Lucas-Kanade window stays inside clouds (cell 9; params in cell 13).
3. Detect corners (Shi-Tomasi, quality 0.001, block 5, min distance 0) in the lower part of the frame (ROI rows from 136 down), track them from frame f to f + frame_diff with pyramidal Lucas-Kanade (block 31, max level 5, 100 iterations) (cell 13).
4. Fit a similarity transform (`estimateAffinePartial2D`, RANSAC, threshold 3 px, 2000 iterations, confidence 0.9999). Output per frame: magnitude of the mean inlier displacement per frame, direction angle, rotation angle = `atan2(T[1,0], T[0,0])`, the transform, the inlier means (cell 13).
5. Run all 1021 frame pairs (frames 0 to 1020), interpolate over the WH-to-BH discontinuity (frames 360 to 372), plot, save `cloud_motion.parquet` (14 MB, uploaded to Hugging Face) (cells 15-21). A second pass saves inlier means for a range of frame differences (`cloud_means.parquet`, 1.2 MB) (cells 22-23).
6. Parameters printed in cell 13: `{'frame_diff_from': 6, 'frame_diff_to': 10, 'erosion': 19, 'min_mag': 1, 'gftt': {...}, 'pyrlk': {...}, 'affine': {...}}`.
7. Test frame 980: 1240 tracked corners; cloud motion magnitude 2.7355 px/frame, angle 25.62 deg, rotation -1.687 deg (printed in cell 14).

### Refining the line of sight (`gimbal_adjust_clouds.ipynb`)

This notebook does not output a refined LOS directly. It cleans the cloud-motion measurement, which is the quantity Sitrec and Peings and von Rennenkampff use to constrain the LOS (see `peings-vonrennenkampff-2023.md` Sec. III.B and `sitrec.md`). For each frame f and frame difference d:

1. Take the similarity transform R (rotation part normalised to unit scale) and the inlier means P1 (at f) and P2 (at f + d) (cell 6).
2. Remove the camera's own rotation about the image centre C = (213, 211): `V = R^-1 (P2 - C) - P1 + C - (O2 - O1)`, where O1, O2 are the object centres of mass at f and f + d (cell 6). That subtracts the apparent cloud motion caused by pod/image rotation and by the object's own motion in the frame (the pod re-centring the object).
3. Adjusted magnitude = `norm(V) / d`; adjusted angle = `atan2(V_y, V_x)`; adjusted rotation = measured rotation + (human_horizon(f + d) - human_horizon(f)) (cell 6).
4. Interactive plots for frame_diff from 2 to 12 and to 4 to 14, default 6 to 10 (cell 10). Example printed for frame 0, d = 5: magnitude 6.4928 -> adjusted 6.5232 px/frame, angle 15.727 -> 16.544 deg, rotation 0.394 -> 0.238 deg.

### Object data (`gimbal_object_data.ipynb`)

Per frame: convert white-hot frames (up to 370) to black-hot with the fitted lookup, threshold, take the largest contour, compute the centre of mass and the elongation angle (image moments) (cell 9), join the Sitrec `human_horizon` column (cell 17), save as `object_data.parquet` with metadata `wh_to_bh_lookup` and `fps` (cell 20). First and last rows: glare_angle 44.75 and -63.48, centre of mass (211.83, 211.28) and (212.76, 210.64), human_horizon -16.62 and -29.59.

### GOFAST passive ranging (`gofast_ranging.ipynb`)

1. Run Sitrec's `gofast` sitch headless and dump jet position, target position and jet roll for all frames (cells 6-8).
2. Constant-velocity ranging (cell 10): given times t[i], camera positions C[i] and unit LOS L[i], unknowns X = (d, Vx, Vy, Vz) with P[0] = C[0] + d L[0] and P[i] = P[0] + V (t[i]-t[0]); each frame requires (P[i] - C[i]) x L[i] = 0, giving 3(n-1) linear equations `d (L0 x Li) + V x Li (ti - t0) = (Ci - C0) x Li`, solved by linear least squares (`numpy.linalg.lstsq`). Returns speed norm(V) and range d at t[0].
3. Add tracking error to each LOS (cell 12): normal noise of standard deviation `FOV / 480 x pixels` degrees with FOV 0.7 deg and 480 px sensor width, i.e. 0.7/480 deg per pixel.
4. Plot (cell 14): first tracked frame 338, first displayed range frame 370; windows of 60 frames, step 1, track error sigma = 0.25 px; compare the "passive range" estimate with Sitrec's actual range (target to jet distance) and the bank angle.
5. Printed in cell 8 (Sitrec output, default traverse): jet at frame 0 (-8.4e-11, 7620.0, -6.x) m and at frame 1030 (-4265.1, 7618.46, 1256.6) m; target at frame 0 (-6367.77, 4008.54, 6036.0) m and at frame 1030 (-5229.30, 4025.88, 6105.96) m; jet roll 1.5275 at frame 0, -20.41 at frame 1030 (degrees, Sitrec sign convention).

## Results

- **GIMBAL:** no trajectory or range result is printed in any notebook. The deliverables are datasets (object geometry, cloud motion, adjusted cloud motion) and plots (image outputs not read). Printed numbers: tracking test at frame 980 (see above), 1021 tracked frame pairs, adjusted/unadjusted example at frame 0.
- **GOFAST:** the ranging notebook output is a plot; no numeric range or speed estimate is printed. What is printed are the Sitrec positions in cell 8, from which the Sitrec default traverse gives an object altitude of about 4009 m (13,151 ft) at frame 0 and 4026 m (13,208 ft) at frame 1030, and an object horizontal displacement of about 1,139 m east and 70 m south in 34.4 s, about 33 m/s (see `sitrec.md`).
- The notebooks do not state a conclusion about the nature of the objects. `transmittance_lowtran.ipynb` has markdown headings for a "Gimbal Distant Jet scenario" and a "Western United States UAP scenario"; their conclusions were not examined here.

## Caveats stated by the author (in code comments and markdown)

- "note: the Sitrec internal API may change over time" (gimbal_object_data cell 15, gofast_ranging cell 6).
- The cloud-tracking notebook only runs the final 1/10 of frames on CPU if OpenCV is not built with CUDA (gimbal_clouds cell 13, `get_cloud_frame_range`).
- Frames 360 to 372 around the WH to BH switch are interpolated for magnitude, angle and rotation (common.py `gimbal_fix_wh_to_bh`).
- Transmittance notebook: LOWTRAN is "an older lower resolution model"; "The most comprehensive atmospheric transmittance models like MODTRAN are not freely available" (transmittance_lowtran cell 2).

## Open points (ambiguous or unstated)

1. No README: the intended order and the meaning of the Hugging Face datasets are not documented; the notebooks reference the older repo path `0x1beef/uap` in their Colab and download URLs (`raw.githubusercontent.com/0x1beef/uap/main/src`), so those links may break.
2. The Sitrec version used for `human_horizon` is "shallow clone HEAD" at run time, not pinned. Values (e.g. -16.623859 at frame 0) are only reproducible if the Sitrec horizon code is unchanged (compare the pinned Sitrec test value, -28.43948837191162 at frame 435).
3. The adjusted cloud-motion vector V mixes a rotation-compensated cloud displacement and the object's centre-of-mass shift; the sign conventions for the angle (image y down) are not tied to a world azimuth; how it feeds back into LOS azimuth is not shown in these notebooks.
4. The cloud-height lookup (25 to 60 px) is hand-keyed; its provenance is not stated.
5. The GOFAST passive-ranging sigma (0.25 px) and 60-frame window are arbitrary demonstration values; no accuracy statement for the real data is made.
6. Sizes: cloud tracking and object segmentation operate on the 428 x 428 crop, not the native 480 px sensor; the 0.7 deg / 480 px pixel scale used for the tracking-error model is therefore not the crop's.
7. The Hugging Face parquet datasets were not retrieved; their row counts (1031 object rows, 1021 cloud-motion rows) are from the printed outputs only.

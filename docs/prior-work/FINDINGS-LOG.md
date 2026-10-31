# Findings log (raw notes feeding DISAGREEMENTS.md)

Each entry: date, what was found, evidence, status.

- 10/30/2026: GIMBAL true airspeed. Peings and von Rennenkampff (2023) convert IAS 238 to 242 kt at 25,000 ft and -25 C to TAS 363 to 369 kt. The standard subsonic compressible conversion (IAS taken as CAS, ISA pressure at 25,000 ft, temperature -25 C) gives 353.6 to 359.6 kt, about 10 kt lower. Their figure matches roughly 250 KCAS. Evidence: `tests/test_atmosphere.py::test_gimbal_airspeed_is_lower_than_2023_paper`. Status: check the paper's exact conversion and the on-screen Mach reading at M0; effect on the path is a sensitivity run at M2.

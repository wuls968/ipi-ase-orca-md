# Example Presets and Representative PLUMED Workflows

These examples are meant to be directly usable, representative, and cheap enough for local validation.

All example scripts assume:
- conda environment: `ipi`
- ORCA available as `orca` or via `ORCA_COMMAND`
- structure source: absolute xyz path
- working directory: project root

## Quick recommendations

If you are new to this repository:
1. Run a non-PLUMED smoke test from the main template first.
2. Then run one of the PLUMED smoke examples below.
3. Only after that, replace the xyz path and PLUMED input with your real system.

## Representative PLUMED examples

### 1. `native_xtb2_distance_restraint.py`

Purpose:
- simplest PLUMED-enabled example
- validates `DISTANCE + RESTRAINT`
- good first example when you just want to confirm the coupling is correct

Physical meaning:
- monitors the O-H distance between atoms `1` and `2`
- applies a harmonic restraint near `0.95 Å`

Main outputs:
- `COLVAR`
- `logs/ipi.log`
- `logs/client.log`
- `orca_native_xtb2/orca.out`

Commands:
```sh
conda run -n ipi python examples/native_xtb2_distance_restraint.py --write-only
conda run -n ipi python examples/native_xtb2_distance_restraint.py --run --smoke
```

When to use:
- first PLUMED smoke test
- restrained MD
- umbrella/window input prototyping

### 2. `native_xtb2_distance_metad.py`

Purpose:
- representative minimal metadynamics example
- validates `DISTANCE + METAD`
- good for checking that `HILLS` is produced correctly

Physical meaning:
- uses one O-H distance as the collective variable
- deposits metadynamics hills on that distance

Main outputs:
- `COLVAR`
- `HILLS`
- `logs/ipi.log`
- `logs/client.log`
- `orca_native_xtb2/orca.out`

Commands:
```sh
conda run -n ipi python examples/native_xtb2_distance_metad.py --write-only
conda run -n ipi python examples/native_xtb2_distance_metad.py --run --smoke
```

When to use:
- metadynamics smoke validation
- learning how this repo wires `METAD`
- building a single-CV enhanced-sampling workflow

### 3. `native_xtb2_angle_windows.py`

Purpose:
- representative bounded-angle example
- validates `ANGLE + LOWER_WALLS + UPPER_WALLS`
- useful as a window/constraint style starting point

Physical meaning:
- tracks the H-O-H angle
- keeps the angle in a bounded interval using lower/upper walls

Main outputs:
- `COLVAR`
- `logs/ipi.log`
- `logs/client.log`
- `orca_native_xtb2/orca.out`

Commands:
```sh
conda run -n ipi python examples/native_xtb2_angle_windows.py --write-only
conda run -n ipi python examples/native_xtb2_angle_windows.py --run --smoke
```

When to use:
- angular confinement
- window generation
- bounded CV tests before umbrella or OPES/metad setups

### 4. `native_xtb2_wtmetad_5ps.py`

Purpose:
- more complete curated WT-Metad example
- representative production-style example rather than just a smoke test

Physical meaning:
- uses the H-O-H angle as CV
- runs well-tempered metadynamics

Commands:
```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --write-only
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run --smoke
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run --hill-smoke
```

Notes:
- `--smoke` is mainly for wiring validation
- `--hill-smoke` is long enough to confirm hill deposition with the default `PACE`

## Curated generated example directory

The repository keeps one curated generated example directory:
- `examples/generated_jobs/native_xtb2_wtmetad_example/`

This directory is useful when you want to inspect what a fully generated PLUMED job looks like.

## How to choose an example

Choose this way:
- want the easiest PLUMED test -> `distance_restraint`
- want to verify metadynamics works -> `distance_metad`
- want bounded angular sampling -> `angle_windows`
- want a fuller WT-Metad reference -> `wtmetad_5ps`

## Suggested progression for researchers

Recommended order:
1. `distance_restraint --run --smoke`
2. `distance_metad --run --smoke`
3. `angle_windows --run --smoke`
4. `wtmetad_5ps --run --hill-smoke`

This progression goes from easiest coupling check to more realistic enhanced sampling.

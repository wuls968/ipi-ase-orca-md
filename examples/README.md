# Example Presets

These presets are small starting points for `ipi_ase_orca_template.py`. Apply them by editing the top-level config block before generating a job directory.

## Minimal AIMD NVT

- `simulation_kind = "aimd"`
- `ensemble = "nvt"`
- `nbeads = 1`
- `thermostat_mode = "svr"`

## Minimal PIMD NVT

- `simulation_kind = "pimd"`
- `ensemble = "nvt"`
- `nbeads = 16`
- `thermostat_mode = "pile_g"`

## Gas-Phase NVE

- `simulation_kind = "aimd"`
- `ensemble = "nve"`
- `nbeads = 1`
- no thermostat block

## Native-XTB2 WT-Metad 5 ps

- script: `examples/native_xtb2_wtmetad_5ps.py`
- backend: `ORCA Native-XTB2`
- system: `H2O`
- thermostat: `langevin`
- timestep: `1.0 fs`
- total steps: `5000` (`5 ps`)
- CV: `ANGLE ATOMS=2,1,3`
- bias: `well-tempered metadynamics`

Generate only:

```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --write-only
```

Run directly:

```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run
```

Fast smoke test with fewer steps:

```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run --smoke
```

Smoke test that confirms the first metadynamics hill is actually deposited:

```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run --hill-smoke
```

Notes:

- The example script uses `ORCA_COMMAND` from the environment if you set it; otherwise it falls back to `orca`.
- `--smoke` runs `20` steps and is mainly for checking `i-PI -> ASE -> ORCA -> PLUMED` wiring.
- `--hill-smoke` runs `120` steps. The default `plumed.dat` uses `PACE=100`, so this is long enough to produce the first entry in `HILLS`.
- The repository now keeps only one curated generated example directory:
  - `examples/generated_jobs/native_xtb2_wtmetad_example/`
- In that directory, the most important result files are:
  - `COLVAR`
  - `HILLS`
  - `native_xtb2_wtmetad_example.out`
  - `logs/ipi.log`
  - `logs/client.log`
- The template now writes `units='angstrom'` on the `init.xyz` reader in `input.xml`, which avoids the common i-PI unit mismatch where a plain xyz file is otherwise interpreted in atomic units.

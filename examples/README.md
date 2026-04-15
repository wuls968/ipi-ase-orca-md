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

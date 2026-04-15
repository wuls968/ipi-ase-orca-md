# i-PI ASE ORCA MD Script Design

## Goal

Create an independent project that provides a single, directly editable Python
script template for running ORCA-based AIMD and PIMD workflows through ASE and
i-PI, while minimizing configuration friction and keeping generated job folders
transparent and easy to modify by hand.

The project should prioritize the most common ORCA molecular AIMD/PIMD use
cases rather than attempting to wrap the entire i-PI feature set. It should
also generate a shell-based submission helper so users can move from local runs
to batch systems with minimal edits.

## Upstream-Driven Architecture

The primary execution path will follow:

`i-PI (server) -> ASE SocketClient -> ASE ORCA calculator -> ORCA`

This decision is based on the upstream projects:

- i-PI documents ASE as a middle layer for many client codes and explicitly
  shows the ASE client pattern in `examples/clients/ase_client`.
- ASE documents `SocketClient` / `SocketIOCalculator` as an implementation of
  the i-PI protocol.
- ASE's ORCA integration is implemented as a `GenericFileIOCalculator`, not as
  a persistent socket-enabled client calculator.

Because of that, the recommended first-class path for ORCA is the ASE client
pattern, where ASE acts as the i-PI client and ORCA is invoked by ASE for each
force evaluation. A double-socket design is not the primary supported path for
this project.

## Project Scope

This project is independent from `/Users/a0000/QCchem` and must live in its own
repository and directory.

The first version will focus on:

- ORCA-driven AIMD with `nbeads=1`
- ORCA-driven PIMD with `nbeads>1`
- `NVE` and `NVT` ensembles
- `unix` sockets as the default local path
- `inet` sockets as an alternative
- automatic generation of readable job directories and helper scripts
- a lightweight local smoke-test path

The first version will not promise full support for:

- multi-forcefield combinations
- RPC, MTS, or multi-level force splitting
- NPT/barostat workflows
- automatic generation of advanced GLE parameter matrices
- large-scale campaign management
- production-grade restart orchestration
- full optimization for ORCA periodic solid-state workloads

## Deliverable Shape

The user-facing deliverable is a single Python template file that can be edited
directly. The user should generally only need to modify that one file.

The template will generate a self-contained job directory with all derived
files, so users can inspect or manually tweak the generated i-PI and ASE inputs
after rendering.

## Planned Repository Layout

```text
ipi-ase-orca-md/
├── README.md
├── ipi_ase_orca_template.py
├── examples/
├── tests/
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-15-ipi-ase-orca-md-design.md
```

## Main Script Responsibilities

`ipi_ase_orca_template.py` will:

1. expose a clearly marked top-level parameter block
2. validate the user configuration
3. render the i-PI XML input
4. render the ASE client script for ORCA
5. copy or write the initial geometry
6. generate helper shell scripts
7. optionally run a lightweight local job
8. save a resolved machine-readable job configuration

The script should remain a single file, but its internal code should still be
structured with focused helper functions so it is readable and easy to edit.

## Configuration Model

The top-level editable parameter block will be organized into six groups.

### 1. Job Settings

- `job_name`
- `work_root`
- `run_mode` with `write_only` or `run`
- `clean_existing`
- `socket_mode` with `unix` or `inet`
- `socket_address`
- `socket_port`

### 2. Structure Settings

- `xyz_path`
- `xyz_string`
- `charge`
- `multiplicity`
- `cell`
- `pbc`

At least one of `xyz_path` or `xyz_string` must be provided.

### 3. ORCA Settings

- `orca_command`
- `orcasimpleinput`
- `orcablocks`
- `nprocs`
- `maxcore`
- `label`
- `extra_keywords`

The design intentionally keeps ORCA settings flexible. The project should not
attempt to abstract away ORCA method selection beyond basic convenience.
Instead, it should pass user-provided ORCA settings through in a predictable
way.

### 4. i-PI Simulation Settings

- `simulation_kind` with `aimd` or `pimd`
- `ensemble` with `nve` or `nvt`
- `nbeads`
- `temperature`
- `timestep_fs`
- `total_steps`
- `seed`

`nbeads=1` should behave as a classical AIMD-compatible setup.

### 5. Thermostat and Output Settings

- `thermostat_mode`
- `tau_fs`
- `properties_stride`
- `trajectory_stride`
- `checkpoint_stride`
- `prefix`

Supported thermostat defaults in v1:

- AIMD/NVT: `svr`, `langevin`
- PIMD/NVT: `pile_g`, `pile_l`

### 6. Advanced Settings

- `fix_com`
- `ffsocket_pbc`
- `latency`
- `timeout`
- `initial_velocities` with `thermal` or `none`
- `velocity_temperature`
- `custom_xml_overrides`
- `job_launcher_prefix`

`custom_xml_overrides` is the escape hatch for adding extra i-PI fragments
without redesigning the whole script.

## Generated Job Directory

For each rendered job, the script will create:

```text
<work_root>/<job_name>/
├── input.xml
├── init.xyz
├── ase_orca_client.py
├── job_config.json
├── run_ipi.sh
├── run_client.sh
├── run_all.sh
├── submit_job.sh
└── README.job.md
```

### File Purposes

- `input.xml`: i-PI input generated from the parameter block
- `init.xyz`: initial geometry used by ASE and i-PI
- `ase_orca_client.py`: ASE SocketClient + ORCA client script
- `job_config.json`: resolved configuration snapshot for reproducibility
- `run_ipi.sh`: launch i-PI only
- `run_client.sh`: launch ASE client only
- `run_all.sh`: sequential local helper for both pieces
- `submit_job.sh`: cluster-friendly shell entry point
- `README.job.md`: job-specific summary and usage notes

## Shell Helper Scripts

### Local Run Helpers

The generated local helpers should be simple and transparent:

- `run_ipi.sh` runs `i-pi input.xml`
- `run_client.sh` runs `python ase_orca_client.py`
- `run_all.sh` starts i-PI, waits for socket availability, then starts the
  ASE client

These scripts should favor debuggability over automation complexity.

### Submission Helper

`submit_job.sh` will be a generic shell launcher rather than a scheduler-
specific submission script. It should be immediately useful locally and easy to
wrap inside a site-specific batch script.

The script will:

- activate the `conda` environment `ipi`
- verify availability of `i-pi`
- verify Python can import ASE
- verify ORCA is reachable
- create a log directory
- start i-PI
- wait for the socket
- start the ASE ORCA client
- record logs and PIDs
- perform simple cleanup on exit

The script will expose a few clearly editable variables near the top, including:

- `CONDA_SH`
- `CONDA_ENV`
- `ORCA_COMMAND`
- `JOB_LAUNCHER_PREFIX`

`JOB_LAUNCHER_PREFIX` defaults to empty and can be set by the user to values
such as `srun`, `mpirun`, or another site-specific launcher.

## Run Modes

### `write_only`

- validate configuration
- generate the job directory and all derived files
- do not launch any process

### `run`

- validate environment
- generate the job directory
- start i-PI
- wait for socket readiness
- start the ASE ORCA client

The initial implementation should keep process management modest and readable.
It does not need to become a general-purpose daemon framework.

## ASE Client Design

The generated ASE client script will:

1. read the geometry from `init.xyz`
2. construct an `ase.calculators.orca.ORCA` calculator
3. create an `ase.calculators.socketio.SocketClient`
4. call `client.run(atoms)`

This mirrors the upstream i-PI ASE client examples and keeps the integration
path aligned with documented behavior.

## Validation Rules

The script should fail early with clear messages for common misconfigurations,
including:

- missing geometry source
- invalid `simulation_kind`
- invalid `ensemble`
- incompatible thermostat choice for the selected mode
- `pimd` with `nbeads < 2`
- missing ORCA command
- missing ASE or i-PI in the active environment
- conflicting socket configuration

## Testing Strategy

Testing is split into fast generation tests and lightweight runtime checks.

### Unit/Generation Tests

Tests should cover:

- rendering `input.xml` for AIMD/NVE
- rendering `input.xml` for AIMD/NVT
- rendering `input.xml` for PIMD/NVT
- generating the ASE client script
- generating helper shell scripts
- validating configuration error cases

These tests should not require ORCA.

### Lightweight Integration Checks

The implementation session should also run simple checks inside the `conda`
environment `ipi`:

- verify the script can generate a complete job directory in `write_only` mode
- verify imports and environment checks behave as expected
- if the local ORCA setup is callable, attempt a very small smoke test with a
  tiny molecular system and very few steps

If a real ORCA smoke test cannot complete, the final report must clearly state
what was verified and what remained blocked.

## Documentation Requirements

The repository README should explain:

- the chosen `i-PI -> ASE -> ORCA` architecture
- why ORCA is not using the double-socket path as the default
- environment expectations for the `ipi` conda environment
- how to edit the main template
- how to generate jobs
- how to run locally
- how to adapt `submit_job.sh` for a cluster

## Non-Goals for v1

The first version is not trying to become:

- a generic i-PI workflow manager
- a full ORCA input design toolkit
- a scheduler-specific submission framework
- a restart and resubmission platform

The design target is a practical, hackable, upstream-aligned template that
covers most common ORCA molecular AIMD/PIMD setups with much less manual
configuration work.

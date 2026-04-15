# i-PI ASE ORCA MD

This repository is a single-file template project for building ORCA-based AIMD/PIMD jobs through ASE and i-PI. The main entry point is `ipi_ase_orca_template.py`, which you edit to generate a ready-to-run job directory.

## Architecture

The supported execution path is:

`i-PI -> ASE SocketClient -> ASE ORCA calculator -> ORCA`

This path is required because ASE's ORCA calculator is not a native long-lived i-PI socket client. The template bridges that gap by running a small ASE client process that connects to i-PI and forwards force/energy requests to ORCA.

## Environment

The template is intended to run inside the `conda` environment named `ipi`.

If `ase` is missing, install it with:

```sh
conda activate ipi
python -m pip install ase
```

If `pip` is restricted by your environment management policy, the equivalent conda-forge install is:

```sh
conda install -n ipi -c conda-forge ase
```

`pytest` is only needed for the local test suite:

```sh
conda run -n ipi python -m pip install pytest
```

## Usage

1. Edit the configuration block at the top of `ipi_ase_orca_template.py`.
2. Generate files without launching anything:

```sh
python ipi_ase_orca_template.py --write-only
```

3. Generate files and start the job:

```sh
python ipi_ase_orca_template.py --run
```

For non-periodic molecules with `pbc=False` and `cell=None`, the template writes a default `15 x 15 x 15` angstrom cubic cell so i-PI can initialize cleanly. Set `structure.cell` explicitly for larger systems or periodic runs.

The generated ASE ORCA client also appends `Engrad` automatically when it is missing, so MD jobs request forces by default. Any `extra_keywords` values are appended to the same ORCA simple-input line.

Each generated job directory includes:

- `input.xml`
- `init.xyz`
- `ase_orca_client.py`
- `job_config.json`
- `run_ipi.sh`
- `run_client.sh`
- `submit_job.sh`
- `run_all.sh`
- `README.job.md`

## Cluster Adaptation

`submit_job.sh` is scheduler-agnostic, so it can be used on a local machine or wrapped by a site-specific batch script.

- Change `CONDA_SH` if your cluster stores `conda.sh` somewhere else.
- Keep `CONDA_ENV=ipi` unless you intentionally rename the environment.
- Set `JOB_LAUNCHER_PREFIX` to a launcher such as `srun`, `mpirun`, or an empty string for direct execution.
- If your site prefers a dedicated batch wrapper, you can embed `submit_job.sh` inside that wrapper instead of running it directly.

# i-PI ASE ORCA MD

This repository is a single-file template project for building ORCA-based AIMD/PIMD jobs through ASE and i-PI. The main entry point is `ipi_ase_orca_template.py`, which you edit to generate a ready-to-run job directory.

## Architecture

The supported execution path is:

`i-PI -> ASE SocketClient -> ASE ORCA calculator -> ORCA`

This path is required because ASE's ORCA calculator is not a native long-lived i-PI socket client. The template bridges that gap by running a small ASE client process that connects to i-PI and forwards force/energy requests to ORCA.

## Environment

The template is intended to run inside the `conda` environment named `ipi`.

If `ase` and `pytest` are missing, install them with:

```sh
conda activate ipi
python -m pip install ase pytest
```

If `pip` is restricted by your environment management policy, the equivalent conda-forge install is:

```sh
conda install -n ipi -c conda-forge ase pytest
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

Each generated job directory includes the core files below:

- `input.xml`
- `ase_orca_client.py`
- `submit_job.sh`
- `run_all.sh`
- `README.job.md`

## Cluster Adaptation

`submit_job.sh` is scheduler-agnostic, so it can be used on a local machine or wrapped by a site-specific batch script.

- Change `CONDA_SH` if your cluster stores `conda.sh` somewhere else.
- Keep `CONDA_ENV=ipi` unless you intentionally rename the environment.
- Set `JOB_LAUNCHER_PREFIX` to a launcher such as `srun`, `mpirun`, or an empty string for direct execution.
- If your site prefers a dedicated batch wrapper, you can embed `submit_job.sh` inside that wrapper instead of running it directly.

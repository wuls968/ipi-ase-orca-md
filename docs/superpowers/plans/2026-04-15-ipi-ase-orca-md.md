# i-PI ASE ORCA MD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent project around a single editable Python template that generates and optionally runs i-PI + ASE + ORCA AIMD/PIMD jobs, plus a generic `submit_job.sh` helper for local and cluster-friendly execution.

**Architecture:** Keep the project centered on one file, `ipi_ase_orca_template.py`, but implement it as a structured script with dataclass-based configuration, pure string renderers for generated artifacts, filesystem materialization helpers, and a thin runtime layer for environment checks and process launch. Test most behavior without requiring ORCA by keeping ASE imports lazy and validating rendered files rather than executing heavy dynamics in unit tests.

**Tech Stack:** Python 3.13, standard library, ASE, i-PI, ORCA, `pytest`, POSIX shell

---

## File Map

- Create: `/Users/a0000/ipi-ase-orca-md/.gitignore`
- Create: `/Users/a0000/ipi-ase-orca-md/README.md`
- Create: `/Users/a0000/ipi-ase-orca-md/examples/README.md`
- Create: `/Users/a0000/ipi-ase-orca-md/pyproject.toml`
- Create: `/Users/a0000/ipi-ase-orca-md/ipi_ase_orca_template.py`
- Create: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`
- Modify: `/Users/a0000/ipi-ase-orca-md/docs/superpowers/plans/2026-04-15-ipi-ase-orca-md.md` only if plan self-review finds gaps

### Responsibility Split

- `ipi_ase_orca_template.py`: editable user template, configuration dataclasses, validation, renderers, job materialization, optional run helpers
- `tests/test_template.py`: unit tests for validation, rendering, filesystem output, and write-only CLI behavior
- `README.md`: architecture, install/use instructions, cluster adaptation notes
- `examples/README.md`: compact example parameter presets
- `pyproject.toml`: pytest config and lightweight project metadata
- `.gitignore`: Python caches, generated job folders, logs, and ORCA/i-PI transient files

### Environment Notes

Local inspection already showed:

- `conda` environment `ipi` exists
- `i-pi` is available inside that environment
- ORCA is available at `/Users/a0000/Library/orca_6_1_0/orca`
- `ase` is **not** currently installed in `ipi`
- `pytest` is **not** currently installed in `ipi`

The implementation must therefore include explicit environment bootstrap and verification steps for `ase` and `pytest`.

### Task 1: Bootstrap the Script, Test Harness, and Validation Layer

**Files:**
- Create: `/Users/a0000/ipi-ase-orca-md/.gitignore`
- Create: `/Users/a0000/ipi-ase-orca-md/pyproject.toml`
- Create: `/Users/a0000/ipi-ase-orca-md/ipi_ase_orca_template.py`
- Create: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`
- Test: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`

- [ ] **Step 1: Write the failing validation tests**

```python
from dataclasses import replace

import pytest

import ipi_ase_orca_template as template


def make_config():
    return template.build_default_config()


def test_validation_requires_geometry_source():
    config = make_config()
    config = replace(
        config,
        structure=replace(config.structure, xyz_path=None, xyz_string=None),
    )

    with pytest.raises(template.ValidationError, match="geometry"):
        template.validate_config(config)


def test_pimd_requires_at_least_two_beads():
    config = make_config()
    config = replace(
        config,
        simulation=replace(
            config.simulation,
            simulation_kind="pimd",
            nbeads=1,
            thermostat_mode="pile_g",
        ),
    )

    with pytest.raises(template.ValidationError, match="nbeads"):
        template.validate_config(config)


def test_pimd_rejects_classical_thermostat():
    config = make_config()
    config = replace(
        config,
        simulation=replace(
            config.simulation,
            simulation_kind="pimd",
            nbeads=16,
            thermostat_mode="svr",
        ),
    )

    with pytest.raises(template.ValidationError, match="thermostat"):
        template.validate_config(config)
```

- [ ] **Step 2: Run the tests to verify they fail for the right reason**

Run: `cd /Users/a0000/ipi-ase-orca-md && python -m pytest tests/test_template.py -k validation -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ipi_ase_orca_template'`

- [ ] **Step 3: Write the minimal validation implementation**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "ipi-ase-orca-md"
version = "0.1.0"
description = "Single-file i-PI + ASE + ORCA job template generator."
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

```gitignore
__pycache__/
.pytest_cache/
*.pyc
jobs/
*.log
*.out
*.err
*.pid
orca_run/
```

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ValidationError(ValueError):
    """Raised when the template configuration is internally inconsistent."""


@dataclass(frozen=True)
class JobSettings:
    job_name: str
    work_root: Path
    run_mode: str
    clean_existing: bool
    socket_mode: str
    socket_address: str
    socket_port: int


@dataclass(frozen=True)
class StructureSettings:
    xyz_path: Path | None
    xyz_string: str | None
    charge: int
    multiplicity: int
    cell: tuple[float, float, float] | None
    pbc: bool


@dataclass(frozen=True)
class SimulationSettings:
    simulation_kind: str
    ensemble: str
    nbeads: int
    temperature: float
    timestep_fs: float
    total_steps: int
    seed: int
    thermostat_mode: str
    tau_fs: float
    properties_stride: int
    trajectory_stride: int
    checkpoint_stride: int
    prefix: str


@dataclass(frozen=True)
class OrcaSettings:
    orca_command: str
    orcasimpleinput: str
    orcablocks: str
    nprocs: int
    maxcore: int
    label: str
    extra_keywords: str


@dataclass(frozen=True)
class AdvancedSettings:
    fix_com: bool
    ffsocket_pbc: bool
    latency: float
    timeout: float
    initial_velocities: str
    velocity_temperature: float
    custom_xml_overrides: str
    job_launcher_prefix: str


@dataclass(frozen=True)
class TemplateConfig:
    job: JobSettings
    structure: StructureSettings
    simulation: SimulationSettings
    orca: OrcaSettings
    advanced: AdvancedSettings


def build_default_config() -> TemplateConfig:
    return TemplateConfig(
        job=JobSettings(
            job_name="h2o_pimd_demo",
            work_root=Path("jobs"),
            run_mode="write_only",
            clean_existing=True,
            socket_mode="unix",
            socket_address="orca_driver",
            socket_port=31415,
        ),
        structure=StructureSettings(
            xyz_path=None,
            xyz_string=\"\"\"3
water
O 0.000000 0.000000 0.000000
H 0.758602 0.000000 0.504284
H -0.758602 0.000000 0.504284
\"\"\",
            charge=0,
            multiplicity=1,
            cell=None,
            pbc=False,
        ),
        simulation=SimulationSettings(
            simulation_kind="pimd",
            ensemble="nvt",
            nbeads=16,
            temperature=300.0,
            timestep_fs=0.5,
            total_steps=20,
            seed=12345,
            thermostat_mode="pile_g",
            tau_fs=100.0,
            properties_stride=1,
            trajectory_stride=10,
            checkpoint_stride=50,
            prefix="simulation",
        ),
        orca=OrcaSettings(
            orca_command="/Users/a0000/Library/orca_6_1_0/orca",
            orcasimpleinput="B3LYP def2-SVP TightSCF",
            orcablocks="%pal nprocs 1 end\n%maxcore 2000",
            nprocs=1,
            maxcore=2000,
            label="orca_run",
            extra_keywords="",
        ),
        advanced=AdvancedSettings(
            fix_com=False,
            ffsocket_pbc=False,
            latency=0.01,
            timeout=600.0,
            initial_velocities="thermal",
            velocity_temperature=300.0,
            custom_xml_overrides="",
            job_launcher_prefix="",
        ),
    )


def validate_config(config: TemplateConfig) -> None:
    if config.structure.xyz_path is None and not config.structure.xyz_string:
        raise ValidationError("A geometry source is required: xyz_path or xyz_string.")
    if config.simulation.simulation_kind not in {"aimd", "pimd"}:
        raise ValidationError("simulation_kind must be 'aimd' or 'pimd'.")
    if config.simulation.ensemble not in {"nve", "nvt"}:
        raise ValidationError("ensemble must be 'nve' or 'nvt'.")
    if config.job.socket_mode not in {"unix", "inet"}:
        raise ValidationError("socket_mode must be 'unix' or 'inet'.")
    if not config.orca.orca_command:
        raise ValidationError("orca_command must not be empty.")
    if config.simulation.simulation_kind == "pimd" and config.simulation.nbeads < 2:
        raise ValidationError("PIMD requires nbeads >= 2.")
    if config.simulation.simulation_kind == "pimd":
        if config.simulation.thermostat_mode not in {"pile_g", "pile_l"}:
            raise ValidationError("PIMD thermostat must be pile_g or pile_l.")
    if config.simulation.simulation_kind == "aimd" and config.simulation.ensemble == "nvt":
        if config.simulation.thermostat_mode not in {"svr", "langevin"}:
            raise ValidationError("AIMD NVT thermostat must be svr or langevin.")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/a0000/ipi-ase-orca-md && python -m pytest tests/test_template.py -k validation -v`

Expected: `3 passed`

- [ ] **Step 5: Commit the validation layer**

```bash
cd /Users/a0000/ipi-ase-orca-md
git add .gitignore pyproject.toml ipi_ase_orca_template.py tests/test_template.py
git commit -m "feat: add template configuration validation"
```

### Task 2: Add Pure Renderers for i-PI XML, ASE Client, and Shell Helpers

**Files:**
- Modify: `/Users/a0000/ipi-ase-orca-md/ipi_ase_orca_template.py`
- Modify: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`
- Test: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`

- [ ] **Step 1: Write the failing renderer tests**

```python
from dataclasses import replace

import ipi_ase_orca_template as template


def test_render_input_xml_for_aimd_nvt():
    config = template.build_default_config()
    config = replace(
        config,
        simulation=replace(
            config.simulation,
            simulation_kind="aimd",
            ensemble="nvt",
            nbeads=1,
            thermostat_mode="svr",
        ),
    )

    xml = template.render_input_xml(config)

    assert "<initialize nbeads='1'>" in xml
    assert "<dynamics mode='nvt'>" in xml
    assert "<thermostat mode='svr'>" in xml


def test_render_input_xml_for_pimd_nvt():
    config = template.build_default_config()
    xml = template.render_input_xml(config)

    assert "<initialize nbeads='16'>" in xml
    assert "<thermostat mode='pile_g'>" in xml
    assert "<temperature units='kelvin'> 300.0 </temperature>" in xml


def test_render_ase_client_contains_orca_profile_and_socketclient():
    config = template.build_default_config()
    script = template.render_ase_orca_client(config)

    assert "from ase.calculators.orca import ORCA, OrcaProfile" in script
    assert "SocketClient" in script
    assert "OrcaProfile(command=" in script


def test_render_shell_scripts_includes_submit_helper_variables():
    config = template.build_default_config()
    scripts = template.render_shell_scripts(config)

    assert "submit_job.sh" in scripts
    submit_script = scripts["submit_job.sh"]
    assert "CONDA_ENV=\"ipi\"" in submit_script
    assert "JOB_LAUNCHER_PREFIX=" in submit_script
    assert "ase_orca_client.py" in submit_script
```

- [ ] **Step 2: Run the renderer tests to verify they fail**

Run: `cd /Users/a0000/ipi-ase-orca-md && python -m pytest tests/test_template.py -k "render_" -v`

Expected: FAIL with `AttributeError` for missing render functions

- [ ] **Step 3: Write the minimal renderer implementation**

```python
def _socket_block(config: TemplateConfig) -> str:
    if config.job.socket_mode == "unix":
        return (
            f"  <ffsocket mode='unix' name='orca' pbc='{str(config.advanced.ffsocket_pbc).lower()}'>\n"
            f"    <address>{config.job.socket_address}</address>\n"
            f"    <latency>{config.advanced.latency}</latency>\n"
            f"    <timeout>{config.advanced.timeout}</timeout>\n"
            "  </ffsocket>"
        )
    return (
        f"  <ffsocket mode='inet' name='orca' pbc='{str(config.advanced.ffsocket_pbc).lower()}'>\n"
        f"    <address>{config.job.socket_address}</address>\n"
        f"    <port>{config.job.socket_port}</port>\n"
        f"    <latency>{config.advanced.latency}</latency>\n"
        f"    <timeout>{config.advanced.timeout}</timeout>\n"
        "  </ffsocket>"
    )


def _velocities_block(config: TemplateConfig) -> str:
    if config.advanced.initial_velocities == "thermal":
        return (
            "      <velocities mode='thermal' units='kelvin'> "
            f"{config.advanced.velocity_temperature} </velocities>\n"
        )
    return ""


def _thermostat_block(config: TemplateConfig) -> str:
    if config.simulation.ensemble == "nve":
        return ""
    return (
        f"        <thermostat mode='{config.simulation.thermostat_mode}'>\n"
        f"          <tau units='femtosecond'> {config.simulation.tau_fs} </tau>\n"
        "        </thermostat>\n"
    )


def render_input_xml(config: TemplateConfig) -> str:
    validate_config(config)
    return f\"\"\"<simulation verbosity='medium'>
  <output prefix='{config.simulation.prefix}'>
    <properties stride='{config.simulation.properties_stride}' filename='out'> [ step, time{{femtosecond}}, potential{{electronvolt}}, temperature{{kelvin}} ] </properties>
    <trajectory stride='{config.simulation.trajectory_stride}' filename='pos'> positions{{angstrom}} </trajectory>
    <checkpoint stride='{config.simulation.checkpoint_stride}' />
  </output>
  <total_steps>{config.simulation.total_steps}</total_steps>
  <prng>
    <seed>{config.simulation.seed}</seed>
  </prng>
{_socket_block(config)}
  <system>
    <initialize nbeads='{config.simulation.nbeads}'>
      <file mode='xyz'> init.xyz </file>
{_velocities_block(config)}    </initialize>
    <forces>
      <force forcefield='orca'></force>
    </forces>
    <motion mode='dynamics'>
      <fixcom> {str(config.advanced.fix_com)} </fixcom>
      <dynamics mode='{config.simulation.ensemble}'>
        <timestep units='femtosecond'> {config.simulation.timestep_fs} </timestep>
{_thermostat_block(config)}      </dynamics>
    </motion>
    <ensemble>
      <temperature units='kelvin'> {config.simulation.temperature} </temperature>
    </ensemble>
  </system>
{config.advanced.custom_xml_overrides}
</simulation>
\"\"\"


def render_ase_orca_client(config: TemplateConfig) -> str:
    validate_config(config)
    socket_ctor = (
        f"SocketClient(unixsocket={config.job.socket_address!r})"
        if config.job.socket_mode == "unix"
        else f"SocketClient(host={config.job.socket_address!r}, port={config.job.socket_port})"
    )
    return f\"\"\"from ase.calculators.orca import ORCA, OrcaProfile
from ase.calculators.socketio import SocketClient
from ase.io import read


def main():
    atoms = read("init.xyz")
    profile = OrcaProfile(command={config.orca.orca_command!r})
    calc = ORCA(
        profile=profile,
        directory={config.orca.label!r},
        charge={config.structure.charge},
        mult={config.structure.multiplicity},
        orcasimpleinput={config.orca.orcasimpleinput!r},
        orcablocks={config.orca.orcablocks!r},
    )
    atoms.calc = calc
    client = {socket_ctor}
    client.run(atoms)


if __name__ == "__main__":
    main()
\"\"\"


def render_job_readme(config: TemplateConfig) -> str:
    return f\"\"\"# {config.job.job_name}

- simulation kind: `{config.simulation.simulation_kind}`
- ensemble: `{config.simulation.ensemble}`
- beads: `{config.simulation.nbeads}`
- socket mode: `{config.job.socket_mode}`
- ORCA command: `{config.orca.orca_command}`

Run locally:

```bash
sh run_all.sh
```

Cluster-friendly entry point:

```bash
sh submit_job.sh
```
\"\"\"


def render_shell_scripts(config: TemplateConfig) -> dict[str, str]:
    run_ipi = \"\"\"#!/bin/sh
set -eu
i-pi input.xml
\"\"\"
    run_client = \"\"\"#!/bin/sh
set -eu
python ase_orca_client.py
\"\"\"
    run_all = \"\"\"#!/bin/sh
set -eu
mkdir -p logs
sh run_ipi.sh > logs/ipi.stdout.log 2> logs/ipi.stderr.log &
IPI_PID=$!
sleep 2
sh run_client.sh > logs/client.stdout.log 2> logs/client.stderr.log
wait \"$IPI_PID\"
\"\"\"
    submit_job = f\"\"\"#!/bin/sh
set -eu

CONDA_SH="${{CONDA_SH:-/opt/anaconda3/etc/profile.d/conda.sh}}"
CONDA_ENV="ipi"
ORCA_COMMAND="{config.orca.orca_command}"
JOB_LAUNCHER_PREFIX="${{JOB_LAUNCHER_PREFIX:-{config.advanced.job_launcher_prefix}}}"

. "$CONDA_SH"
conda activate "$CONDA_ENV"
mkdir -p logs
test -x "$ORCA_COMMAND"
python -c "import ase"
i-pi input.xml > logs/ipi.stdout.log 2> logs/ipi.stderr.log &
IPI_PID=$!
sleep 2
${{JOB_LAUNCHER_PREFIX:+$JOB_LAUNCHER_PREFIX }}python ase_orca_client.py > logs/client.stdout.log 2> logs/client.stderr.log
kill "$IPI_PID" 2>/dev/null || true
wait "$IPI_PID" 2>/dev/null || true
\"\"\"
    return {
        "run_ipi.sh": run_ipi,
        "run_client.sh": run_client,
        "run_all.sh": run_all,
        "submit_job.sh": submit_job,
    }
```

- [ ] **Step 4: Run the renderer tests to verify they pass**

Run: `cd /Users/a0000/ipi-ase-orca-md && python -m pytest tests/test_template.py -k "render_" -v`

Expected: `4 passed`

- [ ] **Step 5: Commit the renderer layer**

```bash
cd /Users/a0000/ipi-ase-orca-md
git add ipi_ase_orca_template.py tests/test_template.py
git commit -m "feat: add i-pi and ASE artifact renderers"
```

### Task 3: Materialize Job Directories and Add Write-Only CLI Execution

**Files:**
- Modify: `/Users/a0000/ipi-ase-orca-md/ipi_ase_orca_template.py`
- Modify: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`
- Test: `/Users/a0000/ipi-ase-orca-md/tests/test_template.py`

- [ ] **Step 1: Write the failing filesystem and CLI tests**

```python
from dataclasses import replace
from pathlib import Path

import ipi_ase_orca_template as template


def test_write_job_directory_creates_expected_files(tmp_path):
    config = template.build_default_config()
    config = replace(
        config,
        job=replace(config.job, work_root=tmp_path, job_name="demo_job"),
    )

    job_dir = template.write_job_directory(config)

    assert (job_dir / "input.xml").exists()
    assert (job_dir / "init.xyz").exists()
    assert (job_dir / "ase_orca_client.py").exists()
    assert (job_dir / "job_config.json").exists()
    assert (job_dir / "run_ipi.sh").exists()
    assert (job_dir / "run_client.sh").exists()
    assert (job_dir / "run_all.sh").exists()
    assert (job_dir / "submit_job.sh").exists()
    assert (job_dir / "README.job.md").exists()


def test_main_write_only_returns_zero_and_creates_job(tmp_path):
    config = template.build_default_config()
    config = replace(
        config,
        job=replace(config.job, work_root=tmp_path, job_name="cli_job"),
    )

    exit_code = template.main(["--write-only"], config=config)

    assert exit_code == 0
    assert (tmp_path / "cli_job" / "input.xml").exists()
```

- [ ] **Step 2: Run the filesystem tests to verify they fail**

Run: `cd /Users/a0000/ipi-ase-orca-md && python -m pytest tests/test_template.py -k "write_job_directory or main_write_only" -v`

Expected: FAIL with `AttributeError` for missing `write_job_directory` or `main`

- [ ] **Step 3: Write the minimal materialization and CLI implementation**

```python
import argparse
import json
import shutil
from dataclasses import asdict


def _structure_text(config: TemplateConfig) -> str:
    if config.structure.xyz_path is not None:
        return config.structure.xyz_path.read_text(encoding="utf-8")
    assert config.structure.xyz_string is not None
    return config.structure.xyz_string.strip() + "\n"


def _to_jsonable(config: TemplateConfig) -> dict:
    payload = asdict(config)
    payload["job"]["work_root"] = str(config.job.work_root)
    if config.structure.xyz_path is not None:
        payload["structure"]["xyz_path"] = str(config.structure.xyz_path)
    return payload


def write_job_directory(config: TemplateConfig) -> Path:
    validate_config(config)
    job_dir = config.job.work_root / config.job.job_name
    if config.job.clean_existing and job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    (job_dir / "input.xml").write_text(render_input_xml(config), encoding="utf-8")
    (job_dir / "init.xyz").write_text(_structure_text(config), encoding="utf-8")
    (job_dir / "ase_orca_client.py").write_text(render_ase_orca_client(config), encoding="utf-8")
    (job_dir / "job_config.json").write_text(json.dumps(_to_jsonable(config), indent=2), encoding="utf-8")
    (job_dir / "README.job.md").write_text(render_job_readme(config), encoding="utf-8")

    for filename, content in render_shell_scripts(config).items():
        path = job_dir / filename
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    return job_dir


def check_environment(config: TemplateConfig) -> None:
    import shutil as _shutil
    import subprocess

    if _shutil.which("i-pi") is None:
        raise RuntimeError("i-pi was not found on PATH.")
    if not Path(config.orca.orca_command).exists():
        raise RuntimeError(f"ORCA executable not found: {config.orca.orca_command}")
    subprocess.run(["python", "-c", "import ase"], check=True)


def run_job(config: TemplateConfig) -> int:
    import subprocess
    import time

    job_dir = write_job_directory(config)
    check_environment(config)
    ipi_proc = subprocess.Popen(["i-pi", "input.xml"], cwd=job_dir)
    try:
        time.sleep(2)
        client_proc = subprocess.run(["python", "ase_orca_client.py"], cwd=job_dir, check=False)
        return client_proc.returncode
    finally:
        ipi_proc.terminate()
        ipi_proc.wait(timeout=10)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or run an i-PI + ASE + ORCA job.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-only", action="store_true", help="Only generate the job directory.")
    mode.add_argument("--run", action="store_true", help="Generate files and launch the job.")
    return parser


def main(argv: list[str] | None = None, *, config: TemplateConfig | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    active = config or build_default_config()
    if args.run:
        return run_job(active)
    write_job_directory(active)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full test suite to verify job generation is green**

Run: `cd /Users/a0000/ipi-ase-orca-md && python -m pytest -q`

Expected: all tests pass

- [ ] **Step 5: Commit the job writer and write-only CLI**

```bash
cd /Users/a0000/ipi-ase-orca-md
git add ipi_ase_orca_template.py tests/test_template.py
git commit -m "feat: add job materialization and write-only cli"
```

### Task 4: Finish Repository Documentation and Example Presets

**Files:**
- Create: `/Users/a0000/ipi-ase-orca-md/README.md`
- Create: `/Users/a0000/ipi-ase-orca-md/examples/README.md`

- [ ] **Step 1: Write the repository README**

```markdown
# i-PI ASE ORCA MD

This repository provides a single editable Python template for building
ORCA-based AIMD and PIMD jobs through ASE and i-PI.

## Architecture

The supported path is:

`i-PI -> ASE SocketClient -> ASE ORCA calculator -> ORCA`

This follows the documented ASE client pattern from the i-PI examples and
avoids pretending that ASE's ORCA calculator is a native long-lived i-PI
socket client.

## Environment

Use the `ipi` conda environment and install the missing Python packages:

```bash
conda activate ipi
python -m pip install ase pytest
```

## Usage

Edit the top-level configuration block inside `ipi_ase_orca_template.py`, then:

```bash
python ipi_ase_orca_template.py --write-only
```

To try launching the job locally:

```bash
python ipi_ase_orca_template.py --run
```

Each generated job directory contains:

- `input.xml`
- `ase_orca_client.py`
- `submit_job.sh`
- `run_all.sh`
- `README.job.md`

## Cluster Adaptation

`submit_job.sh` is intentionally scheduler-agnostic. To adapt it to a site:

- update `CONDA_SH` if your conda installation lives elsewhere
- keep `CONDA_ENV=ipi`
- set `JOB_LAUNCHER_PREFIX` to `srun`, `mpirun`, or another launcher if needed
- wrap `submit_job.sh` inside your scheduler's submission file if required
```

- [ ] **Step 2: Write the examples README**

```markdown
# Example Presets

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
```

- [ ] **Step 3: Commit the documentation**

```bash
cd /Users/a0000/ipi-ase-orca-md
git add README.md examples/README.md
git commit -m "docs: add usage guide and example presets"
```

### Task 5: Verify in the `ipi` Conda Environment and Run a Smoke Test

**Files:**
- Modify only if verification exposes issues

- [ ] **Step 1: Install the missing Python dependencies into `ipi`**

Run: `conda run -n ipi python -m pip install ase pytest`

Expected: successful installation of `ase` and `pytest`

- [ ] **Step 2: Run the test suite inside the target environment**

Run: `cd /Users/a0000/ipi-ase-orca-md && conda run -n ipi python -m pytest -q`

Expected: all tests pass inside `ipi`

- [ ] **Step 3: Run the script in write-only mode inside `ipi`**

Run: `cd /Users/a0000/ipi-ase-orca-md && conda run -n ipi python ipi_ase_orca_template.py --write-only`

Expected: a generated job directory under `/Users/a0000/ipi-ase-orca-md/jobs/`

- [ ] **Step 4: Inspect the generated helper scripts and job files**

Run: `cd /Users/a0000/ipi-ase-orca-md/jobs/h2o_pimd_demo && ls -1`

Expected:

```text
README.job.md
ase_orca_client.py
init.xyz
input.xml
job_config.json
run_all.sh
run_client.sh
run_ipi.sh
submit_job.sh
```

- [ ] **Step 5: Attempt a tiny runtime smoke test with a one-bead override if ORCA is callable**

Run:

```bash
cd /Users/a0000/ipi-ase-orca-md
conda run -n ipi python - <<'PY'
from dataclasses import replace
import ipi_ase_orca_template as template

config = template.build_default_config()
config = replace(
    config,
    job=replace(config.job, job_name="h2o_aimd_smoke"),
    simulation=replace(
        config.simulation,
        simulation_kind="aimd",
        ensemble="nvt",
        nbeads=1,
        total_steps=1,
        thermostat_mode="svr",
    ),
)
raise SystemExit(template.run_job(config))
PY
```

Expected: either

- a short local launch that reaches i-PI and the ASE client, or
- a concrete, debuggable failure that identifies the next missing runtime requirement

If the local machine cannot complete a real ORCA-driven dynamics step, record the exact blocking point and do not claim success beyond the verified write-only path.

- [ ] **Step 6: Commit only if verification required code or docs fixes**

```bash
cd /Users/a0000/ipi-ase-orca-md
git status --short
git add <files-fixed-during-verification>
git commit -m "fix: address verification issues"
```

## Plan Self-Review

- Spec coverage: the plan covers the single-file template, job generation, `submit_job.sh`, write-only/run modes, documentation, and `ipi` environment verification.
- Placeholder scan: no `TODO`, `TBD`, or vague "handle edge cases" placeholders remain.
- Type consistency: the same dataclass names, function names, and generated filenames are used consistently across tests, implementation, and documentation.

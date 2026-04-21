from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import shlex
import socket
import subprocess
import sys
import time
import tempfile
from typing import TextIO


DEFAULT_NONPERIODIC_CELL_ANGSTROM = 15.0

# ============================================================================
# USER TUNING SECTION
# Edit these values first. Most researchers do not need to touch the template
# machinery below this block.
# ============================================================================
USER_JOB_NAME = "h2o_pimd_demo"
USER_WORK_ROOT = Path("jobs")
USER_STRUCTURE_XYZ_PATH = (
    Path(__file__).resolve().parent / "examples" / "generated_jobs" / "native_xtb2_wtmetad_example" / "init.xyz"
).resolve()
USER_CHARGE = 0
USER_MULTIPLICITY = 1
USER_SIMULATION_KIND = "pimd"
USER_ENSEMBLE = "nvt"
USER_NBEADS = 16
USER_TEMPERATURE_K = 300.0
USER_TIMESTEP_FS = 0.5
USER_TOTAL_STEPS = 20
USER_THERMOSTAT_MODE = "pile_g"
USER_ORCA_COMMAND = "orca"
USER_ORCA_SIMPLEINPUT = "B3LYP def2-SVP TightSCF"
USER_ORCA_NPROCS = 1
USER_ORCA_MAXCORE_MB = 2000
USER_ORCA_BLOCKS = f"%pal nprocs {USER_ORCA_NPROCS} end\n%maxcore {USER_ORCA_MAXCORE_MB}"
USER_JOB_LAUNCHER_PREFIX = ""
USER_PLUMED_ENABLED = False


class ValidationError(ValueError):
    """Raised when the template configuration is internally inconsistent."""


class EnvironmentCheckError(RuntimeError):
    """Raised when the local runtime environment is not ready for this template."""


class JobExecutionError(RuntimeError):
    """Raised when a generated job fails during execution."""


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
    xyz_path: Path
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
class PlumedSettings:
    enabled: bool
    input_filename: str
    source_path: Path | None
    source_string: str | None
    bias_name: str
    bias_nbeads: int
    plumed_step: int
    compute_work: bool
    use_metad_smotion: bool
    plumed_extras: tuple[str, ...]


@dataclass(frozen=True)
class TemplateConfig:
    job: JobSettings
    structure: StructureSettings
    simulation: SimulationSettings
    orca: OrcaSettings
    advanced: AdvancedSettings
    plumed: PlumedSettings


def build_default_config() -> TemplateConfig:
    return TemplateConfig(
        job=JobSettings(
            job_name=USER_JOB_NAME,
            work_root=USER_WORK_ROOT,
            run_mode="write_only",
            clean_existing=True,
            socket_mode="unix",
            socket_address="orca_driver",
            socket_port=31415,
        ),
        structure=StructureSettings(
            xyz_path=USER_STRUCTURE_XYZ_PATH,
            charge=USER_CHARGE,
            multiplicity=USER_MULTIPLICITY,
            cell=None,
            pbc=False,
        ),
        simulation=SimulationSettings(
            simulation_kind=USER_SIMULATION_KIND,
            ensemble=USER_ENSEMBLE,
            nbeads=USER_NBEADS,
            temperature=USER_TEMPERATURE_K,
            timestep_fs=USER_TIMESTEP_FS,
            total_steps=USER_TOTAL_STEPS,
            seed=12345,
            thermostat_mode=USER_THERMOSTAT_MODE,
            tau_fs=100.0,
            properties_stride=1,
            trajectory_stride=10,
            checkpoint_stride=50,
            prefix="simulation",
        ),
        orca=OrcaSettings(
            orca_command=USER_ORCA_COMMAND,
            orcasimpleinput=USER_ORCA_SIMPLEINPUT,
            orcablocks=USER_ORCA_BLOCKS,
            nprocs=USER_ORCA_NPROCS,
            maxcore=USER_ORCA_MAXCORE_MB,
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
            job_launcher_prefix=USER_JOB_LAUNCHER_PREFIX,
        ),
        plumed=PlumedSettings(
            enabled=USER_PLUMED_ENABLED,
            input_filename="plumed.dat",
            source_path=None,
            source_string=None,
            bias_name="plumed",
            bias_nbeads=1,
            plumed_step=0,
            compute_work=True,
            use_metad_smotion=True,
            plumed_extras=(),
        ),
    )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValidationError(f"{field_name} must not be empty")


def _require_in(value: str, field_name: str, allowed: set[str]) -> None:
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValidationError(f"{field_name} must be one of: {options}")


def validate_config(config: TemplateConfig) -> None:
    if not isinstance(config.structure.xyz_path, Path):
        raise ValidationError("structure.xyz_path must be a pathlib.Path pointing to an absolute xyz file")
    if not config.structure.xyz_path.is_absolute():
        raise ValidationError("structure.xyz_path must be an absolute path")
    if config.structure.xyz_path.suffix.lower() != ".xyz":
        raise ValidationError("structure.xyz_path must point to a .xyz file")
    if not config.structure.xyz_path.is_file():
        raise ValidationError(f"structure.xyz_path does not exist: {config.structure.xyz_path}")
    if config.structure.pbc and config.structure.cell is None:
        raise ValidationError("cell must be provided when pbc is True")

    _require_in(config.job.socket_mode, "socket_mode", {"unix", "inet"})
    _require_non_empty(config.job.socket_mode, "socket_mode")
    _require_non_empty(config.orca.orca_command, "orca_command")

    simulation_kind = config.simulation.simulation_kind
    ensemble = config.simulation.ensemble
    thermostat = config.simulation.thermostat_mode

    _require_in(simulation_kind, "simulation_kind", {"aimd", "pimd"})
    _require_in(ensemble, "ensemble", {"nve", "nvt"})

    if simulation_kind == "pimd":
        if config.simulation.nbeads < 2:
            raise ValidationError("nbeads must be at least 2 for PIMD")
        if thermostat not in {"pile_g", "pile_l"}:
            raise ValidationError("thermostat must be pile_g or pile_l for PIMD")

    if simulation_kind == "aimd" and ensemble == "nvt":
        if thermostat not in {"svr", "langevin"}:
            raise ValidationError("thermostat must be svr or langevin for AIMD NVT")

    if config.plumed.source_path is not None and config.plumed.source_string is not None:
        raise ValidationError("plumed source_path and source_string are mutually exclusive")

    if config.plumed.source_path is not None and not config.plumed.source_path.is_file():
        raise ValidationError("plumed source_path must point to an existing file")

    _require_non_empty(config.plumed.input_filename, "plumed input_filename")
    _require_non_empty(config.plumed.bias_name, "plumed bias_name")

    if config.plumed.plumed_step < 0:
        raise ValidationError("plumed_step must be non-negative")

    if config.plumed.bias_nbeads < 1:
        raise ValidationError("plumed bias_nbeads must be at least 1")

    if config.plumed.bias_nbeads > config.simulation.nbeads:
        raise ValidationError("plumed bias_nbeads must not exceed simulation nbeads")


def _socket_block(config: TemplateConfig) -> str:
    pbc = str(config.advanced.ffsocket_pbc).lower()
    latency = config.advanced.latency
    timeout = config.advanced.timeout

    if config.job.socket_mode == "unix":
        return (
            f"<ffsocket mode='unix' name='orca' pbc='{pbc}'>\n"
            f"      <address>{config.job.socket_address}</address>\n"
            f"      <latency>{latency}</latency>\n"
            f"      <timeout>{timeout}</timeout>\n"
            "    </ffsocket>"
        )

    return (
        f"<ffsocket mode='inet' name='orca' pbc='{pbc}'>\n"
        f"      <address>{config.job.socket_address}</address>\n"
        f"      <port>{config.job.socket_port}</port>\n"
        f"      <latency>{latency}</latency>\n"
        f"      <timeout>{timeout}</timeout>\n"
        "    </ffsocket>"
    )


def _unix_socket_path(config: TemplateConfig) -> Path:
    return Path(f"/tmp/ipi_{config.job.socket_address}")


def _velocities_block(config: TemplateConfig) -> str:
    if config.advanced.initial_velocities != "thermal":
        return ""

    return (
        f"      <velocities mode='thermal' units='kelvin'> {config.advanced.velocity_temperature} </velocities>\n"
    )


def _cell_block(config: TemplateConfig) -> str:
    cell = config.structure.cell
    if cell is None:
        cell = (DEFAULT_NONPERIODIC_CELL_ANGSTROM,) * 3

    a, b, c = (float(axis) for axis in cell)
    return f"      <cell mode='abc' units='angstrom'> [ {a}, {b}, {c} ] </cell>\n"


def _thermostat_block(config: TemplateConfig) -> str:
    if config.simulation.ensemble == "nve":
        return ""

    return (
        f"      <thermostat mode='{config.simulation.thermostat_mode}'>\n"
        f"        <tau units='femtosecond'> {config.simulation.tau_fs} </tau>\n"
        "      </thermostat>\n"
    )


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _format_string_list(values: tuple[str, ...]) -> str:
    if not values:
        return "[]"
    return "[ " + ", ".join(values) + " ]"


def _plumed_forcefield_block(config: TemplateConfig) -> str:
    if not config.plumed.enabled:
        return ""

    lines = [
        f"  <ffplumed name='{config.plumed.bias_name}'>",
        "    <file mode='xyz' units='angstrom'> init.xyz </file>",
        f"    <plumed_dat> {config.plumed.input_filename} </plumed_dat>",
        f"    <plumed_step> {config.plumed.plumed_step} </plumed_step>",
        f"    <compute_work> {_bool_text(config.plumed.compute_work)} </compute_work>",
    ]
    if config.plumed.plumed_extras:
        lines.append(
            f"    <plumed_extras> {_format_string_list(config.plumed.plumed_extras)} </plumed_extras>"
        )
    lines.append("  </ffplumed>")
    return "\n".join(lines)


def _plumed_bias_block(config: TemplateConfig) -> list[str]:
    if not config.plumed.enabled:
        return []

    lines = [
        "      <bias>",
        f"        <force forcefield='{config.plumed.bias_name}' nbeads='{config.plumed.bias_nbeads}'>",
    ]
    if config.plumed.plumed_extras:
        lines.append(
            f"          <interpolate_extras> {_format_string_list(config.plumed.plumed_extras)} </interpolate_extras>"
        )
    lines.extend(
        [
            "        </force>",
            "      </bias>",
        ]
    )
    return lines


def _plumed_smotion_block(config: TemplateConfig) -> str:
    if not config.plumed.enabled or not config.plumed.use_metad_smotion:
        return ""

    return (
        "  <smotion mode='metad'>\n"
        "    <metad>\n"
        f"      <metaff> {_format_string_list((config.plumed.bias_name,))} </metaff>\n"
        "    </metad>\n"
        "  </smotion>"
    )


def _default_plumed_dat_template(config: TemplateConfig) -> str:
    return (
        "# PLUMED input template generated by ipi_ase_orca_template.py\n"
        "#\n"
        "# Edit this file before submitting a PLUMED-enabled job.\n"
        "# PLUMED atom indices are 1-based.\n"
        "# The XML side is already wired through <ffplumed> + <ensemble><bias>.\n"
        "# If you define variables that should be passed back to i-PI as extras,\n"
        "# list their names in config.plumed.plumed_extras.\n"
        "#\n"
        "UNITS LENGTH=A TIME=fs ENERGY=eV\n"
        "\n"
        "# Example 1: metadynamics on a distance CV\n"
        "# d12: DISTANCE ATOMS=1,2\n"
        "# METAD ARG=d12 SIGMA=0.05 HEIGHT=0.001 PACE=200 BIASFACTOR=10 TEMP="
        f"{config.simulation.temperature:.1f} FILE=HILLS\n"
        "# PRINT STRIDE=20 ARG=d12,metad.bias FILE=COLVAR\n"
        "\n"
        "# Example 2: umbrella/restraint\n"
        "# d12: DISTANCE ATOMS=1,2\n"
        "# RESTRAINT ARG=d12 AT=1.0 KAPPA=200.0\n"
        "# PRINT STRIDE=20 ARG=d12,restraint.bias FILE=COLVAR\n"
    )


def _plumed_dat_text(config: TemplateConfig) -> str:
    if config.plumed.source_path is not None:
        text = config.plumed.source_path.read_text()
    elif config.plumed.source_string is not None:
        text = config.plumed.source_string
    else:
        text = _default_plumed_dat_template(config)

    return text if text.endswith("\n") else text + "\n"


def _orca_simpleinput(config: TemplateConfig) -> str:
    tokens = config.orca.orcasimpleinput.split()
    extra_tokens = config.orca.extra_keywords.split()
    has_engrad = any(token.lower() == "engrad" for token in tokens + extra_tokens)
    merged = tokens + extra_tokens
    if not has_engrad:
        merged.append("Engrad")
    return " ".join(merged)


def render_input_xml(config: TemplateConfig) -> str:
    validate_config(config)

    velocities_block = _velocities_block(config)
    thermostat_block = _thermostat_block(config)
    custom_overrides = config.advanced.custom_xml_overrides.strip()
    plumed_forcefield_block = _plumed_forcefield_block(config)
    plumed_bias_block = _plumed_bias_block(config)
    plumed_smotion_block = _plumed_smotion_block(config)
    lines = [
        "<simulation>",
        f"  <output prefix='{config.simulation.prefix}'>",
        (
            f"    <properties stride='{config.simulation.properties_stride}' "
            "filename='out'> [ step, time{femtosecond}, "
            "potential{electronvolt}, temperature{kelvin} ] </properties>"
        ),
        (
            f"    <trajectory stride='{config.simulation.trajectory_stride}' "
            "filename='pos'> positions{angstrom} </trajectory>"
        ),
        f"    <checkpoint stride='{config.simulation.checkpoint_stride}' filename='chk'/>",
        "  </output>",
        f"  <total_steps> {config.simulation.total_steps} </total_steps>",
        "  <prng>",
        f"    <seed> {config.simulation.seed} </seed>",
        "  </prng>",
        f"  {_socket_block(config)}",
    ]
    if plumed_forcefield_block:
        lines.append(plumed_forcefield_block)
    lines.extend(
        [
            "  <system>",
            f"    <initialize nbeads='{config.simulation.nbeads}'>",
            "      <file mode='xyz' units='angstrom'> init.xyz </file>",
            _cell_block(config).rstrip("\n"),
        ]
    )
    if velocities_block:
        lines.append(velocities_block.rstrip("\n"))
    lines.extend(
        [
            "    </initialize>",
            "    <forces>",
            "      <force forcefield='orca'></force>",
            "    </forces>",
            "    <motion mode='dynamics'>",
        ]
    )
    if config.advanced.fix_com:
        lines.append("      <fixcom> True </fixcom>")
    lines.extend(
        [
            f"      <dynamics mode='{config.simulation.ensemble}'>",
            f"        <timestep units='femtosecond'> {config.simulation.timestep_fs} </timestep>",
        ]
    )
    if thermostat_block:
        lines.append(thermostat_block.rstrip("\n"))
    lines.extend(
        [
            "      </dynamics>",
            "    </motion>",
            "    <ensemble>",
            f"      <temperature units='kelvin'> {config.simulation.temperature} </temperature>",
        ]
    )
    if plumed_bias_block:
        lines.extend(plumed_bias_block)
    lines.extend(
        [
            "    </ensemble>",
            "  </system>",
        ]
    )
    if plumed_smotion_block:
        lines.append(plumed_smotion_block)
    if custom_overrides:
        lines.append(custom_overrides)
    lines.append("</simulation>")
    return "\n".join(lines) + "\n"


def render_ase_orca_client(config: TemplateConfig) -> str:
    validate_config(config)

    socket_client = (
        "SocketClient(unixsocket={!r})".format(config.job.socket_address)
        if config.job.socket_mode == "unix"
        else "SocketClient(host={!r}, port={!r})".format(
            config.job.socket_address, config.job.socket_port
        )
    )

    return (
        "from ase.calculators.orca import ORCA, OrcaProfile\n"
        "from ase.calculators.socketio import SocketClient\n"
        "from ase.io import read\n\n"
        f"profile = OrcaProfile(command={config.orca.orca_command!r})\n"
        "calc = ORCA(\n"
        "    profile=profile,\n"
        f"    directory={config.orca.label!r},\n"
        f"    charge={config.structure.charge},\n"
        f"    mult={config.structure.multiplicity},\n"
        f"    orcasimpleinput={_orca_simpleinput(config)!r},\n"
        f"    orcablocks={config.orca.orcablocks!r},\n"
        ")\n"
        "atoms = read('init.xyz')\n"
        "atoms.calc = calc\n"
        f"client = {socket_client}\n"
        "client.run(atoms)\n"
    )


def render_job_readme(config: TemplateConfig) -> str:
    validate_config(config)

    return (
        f"# {config.job.job_name}\n\n"
        f"- simulation kind: {config.simulation.simulation_kind}\n"
        f"- ensemble: {config.simulation.ensemble}\n"
        f"- beads: {config.simulation.nbeads}\n"
        f"- socket mode: {config.job.socket_mode}\n"
        f"- ORCA command: {config.orca.orca_command}\n"
        f"- PLUMED enabled: {config.plumed.enabled}\n"
        f"- PLUMED input: {config.plumed.input_filename}\n\n"
        "## Commands\n\n"
        "```sh\n"
        "sh run_all.sh\n"
        "sh submit_job.sh\n"
        "```\n"
    )


def render_shell_scripts(config: TemplateConfig) -> dict[str, str]:
    validate_config(config)

    orca_command = shlex.split(config.orca.orca_command)[0]
    unix_socket_path = str(_unix_socket_path(config))
    wait_for_socket_fn = (
        "wait_for_socket() {\n"
        "  mode=\"$1\"\n"
        "  target=\"$2\"\n"
        "  port=\"${3:-}\"\n"
        "  python - \"$mode\" \"$target\" \"$port\" <<'PY'\n"
        "import os\n"
        "import socket\n"
        "import sys\n"
        "import time\n"
        "\n"
        "mode, target, port = sys.argv[1], sys.argv[2], sys.argv[3]\n"
        "deadline = time.time() + 120\n"
        "if mode == 'unix':\n"
        "    while time.time() < deadline:\n"
        "        if os.path.exists(target):\n"
        "            time.sleep(1)\n"
        "            raise SystemExit(0)\n"
        "        time.sleep(1)\n"
        "else:\n"
        "    host = target\n"
        "    port = int(port)\n"
        "    while time.time() < deadline:\n"
        "        try:\n"
        "            with socket.create_connection((host, port), timeout=1):\n"
        "                raise SystemExit(0)\n"
        "        except OSError:\n"
        "            time.sleep(1)\n"
        "raise SystemExit(1)\n"
        "PY\n"
        "}\n"
    )

    cleanup_fn = (
        "cleanup() {\n"
        '  if [ -n "${IPI_PID:-}" ]; then\n'
        '    kill "$IPI_PID" 2>/dev/null || true\n'
        '    wait "$IPI_PID" 2>/dev/null || true\n'
        "  fi\n"
        f'  rm -f "{unix_socket_path}"\n'
        "}\n"
    )

    socket_wait_args = (
        f'wait_for_socket unix "{unix_socket_path}"'
        if config.job.socket_mode == "unix"
        else f'wait_for_socket inet "{config.job.socket_address}" "{config.job.socket_port}"'
    )
    detect_ipi_bin_fn = (
        "detect_ipi_bin() {\n"
        "  python - <<'PY'\n"
        "import os\n"
        "from pathlib import Path\n"
        "import shutil\n"
        "import sys\n"
        "\n"
        "candidate = Path(sys.executable).with_name('i-pi')\n"
        "if candidate.is_file() and os.access(candidate, os.X_OK):\n"
        "    print(candidate)\n"
        "else:\n"
        "    print(shutil.which('i-pi') or '')\n"
        "PY\n"
        "}\n"
    )

    run_ipi_sh = (
        "#!/bin/sh\n"
        "set -eu\n"
        f"{detect_ipi_bin_fn}"
        'IPI_BIN="${IPI_BIN:-$(detect_ipi_bin)}"\n'
        "test -n \"$IPI_BIN\"\n"
        "\"$IPI_BIN\" input.xml\n"
    )
    run_client_sh = (
        "#!/bin/sh\n"
        "set -eu\n"
        "python ase_orca_client.py\n"
    )
    run_all_sh = (
        "#!/bin/sh\n"
        "set -eu\n"
        f"{wait_for_socket_fn}\n"
        f"{cleanup_fn}"
        "trap cleanup INT TERM EXIT\n"
        "mkdir -p logs\n"
        f'rm -f "{unix_socket_path}"\n'
        "sh run_ipi.sh > logs/ipi.log 2>&1 &\n"
        "IPI_PID=$!\n"
        f"{socket_wait_args}\n"
        "sh run_client.sh > logs/client.log 2>&1\n"
        'wait "$IPI_PID"\n'
    )
    submit_job_sh = (
        "#!/bin/sh\n"
        "set -eu\n\n"
        'CONDA_ENV="ipi"\n'
        f'ORCA_COMMAND="{config.orca.orca_command}"\n'
        f'JOB_LAUNCHER_PREFIX="${{JOB_LAUNCHER_PREFIX:-{config.advanced.job_launcher_prefix}}}"\n\n'
        f"ORCA_COMMAND_BIN={orca_command!r}\n"
        f"{wait_for_socket_fn}\n"
        f"{cleanup_fn}"
        "detect_conda_sh() {\n"
        '  if [ -n "${CONDA_SH:-}" ] && [ -f "$CONDA_SH" ]; then\n'
        '    printf "%s\\n" "$CONDA_SH"\n'
        "    return\n"
        "  fi\n"
        "  if command -v conda >/dev/null 2>&1; then\n"
        '    conda_base="$(conda info --base 2>/dev/null || true)"\n'
        '    if [ -n "$conda_base" ] && [ -f "$conda_base/etc/profile.d/conda.sh" ]; then\n'
        '      printf "%s\\n" "$conda_base/etc/profile.d/conda.sh"\n'
        "      return\n"
        "    fi\n"
        "  fi\n"
        '  printf "\\n"\n'
        "}\n"
        "trap cleanup INT TERM EXIT\n"
        'CONDA_SH="$(detect_conda_sh)"\n'
        'if [ -f "$CONDA_SH" ]; then\n'
        '  . "$CONDA_SH"\n'
        'fi\n'
        'command -v conda >/dev/null\n'
        'conda activate "$CONDA_ENV"\n\n'
        f"{detect_ipi_bin_fn}"
        'IPI_BIN="${IPI_BIN:-$(detect_ipi_bin)}"\n'
        'test -n "$IPI_BIN"\n'
        "mkdir -p logs\n"
        f'rm -f "{unix_socket_path}"\n'
        'command -v "$ORCA_COMMAND_BIN" >/dev/null\n'
        f'python -c "import ase{", plumed" if config.plumed.enabled else ""}"\n'
        '"$IPI_BIN" input.xml > logs/ipi.log 2>&1 &\n'
        "IPI_PID=$!\n"
        f"{socket_wait_args}\n"
        'sh -c "${JOB_LAUNCHER_PREFIX} python ase_orca_client.py" > logs/client.log 2>&1\n'
        'wait "$IPI_PID"\n'
    )

    return {
        "run_ipi.sh": run_ipi_sh,
        "run_client.sh": run_client_sh,
        "run_all.sh": run_all_sh,
        "submit_job.sh": submit_job_sh,
    }


def _structure_text(config: TemplateConfig) -> str:
    xyz_text = config.structure.xyz_path.read_text()
    return xyz_text if xyz_text.endswith("\n") else xyz_text + "\n"


def _jsonable_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable_value(item) for item in value]
    if isinstance(value, list):
        return [_jsonable_value(item) for item in value]
    return value


def _to_jsonable(config: TemplateConfig) -> dict:
    return _jsonable_value(asdict(config))


def _job_dir(config: TemplateConfig) -> Path:
    return config.job.work_root / config.job.job_name


def _indent_block(text: str, prefix: str = "    ") -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _tail_text(path: Path, max_lines: int = 12) -> str | None:
    if not path.exists():
        return None

    text = path.read_text(errors="replace").strip()
    if not text:
        return "(log is empty)"
    return "\n".join(text.splitlines()[-max_lines:])


def _format_validation_error(config: TemplateConfig, exc: ValidationError) -> str:
    return "\n".join(
        [
            f"Validation failed: {exc}",
            f"Job directory: {_job_dir(config)}",
            "Edit the USER TUNING SECTION near the top of ipi_ase_orca_template.py and try again.",
        ]
    )


def _format_environment_error(
    config: TemplateConfig,
    summary: str,
    *,
    hints: tuple[str, ...] = (),
    excerpt: str | None = None,
) -> str:
    lines = [
        f"Environment check failed: {summary}",
        f"Job directory: {_job_dir(config)}",
    ]
    for hint in hints:
        lines.append(f"Hint: {hint}")
    if excerpt:
        lines.append("Relevant output:")
        lines.append(_indent_block(excerpt))
    return "\n".join(lines)


def _format_run_failure(
    config: TemplateConfig,
    job_dir: Path,
    summary: str,
    *,
    hints: tuple[str, ...] = (),
) -> str:
    client_log = job_dir / "logs" / "client.log"
    ipi_log = job_dir / "logs" / "ipi.log"
    orca_dir = job_dir / config.orca.label
    orca_out = orca_dir / "orca.out"
    orca_err = orca_dir / "orca.err"
    lines = [
        f"Run failed: {summary}",
        f"Job directory: {job_dir}",
        f"Inspect client log: {client_log}",
        f"Inspect i-PI log: {ipi_log}",
        f"Inspect ORCA output: {orca_out}",
        f"Inspect ORCA stderr: {orca_err}",
    ]
    for hint in hints:
        lines.append(f"Hint: {hint}")
    for log_path in (client_log, ipi_log, orca_out, orca_err):
        excerpt = _tail_text(log_path)
        if excerpt is None:
            continue
        lines.append(f"Recent lines from {log_path.relative_to(job_dir)}:")
        lines.append(_indent_block(excerpt))
    return "\n".join(lines)


def _write_job_directory_contents(job_dir: Path, config: TemplateConfig) -> None:
    (job_dir / "input.xml").write_text(render_input_xml(config))
    (job_dir / "init.xyz").write_text(_structure_text(config))
    (job_dir / config.plumed.input_filename).write_text(_plumed_dat_text(config))
    (job_dir / "ase_orca_client.py").write_text(render_ase_orca_client(config))
    (job_dir / "job_config.json").write_text(
        json.dumps(_to_jsonable(config), indent=2, sort_keys=True) + "\n"
    )
    (job_dir / "README.job.md").write_text(render_job_readme(config))

    for name, content in render_shell_scripts(config).items():
        script_path = job_dir / name
        script_path.write_text(content)
        script_path.chmod(0o755)


def write_job_directory(config: TemplateConfig) -> Path:
    validate_config(config)

    job_dir = config.job.work_root / config.job.job_name
    job_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        dir=job_dir.parent, prefix=f".{job_dir.name}.tmp-"
    ) as temp_root:
        temp_dir = Path(temp_root)
        _write_job_directory_contents(temp_dir, config)

        if job_dir.exists():
            if not config.job.clean_existing:
                raise FileExistsError(f"{job_dir} already exists")
            shutil.rmtree(job_dir)

        temp_dir.replace(job_dir)
    return job_dir


def _resolve_executable_token(command: str) -> str:
    token = shlex.split(command)[0]
    resolved = shutil.which(token)
    if resolved is not None:
        return resolved

    path = Path(token)
    looks_like_path = (
        path.is_absolute()
        or token.startswith(".")
        or os.sep in token
        or (os.path.altsep is not None and os.path.altsep in token)
    )
    if looks_like_path and path.is_file() and os.access(path, os.X_OK):
        return str(path)

    raise RuntimeError(f"orca executable was not found or is not executable: {token}")


def _resolve_env_script(script_name: str) -> str:
    candidate = Path(sys.executable).with_name(script_name)
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)

    resolved = shutil.which(script_name)
    if resolved is not None:
        return resolved

    raise RuntimeError(f"{script_name} was not found on PATH")


def _prepare_socket_path(config: TemplateConfig) -> None:
    if config.job.socket_mode != "unix":
        return

    socket_path = _unix_socket_path(config)
    if socket_path.exists():
        socket_path.unlink()


def inspect_environment(config: TemplateConfig) -> dict[str, str]:
    validate_config(config)

    try:
        i_pi_executable = _resolve_env_script("i-pi")
    except RuntimeError as exc:
        raise EnvironmentCheckError(
            _format_environment_error(
                config,
                str(exc),
                hints=(
                    "Activate the conda environment that provides i-pi, for example: conda activate ipi",
                ),
            )
        ) from exc

    try:
        orca_executable = _resolve_executable_token(config.orca.orca_command)
    except RuntimeError as exc:
        raise EnvironmentCheckError(
            _format_environment_error(
                config,
                str(exc),
                hints=(
                    "Update USER_ORCA_COMMAND in the USER TUNING SECTION or put ORCA on PATH.",
                ),
            )
        ) from exc

    imports = "import ase"
    if config.plumed.enabled:
        imports += ", plumed"
    try:
        subprocess.run(
            [sys.executable, "-c", imports],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        excerpt = (exc.stderr or exc.stdout or str(exc)).strip()
        raise EnvironmentCheckError(
            _format_environment_error(
                config,
                f"python import check failed for `{imports}`",
                hints=(
                    "Activate the expected conda environment first: conda activate ipi",
                    "Install the missing package in that environment, for example: python -m pip install ase",
                ),
                excerpt=excerpt,
            )
        ) from exc

    return {
        "i-pi": i_pi_executable,
        "orca": orca_executable,
        "python": sys.executable,
        "imports": imports.replace("import ", ""),
    }


def check_environment(config: TemplateConfig) -> None:
    inspect_environment(config)


def _wait_for_socket(config: TemplateConfig, timeout: float | None = None) -> None:
    deadline = time.monotonic() + (timeout if timeout is not None else config.advanced.timeout)
    poll_interval = 0.5

    if config.job.socket_mode == "unix":
        socket_path = _unix_socket_path(config)
        while time.monotonic() < deadline:
            if socket_path.exists():
                return
            time.sleep(poll_interval)
        raise TimeoutError(f"timed out waiting for unix socket {socket_path}")

    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (config.job.socket_address, config.job.socket_port), timeout=poll_interval
            ):
                return
        except OSError:
            time.sleep(poll_interval)
    raise TimeoutError(
        f"timed out waiting for socket {config.job.socket_address}:{config.job.socket_port}"
    )


def run_job(config: TemplateConfig) -> int:
    check_environment(config)
    job_dir = write_job_directory(config)
    _prepare_socket_path(config)
    i_pi_executable = _resolve_env_script("i-pi")
    logs_dir = job_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    with open(logs_dir / "ipi.log", "w") as ipi_log, open(
        logs_dir / "client.log", "w"
    ) as client_log:
        i_pi_proc = subprocess.Popen(
            [i_pi_executable, "input.xml"],
            cwd=job_dir,
            stdout=ipi_log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_socket(config)
            client_proc = subprocess.run(
                [sys.executable, "ase_orca_client.py"],
                cwd=job_dir,
                check=False,
                stdout=client_log,
                stderr=subprocess.STDOUT,
            )
            if client_proc.returncode != 0:
                raise JobExecutionError(
                    _format_run_failure(
                        config,
                        job_dir,
                        f"ASE ORCA client exited with return code {client_proc.returncode}",
                        hints=(
                            "The client log usually shows Python, ASE, ORCA, or socket connection failures.",
                        ),
                    )
                )
            grace_timeout = max(5.0, min(config.advanced.timeout, 30.0))
            try:
                ipi_returncode = i_pi_proc.wait(timeout=grace_timeout)
            except subprocess.TimeoutExpired as exc:
                raise JobExecutionError(
                    _format_run_failure(
                        config,
                        job_dir,
                        f"i-pi did not exit cleanly within {grace_timeout:.1f}s after the client finished",
                        hints=(
                            "Check whether the client finished before i-PI flushed its final step or checkpoint.",
                        ),
                    )
                ) from exc
            if ipi_returncode != 0:
                raise JobExecutionError(
                    _format_run_failure(
                        config,
                        job_dir,
                        f"i-pi exited with return code {ipi_returncode}",
                        hints=(
                            "The i-PI log usually shows XML parsing, socket, or runtime integration problems.",
                        ),
                    )
                )
            return 0
        except TimeoutError as exc:
            raise JobExecutionError(
                _format_run_failure(
                    config,
                    job_dir,
                    str(exc),
                    hints=(
                        "If the socket never came up, inspect logs/ipi.log first and confirm the ORCA client can start.",
                    ),
                )
            ) from exc
        finally:
            if i_pi_proc.poll() is None:
                i_pi_proc.terminate()
                try:
                    i_pi_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    i_pi_proc.kill()
                    i_pi_proc.wait()
            _prepare_socket_path(config)


def print_config(config: TemplateConfig, out: TextIO | None = None) -> None:
    destination = sys.stdout if out is None else out
    destination.write(json.dumps(_to_jsonable(config), indent=2, sort_keys=True) + "\n")


def doctor(config: TemplateConfig, out: TextIO | None = None) -> int:
    destination = sys.stdout if out is None else out
    environment = inspect_environment(config)
    lines = [
        f"Job directory: {_job_dir(config)}",
        "[ok] config validation",
        f"[ok] i-pi: {environment['i-pi']}",
        f"[ok] orca: {environment['orca']}",
        f"[ok] python: {environment['python']}",
        f"[ok] imports: {environment['imports']}",
    ]
    destination.write("\n".join(lines) + "\n")
    return 0


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--doctor", action="store_true")
    mode.add_argument("--print-config", action="store_true")
    return parser


def main(argv=None, *, config=None) -> int:
    args = build_arg_parser().parse_args(argv)
    active = config if config is not None else build_default_config()

    try:
        if args.print_config:
            print_config(active)
            return 0

        if args.doctor:
            return doctor(active)

        if args.run:
            return run_job(active)

        write_job_directory(active)
        return 0
    except ValidationError as exc:
        print(_format_validation_error(active, exc), file=sys.stderr)
        return 1
    except (EnvironmentCheckError, JobExecutionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

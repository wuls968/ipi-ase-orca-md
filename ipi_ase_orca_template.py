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


DEFAULT_NONPERIODIC_CELL_ANGSTROM = 15.0


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
            xyz_string="""3
water
O 0.000000 0.000000 0.000000
H 0.758602 0.000000 0.504284
H -0.758602 0.000000 0.504284
""",
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


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValidationError(f"{field_name} must not be empty")


def _require_in(value: str, field_name: str, allowed: set[str]) -> None:
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValidationError(f"{field_name} must be one of: {options}")


def validate_config(config: TemplateConfig) -> None:
    geometry_sources = [
        config.structure.xyz_path,
        config.structure.xyz_string.strip() if config.structure.xyz_string else None,
    ]
    if not any(geometry_sources):
        raise ValidationError("geometry source must be provided")
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
        "  <system>",
        f"    <initialize nbeads='{config.simulation.nbeads}'>",
        "      <file mode='xyz'> init.xyz </file>",
        _cell_block(config).rstrip("\n"),
    ]
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
            "    </ensemble>",
            "  </system>",
        ]
    )
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
        f"- ORCA command: {config.orca.orca_command}\n\n"
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

    run_ipi_sh = (
        "#!/bin/sh\n"
        "set -eu\n"
        "i-pi input.xml\n"
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
        'CONDA_SH="${CONDA_SH:-/opt/anaconda3/etc/profile.d/conda.sh}"\n'
        'CONDA_ENV="ipi"\n'
        f'ORCA_COMMAND="{config.orca.orca_command}"\n'
        f'JOB_LAUNCHER_PREFIX="${{JOB_LAUNCHER_PREFIX:-{config.advanced.job_launcher_prefix}}}"\n\n'
        f"ORCA_COMMAND_BIN={orca_command!r}\n"
        f"{wait_for_socket_fn}\n"
        f"{cleanup_fn}"
        "trap cleanup INT TERM EXIT\n"
        'if [ -f "$CONDA_SH" ]; then\n'
        '  . "$CONDA_SH"\n'
        'fi\n'
        'conda activate "$CONDA_ENV"\n\n'
        "mkdir -p logs\n"
        f'rm -f "{unix_socket_path}"\n'
        'command -v "$ORCA_COMMAND_BIN" >/dev/null\n'
        'python -c "import ase"\n'
        "i-pi input.xml > logs/ipi.log 2>&1 &\n"
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
    if config.structure.xyz_path is not None:
        return config.structure.xyz_path.read_text()

    xyz_text = config.structure.xyz_string or ""
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


def _write_job_directory_contents(job_dir: Path, config: TemplateConfig) -> None:
    (job_dir / "input.xml").write_text(render_input_xml(config))
    (job_dir / "init.xyz").write_text(_structure_text(config))
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


def _prepare_socket_path(config: TemplateConfig) -> None:
    if config.job.socket_mode != "unix":
        return

    socket_path = _unix_socket_path(config)
    if socket_path.exists():
        socket_path.unlink()


def check_environment(config: TemplateConfig) -> None:
    validate_config(config)

    if shutil.which("i-pi") is None:
        raise RuntimeError("i-pi was not found on PATH")

    _resolve_executable_token(config.orca.orca_command)

    subprocess.run([sys.executable, "-c", "import ase"], check=True)


def _wait_for_socket(config: TemplateConfig, timeout: float | None = None) -> None:
    deadline = time.monotonic() + (timeout if timeout is not None else config.advanced.timeout)
    poll_interval = 0.5

    if config.job.socket_mode == "unix":
        socket_address = str(_unix_socket_path(config))
        while time.monotonic() < deadline:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                    probe.settimeout(poll_interval)
                    probe.connect(socket_address)
                return
            except OSError:
                time.sleep(poll_interval)
        raise TimeoutError(f"timed out waiting for unix socket {socket_address}")

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

    i_pi_proc = subprocess.Popen(["i-pi", "input.xml"], cwd=job_dir)
    client_proc = None
    try:
        _wait_for_socket(config)
        client_proc = subprocess.run(
            [sys.executable, "ase_orca_client.py"],
            cwd=job_dir,
            check=False,
        )
        if client_proc.returncode != 0:
            return client_proc.returncode
        grace_timeout = max(5.0, min(config.advanced.timeout, 30.0))
        try:
            return i_pi_proc.wait(timeout=grace_timeout)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"i-pi did not exit cleanly within {grace_timeout:.1f}s after the client finished"
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


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    return parser


def main(argv=None, *, config=None) -> int:
    args = build_arg_parser().parse_args(argv)
    active = config if config is not None else build_default_config()

    if args.run:
        return run_job(active)

    write_job_directory(active)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

    _require_in(config.job.socket_mode.strip().lower(), "socket_mode", {"unix", "inet"})
    _require_non_empty(config.job.socket_mode, "socket_mode")
    _require_non_empty(config.orca.orca_command, "orca_command")

    simulation_kind = config.simulation.simulation_kind.strip().lower()
    ensemble = config.simulation.ensemble.strip().lower()
    thermostat = config.simulation.thermostat_mode.strip().lower()

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

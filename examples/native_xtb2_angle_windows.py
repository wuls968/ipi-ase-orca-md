from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import replace
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import ipi_ase_orca_template as template


DEFAULT_TOTAL_STEPS = 50
SMOKE_STEPS = 10
DEFAULT_ORCA_COMMAND = os.environ.get("ORCA_COMMAND", "orca")
DEFAULT_STRUCTURE_PATH = (
    REPO_ROOT / "examples" / "generated_jobs" / "native_xtb2_wtmetad_example" / "init.xyz"
).resolve()


def build_config(
    *,
    total_steps: int = DEFAULT_TOTAL_STEPS,
    job_name: str = "native_xtb2_angle_windows",
) -> template.TemplateConfig:
    config = template.build_default_config()
    return replace(
        config,
        job=replace(
            config.job,
            work_root=REPO_ROOT / "examples" / "generated_jobs",
            job_name=job_name,
            clean_existing=True,
            socket_address=f"{job_name}_sock",
        ),
        structure=replace(
            config.structure,
            xyz_path=DEFAULT_STRUCTURE_PATH,
            charge=0,
            multiplicity=1,
            cell=None,
            pbc=False,
        ),
        simulation=replace(
            config.simulation,
            simulation_kind="aimd",
            ensemble="nvt",
            nbeads=1,
            temperature=300.0,
            timestep_fs=0.5,
            total_steps=total_steps,
            thermostat_mode="svr",
            tau_fs=10.0,
            properties_stride=2,
            trajectory_stride=2,
            checkpoint_stride=20,
            prefix=job_name,
        ),
        orca=replace(
            config.orca,
            orca_command=DEFAULT_ORCA_COMMAND,
            orcasimpleinput="Native-XTB2 TightSCF",
            orcablocks="%pal nprocs 1 end\n%maxcore 800",
            nprocs=1,
            maxcore=800,
            label="orca_native_xtb2",
            extra_keywords="",
        ),
        plumed=replace(
            config.plumed,
            enabled=True,
            input_filename="plumed.dat",
            source_string=(
                "UNITS LENGTH=A TIME=fs ENERGY=eV\n"
                "theta: ANGLE ATOMS=2,1,3\n"
                "LOWER_WALLS ARG=theta AT=90.0 KAPPA=0.02 EXP=2 EPS=1 OFFSET=0\n"
                "UPPER_WALLS ARG=theta AT=130.0 KAPPA=0.02 EXP=2 EPS=1 OFFSET=0\n"
                "PRINT STRIDE=2 ARG=theta FILE=COLVAR\n"
            ),
            bias_name="plumed",
            bias_nbeads=1,
            plumed_step=0,
            compute_work=True,
            use_metad_smotion=False,
            plumed_extras=("theta",),
        ),
        advanced=replace(
            config.advanced,
            fix_com=True,
            initial_velocities="thermal",
        ),
    )


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument("--total-steps", type=int, default=DEFAULT_TOTAL_STEPS)
    parser.add_argument("--job-name", default="native_xtb2_angle_windows")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=f"Use a fast {SMOKE_STEPS}-step angular-wall smoke test.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    total_steps = SMOKE_STEPS if args.smoke else args.total_steps
    job_name = args.job_name
    if args.smoke and job_name == "native_xtb2_angle_windows":
        job_name = "native_xtb2_angle_windows_smoke"

    config = build_config(total_steps=total_steps, job_name=job_name)
    forwarded: list[str] = []
    if args.run:
        forwarded.append("--run")
    elif args.write_only:
        forwarded.append("--write-only")
    return template.main(forwarded, config=config)


if __name__ == "__main__":
    raise SystemExit(main())

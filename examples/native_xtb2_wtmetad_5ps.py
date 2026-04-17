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


DEFAULT_TIMESTEP_FS = 1.0
DEFAULT_TOTAL_STEPS = 5000
SMOKE_STEPS = 20
HILL_SMOKE_STEPS = 120
DEFAULT_ORCA_COMMAND = os.environ.get("ORCA_COMMAND", "orca")


def build_config(*, total_steps: int = DEFAULT_TOTAL_STEPS, job_name: str = "native_xtb2_wtmetad_5ps") -> template.TemplateConfig:
    config = template.build_default_config()
    return replace(
        config,
        job=replace(
            config.job,
            work_root=REPO_ROOT / "examples" / "generated_jobs",
            job_name=job_name,
            clean_existing=True,
        ),
        structure=replace(
            config.structure,
            xyz_path=None,
            xyz_string=(
                "3\n"
                "water\n"
                "O 0.000000 0.000000 0.000000\n"
                "H 0.758602 0.000000 0.504284\n"
                "H -0.758602 0.000000 0.504284\n"
            ),
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
            timestep_fs=DEFAULT_TIMESTEP_FS,
            total_steps=total_steps,
            thermostat_mode="langevin",
            tau_fs=10.0,
            properties_stride=50,
            trajectory_stride=100,
            checkpoint_stride=500,
            prefix=job_name,
        ),
        orca=replace(
            config.orca,
            orca_command=DEFAULT_ORCA_COMMAND,
            orcasimpleinput="Native-XTB2",
            orcablocks="%pal nprocs 1 end\n%maxcore 1000",
            nprocs=1,
            maxcore=1000,
            label="orca_native_xtb2",
            extra_keywords="",
        ),
        plumed=replace(
            config.plumed,
            enabled=True,
            input_filename="plumed.dat",
            source_string=(
                "UNITS LENGTH=A TIME=fs ENERGY=eV\n"
                "\n"
                "theta: ANGLE ATOMS=2,1,3\n"
                "METAD ARG=theta SIGMA=0.08 HEIGHT=0.001 PACE=100 BIASFACTOR=10 TEMP=300 LABEL=metad FILE=HILLS\n"
                "PRINT STRIDE=50 ARG=theta,metad.bias FILE=COLVAR\n"
            ),
            bias_name="plumed",
            bias_nbeads=1,
            plumed_step=0,
            compute_work=True,
            use_metad_smotion=True,
            plumed_extras=("theta", "metad.bias"),
        ),
        advanced=replace(
            config.advanced,
            fix_com=True,
            initial_velocities="none",
        ),
    )


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument("--total-steps", type=int, default=DEFAULT_TOTAL_STEPS)
    parser.add_argument("--job-name", default="native_xtb2_wtmetad_5ps")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=f"Use a fast {SMOKE_STEPS}-step smoke test configuration.",
    )
    parser.add_argument(
        "--hill-smoke",
        action="store_true",
        help=f"Run {HILL_SMOKE_STEPS} steps so the default METAD PACE=100 deposits the first hill.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    total_steps = args.total_steps
    job_name = args.job_name
    if args.hill_smoke:
        total_steps = HILL_SMOKE_STEPS
        if job_name == "native_xtb2_wtmetad_5ps":
            job_name = "native_xtb2_wtmetad_hill_smoke"
    elif args.smoke:
        total_steps = SMOKE_STEPS
        if job_name == "native_xtb2_wtmetad_5ps":
            job_name = "native_xtb2_wtmetad_smoke"

    config = build_config(total_steps=total_steps, job_name=job_name)
    forwarded = []
    if args.run:
        forwarded.append("--run")
    elif args.write_only:
        forwarded.append("--write-only")
    return template.main(forwarded, config=config)


if __name__ == "__main__":
    raise SystemExit(main())

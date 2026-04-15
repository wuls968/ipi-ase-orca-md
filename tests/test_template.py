import json
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

import ipi_ase_orca_template as template


def make_config():
    return template.build_default_config()


def test_default_config_matches_spec():
    config = make_config()

    assert config.simulation.checkpoint_stride == 50
    assert config.simulation.prefix == "simulation"
    assert config.orca.orcablocks == "%pal nprocs 1 end\n%maxcore 2000"
    assert config.orca.nprocs == 1
    assert config.orca.label == "orca_run"
    assert config.advanced.fix_com is False
    assert config.advanced.latency == 0.01
    assert config.advanced.timeout == 600.0


def test_default_config_validates_cleanly():
    template.validate_config(make_config())


def test_validation_rejects_empty_orca_command():
    config = make_config()
    config = replace(config, orca=replace(config.orca, orca_command=""))

    with pytest.raises(template.ValidationError, match="orca_command"):
        template.validate_config(config)


def test_validation_requires_geometry_source():
    config = make_config()
    config = replace(
        config,
        structure=replace(config.structure, xyz_path=None, xyz_string=None),
    )

    with pytest.raises(template.ValidationError, match="geometry"):
        template.validate_config(config)


def test_validation_requires_cell_for_periodic_structure():
    config = make_config()
    config = replace(
        config,
        structure=replace(config.structure, pbc=True, cell=None),
    )

    with pytest.raises(template.ValidationError, match="cell"):
        template.validate_config(config)


def test_validation_pimd_requires_at_least_two_beads():
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


def test_validation_pimd_rejects_classical_thermostat():
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


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("simulation_kind", "PIMD", "simulation_kind"),
        ("ensemble", "NVT", "ensemble"),
        ("socket_mode", " UNIX ", "socket_mode"),
        ("thermostat_mode", "PILE_G", "thermostat"),
    ],
)
def test_validation_rejects_invalid_enumerations(field, value, match):
    config = make_config()

    if field == "simulation_kind":
        config = replace(config, simulation=replace(config.simulation, simulation_kind=value))
    elif field == "ensemble":
        config = replace(config, simulation=replace(config.simulation, ensemble=value))
    elif field == "socket_mode":
        config = replace(config, job=replace(config.job, socket_mode=value))
    elif field == "thermostat_mode":
        config = replace(config, simulation=replace(config.simulation, thermostat_mode=value))

    with pytest.raises(template.ValidationError, match=match):
        template.validate_config(config)


def test_validation_rejects_aimd_nvt_pile_g():
    config = make_config()
    config = replace(
        config,
        simulation=replace(
            config.simulation,
            simulation_kind="aimd",
            ensemble="nvt",
            thermostat_mode="pile_g",
        ),
    )

    with pytest.raises(template.ValidationError, match="thermostat"):
        template.validate_config(config)


def test_render_input_xml_for_aimd_nvt():
    config = make_config()
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


def test_render_input_xml_adds_vacuum_cell_for_nonperiodic_system():
    root = ET.fromstring(template.render_input_xml(make_config()))

    cell = root.find("system/initialize/cell")

    assert cell is not None
    assert cell.get("mode") == "abc"
    assert cell.get("units") == "angstrom"
    assert "15.0" in (cell.text or "")


def test_render_input_xml_for_pimd_nvt():
    xml = template.render_input_xml(make_config())
    root = ET.fromstring(xml)
    system = root.find("system")
    assert system is not None

    assert "<initialize nbeads='16'>" in xml
    assert "<thermostat mode='pile_g'>" in xml
    assert "<temperature units='kelvin'> 300.0 </temperature>" in xml
    assert root.find("ffsocket") is not None
    assert system.find("forces/ffsocket") is None
    assert system.find("forces/force[@forcefield='orca']") is not None
    assert root.find("ffsocket[@name='orca']") is not None
    assert system.find("forces/force").get("forcefield") == root.find("ffsocket").get("name")
    assert system.find("ensemble") is not None
    dynamics = system.find("motion/dynamics")
    assert dynamics is not None
    assert dynamics.find("timestep") is not None
    velocities = system.find("initialize/velocities")
    assert velocities is not None
    assert velocities.get("mode") == "thermal"
    assert velocities.get("units") == "kelvin"
    assert str(make_config().advanced.velocity_temperature) in (velocities.text or "")
    properties = root.find("output/properties")
    trajectory = root.find("output/trajectory")
    assert properties is not None and properties.get("filename") is not None
    assert trajectory is not None and trajectory.get("filename") is not None


def test_render_ase_client_contains_orca_profile_and_socketclient():
    client_script = template.render_ase_orca_client(make_config())

    assert "from ase.calculators.orca import ORCA, OrcaProfile" in client_script
    assert "SocketClient" in client_script
    assert "OrcaProfile(command=" in client_script


def test_render_ase_client_requests_engrad_for_md():
    client_script = template.render_ase_orca_client(make_config())

    assert "Engrad" in client_script


def test_render_ase_client_merges_extra_keywords_without_duplicate_engrad():
    config = make_config()
    config = replace(
        config,
        orca=replace(
            config.orca,
            orcasimpleinput="B3LYP def2-SVP TightSCF engrad",
            extra_keywords="D3BJ",
        ),
    )

    client_script = template.render_ase_orca_client(config)

    assert "D3BJ" in client_script
    assert client_script.lower().count("engrad") == 1


def test_render_shell_scripts_includes_submit_helper_variables():
    scripts = template.render_shell_scripts(make_config())

    assert "submit_job.sh" in scripts
    assert 'CONDA_ENV="ipi"' in scripts["submit_job.sh"]
    assert "JOB_LAUNCHER_PREFIX=" in scripts["submit_job.sh"]
    assert "ase_orca_client.py" in scripts["submit_job.sh"]
    assert "command -v" in scripts["submit_job.sh"]
    assert "wait_for_socket" in scripts["submit_job.sh"]
    assert "trap cleanup" in scripts["submit_job.sh"]
    assert "/tmp/ipi_orca_driver" in scripts["run_all.sh"]


def test_render_shell_scripts_remove_stale_unix_socket():
    scripts = template.render_shell_scripts(make_config())

    assert 'rm -f "/tmp/ipi_orca_driver"' in scripts["run_all.sh"]
    assert 'rm -f "/tmp/ipi_orca_driver"' in scripts["submit_job.sh"]


def test_write_job_directory_creates_expected_files(tmp_path):
    config = make_config()
    config = replace(config, job=replace(config.job, work_root=tmp_path, job_name="demo_job"))

    job_dir = template.write_job_directory(config)

    assert job_dir == tmp_path / "demo_job"
    for name in [
        "input.xml",
        "init.xyz",
        "ase_orca_client.py",
        "job_config.json",
        "run_ipi.sh",
        "run_client.sh",
        "run_all.sh",
        "submit_job.sh",
        "README.job.md",
    ]:
        assert (job_dir / name).exists()


def test_write_job_directory_keeps_existing_directory_on_failure(tmp_path, monkeypatch):
    config = make_config()
    config = replace(config, job=replace(config.job, work_root=tmp_path, job_name="demo_job"))

    job_dir = tmp_path / "demo_job"
    job_dir.mkdir()
    sentinel = job_dir / "sentinel.txt"
    sentinel.write_text("keep-me")

    def fail_render_shell_scripts(_config):
        raise RuntimeError("boom")

    monkeypatch.setattr(template, "render_shell_scripts", fail_render_shell_scripts)

    with pytest.raises(RuntimeError, match="boom"):
        template.write_job_directory(config)

    assert sentinel.read_text() == "keep-me"
    assert not (job_dir / "input.xml").exists()


def test_write_job_directory_writes_json_and_exec_permissions(tmp_path):
    xyz_path = tmp_path / "structure.xyz"
    xyz_path.write_text("1\nH\nH 0 0 0\n")

    config = make_config()
    config = replace(
        config,
        job=replace(config.job, work_root=tmp_path, job_name="json_job"),
        structure=replace(config.structure, xyz_path=xyz_path, xyz_string=None),
    )

    job_dir = template.write_job_directory(config)
    payload = json.loads((job_dir / "job_config.json").read_text())

    assert payload["job"]["work_root"] == str(tmp_path)
    assert payload["structure"]["xyz_path"] == str(xyz_path)
    assert (job_dir / "run_all.sh").stat().st_mode & 0o777 == 0o755
    assert (job_dir / "submit_job.sh").stat().st_mode & 0o777 == 0o755


def test_run_job_checks_environment_before_writing_directory(monkeypatch):
    config = make_config()
    calls = []

    def fake_check_environment(_config):
        calls.append("check")
        raise RuntimeError("env")

    def fake_write_job_directory(_config):
        calls.append("write")
        return config.job.work_root / config.job.job_name

    monkeypatch.setattr(template, "check_environment", fake_check_environment)
    monkeypatch.setattr(template, "write_job_directory", fake_write_job_directory)

    with pytest.raises(RuntimeError, match="env"):
        template.run_job(config)

    assert calls == ["check"]


def test_prepare_socket_path_removes_stale_unix_socket(tmp_path, monkeypatch):
    config = make_config()
    stale_socket = tmp_path / "ipi_orca_driver"
    stale_socket.write_text("stale")

    monkeypatch.setattr(template, "_unix_socket_path", lambda _config: stale_socket)

    template._prepare_socket_path(config)

    assert not stale_socket.exists()


def test_run_job_returns_nonzero_if_ipi_exits_with_error(monkeypatch, tmp_path):
    config = make_config()

    class FakeIpiProc:
        def __init__(self):
            self.returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 7
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    fake_ipi_proc = FakeIpiProc()

    monkeypatch.setattr(template, "check_environment", lambda _config: None)
    monkeypatch.setattr(template, "write_job_directory", lambda _config: tmp_path)
    monkeypatch.setattr(template, "_prepare_socket_path", lambda _config: None)
    monkeypatch.setattr(template, "_wait_for_socket", lambda _config: None)
    monkeypatch.setattr(template.subprocess, "Popen", lambda *args, **kwargs: fake_ipi_proc)
    monkeypatch.setattr(
        template.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0})(),
    )

    assert template.run_job(config) == 7


def test_check_environment_rejects_non_executable_orca_path(tmp_path, monkeypatch):
    orca_path = tmp_path / "orca"
    orca_path.write_text("#!/bin/sh\nexit 0\n")
    orca_path.chmod(0o644)

    config = make_config()
    config = replace(config, orca=replace(config.orca, orca_command=str(orca_path)))

    monkeypatch.setattr(
        template.shutil,
        "which",
        lambda token: "/usr/bin/i-pi" if token == "i-pi" else None,
    )
    monkeypatch.setattr(template.subprocess, "run", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="orca executable"):
        template.check_environment(config)


def test_build_arg_parser_rejects_conflicting_modes():
    parser = template.build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--write-only", "--run"])


def test_main_rejects_conflicting_modes(tmp_path):
    config = make_config()
    config = replace(config, job=replace(config.job, work_root=tmp_path, job_name="cli_job"))

    with pytest.raises(SystemExit):
        template.main(["--write-only", "--run"], config=config)


def test_main_write_only_returns_zero_and_creates_job(tmp_path):
    config = make_config()
    config = replace(config, job=replace(config.job, work_root=tmp_path, job_name="cli_job"))

    result = template.main(["--write-only"], config=config)

    assert result == 0
    assert (tmp_path / "cli_job" / "input.xml").exists()

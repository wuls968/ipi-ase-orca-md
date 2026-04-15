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
    assert system.find("ensemble") is not None
    dynamics = system.find("motion/dynamics")
    assert dynamics is not None
    assert dynamics.find("timestep") is not None
    properties = root.find("output/properties")
    trajectory = root.find("output/trajectory")
    assert properties is not None and properties.get("filename") is not None
    assert trajectory is not None and trajectory.get("filename") is not None


def test_render_ase_client_contains_orca_profile_and_socketclient():
    client_script = template.render_ase_orca_client(make_config())

    assert "from ase.calculators.orca import ORCA, OrcaProfile" in client_script
    assert "SocketClient" in client_script
    assert "OrcaProfile(command=" in client_script


def test_render_shell_scripts_includes_submit_helper_variables():
    scripts = template.render_shell_scripts(make_config())

    assert "submit_job.sh" in scripts
    assert 'CONDA_ENV="ipi"' in scripts["submit_job.sh"]
    assert "JOB_LAUNCHER_PREFIX=" in scripts["submit_job.sh"]
    assert "ase_orca_client.py" in scripts["submit_job.sh"]
    assert "command -v" in scripts["submit_job.sh"]
    assert "wait_for_socket" in scripts["submit_job.sh"]
    assert "trap cleanup" in scripts["submit_job.sh"]

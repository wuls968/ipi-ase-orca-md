from dataclasses import replace

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
        ("simulation_kind", "unsupported", "simulation_kind"),
        ("ensemble", "invalid", "ensemble"),
        ("socket_mode", "tcp", "socket_mode"),
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

    with pytest.raises(template.ValidationError, match=match):
        template.validate_config(config)

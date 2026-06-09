from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from pyssp_standard.fmu import FMU
from pyssp_standard.ssp import SSP


def test_archive_lists_binary_and_documentation_entries(fmu_archive_fixture, tmp_path):
    test_fmu_file = tmp_path / "ecs.fmu"
    shutil.copy(fmu_archive_fixture, test_fmu_file)

    with FMU(test_fmu_file) as fmu:
        assert all(entry.startswith("binaries/") for entry in fmu.binaries)
        assert fmu.documentation == []


def test_archive_uses_temp_workdir_and_cleans_up_after_exit(fmu_archive_fixture, tmp_path):
    test_fmu_file = tmp_path / "ecs.fmu"
    shutil.copy(fmu_archive_fixture, test_fmu_file)

    archive = FMU(test_fmu_file)
    with archive as fmu:
        root = fmu.runtime.root
        assert root.exists()
        assert (root / "modelDescription.xml").exists()

    assert not root.exists()


def test_model_description_facade_reads_from_archive_contents(fmu_archive_fixture, tmp_path):
    test_fmu_file = tmp_path / "ecs.fmu"
    shutil.copy(fmu_archive_fixture, test_fmu_file)

    with FMU(test_fmu_file) as fmu:
        archive_xml = fmu.runtime.read_text("modelDescription.xml")
        with fmu.model_description as md:
            assert len(md.xml.inputs) > 0
            assert md.path.read_text(encoding="utf-8") == archive_xml
            assert md.check_compliance() is True


def test_strip_model_exchange_preserves_archive_model_description_guid(fmu_archive_fixture, tmp_path):
    test_fmu_file = tmp_path / "ecs.fmu"
    shutil.copy(fmu_archive_fixture, test_fmu_file)

    with FMU(test_fmu_file, mode="r") as fmu:
        with fmu.model_description as md:
            original_guid = md.xml.guid

    with FMU(test_fmu_file, mode="a") as fmu:
        with fmu.model_description as md:
            md.strip_model_exchange()

    with FMU(test_fmu_file, mode="r") as fmu:
        with fmu.model_description as md:
            assert md.xml.guid == original_guid


def test_directory_mode_reads_fmu_contents_from_persistent_root(fmu_directory_fixture):
    archive = FMU(fmu_directory_fixture, mode="r")
    with archive as fmu:
        root = fmu.runtime.root
        assert root == fmu_directory_fixture
        assert "modelDescription.xml" in fmu.runtime.namelist()
        assert all(entry.startswith("binaries/") for entry in fmu.binaries)
        assert len(fmu.documentation) == 0

    assert root.exists()


def test_directory_mode_exposes_model_description(fmu_directory_fixture):
    with FMU(fmu_directory_fixture, mode="r") as fmu:
        with fmu.model_description as md:
            assert len(md.xml.inputs) > 0
            assert md.path == fmu_directory_fixture / "modelDescription.xml"


def test_archive_and_directory_modes_expose_same_model_name(fmu_archive_fixture, fmu_directory_fixture):
    with FMU(fmu_archive_fixture, mode="r") as archive_fmu:
        with archive_fmu.model_description as archive_md:
            archive_name = archive_md.xml.model_name

    with FMU(fmu_directory_fixture, mode="r") as directory_fmu:
        with directory_fmu.model_description as directory_md:
            directory_name = directory_md.xml.model_name

    assert archive_name == directory_name


def test_fmu_create_empty_in_directory_mode(tmp_path):
    fmu_dir = tmp_path / "empty_fmu"
    with FMU(fmu_dir, mode="w") as fmu:
        assert fmu.runtime.root == fmu_dir
        assert fmu_dir.is_dir()
        assert fmu.binaries == []

    assert fmu_dir.is_dir()


def test_fmu_create_empty_archive(tmp_path):
    fmu_path = tmp_path / "empty.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        assert fmu.runtime.root.is_dir()
        assert fmu.binaries == []

    assert fmu_path.is_file()
    assert fmu_path.stat().st_size > 0


def test_add_binary(tmp_path):
    source_file = tmp_path / "mylib.so"
    source_file.write_text("fake binary content")

    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        result = fmu.add_binary(source_file)
        assert result == "binaries/mylib.so"
        assert "binaries/mylib.so" in fmu.runtime.namelist()


def test_add_binary_with_platform(tmp_path):
    source_file = tmp_path / "mylib.so"
    source_file.write_text("fake binary content")

    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        result = fmu.add_binary(source_file, platform="linux64")
        assert result == "binaries/linux64/mylib.so"
        assert "binaries/linux64/mylib.so" in fmu.runtime.namelist()


def test_add_resource_to_fmu(tmp_path):
    source_file = tmp_path / "data.csv"
    source_file.write_text("a,b,c\n1,2,3")

    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        result = fmu.add_resource(source_file)
        assert result == "resources/data.csv"
        assert "resources/data.csv" in fmu.runtime.namelist()
        assert fmu.runtime.read_text("resources/data.csv") == "a,b,c\n1,2,3"


def test_add_resource_with_target_name(tmp_path):
    source_file = tmp_path / "data.csv"
    source_file.write_text("a,b,c\n1,2,3")

    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        result = fmu.add_resource(source_file, target_name="my_data.csv")
        assert result == "resources/my_data.csv"
        assert "resources/my_data.csv" in fmu.runtime.namelist()


def test_fmu_builder_contents_survive_commit(tmp_path):
    binary_file = tmp_path / "engine.so"
    binary_file.write_text("binary content")
    resource_file = tmp_path / "config.json"
    resource_file.write_text('{"key": "value"}')

    fmu_path = tmp_path / "built.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        fmu.add_binary(binary_file, platform="linux64")
        fmu.add_resource(resource_file)

    # Re-open in read mode
    with FMU(fmu_path, mode="r") as fmu:
        assert "binaries/linux64/engine.so" in fmu.runtime.namelist()
        assert "resources/config.json" in fmu.runtime.namelist()
        assert fmu.runtime.read_text("resources/config.json") == '{"key": "value"}'


def test_package_as_ssp_creates_single_component_ssp(fmu_archive_fixture, tmp_path):
    ssp_path = tmp_path / "packaged.ssp"

    with FMU(fmu_archive_fixture, mode="r") as fmu:
        returned_path = fmu.package_as_ssp(
            ssp_path,
            system_name="custom_system",
            component_name="controller",
            expose_system_connectors=True,
        )

    assert returned_path == ssp_path

    with SSP(ssp_path, mode="r") as ssp:
        assert "0001_ECS_HW.fmu" in ssp.resources
        with ssp.system_structure() as ssd:
            assert ssd.xml.name == "custom_system"
            assert ssd.xml.system is not None
            assert ssd.xml.system.name == "custom_system"
            component = next(element for element in ssd.xml.system.elements if element.name == "controller")
            assert component.source == "resources/0001_ECS_HW.fmu"
            assert any(connector.kind == "input" for connector in ssd.xml.system.connectors)
            assert any(connector.kind == "output" for connector in ssd.xml.system.connectors)


# --- add_model_description tests ---

_MINIMAL_MD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="TestModel"
  guid="{test-guid-0000-0000-0000-000000000000}"
  generationDateAndTime="2024-01-01T00:00:00Z"
  variableNamingConvention="structured"
  numberOfEventIndicators="0">
  <ModelExchange modelIdentifier="TestModel"/>
</fmiModelDescription>"""


def test_add_model_description_from_file(tmp_path):
    md_file = tmp_path / "modelDescription.xml"
    md_file.write_text(_MINIMAL_MD_XML)

    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        result = fmu.add_model_description(md_file)
        assert result == "modelDescription.xml"
        assert "modelDescription.xml" in fmu.runtime.namelist()


def test_add_model_description_survives_commit(tmp_path):
    md_file = tmp_path / "modelDescription.xml"
    md_file.write_text(_MINIMAL_MD_XML)

    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        fmu.add_model_description(md_file)

    with FMU(fmu_path, mode="r") as fmu:
        assert "modelDescription.xml" in fmu.runtime.namelist()
        with fmu.model_description as md:
            assert md.xml.model_name == "TestModel"


def test_add_model_description_invalid_path(tmp_path):
    fmu_path = tmp_path / "test.fmu"
    with FMU(fmu_path, mode="w") as fmu:
        with pytest.raises(FileNotFoundError):
            fmu.add_model_description(tmp_path / "nonexistent.xml")


# --- FMU.create tests ---


def test_fmu_create_with_minimal(tmp_path):
    md_file = tmp_path / "modelDescription.xml"
    md_file.write_text(_MINIMAL_MD_XML)

    fmu_path = tmp_path / "created.fmu"
    result = FMU.create(fmu_path, md_file)

    assert result == fmu_path
    assert fmu_path.is_file()
    assert fmu_path.stat().st_size > 0

    with FMU(fmu_path, mode="r") as fmu:
        assert "modelDescription.xml" in fmu.runtime.namelist()


def test_fmu_create_with_all_components(tmp_path):
    md_file = tmp_path / "modelDescription.xml"
    md_file.write_text(_MINIMAL_MD_XML)

    binary_file = tmp_path / "engine.so"
    binary_file.write_text("binary content")
    resource_file = tmp_path / "config.json"
    resource_file.write_text('{"key": "value"}')

    binaries = {"linux64": binary_file}
    resources = [resource_file]

    fmu_path = tmp_path / "full.fmu"
    result = FMU.create(fmu_path, md_file, binaries=binaries, resources=resources)

    assert result == fmu_path

    with FMU(fmu_path, mode="r") as fmu:
        assert "modelDescription.xml" in fmu.runtime.namelist()
        assert "binaries/linux64/engine.so" in fmu.runtime.namelist()
        assert "resources/config.json" in fmu.runtime.namelist()


def test_fmu_create_returns_path(tmp_path):
    md_file = tmp_path / "modelDescription.xml"
    md_file.write_text(_MINIMAL_MD_XML)

    fmu_path = tmp_path / "created.fmu"
    result = FMU.create(fmu_path, md_file)

    assert isinstance(result, Path)
    assert result == fmu_path

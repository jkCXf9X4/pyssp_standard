"""Tests for Fmi2DefaultExperiment step_size field parse/serialize roundtrip."""

from __future__ import annotations

import pytest

from pyssp_standard.standard.fmi2.codec.model_description_xml_codec import (
    Fmi2ModelDescriptionXmlCodec,
)
from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2DefaultExperiment,
    Fmi2ElementInfo,
    Fmi2ModelDescriptionDocument,
)


@pytest.fixture
def codec() -> Fmi2ModelDescriptionXmlCodec:
    return Fmi2ModelDescriptionXmlCodec()


_XML_WITH_STEP_SIZE = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="Test"
  guid="{abc123}"
>
  <DefaultExperiment stepSize="0.001"/>
</fmiModelDescription>"""

_XML_WITHOUT_STEP_SIZE = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="Test"
  guid="{abc123}"
>
  <DefaultExperiment startTime="0.0"/>
</fmiModelDescription>"""

_XML_NO_DEFAULT_EXPERIMENT = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="Test"
  guid="{abc123}"
/>"""


def test_parse_step_size(codec: Fmi2ModelDescriptionXmlCodec) -> None:
    doc = codec.parse(_XML_WITH_STEP_SIZE)
    assert doc.default_experiment is not None
    assert doc.default_experiment.step_size == 0.001


def test_parse_missing_step_size(codec: Fmi2ModelDescriptionXmlCodec) -> None:
    doc = codec.parse(_XML_WITHOUT_STEP_SIZE)
    assert doc.default_experiment is not None
    assert doc.default_experiment.step_size is None


def test_serialize_step_size(codec: Fmi2ModelDescriptionXmlCodec) -> None:
    doc = Fmi2ModelDescriptionDocument(
        root=Fmi2ElementInfo(tag="fmiModelDescription"),
        fmi_version="2.0",
        model_name="Test",
        guid="{abc123}",
        default_experiment=Fmi2DefaultExperiment(step_size=0.001),
    )
    xml = codec.serialize(doc)
    assert 'stepSize="0.001"' in xml


def test_serialize_missing_step_size(codec: Fmi2ModelDescriptionXmlCodec) -> None:
    doc = Fmi2ModelDescriptionDocument(
        root=Fmi2ElementInfo(tag="fmiModelDescription"),
        fmi_version="2.0",
        model_name="Test",
        guid="{abc123}",
        default_experiment=Fmi2DefaultExperiment(step_size=None),
    )
    xml = codec.serialize(doc)
    assert "stepSize" not in xml


def test_roundtrip_step_size(codec: Fmi2ModelDescriptionXmlCodec) -> None:
    xml = _XML_WITH_STEP_SIZE
    doc1 = codec.parse(xml)
    assert doc1.default_experiment is not None
    assert doc1.default_experiment.step_size == 0.001
    serialized = codec.serialize(doc1)
    doc2 = codec.parse(serialized)
    assert doc2.default_experiment is not None
    assert doc2.default_experiment.step_size == 0.001
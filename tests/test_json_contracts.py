from __future__ import annotations

# ruff: noqa: S101
import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest
from x_make_common_x.exporters import ExportResult
from x_make_common_x.json_contracts import validate_payload, validate_schema

from x_make_mermaid_x.json_contracts import ERROR_SCHEMA, INPUT_SCHEMA, OUTPUT_SCHEMA
from x_make_mermaid_x.x_cls_make_mermaid_x import main_json

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "json_contracts"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
EXPECTED_NODE_COUNT = 2
EXPECTED_EDGE_COUNT = 1


def _load_fixture(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / f"{name}.json").open("r", encoding="utf-8") as handle:
        raw_payload = cast("object", json.load(handle))
    if not isinstance(raw_payload, dict):
        message = f"Fixture payload must be an object: {name}"
        raise TypeError(message)
    typed_payload: dict[str, object] = {}
    for key, value in raw_payload.items():
        typed_payload[str(key)] = value
    return typed_payload


SAMPLE_INPUT: Final[dict[str, object]] = _load_fixture("input")
SAMPLE_OUTPUT: Final[dict[str, object]] = _load_fixture("output")
SAMPLE_ERROR: Final[dict[str, object]] = _load_fixture("error")


def test_schemas_are_valid() -> None:
    for schema in (INPUT_SCHEMA, OUTPUT_SCHEMA, ERROR_SCHEMA):
        validate_schema(schema)


def test_sample_payloads_match_schema() -> None:
    validate_payload(SAMPLE_INPUT, INPUT_SCHEMA)
    validate_payload(SAMPLE_OUTPUT, OUTPUT_SCHEMA)
    validate_payload(SAMPLE_ERROR, ERROR_SCHEMA)


def test_existing_reports_align_with_schema() -> None:
    if not REPORTS_DIR.exists():
        pytest.skip("no reports directory for mermaid tool")
    report_files = sorted(REPORTS_DIR.glob("x_make_mermaid_x_run_*.json"))
    if not report_files:
        pytest.skip("no mermaid run reports to validate")
    for report_file in report_files:
        with report_file.open("r", encoding="utf-8") as handle:
            payload_obj: object = json.load(handle)
        if isinstance(payload_obj, Mapping):
            payload_map = cast("Mapping[str, object]", payload_obj)
            validate_payload(dict(payload_map), OUTPUT_SCHEMA)
        else:
            message = f"Report {report_file.name} must contain a JSON object"
            raise TypeError(message)


def test_main_json_builds_from_document(  # noqa: PLR0915 - test covers varied behaviors
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    payload = copy.deepcopy(SAMPLE_INPUT)
    output_dir = tmp_path / "artifacts"
    parameters_obj = payload.get("parameters")
    if not isinstance(parameters_obj, dict):
        message = "sample fixture payload must contain parameters object"
        raise TypeError(message)
    parameters = cast("dict[str, object]", parameters_obj)
    parameters["output_mermaid"] = str(output_dir / "diagram.mmd")
    parameters["output_svg"] = str(output_dir / "diagram.svg")
    fake_cli = tmp_path / "bin" / "mmdc.cmd"
    fake_cli.parent.mkdir(parents=True, exist_ok=True)
    fake_cli.write_text("binary", encoding="utf-8")
    parameters["mermaid_cli_path"] = str(fake_cli)

    def fake_export(
        mermaid_source: str,
        *,
        output_dir: Path,
        stem: str,
        mermaid_cli_path: str | None = None,
        **_kwargs: object,
    ) -> ExportResult:
        mmd_path = output_dir / f"{stem}.mmd"
        output_dir.mkdir(parents=True, exist_ok=True)
        mmd_path.write_text(mermaid_source, encoding="utf-8")
        svg_path = output_dir / f"{stem}.svg"
        svg_path.write_text("<svg />", encoding="utf-8")
        command = ("mmdc", "-i", str(mmd_path), "-o", str(svg_path))
        return ExportResult(
            exporter="mermaid-cli",
            succeeded=True,
            output_path=svg_path,
            command=command,
            stdout="",
            stderr="",
            inputs={"mermaid": mmd_path},
            binary_path=Path(mermaid_cli_path) if mermaid_cli_path else None,
        )

    monkeypatch.setattr(
        "x_make_mermaid_x.x_cls_make_mermaid_x.export_mermaid_to_svg",
        fake_export,
    )

    result = main_json(payload)

    validate_payload(result, OUTPUT_SCHEMA)
    status_value = result.get("status")
    assert isinstance(status_value, str)
    assert status_value == "success"

    artifact_obj = result.get("mermaid")
    assert isinstance(artifact_obj, dict)
    artifact_map = cast("dict[str, object]", artifact_obj)
    source_path_value = artifact_map.get("source_path")
    assert isinstance(source_path_value, str)
    mermaid_path = Path(source_path_value)
    assert mermaid_path.exists()
    source_bytes = artifact_map.get("source_bytes")
    assert isinstance(source_bytes, int)
    assert source_bytes > 0

    svg_info_obj = artifact_map.get("svg")
    assert isinstance(svg_info_obj, dict)
    svg_info_map = cast("dict[str, object]", svg_info_obj)
    assert svg_info_map.get("succeeded") is True

    summary_obj = result.get("summary")
    assert isinstance(summary_obj, dict)
    summary_map = cast("dict[str, object]", summary_obj)
    assert summary_map.get("diagram") == "flowchart"
    assert summary_map.get("nodes") == EXPECTED_NODE_COUNT
    assert summary_map.get("edges") == EXPECTED_EDGE_COUNT

    messages_obj = result.get("messages")
    assert isinstance(messages_obj, list)
    assert messages_obj
    first_message = messages_obj[0]
    assert isinstance(first_message, str)
    assert "Mermaid CLI executed successfully" in first_message


def test_main_json_uses_raw_source(tmp_path: Path) -> None:
    payload: dict[str, object] = {
        "command": "x_make_mermaid_x",
        "parameters": {
            "output_mermaid": str(tmp_path / "raw.mmd"),
            "source": "graph TB; A-->B;",
        },
    }

    result = main_json(payload)

    validate_payload(result, OUTPUT_SCHEMA)
    artifact_obj = result.get("mermaid")
    assert isinstance(artifact_obj, dict)
    source_path_value = artifact_obj.get("source_path")
    assert isinstance(source_path_value, str)
    mermaid_path = Path(source_path_value)
    assert mermaid_path.read_text(encoding="utf-8").endswith("\n")

    summary_obj = result.get("summary")
    assert isinstance(summary_obj, dict)
    summary_map = cast("dict[str, object]", summary_obj)
    export_svg_value = summary_map.get("export_svg")
    assert isinstance(export_svg_value, bool)
    assert export_svg_value is False


def test_main_json_reports_validation_error() -> None:
    payload: dict[str, object] = {"command": "x_make_mermaid_x", "parameters": {}}

    result = main_json(payload)

    validate_payload(result, ERROR_SCHEMA)
    status_value = result.get("status")
    message_value = result.get("message")
    assert isinstance(status_value, str)
    assert isinstance(message_value, str)
    assert status_value == "failure"
    assert message_value == "input payload failed validation"

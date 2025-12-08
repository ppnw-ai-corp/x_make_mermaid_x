"""Mermaid diagram builder.

Builds Mermaid source for many diagram types with a concise, fluent API.
Output is a plain string suitable for Markdown or Mermaid CLI.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import subprocess
import sys as _sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from collections.abc import Iterable as _Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import IO, Protocol, Self, cast

from x_make_common_x.exporters import (
    CommandRunner,
    ExportResult,
    export_mermaid_to_svg,
)
from x_make_common_x.json_contracts import validate_payload

from x_make_mermaid_x.json_contracts import ERROR_SCHEMA, INPUT_SCHEMA, OUTPUT_SCHEMA


class CommandError(RuntimeError):
    def __init__(
        self,
        argv: tuple[str, ...],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        message = (
            "Command "
            + " ".join(argv)
            + f" failed with exit code {returncode}: {stderr or stdout}"
        )
        super().__init__(message)
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_command(
    args: _Iterable[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    argv = tuple(args)
    completed = subprocess.run(  # noqa: S603
        list(argv),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise CommandError(
            argv,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
    return completed


_LOGGER = logging.getLogger("x_make")


class _SchemaValidationError(Exception):
    message: str
    path: tuple[object, ...]
    schema_path: tuple[object, ...]


class _JsonSchemaModule(Protocol):
    ValidationError: type[_SchemaValidationError]


def _load_validation_error() -> type[_SchemaValidationError]:
    module = cast("_JsonSchemaModule", importlib.import_module("jsonschema"))
    return module.ValidationError


ValidationErrorType: type[_SchemaValidationError] = _load_validation_error()

_EMPTY_MAPPING: Mapping[str, object] = MappingProxyType(cast("dict[str, object]", {}))


def _info(*args: object) -> None:
    msg = " ".join(str(a) for a in args)
    with suppress(Exception):
        _LOGGER.info("%s", msg)
    printed = False
    with suppress(Exception):
        print(msg)
        printed = True
    if not printed:
        with suppress(Exception):
            _sys.stdout.write(msg + "\n")


SCHEMA_VERSION = "x_make_mermaid_x.run/1.0"


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def _failure_payload(
    message: str,
    *,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "failure",
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    with suppress(ValidationErrorType):
        validate_payload(payload, ERROR_SCHEMA)
    return payload


# Diagram kinds supported (primary headers)
_FLOW = "flowchart"
_SEQ = "sequenceDiagram"
_CLASS = "classDiagram"
_STATE = "stateDiagram-v2"
_ER = "erDiagram"
_GANTT = "gantt"
_JOURNEY = "journey"
_PIE = "pie"
_TIMELINE = "timeline"
_GIT = "gitGraph"
_MINDMAP = "mindmap"
_REQ = "requirementDiagram"
_QUAD = "quadrantChart"
_SANKEY = "sankey-beta"
_XY = "xychart-beta"
_BLOCK = "block-beta"

FlowDir = tuple[str, ...]
AttrValue = str | int | float | bool | None
DirectivePayload = Mapping[str, object]

_NOTE_PAIR_LENGTH = 2


def _new_str_list() -> list[str]:
    return []


def _esc(s: str) -> str:
    return s.replace("\n", "\\n")


@dataclass
class MermaidDoc:
    kind: str
    header: str
    lines: list[str] = field(default_factory=_new_str_list)
    directives: list[str] = field(
        default_factory=_new_str_list
    )  # e.g., %%{init: {...}}%%
    comments: list[str] = field(default_factory=_new_str_list)


def _handle_flowchart(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del date_format, diagram
    builder.flowchart(direction)
    if title:
        builder.raw(f"title {_esc(title)}")


def _handle_sequence(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram
    builder.sequence(title)


def _handle_state(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram
    builder.state()
    if title:
        builder.raw(f"title {_esc(title)}")


def _handle_class_diagram(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram, title
    builder.class_diagram()


def _handle_er_diagram(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram, title
    builder.er()


def _handle_journey(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram
    builder.journey(title)


def _handle_pie(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram
    builder.pie(title)


def _handle_timeline(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram
    builder.timeline(title)


def _handle_gitgraph(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram, title
    builder.gitgraph()


def _handle_mindmap(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram, title
    builder.mindmap()


def _handle_requirement(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram, title
    builder.requirement()


def _handle_gantt(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, diagram
    builder.gantt(title, date_format=date_format)


def _handle_quadrants(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, diagram
    builder.quadrants(title)


def _handle_beta(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format, title
    builder.custom(diagram, header=diagram)


def _handle_custom_fallback(
    builder: MermaidBuilder,
    *,
    direction: str,
    title: str | None,
    date_format: str,
    diagram: str,
) -> None:
    del direction, date_format
    builder.custom(diagram, header=diagram)
    if title:
        builder.raw(f"title {_esc(title)}")


def _set_diagram(builder: MermaidBuilder, document: Mapping[str, object]) -> str:
    diagram_obj = document.get("diagram")
    diagram = (
        str(diagram_obj) if isinstance(diagram_obj, str) and diagram_obj else _FLOW
    )
    direction_obj = document.get("direction")
    direction = (
        str(direction_obj) if isinstance(direction_obj, str) and direction_obj else "LR"
    )
    title_obj = document.get("title")
    title = str(title_obj) if isinstance(title_obj, str) and title_obj else None
    date_format_obj = document.get("date_format")
    date_format = (
        str(date_format_obj)
        if isinstance(date_format_obj, str) and date_format_obj
        else "YYYY-MM-DD"
    )

    handler_map = {
        _FLOW: _handle_flowchart,
        _SEQ: _handle_sequence,
        _CLASS: _handle_class_diagram,
        _STATE: _handle_state,
        _ER: _handle_er_diagram,
        _GANTT: _handle_gantt,
        _JOURNEY: _handle_journey,
        _PIE: _handle_pie,
        _TIMELINE: _handle_timeline,
        _GIT: _handle_gitgraph,
        _MINDMAP: _handle_mindmap,
        _REQ: _handle_requirement,
        _QUAD: _handle_quadrants,
        _SANKEY: _handle_beta,
        _XY: _handle_beta,
        _BLOCK: _handle_beta,
    }

    handler = handler_map.get(diagram, _handle_custom_fallback)
    handler(
        builder,
        direction=direction,
        title=title,
        date_format=date_format,
        diagram=diagram,
    )
    return diagram


def _apply_directives(builder: MermaidBuilder, directives: object) -> None:
    if not isinstance(directives, Sequence):
        return
    for entry in directives:
        if not isinstance(entry, Mapping):
            continue
        text_obj = entry.get("text")
        payload_obj = entry.get("payload")
        if isinstance(payload_obj, Mapping):
            typed_payload = cast("Mapping[str, object]", payload_obj)
            builder.set_directive(dict(typed_payload))
        elif isinstance(text_obj, str) and text_obj:
            builder.set_directive(text_obj)


def _apply_comments(builder: MermaidBuilder, comments: object) -> None:
    if not isinstance(comments, Sequence):
        return
    for item in comments:
        if isinstance(item, str) and item:
            builder.add_comment(item)


def _apply_nodes(builder: MermaidBuilder, nodes: object) -> int:
    if not isinstance(nodes, Sequence):
        return 0
    count = 0
    for entry in nodes:
        if not isinstance(entry, Mapping):
            continue
        node_id_obj = entry.get("id")
        if not isinstance(node_id_obj, str) or not node_id_obj:
            continue
        label_obj = entry.get("label")
        label = None
        if isinstance(label_obj, str) and label_obj:
            label = label_obj
        shape_obj = entry.get("shape")
        shape = shape_obj if isinstance(shape_obj, str) and shape_obj else None
        builder.node(node_id_obj, label, shape)
        count += 1
    return count


def _apply_edges(builder: MermaidBuilder, edges: object) -> int:
    if not isinstance(edges, Sequence):
        return 0
    count = 0
    for entry in edges:
        if not isinstance(entry, Mapping):
            continue
        src = entry.get("source")
        dst = entry.get("target")
        if not isinstance(src, str) or not isinstance(dst, str):
            continue
        label_obj = entry.get("label")
        label = None
        if isinstance(label_obj, str) and label_obj:
            label = label_obj
        arrow_obj = entry.get("arrow")
        arrow = arrow_obj if isinstance(arrow_obj, str) and arrow_obj else "-->"
        style_obj = entry.get("style")
        style = style_obj if isinstance(style_obj, str) and style_obj else None
        builder.edge(src, dst, label, arrow=arrow, style=style)
        count += 1
    return count


def _apply_lines(builder: MermaidBuilder, lines: object) -> None:
    if not isinstance(lines, Sequence):
        return
    for line in lines:
        if isinstance(line, str) and line:
            builder.raw(line)


def _instruction_participant(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    pid = payload.get("id")
    label = payload.get("label")
    if isinstance(pid, str):
        builder.participant(pid, label if isinstance(label, str) else None)


def _instruction_message(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    src = payload.get("source")
    dst = payload.get("target")
    text = payload.get("text")
    kind = payload.get("kind")
    if isinstance(src, str) and isinstance(dst, str) and isinstance(text, str):
        arrow = kind if isinstance(kind, str) and kind else "->>"
        builder.message(src, dst, text, kind=arrow)


def _instruction_note(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    who = payload.get("who")
    text = payload.get("text")
    if not isinstance(text, str):
        return
    if isinstance(who, (list, tuple)) and len(who) == _NOTE_PAIR_LENGTH:
        first, second = who
        if isinstance(first, str) and isinstance(second, str):
            builder.note_over((first, second), text)
            return
    if isinstance(who, str):
        builder.note_over(who, text)


def _instruction_activate(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        pid = payload.get("id")
        if isinstance(pid, str):
            builder.activate(pid)


def _instruction_deactivate(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        pid = payload.get("id")
        if isinstance(pid, str):
            builder.deactivate(pid)


def _instruction_block(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    kind = payload.get("kind")
    title = payload.get("title")
    body = payload.get("body")
    if isinstance(kind, str) and isinstance(title, str) and isinstance(body, Sequence):
        lines = [str(entry) for entry in body]
        builder.block(kind, title, lines)


def _instruction_gantt_section(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        name = payload.get("name")
        if isinstance(name, str):
            builder.raw(f"section {_esc(name)}")


def _instruction_gantt_task(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    name = payload.get("name")
    span = payload.get("span")
    if isinstance(name, str) and isinstance(span, str):
        builder.raw(f"{name}: {span}")


def _instruction_journey_section(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        name = payload.get("name")
        if isinstance(name, str):
            builder.raw(f"section {_esc(name)}")


def _instruction_journey_step(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    text = payload.get("text")
    score = payload.get("score")
    actor = payload.get("actor")
    if (
        isinstance(text, str)
        and isinstance(score, (int, float))
        and isinstance(actor, str)
    ):
        builder.raw(f"  {_esc(text)}: {float(score)}, {_esc(actor)}")


def _instruction_pie_slice(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    label = payload.get("label")
    value = payload.get("value")
    if isinstance(label, str) and isinstance(value, (int, float)):
        builder.raw(f'"{_esc(label)}" : {value}')


def _instruction_timeline_entry(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    label = payload.get("label")
    value = payload.get("value")
    if isinstance(label, str) and isinstance(value, str):
        builder.raw(f"{label}: {value}")


def _instruction_git_commit(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        message = payload.get("message")
        if isinstance(message, str):
            builder.raw(f'commit id: "{_esc(message)}"')


def _instruction_git_branch(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        name = payload.get("name")
        if isinstance(name, str):
            builder.raw(f"branch {name}")


def _instruction_git_checkout(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        branch = payload.get("branch")
        if isinstance(branch, str):
            builder.raw(f"checkout {branch}")


def _instruction_git_merge(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        branch = payload.get("branch")
        if isinstance(branch, str):
            builder.raw(f"merge {branch}")


def _instruction_mindmap_node(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        path = payload.get("path")
        if isinstance(path, Sequence):
            nodes = [str(part) for part in path if isinstance(part, str)]
            builder.mindmap_node(nodes)


def _instruction_req(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    kind = payload.get("kind")
    ident = payload.get("id")
    attrs = payload.get("attributes")
    if isinstance(kind, str) and isinstance(ident, str) and isinstance(attrs, Mapping):
        builder.req(kind, ident, {str(k): str(v) for k, v in attrs.items()})


def _instruction_req_link(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    source = payload.get("source")
    operator = payload.get("operator")
    target = payload.get("target")
    label = payload.get("label")
    if (
        isinstance(source, str)
        and isinstance(operator, str)
        and isinstance(target, str)
    ):
        link_label = label if isinstance(label, str) else None
        builder.req_link(source, operator, target, link_label)


def _instruction_quadrant(builder: MermaidBuilder, payload: object) -> None:
    if isinstance(payload, Mapping):
        index = payload.get("index")
        name = payload.get("name")
        if isinstance(index, int) and isinstance(name, str):
            builder.quadrant(index, name)


def _instruction_quadrant_point(builder: MermaidBuilder, payload: object) -> None:
    if not isinstance(payload, Mapping):
        return
    label = payload.get("label")
    x = payload.get("x")
    y = payload.get("y")
    if (
        isinstance(label, str)
        and isinstance(x, (int, float))
        and isinstance(y, (int, float))
    ):
        builder.quad_point(label, float(x), float(y))


_INSTRUCTION_HANDLERS: dict[str, Callable[[MermaidBuilder, object], None]] = {
    "participant": _instruction_participant,
    "message": _instruction_message,
    "note": _instruction_note,
    "activate": _instruction_activate,
    "deactivate": _instruction_deactivate,
    "block": _instruction_block,
    "gantt_section": _instruction_gantt_section,
    "gantt_task": _instruction_gantt_task,
    "journey_section": _instruction_journey_section,
    "journey_step": _instruction_journey_step,
    "pie_slice": _instruction_pie_slice,
    "timeline_entry": _instruction_timeline_entry,
    "git_commit": _instruction_git_commit,
    "git_branch": _instruction_git_branch,
    "git_checkout": _instruction_git_checkout,
    "git_merge": _instruction_git_merge,
    "mindmap_node": _instruction_mindmap_node,
    "req": _instruction_req,
    "req_link": _instruction_req_link,
    "quadrant": _instruction_quadrant,
    "quadrant_point": _instruction_quadrant_point,
}


def _apply_instruction(
    builder: MermaidBuilder, instr_type: str, payload: object
) -> None:
    if instr_type in {"line", "raw"}:
        if isinstance(payload, str):
            builder.raw(payload)
        return
    handler = _INSTRUCTION_HANDLERS.get(instr_type)
    if handler:
        handler(builder, payload)


def _apply_instructions(builder: MermaidBuilder, instructions: object) -> None:
    if not isinstance(instructions, Sequence):
        return
    for entry in instructions:
        if not isinstance(entry, Mapping):
            continue
        type_obj = entry.get("type")
        payload = entry.get("payload")
        if isinstance(type_obj, str) and type_obj:
            _apply_instruction(builder, type_obj, payload)


def _apply_document(
    builder: MermaidBuilder,
    document: Mapping[str, object],
) -> dict[str, object]:
    diagram = _set_diagram(builder, document)
    _apply_directives(builder, document.get("directives"))
    _apply_comments(builder, document.get("comments"))
    node_count = _apply_nodes(builder, document.get("nodes"))
    edge_count = _apply_edges(builder, document.get("edges"))
    _apply_lines(builder, document.get("lines"))
    _apply_instructions(builder, document.get("instructions"))
    metadata_obj = document.get("metadata")
    summary: dict[str, object] = {
        "diagram": diagram,
        "nodes": node_count,
        "edges": edge_count,
    }
    if isinstance(metadata_obj, Mapping):
        typed_metadata = cast("Mapping[str, object]", metadata_obj)
        summary["metadata"] = dict(typed_metadata)
    return summary


def _maybe_to_svg(
    mermaid_source: str,
    *,
    output_svg: str | None,
    output_mermaid: Path,
    mermaid_cli_path: str | None,
    builder: MermaidBuilder | None,
) -> tuple[dict[str, object] | None, list[str]]:
    messages: list[str] = []
    export_result: dict[str, object] | None = None
    output_path = Path(output_svg) if output_svg else output_mermaid.with_suffix(".svg")
    export = export_mermaid_to_svg(
        mermaid_source,
        output_dir=output_path.parent,
        stem=output_path.stem,
        mermaid_cli_path=mermaid_cli_path,
        runner=builder.get_runner() if builder else None,
    )
    if export.succeeded:
        messages.append("Mermaid CLI executed successfully")
    else:
        detail = export.detail or "Mermaid CLI execution failed"
        messages.append(detail)
    export_result = export.to_metadata()
    return export_result, messages


def _write_mermaid_source(path: Path, source: str) -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    size = path.stat().st_size
    return str(path), size


def _validate_input_schema(payload: Mapping[str, object]) -> dict[str, object] | None:
    try:
        validate_payload(payload, INPUT_SCHEMA)
    except ValidationErrorType as exc:
        error = exc
        return _failure_payload(
            "input payload failed validation",
            details={
                "error": error.message,
                "path": [str(p) for p in error.path],
                "schema_path": [str(p) for p in error.schema_path],
            },
        )
    return None


def _extract_parameters(payload: Mapping[str, object]) -> Mapping[str, object]:
    parameters_obj = payload.get("parameters")
    if isinstance(parameters_obj, Mapping):
        typed_parameters = cast("Mapping[str, object]", parameters_obj)
        return MappingProxyType(dict(typed_parameters))
    return _EMPTY_MAPPING


def _resolve_output_mermaid(
    parameters: Mapping[str, object],
) -> Path | dict[str, object]:
    output_mermaid_obj = parameters.get("output_mermaid")
    if isinstance(output_mermaid_obj, str) and output_mermaid_obj:
        return Path(output_mermaid_obj)
    return _failure_payload(
        "output_mermaid path missing",
        details={"field": "output_mermaid"},
    )


def _extract_export_options(
    parameters: Mapping[str, object],
) -> tuple[bool, str | None, str | None]:
    export_svg_obj = parameters.get("export_svg")
    export_svg = (
        bool(export_svg_obj) if not isinstance(export_svg_obj, bool) else export_svg_obj
    )
    output_svg_obj = parameters.get("output_svg")
    output_svg: str | None = None
    if isinstance(output_svg_obj, str) and output_svg_obj:
        output_svg = output_svg_obj
    mermaid_cli_obj = parameters.get("mermaid_cli_path")
    mermaid_cli_path: str | None = None
    if isinstance(mermaid_cli_obj, str) and mermaid_cli_obj:
        mermaid_cli_path = mermaid_cli_obj
    return export_svg, output_svg, mermaid_cli_path


def _prepare_mermaid_source(
    parameters: Mapping[str, object],
    *,
    ctx: object | None,
) -> tuple[MermaidBuilder | None, str, dict[str, object]] | dict[str, object]:
    document_obj = parameters.get("document")
    document = None
    if isinstance(document_obj, Mapping):
        typed_document = cast("Mapping[str, object]", document_obj)
        document = MappingProxyType(dict(typed_document))
    builder: MermaidBuilder | None = None
    summary_data: dict[str, object] = {}
    document_source: str | None = None
    if document is not None:
        builder = MermaidBuilder(ctx=ctx)
        summary_data = _apply_document(builder, document)
        document_source = builder.source()

    source_obj = parameters.get("source")
    explicit_source = source_obj if isinstance(source_obj, str) and source_obj else None
    mermaid_source = explicit_source if explicit_source is not None else document_source
    if mermaid_source is None:
        return _failure_payload(
            "no Mermaid document or source provided",
            details={"reason": "document and source were empty"},
        )
    return builder, mermaid_source, summary_data


def _compose_summary(
    summary_data: Mapping[str, object],
    *,
    source_path: str,
    export_svg_flag: bool,
    output_svg: str | None,
    mermaid_cli_path: str | None,
) -> dict[str, object]:
    summary: dict[str, object] = dict(summary_data)
    summary["output_mermaid"] = source_path
    summary["export_svg"] = export_svg_flag
    if output_svg:
        summary["output_svg"] = output_svg
    if mermaid_cli_path:
        summary["mermaid_cli_path"] = mermaid_cli_path
    return summary


def _compose_success_result(
    mermaid_artifact: Mapping[str, object],
    messages: Sequence[str],
    summary: Mapping[str, object],
) -> dict[str, object]:
    mermaid_payload: dict[str, object] = dict(mermaid_artifact)
    summary_payload: dict[str, object] = dict(summary)
    return {
        "status": "success",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _timestamp(),
        "mermaid": mermaid_payload,
        "messages": list(messages),
        "summary": summary_payload,
    }


def _validate_output_schema(result: Mapping[str, object]) -> dict[str, object] | None:
    try:
        validate_payload(result, OUTPUT_SCHEMA)
    except ValidationErrorType as exc:
        error = exc
        return _failure_payload(
            "generated output failed schema validation",
            details={
                "error": error.message,
                "path": [str(p) for p in error.path],
                "schema_path": [str(p) for p in error.schema_path],
            },
        )
    return None


class MermaidBuilder:
    """Flexible Mermaid builder covering many diagram kinds.

    Typical usage:
      m = x_cls_make_mermaid_x().flowchart("LR").node("A","Start").edge("A","B","go")
      m.sequence().participant("A","Alice").message("A","B","Hi")
      src = m.source()
    """

    def __init__(
        self,
        direction: str = "LR",
        ctx: object | None = None,
        *,
        runner: CommandRunner | None = None,
        mermaid_cli: str | None = None,
    ) -> None:
        self._ctx = ctx
        self._doc = MermaidDoc(kind=_FLOW, header=f"{_FLOW} {direction}")
        self._runner: CommandRunner | None = runner
        self._mermaid_cli: str | None = mermaid_cli
        self._last_export_result: ExportResult | None = None

    def _is_verbose(self) -> bool:
        value: object = getattr(self._ctx, "verbose", False)
        if isinstance(value, bool):
            return value
        return bool(value)

    # Core controls

    def set_directive(self, directive_json: str | DirectivePayload) -> Self:
        """Add a directive block like %%{init: { 'theme':'dark' }}%%."""
        if isinstance(directive_json, dict):
            # minimal serializer without imports
            txt = json.dumps(directive_json, separators=(",", ":"))
            self._doc.directives.append(f"%%{{init: {txt}}}%%")
        else:
            self._doc.directives.append(str(directive_json))
        return self

    def add_comment(self, text: str) -> Self:
        self._doc.comments.append(f"%% {_esc(text)} %%")
        return self

    # Kind switches

    def flowchart(self, direction: str = "LR") -> Self:
        self._doc = MermaidDoc(kind=_FLOW, header=f"{_FLOW} {direction}")
        return self

    def sequence(self, title: str | None = None) -> Self:
        self._doc = MermaidDoc(kind=_SEQ, header=_SEQ)
        if title:
            self._doc.lines.append(f"title {_esc(title)}")
        return self

    def class_diagram(self) -> Self:
        self._doc = MermaidDoc(kind=_CLASS, header=_CLASS)
        return self

    def state(self) -> Self:
        self._doc = MermaidDoc(kind=_STATE, header=_STATE)
        return self

    def er(self) -> Self:
        self._doc = MermaidDoc(kind=_ER, header=_ER)
        return self

    def gantt(self, title: str | None = None, date_format: str = "YYYY-MM-DD") -> Self:
        self._doc = MermaidDoc(kind=_GANTT, header=_GANTT)
        self._doc.lines.append(f"dateFormat {date_format}")
        if title:
            self._doc.lines.append(f"title {_esc(title)}")
        return self

    def journey(self, title: str | None = None) -> Self:
        self._doc = MermaidDoc(kind=_JOURNEY, header=_JOURNEY)
        if title:
            self._doc.lines.append(f"title {_esc(title)}")
        return self

    def pie(self, title: str | None = None) -> Self:
        self._doc = MermaidDoc(kind=_PIE, header=_PIE)
        if title:
            self._doc.lines.append(f"title {_esc(title)}")
        return self

    def timeline(self, title: str | None = None) -> Self:
        self._doc = MermaidDoc(kind=_TIMELINE, header=_TIMELINE)
        if title:
            self._doc.lines.append(f"title {_esc(title)}")
        return self

    def gitgraph(self) -> Self:
        self._doc = MermaidDoc(kind=_GIT, header=_GIT)
        return self

    def mindmap(self) -> Self:
        self._doc = MermaidDoc(kind=_MINDMAP, header=_MINDMAP)
        return self

    def requirement(self) -> Self:
        self._doc = MermaidDoc(kind=_REQ, header=_REQ)
        return self

    def quadrants(
        self,
        title: str | None = None,
        x_left: str = "Low",
        x_right: str = "High",
        y_bottom: str = "Low",
        y_top: str = "High",
    ) -> Self:
        self._doc = MermaidDoc(kind=_QUAD, header=_QUAD)
        if title:
            self._doc.lines.append(f"title {_esc(title)}")
        self._doc.lines.append(f'x-axis "{_esc(x_left)}" "{_esc(x_right)}"')
        self._doc.lines.append(f'y-axis "{_esc(y_bottom)}" "{_esc(y_top)}"')
        return self

    def custom(self, kind: str, header: str | None = None) -> Self:
        self._doc = MermaidDoc(kind=kind, header=header or kind)
        return self

    # Flowchart API

    def node(
        self, node_id: str, label: str | None = None, shape: str | None = None
    ) -> Self:
        """Add a node; shape can be: [], (), (()) , {} , [[]], >, etc."""
        if self._doc.kind != _FLOW:
            return self
        if label is None:
            self._doc.lines.append(f"{node_id}")
            return self
        shape_map = {
            "rect": ("[", "]"),
            "round": ("(", ")"),
            "stadium": ("((", "))"),
            "subroutine": ("[[", "]]"),
            "cylinder": ("[(", ")]"),
            "circle": ("((", "))"),
            "asym": (">", "]"),
        }
        if shape and shape in shape_map:
            left_delim, right_delim = shape_map[shape]
            self._doc.lines.append(f"{node_id}{left_delim}{_esc(label)}{right_delim}")
        else:
            self._doc.lines.append(f'{node_id}["{_esc(label)}"]')
        return self

    def edge(
        self,
        src: str,
        dst: str,
        label: str | None = None,
        arrow: str = "-->",
        style: str | None = None,
    ) -> Self:
        if self._doc.kind != _FLOW:
            return self
        mid = f"|{_esc(label)}|" if label else ""
        sfx = f" {style}" if style else ""
        self._doc.lines.append(f"{src} {arrow}{mid} {dst}{sfx}")
        return self

    def subgraph(self, title: str, body: Iterable[str] | None = None) -> Self:
        if self._doc.kind != _FLOW:
            return self
        self._doc.lines.append(f"subgraph {_esc(title)}")
        if body:
            for ln in body:
                self._doc.lines.append(ln)
        self._doc.lines.append("end")
        return self

    def style_node(self, node_id: str, css: str) -> Self:
        if self._doc.kind == _FLOW:
            self._doc.lines.append(f"style {node_id} {_esc(css)}")
        return self

    def link_style(self, idx: int, css: str) -> Self:
        if self._doc.kind == _FLOW:
            self._doc.lines.append(f"linkStyle {idx} {_esc(css)}")
        return self

    def click(self, node_id: str, url: str, tooltip: str | None = None) -> Self:
        if self._doc.kind == _FLOW:
            if tooltip:
                self._doc.lines.append(
                    f'click {node_id} "{_esc(url)}" "{_esc(tooltip)}"'
                )
            else:
                self._doc.lines.append(f'click {node_id} "{_esc(url)}"')
        return self

    # Sequence API

    def participant(self, pid: str, label: str | None = None) -> Self:
        if self._doc.kind == _SEQ:
            if label:
                self._doc.lines.append(f'participant {pid} as "{_esc(label)}"')
            else:
                self._doc.lines.append(f"participant {pid}")
        return self

    def message(self, src: str, dst: str, text: str, kind: str = "->>") -> Self:
        if self._doc.kind == _SEQ:
            self._doc.lines.append(f"{src} {kind} {dst}: {_esc(text)}")
        return self

    def note_over(self, who: str | tuple[str, str], text: str) -> Self:
        if self._doc.kind == _SEQ:
            if isinstance(who, tuple):
                self._doc.lines.append(f"Note over {who[0]},{who[1]}: {_esc(text)}")
            else:
                self._doc.lines.append(f"Note over {who}: {_esc(text)}")
        return self

    def activate(self, pid: str) -> Self:
        if self._doc.kind == _SEQ:
            self._doc.lines.append(f"activate {pid}")
        return self

    def deactivate(self, pid: str) -> Self:
        if self._doc.kind == _SEQ:
            self._doc.lines.append(f"deactivate {pid}")
        return self

    def block(self, kind: str, title: str, body: Iterable[str]) -> Self:
        """Generic sequence block: kind in ('loop','alt','opt','par','rect')."""
        if self._doc.kind == _SEQ:
            self._doc.lines.append(f"{kind} {_esc(title)}")
            for ln in body:
                self._doc.lines.append(ln)
            self._doc.lines.append("end")
        return self

    # Class API

    def class_(
        self,
        name: str,
        fields: list[str] | None = None,
        methods: list[str] | None = None,
    ) -> Self:
        if self._doc.kind == _CLASS:
            self._doc.lines.append(f"class {name} {{")
            for f in fields or []:
                self._doc.lines.append(f"  {f}")
            for m in methods or []:
                self._doc.lines.append(f"  {m}()")
            self._doc.lines.append("}")
        return self

    def class_rel(self, a: str, op: str, b: str, label: str | None = None) -> Self:
        """op: '<|--', '*--', 'o--', '--', '<..', etc."""
        if self._doc.kind == _CLASS:
            lab = f" : {_esc(label)}" if label else ""
            self._doc.lines.append(f"{a} {op} {b}{lab}")
        return self

    # State API

    def state_node(self, name: str, alias: str | None = None) -> Self:
        if self._doc.kind == _STATE:
            if alias:
                self._doc.lines.append(f'state "{_esc(name)}" as {alias}')
            else:
                self._doc.lines.append(f'state "{_esc(name)}"')
        return self

    def state_trans(self, src: str, dst: str, event: str | None = None) -> Self:
        if self._doc.kind == _STATE:
            ev = f" : {_esc(event)}" if event else ""
            self._doc.lines.append(f"{src} --> {dst}{ev}")
        return self

    def state_start(self, to: str) -> Self:
        return self.state_trans("[*]", to)

    def state_end(self, frm: str) -> Self:
        return self.state_trans(frm, "[*]")

    def state_subgraph(self, name: str, body: Iterable[str]) -> Self:
        if self._doc.kind == _STATE:
            self._doc.lines.append(f"state {_esc(name)} {{")
            for ln in body:
                self._doc.lines.append(ln)
            self._doc.lines.append("}")
        return self

    # ER API

    def er_entity(self, name: str, *fields: str) -> Self:
        if self._doc.kind == _ER:
            if fields:
                self._doc.lines.append(
                    f"{name} {{ {'; '.join(_esc(f) for f in fields)} }}"
                )
            else:
                self._doc.lines.append(f"{name}")
        return self

    def er_rel(self, left: str, card: str, right: str, label: str = "") -> Self:
        """card like '||--o{' etc."""
        if self._doc.kind == _ER:
            lab = f" : {_esc(label)}" if label else ""
            self._doc.lines.append(f"{left} {card} {right}{lab}")
        return self

    # Gantt API

    def gantt_section(self, title: str) -> Self:
        if self._doc.kind == _GANTT:
            self._doc.lines.append(f"section {_esc(title)}")
        return self

    def gantt_task(
        self,
        title: str,
        task_id: str | None = None,
        start_or_rel: str | None = None,
        duration: str | None = None,
        depends_on: str | None = None,
    ) -> Self:
        """Examples:
        Task :t1, 2025-01-01, 3d
        Task :t2, after t1, 5d
        Task :t3, 2025-01-02, 1d
        """
        if self._doc.kind == _GANTT:
            parts: list[str] = []
            if task_id:
                parts.append(task_id)
            if start_or_rel:
                parts.append(start_or_rel)
            if duration:
                parts.append(duration)
            if depends_on:
                parts.append(f"after {depends_on}")
            meta = ", ".join(parts) if parts else ""
            self._doc.lines.append(f"{_esc(title)} : {meta}".rstrip())
        return self

    # Journey

    def journey_section(self, title: str) -> Self:
        if self._doc.kind == _JOURNEY:
            self._doc.lines.append(f"section {_esc(title)}")
        return self

    def journey_step(self, actor: str, score: int, text: str) -> Self:
        if self._doc.kind == _JOURNEY:
            self._doc.lines.append(f"{_esc(actor)}: {score}: {_esc(text)}")
        return self

    # Pie

    def pie_slice(self, label: str, value: float) -> Self:
        if self._doc.kind == _PIE:
            self._doc.lines.append(f'"{_esc(label)}" : {value}')
        return self

    # Timeline

    def timeline_entry(self, when: str, *items: str) -> Self:
        if self._doc.kind == _TIMELINE:
            self._doc.lines.append(
                f'{_esc(when)} : {", ".join(_esc(i) for i in items)}'
            )
        return self

    # GitGraph

    def git_commit(self, msg: str | None = None) -> Self:
        if self._doc.kind == _GIT:
            tag_part = f'tag: "{_esc(msg)}"' if msg else ""
            entry = f"commit {tag_part}".rstrip()
            self._doc.lines.append(entry)
        return self

    def git_branch(self, name: str) -> Self:
        if self._doc.kind == _GIT:
            self._doc.lines.append(f"branch {name}")
        return self

    def git_checkout(self, name: str) -> Self:
        if self._doc.kind == _GIT:
            self._doc.lines.append(f"checkout {name}")
        return self

    def git_merge(self, name: str) -> Self:
        if self._doc.kind == _GIT:
            self._doc.lines.append(f"merge {name}")
        return self

    # Mindmap

    def mindmap_node(self, path: list[str]) -> Self:
        """Add a node by path; indent with 2 spaces per level."""
        if self._doc.kind == _MINDMAP and path:
            for i, part in enumerate(path):
                indent = "  " * i
                self._doc.lines.append(f"{indent}{_esc(part)}")
        return self

    # Requirement

    def req(self, kind: str, ident: str, attrs: dict[str, str]) -> Self:
        """kind in ('requirement','functionalRequirement','test','risk',...)."""
        if self._doc.kind == _REQ:
            self._doc.lines.append(f"{kind} {ident} {{")
            for k, v in attrs.items():
                self._doc.lines.append(f"  {k}: {_esc(v)}")
            self._doc.lines.append("}")
        return self

    def req_link(self, a: str, op: str, b: str, label: str | None = None) -> Self:
        if self._doc.kind == _REQ:
            lab = f" : {_esc(label)}" if label else ""
            self._doc.lines.append(f"{a} {op} {b}{lab}")
        return self

    # Quadrant chart

    def quadrant(self, idx: int, name: str) -> Self:
        if self._doc.kind == _QUAD:
            self._doc.lines.append(f'quadrant-{idx} "{_esc(name)}"')
        return self

    def quad_point(self, label: str, x: float, y: float) -> Self:
        if self._doc.kind == _QUAD:
            self._doc.lines.append(f'point "{_esc(label)}" : {x}, {y}')
        return self

    # Beta charts (stubs: let callers write lines)

    def raw(self, line: str) -> Self:
        """Append a raw Mermaid line (escape yourself if needed)."""
        self._doc.lines.append(line)
        return self

    # Output

    def source(self) -> str:
        parts: list[str] = []
        parts.extend(self._doc.directives)
        parts.extend(self._doc.comments)
        parts.append(self._doc.header)
        parts.extend(self._doc.lines)
        return "\n".join(parts) + "\n"

    def save(self, path: str = "diagram.mmd") -> str:
        src = self.source()
        path_obj = Path(path)
        path_obj.write_text(src, encoding="utf-8")
        if self._is_verbose():
            _info(f"[mermaid] saved mermaid source to {path}")
        return str(path_obj)

    def to_svg(
        self,
        mmd_path: str | None = None,
        svg_path: str | None = None,
        mmdc_cmd: str | None = None,
        extra_args: list[str] | None = None,
    ) -> str | None:
        """Convert Mermaid to SVG via mermaid-cli (mmdc) if available.

        Returns SVG path on success, or None if CLI not found or conversion failed.
        """
        source_text = self.source()
        # Determine output naming
        if svg_path:
            svg_candidate = Path(svg_path)
            output_dir = svg_candidate.parent or Path()
            stem = svg_candidate.stem
        elif mmd_path:
            mmd_candidate = Path(mmd_path)
            output_dir = mmd_candidate.parent or Path()
            stem = mmd_candidate.stem
        else:
            output_dir = Path()
            stem = "diagram"

        cli_path = mmdc_cmd or self._mermaid_cli
        result = export_mermaid_to_svg(
            source_text,
            output_dir=output_dir,
            stem=stem,
            mermaid_cli_path=cli_path,
            runner=self._runner,
            extra_args=extra_args,
        )
        self._last_export_result = result

        if result.succeeded and result.output_path is not None:
            return str(result.output_path)
        if self._is_verbose():
            _info(
                "[mermaid] mmdc export failed; retained Mermaid at",
                str((output_dir / f"{stem}.mmd").resolve()),
            )
        return None

    def get_last_export_result(self) -> ExportResult | None:
        return self._last_export_result

    def get_runner(self) -> CommandRunner | None:
        return self._runner


def main() -> str:
    # Tiny demo
    m = (
        MermaidBuilder()
        .flowchart("LR")
        .node("A", "Start")
        .node("B", "End")
        .edge("A", "B", "next")
    )
    m.save("example.mmd")
    svg = m.to_svg("example.mmd", "example.svg")
    return svg or "example.mmd"


def main_json(
    payload: Mapping[str, object], *, ctx: object | None = None
) -> dict[str, object]:
    schema_failure = _validate_input_schema(payload)
    if schema_failure:
        return schema_failure

    parameters = _extract_parameters(payload)
    output_mermaid_result = _resolve_output_mermaid(parameters)
    if isinstance(output_mermaid_result, dict):
        return output_mermaid_result
    output_mermaid_path = output_mermaid_result

    export_svg, output_svg, mermaid_cli_path = _extract_export_options(parameters)

    try:
        builder_result = _prepare_mermaid_source(parameters, ctx=ctx)
        if isinstance(builder_result, dict):
            return builder_result
        builder, mermaid_source, summary_data = builder_result

        mermaid_source = _ensure_trailing_newline(mermaid_source)
        source_path_str, source_bytes = _write_mermaid_source(
            output_mermaid_path, mermaid_source
        )

        messages: list[str] = []
        mermaid_artifact: dict[str, object] = {
            "source_path": source_path_str,
            "source_bytes": source_bytes,
        }

        if export_svg or output_svg is not None:
            svg_payload, export_messages = _maybe_to_svg(
                mermaid_source,
                output_svg=output_svg,
                output_mermaid=output_mermaid_path,
                mermaid_cli_path=mermaid_cli_path,
                builder=builder,
            )
            messages.extend(export_messages)
            if svg_payload is not None:
                mermaid_artifact["svg"] = svg_payload

        summary = _compose_summary(
            summary_data,
            source_path=source_path_str,
            export_svg_flag=export_svg or bool(output_svg),
            output_svg=output_svg,
            mermaid_cli_path=mermaid_cli_path,
        )

        result = _compose_success_result(mermaid_artifact, messages, summary)
    except Exception as exc:  # noqa: BLE001 - capture unexpected runtime issues
        return _failure_payload(
            "unexpected error while generating Mermaid artifacts",
            details={"error": str(exc)},
        )

    output_failure = _validate_output_schema(result)
    if output_failure:
        return output_failure
    return result


def _load_json_payload(file_path: str | None) -> Mapping[str, object]:
    def _load(stream: IO[str]) -> Mapping[str, object]:
        raw_payload_obj = cast("object", json.load(stream))
        if not isinstance(raw_payload_obj, Mapping):
            message = "JSON payload must be a mapping"
            raise TypeError(message)
        raw_payload = cast("Mapping[object, object]", raw_payload_obj)
        payload_dict: dict[str, object] = {}
        for key, value in raw_payload.items():
            if not isinstance(key, str):
                message = "JSON payload keys must be strings"
                raise TypeError(message)
            payload_dict[key] = value
        return MappingProxyType(payload_dict)

    if file_path:
        with Path(file_path).open("r", encoding="utf-8") as handle:
            return _load(handle)
    return _load(_sys.stdin)


def _run_json_cli(args: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(description="x_make_mermaid_x JSON runner")
    parser.add_argument(
        "--json", action="store_true", help="Read JSON payload from stdin"
    )
    parser.add_argument("--json-file", type=str, help="Path to JSON payload file")
    parsed = parser.parse_args(args)

    json_flag_obj: object = cast("object", getattr(parsed, "json", False))
    read_from_stdin = bool(json_flag_obj)
    json_file_obj: object = cast("object", getattr(parsed, "json_file", None))
    json_file = json_file_obj if isinstance(json_file_obj, str) else None

    if not (read_from_stdin or json_file):
        parser.error("JSON input required. Use --json for stdin or --json-file <path>.")

    payload = _load_json_payload(None if read_from_stdin else json_file)
    result = main_json(payload)
    json.dump(result, _sys.stdout, indent=2)
    _sys.stdout.write("\n")


if __name__ == "__main__":
    _run_json_cli(_sys.argv[1:])


class MermaidMake(MermaidBuilder):
    """Backward-compatible alias for legacy consumers."""


x_cls_make_mermaid_x = MermaidMake


__all__ = ["MermaidBuilder", "MermaidMake", "main_json", "x_cls_make_mermaid_x"]

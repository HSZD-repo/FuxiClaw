"""Tool for drawing Kaplan-Meier survival curves from clinical tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SurvivalCurveToolInput(BaseModel):
    """Arguments for survival curve generation."""

    data_path: str = Field(description="Path to a CSV or TSV clinical table")
    time_column: str = Field(
        default="time",
        description="Column containing survival time values",
    )
    event_column: str = Field(
        default="event",
        description="Column indicating whether an event occurred (1/0, true/false, yes/no supported)",
    )
    group_column: str = Field(
        default="group",
        description="Column containing group labels used to stratify the survival curves",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_survival_curve.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")
    show_censor_marks: bool = Field(
        default=True,
        description="Whether to draw censor marks on the Kaplan-Meier curves",
    )


class SurvivalCurveTool(BaseTool):
    """Draw Kaplan-Meier survival curves from a clinical table."""

    name = "survival_curve"
    description = "Draw Kaplan-Meier survival curves from a CSV or TSV clinical table."
    input_model = SurvivalCurveToolInput

    async def execute(
        self,
        arguments: SurvivalCurveToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        data_path = _resolve_path(context.cwd, arguments.data_path)
        if not data_path.exists():
            return ToolResult(output=f"Data file not found: {data_path}", is_error=True)
        if data_path.is_dir():
            return ToolResult(output=f"Expected a file but got a directory: {data_path}", is_error=True)

        try:
            fieldnames, rows = _load_rows(data_path)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)

        missing_columns = [
            column
            for column in (
                arguments.time_column,
                arguments.event_column,
                arguments.group_column,
            )
            if column not in fieldnames
        ]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        grouped_records: dict[str, list[tuple[float, int]]] = {}
        group_order: list[str] = []
        skipped_rows = 0

        for row in rows:
            raw_group = str(row.get(arguments.group_column, "")).strip()
            if not raw_group:
                skipped_rows += 1
                continue

            try:
                time_value = float(str(row[arguments.time_column]).strip())
                event_value = _parse_event_value(row[arguments.event_column])
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            if not math.isfinite(time_value) or time_value < 0:
                skipped_rows += 1
                continue

            if raw_group not in grouped_records:
                grouped_records[raw_group] = []
                group_order.append(raw_group)
            grouped_records[raw_group].append((time_value, event_value))

        if not grouped_records:
            return ToolResult(
                output="No valid survival rows were found after parsing the requested columns.",
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output=(
                    "matplotlib is required for survival_curve. "
                    "Install it with: pip install matplotlib"
                ),
                is_error=True,
                metadata={"exception": str(exc)},
            )

        figure, axis = plt.subplots(figsize=(8.5, 6))
        palette = [
            "#2563EB",
            "#DC2626",
            "#059669",
            "#D97706",
            "#7C3AED",
            "#0891B2",
        ]

        group_sample_counts: dict[str, int] = {}
        group_event_counts: dict[str, int] = {}

        for index, group in enumerate(group_order):
            records = grouped_records[group]
            km_times, km_survival, censor_times, censor_survival = _kaplan_meier(records)
            color = palette[index % len(palette)]
            axis.step(
                km_times,
                km_survival,
                where="post",
                linewidth=2,
                color=color,
                label=group,
            )
            if arguments.show_censor_marks and censor_times:
                axis.scatter(
                    censor_times,
                    censor_survival,
                    marker="+",
                    s=28,
                    color=color,
                    linewidths=1.1,
                )
            group_sample_counts[group] = len(records)
            group_event_counts[group] = sum(event for _, event in records)

        axis.set_xlabel(arguments.time_column)
        axis.set_ylabel("Survival probability")
        axis.set_ylim(0.0, 1.05)
        axis.set_title(arguments.title or f"Kaplan-Meier survival curve: {data_path.stem}")
        axis.legend(frameon=False)
        axis.grid(axis="y", linestyle="--", alpha=0.35)

        figure.tight_layout()

        output_path = _resolve_output_path(
            base=context.cwd,
            input_path=data_path,
            candidate=arguments.output_path,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_path, dpi=200, bbox_inches="tight")
        plt.close(figure)

        return ToolResult(
            output=(
                f"Saved survival curve to {output_path}\n"
                f"Plotted {len(group_order)} groups from {sum(group_sample_counts.values())} valid samples "
                f"(skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "group_count": len(group_order),
                "group_order": group_order,
                "group_sample_counts": group_sample_counts,
                "group_event_counts": group_event_counts,
                "valid_rows": sum(group_sample_counts.values()),
                "skipped_rows": skipped_rows,
                "time_column": arguments.time_column,
                "event_column": arguments.event_column,
                "group_column": arguments.group_column,
            },
        )


def _kaplan_meier(records: list[tuple[float, int]]) -> tuple[list[float], list[float], list[float], list[float]]:
    ordered = sorted(records, key=lambda item: item[0])
    times = sorted({time for time, event in ordered if event == 1})

    km_times = [0.0]
    km_survival = [1.0]
    survival = 1.0

    for time in times:
        at_risk = sum(1 for candidate_time, _ in ordered if candidate_time >= time)
        events = sum(1 for candidate_time, event in ordered if candidate_time == time and event == 1)
        if at_risk == 0:
            continue
        survival *= 1.0 - (events / at_risk)
        km_times.append(time)
        km_survival.append(survival)

    censor_times: list[float] = []
    censor_survival: list[float] = []
    for time, event in ordered:
        if event != 0:
            continue
        censor_times.append(time)
        censor_survival.append(_survival_before_or_at(time, km_times, km_survival))

    return km_times, km_survival, censor_times, censor_survival


def _survival_before_or_at(time_value: float, km_times: list[float], km_survival: list[float]) -> float:
    survival = 1.0
    for km_time, km_value in zip(km_times, km_survival, strict=True):
        if km_time <= time_value:
            survival = km_value
        else:
            break
    return survival


def _parse_event_value(value) -> int:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "dead", "event"}:
        return 1
    if text in {"0", "false", "no", "n", "alive", "censored", "censor"}:
        return 0
    raise ValueError(f"Unsupported event value: {value}")


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(f"Unsupported file type for survival_curve: {path.suffix or '(no suffix)'}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        return reader.fieldnames, list(reader)


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_survival_curve.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

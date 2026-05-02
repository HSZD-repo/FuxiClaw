"""Tool for drawing forest plots from summary result tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ForestPlotToolInput(BaseModel):
    """Arguments for forest plot generation."""

    data_path: str = Field(description="Path to a CSV or TSV summary result table")
    label_column: str = Field(default="label", description="Column containing row labels")
    effect_column: str = Field(
        default="effect",
        description="Column containing the effect estimate, such as HR or OR",
    )
    lower_ci_column: str = Field(
        default="lower_ci",
        description="Column containing the lower confidence interval bound",
    )
    upper_ci_column: str = Field(
        default="upper_ci",
        description="Column containing the upper confidence interval bound",
    )
    pvalue_column: str | None = Field(
        default=None,
        description="Optional p-value column to annotate beside each row",
    )
    reference_line: float = Field(
        default=1.0,
        description="Reference line value, often 1.0 for HR/OR style forest plots",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_forest_plot.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")


class ForestPlotTool(BaseTool):
    """Draw a forest plot from a summary result table."""

    name = "forest_plot"
    description = "Draw a forest plot from a CSV or TSV summary result table."
    input_model = ForestPlotToolInput

    async def execute(
        self,
        arguments: ForestPlotToolInput,
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

        required_columns = [
            arguments.label_column,
            arguments.effect_column,
            arguments.lower_ci_column,
            arguments.upper_ci_column,
        ]
        if arguments.pvalue_column is not None:
            required_columns.append(arguments.pvalue_column)

        missing_columns = [column for column in required_columns if column not in fieldnames]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        parsed_rows: list[dict[str, float | str | None]] = []
        skipped_rows = 0
        for row in rows:
            label = str(row.get(arguments.label_column, "")).strip()
            if not label:
                skipped_rows += 1
                continue

            try:
                effect = float(str(row[arguments.effect_column]).strip())
                lower_ci = float(str(row[arguments.lower_ci_column]).strip())
                upper_ci = float(str(row[arguments.upper_ci_column]).strip())
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            if (
                not math.isfinite(effect)
                or not math.isfinite(lower_ci)
                or not math.isfinite(upper_ci)
                or lower_ci > effect
                or effect > upper_ci
            ):
                skipped_rows += 1
                continue

            pvalue_text = None
            if arguments.pvalue_column is not None:
                raw_pvalue = str(row.get(arguments.pvalue_column, "")).strip()
                if raw_pvalue:
                    pvalue_text = raw_pvalue

            parsed_rows.append(
                {
                    "label": label,
                    "effect": effect,
                    "lower_ci": lower_ci,
                    "upper_ci": upper_ci,
                    "pvalue_text": pvalue_text,
                }
            )

        if not parsed_rows:
            return ToolResult(
                output="No valid forest plot rows were found after parsing the requested columns.",
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output="matplotlib is required for forest_plot. Install it with: pip install matplotlib",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        display_rows = list(reversed(parsed_rows))
        y_positions = list(range(len(display_rows)))
        labels = [str(row["label"]) for row in display_rows]
        effects = [float(row["effect"]) for row in display_rows]
        lower_errors = [float(row["effect"]) - float(row["lower_ci"]) for row in display_rows]
        upper_errors = [float(row["upper_ci"]) - float(row["effect"]) for row in display_rows]

        figure_height = max(4.5, 0.5 * len(display_rows) + 1.8)
        figure, axis = plt.subplots(figsize=(9.5, figure_height))
        axis.errorbar(
            effects,
            y_positions,
            xerr=[lower_errors, upper_errors],
            fmt="o",
            color="#2563EB",
            ecolor="#6B7280",
            elinewidth=1.2,
            capsize=3,
            markersize=6,
        )
        axis.axvline(arguments.reference_line, color="#DC2626", linestyle="--", linewidth=1)
        axis.set_yticks(y_positions)
        axis.set_yticklabels(labels)
        axis.set_xlabel(arguments.effect_column)
        axis.set_ylabel(arguments.label_column)
        axis.set_title(arguments.title or f"Forest plot: {data_path.stem}")
        axis.grid(axis="x", linestyle="--", alpha=0.35)

        min_x = min(float(row["lower_ci"]) for row in display_rows)
        max_x = max(float(row["upper_ci"]) for row in display_rows)
        span = max(max_x - min_x, 0.1)
        axis.set_xlim(min_x - 0.15 * span, max_x + 0.35 * span)

        for effect, y_pos, row in zip(effects, y_positions, display_rows, strict=True):
            ci_text = f"{float(row['effect']):.2f} ({float(row['lower_ci']):.2f}, {float(row['upper_ci']):.2f})"
            if row["pvalue_text"]:
                ci_text += f"; p={row['pvalue_text']}"
            axis.text(
                max_x + 0.05 * span,
                y_pos,
                ci_text,
                va="center",
                fontsize=8,
            )

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
                f"Saved forest plot to {output_path}\n"
                f"Plotted {len(parsed_rows)} rows (skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "row_count": len(parsed_rows),
                "skipped_rows": skipped_rows,
                "label_column": arguments.label_column,
                "effect_column": arguments.effect_column,
                "lower_ci_column": arguments.lower_ci_column,
                "upper_ci_column": arguments.upper_ci_column,
                "pvalue_column": arguments.pvalue_column,
                "reference_line": arguments.reference_line,
            },
        )


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(f"Unsupported file type for forest_plot: {path.suffix or '(no suffix)'}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        return reader.fieldnames, list(reader)


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_forest_plot.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

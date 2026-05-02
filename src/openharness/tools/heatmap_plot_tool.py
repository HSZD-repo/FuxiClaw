"""Tool for drawing heatmaps from numeric matrix tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class HeatmapPlotToolInput(BaseModel):
    """Arguments for heatmap generation."""

    data_path: str = Field(
        description="Path to a CSV or TSV numeric matrix with one row label column and sample columns"
    )
    row_label_column: str = Field(
        default="gene",
        description="Column containing row labels such as gene symbols",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_heatmap.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")
    row_scale: bool = Field(
        default=True,
        description="Whether to z-score each row before plotting",
    )
    cmap: str = Field(
        default="RdBu_r",
        description="Matplotlib colormap name for the heatmap",
    )
    show_values: bool = Field(
        default=False,
        description="Whether to annotate each cell with its numeric value",
    )


class HeatmapPlotTool(BaseTool):
    """Draw a heatmap from a numeric matrix table."""

    name = "heatmap_plot"
    description = "Draw a heatmap from a CSV or TSV numeric matrix table."
    input_model = HeatmapPlotToolInput

    async def execute(
        self,
        arguments: HeatmapPlotToolInput,
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

        if arguments.row_label_column not in fieldnames:
            return ToolResult(
                output=f"Missing required column(s): {arguments.row_label_column}",
                is_error=True,
            )

        numeric_columns = [column for column in fieldnames if column != arguments.row_label_column]
        if not numeric_columns:
            return ToolResult(
                output="No numeric sample columns were found after excluding the row label column.",
                is_error=True,
            )

        parsed_rows: list[dict[str, object]] = []
        skipped_rows = 0
        for row in rows:
            label = str(row.get(arguments.row_label_column, "")).strip()
            if not label:
                skipped_rows += 1
                continue

            values: list[float] = []
            try:
                for column in numeric_columns:
                    value = float(str(row[column]).strip())
                    if not math.isfinite(value):
                        raise ValueError("non-finite value")
                    values.append(value)
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            parsed_rows.append({"label": label, "values": values})

        if not parsed_rows:
            return ToolResult(
                output="No valid numeric rows were found after parsing the matrix.",
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output="matplotlib is required for heatmap_plot. Install it with: pip install matplotlib",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            import pandas as pd
        except ImportError as exc:
            return ToolResult(
                output="pandas is required for heatmap_plot. Install it with: pip install pandas",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            import seaborn as sns
        except ImportError as exc:
            return ToolResult(
                output="seaborn is required for heatmap_plot. Install it with: pip install seaborn",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        matrix = pd.DataFrame(
            [row["values"] for row in parsed_rows],
            index=[str(row["label"]) for row in parsed_rows],
            columns=numeric_columns,
        )

        if arguments.row_scale:
            matrix = matrix.apply(_zscore_row, axis=1, result_type="broadcast")

        figure_width = max(7.0, 0.6 * len(numeric_columns) + 2.5)
        figure_height = max(5.0, 0.42 * len(parsed_rows) + 2.0)
        figure, axis = plt.subplots(figsize=(figure_width, figure_height))

        sns.heatmap(
            matrix,
            cmap=arguments.cmap,
            annot=arguments.show_values,
            fmt=".2f" if arguments.show_values else "",
            linewidths=0.4,
            linecolor="white",
            cbar_kws={"label": "Row-scaled expression" if arguments.row_scale else "Expression"},
            ax=axis,
        )

        axis.set_xlabel("Samples")
        axis.set_ylabel(arguments.row_label_column)
        axis.set_title(arguments.title or f"Heatmap: {data_path.stem}")

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
                f"Saved heatmap to {output_path}\n"
                f"Plotted {len(parsed_rows)} rows by {len(numeric_columns)} columns "
                f"(skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "row_count": len(parsed_rows),
                "column_count": len(numeric_columns),
                "skipped_rows": skipped_rows,
                "row_label_column": arguments.row_label_column,
                "numeric_columns": numeric_columns,
                "row_scale": arguments.row_scale,
                "cmap": arguments.cmap,
            },
        )


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(f"Unsupported file type for heatmap_plot: {path.suffix or '(no suffix)'}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        return reader.fieldnames, list(reader)


def _zscore_row(row):
    mean = row.mean()
    std = row.std(ddof=0)
    if std == 0 or not math.isfinite(float(std)):
        return row * 0
    return (row - mean) / std


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_heatmap.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

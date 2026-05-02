"""Tool for drawing volcano plots from differential analysis tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class VolcanoPlotToolInput(BaseModel):
    """Arguments for volcano plot generation."""

    data_path: str = Field(description="Path to a CSV or TSV table with differential analysis results")
    log2fc_column: str = Field(
        default="log2FC",
        description="Column containing log2 fold-change values",
    )
    significance_column: str = Field(
        default="padj",
        description="Column containing p-values or adjusted p-values; used as the y-axis significance",
    )
    label_column: str | None = Field(
        default=None,
        description="Optional column used to label top significant points, such as gene symbol",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_volcano.png next to the input file.",
    )
    fc_threshold: float = Field(
        default=1.0,
        ge=0.0,
        description="Absolute log2 fold-change threshold for highlighting significant points",
    )
    significance_threshold: float = Field(
        default=0.05,
        gt=0.0,
        description="Maximum p-value or adjusted p-value considered significant",
    )
    top_n_labels: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Number of top significant points to label when label_column is provided",
    )
    title: str | None = Field(
        default=None,
        description="Optional title to place above the volcano plot",
    )


class VolcanoPlotTool(BaseTool):
    """Draw a volcano plot from a differential analysis table."""

    name = "volcano_plot"
    description = "Draw a volcano plot from a CSV or TSV differential analysis result table."
    input_model = VolcanoPlotToolInput

    async def execute(
        self,
        arguments: VolcanoPlotToolInput,
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
                arguments.log2fc_column,
                arguments.significance_column,
                arguments.label_column,
            )
            if column is not None and column not in fieldnames
        ]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        points: list[dict[str, float | str | None]] = []
        skipped_rows = 0
        for row in rows:
            try:
                log2fc = float(str(row[arguments.log2fc_column]).strip())
                significance = float(str(row[arguments.significance_column]).strip())
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            if not math.isfinite(log2fc) or not math.isfinite(significance) or significance <= 0:
                skipped_rows += 1
                continue

            label = None
            if arguments.label_column is not None:
                raw_label = row.get(arguments.label_column)
                if raw_label is not None:
                    label = str(raw_label).strip() or None

            points.append(
                {
                    "log2fc": log2fc,
                    "significance": significance,
                    "neg_log10_significance": -math.log10(significance),
                    "label": label,
                }
            )

        if not points:
            return ToolResult(
                output="No valid rows were found after parsing the requested columns.",
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output=(
                    "matplotlib is required for volcano_plot. "
                    "Install it with: pip install matplotlib"
                ),
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            from adjustText import adjust_text
        except ImportError:
            adjust_text = None

        nonsignificant = [
            point
            for point in points
            if point["significance"] > arguments.significance_threshold
            or abs(float(point["log2fc"])) < arguments.fc_threshold
        ]
        upregulated = [
            point
            for point in points
            if point["significance"] <= arguments.significance_threshold
            and float(point["log2fc"]) >= arguments.fc_threshold
        ]
        downregulated = [
            point
            for point in points
            if point["significance"] <= arguments.significance_threshold
            and float(point["log2fc"]) <= -arguments.fc_threshold
        ]

        figure, axis = plt.subplots(figsize=(8, 6))
        if nonsignificant:
            axis.scatter(
                [float(point["log2fc"]) for point in nonsignificant],
                [float(point["neg_log10_significance"]) for point in nonsignificant],
                s=18,
                c="#B0B7C3",
                alpha=0.7,
                label="Not significant",
            )
        if downregulated:
            axis.scatter(
                [float(point["log2fc"]) for point in downregulated],
                [float(point["neg_log10_significance"]) for point in downregulated],
                s=20,
                c="#2563EB",
                alpha=0.8,
                label="Downregulated",
            )
        if upregulated:
            axis.scatter(
                [float(point["log2fc"]) for point in upregulated],
                [float(point["neg_log10_significance"]) for point in upregulated],
                s=20,
                c="#DC2626",
                alpha=0.8,
                label="Upregulated",
            )

        threshold_line = -math.log10(arguments.significance_threshold)
        axis.axvline(arguments.fc_threshold, color="#6B7280", linestyle="--", linewidth=1)
        axis.axvline(-arguments.fc_threshold, color="#6B7280", linestyle="--", linewidth=1)
        axis.axhline(threshold_line, color="#6B7280", linestyle="--", linewidth=1)
        axis.set_xlabel(f"log2 fold change ({arguments.log2fc_column})")
        axis.set_ylabel(f"-log10({arguments.significance_column})")
        axis.set_title(arguments.title or f"Volcano plot: {data_path.stem}")
        axis.legend(frameon=False)

        label_texts = []
        if arguments.label_column and arguments.top_n_labels > 0:
            sortable_points = [
                point
                for point in points
                if point["label"] is not None
                and point["significance"] <= arguments.significance_threshold
                and abs(float(point["log2fc"])) >= arguments.fc_threshold
            ]
            sortable_points.sort(
                key=lambda point: (
                    float(point["significance"]),
                    -abs(float(point["log2fc"])),
                )
            )
            for point in sortable_points[: arguments.top_n_labels]:
                label_texts.append(
                    axis.text(
                        float(point["log2fc"]),
                        float(point["neg_log10_significance"]),
                        str(point["label"]),
                        fontsize=8,
                    )
                )
            if label_texts and adjust_text is not None:
                adjust_text(label_texts, ax=axis)

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
                f"Saved volcano plot to {output_path}\n"
                f"Processed {len(points)} valid rows"
                f" ({len(upregulated)} upregulated, {len(downregulated)} downregulated, "
                f"{len(nonsignificant)} not significant; skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "valid_rows": len(points),
                "skipped_rows": skipped_rows,
                "upregulated_count": len(upregulated),
                "downregulated_count": len(downregulated),
                "nonsignificant_count": len(nonsignificant),
                "log2fc_column": arguments.log2fc_column,
                "significance_column": arguments.significance_column,
                "fc_threshold": arguments.fc_threshold,
                "significance_threshold": arguments.significance_threshold,
            },
        )


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(f"Unsupported file type for volcano_plot: {path.suffix or '(no suffix)'}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        rows = list(reader)
        return reader.fieldnames, rows


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_volcano.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

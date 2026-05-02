"""Tool for drawing PCA plots from sample-by-feature matrices."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class PcaPlotToolInput(BaseModel):
    """Arguments for PCA plot generation."""

    data_path: str = Field(
        description="Path to a CSV or TSV matrix where each row is a sample and each numeric column is a feature"
    )
    sample_id_column: str = Field(
        default="sample_id",
        description="Column containing sample identifiers",
    )
    color_by_column: str | None = Field(
        default=None,
        description="Optional metadata column used to color points by group",
    )
    exclude_columns: list[str] = Field(
        default_factory=list,
        description="Additional non-numeric columns to exclude from PCA features",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_pca_plot.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")
    scale_features: bool = Field(
        default=True,
        description="Whether to z-score each feature before PCA",
    )
    show_labels: bool = Field(
        default=True,
        description="Whether to label points with sample IDs",
    )


class PcaPlotTool(BaseTool):
    """Draw a PCA scatter plot from a sample-by-feature matrix."""

    name = "pca_plot"
    description = "Draw a PCA scatter plot from a CSV or TSV sample-by-feature matrix."
    input_model = PcaPlotToolInput

    async def execute(
        self,
        arguments: PcaPlotToolInput,
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

        required_columns = [arguments.sample_id_column]
        if arguments.color_by_column is not None:
            required_columns.append(arguments.color_by_column)

        missing_columns = [column for column in required_columns if column not in fieldnames]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        excluded = set(arguments.exclude_columns)
        excluded.add(arguments.sample_id_column)
        if arguments.color_by_column is not None:
            excluded.add(arguments.color_by_column)

        feature_columns = [column for column in fieldnames if column not in excluded]
        if len(feature_columns) < 2:
            return ToolResult(
                output="At least two numeric feature columns are required for PCA.",
                is_error=True,
            )

        parsed_rows: list[dict[str, object]] = []
        skipped_rows = 0
        group_order: list[str] = []
        for row in rows:
            sample_id = str(row.get(arguments.sample_id_column, "")).strip()
            if not sample_id:
                skipped_rows += 1
                continue

            group_value = None
            if arguments.color_by_column is not None:
                group_value = str(row.get(arguments.color_by_column, "")).strip() or None
                if group_value is not None and group_value not in group_order:
                    group_order.append(group_value)

            values: list[float] = []
            try:
                for column in feature_columns:
                    value = float(str(row[column]).strip())
                    if not math.isfinite(value):
                        raise ValueError("non-finite value")
                    values.append(value)
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            parsed_rows.append(
                {
                    "sample_id": sample_id,
                    "group": group_value,
                    "values": values,
                }
            )

        if len(parsed_rows) < 2:
            return ToolResult(
                output="At least two valid samples are required for PCA.",
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output="matplotlib is required for pca_plot. Install it with: pip install matplotlib",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            import numpy as np
        except ImportError as exc:
            return ToolResult(
                output="numpy is required for pca_plot. Install it with: pip install numpy",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        matrix = np.array([row["values"] for row in parsed_rows], dtype=float)
        matrix = matrix - matrix.mean(axis=0, keepdims=True)
        if arguments.scale_features:
            std = matrix.std(axis=0, ddof=0, keepdims=True)
            std[std == 0] = 1.0
            matrix = matrix / std

        u, singular_values, _vh = np.linalg.svd(matrix, full_matrices=False)
        coordinates = u[:, :2] * singular_values[:2]

        total_variance = (singular_values ** 2).sum()
        if total_variance > 0:
            explained = (singular_values ** 2) / total_variance
        else:
            explained = np.zeros_like(singular_values)

        figure, axis = plt.subplots(figsize=(8.5, 6.5))
        palette = [
            "#2563EB",
            "#DC2626",
            "#059669",
            "#D97706",
            "#7C3AED",
            "#0891B2",
        ]

        if arguments.color_by_column is not None:
            groups = [str(row["group"]) if row["group"] is not None else "(unlabeled)" for row in parsed_rows]
            display_groups = list(group_order)
            if any(group == "(unlabeled)" for group in groups) and "(unlabeled)" not in display_groups:
                display_groups.append("(unlabeled)")

            for index, group in enumerate(display_groups):
                x_values = [coordinates[i, 0] for i, item_group in enumerate(groups) if item_group == group]
                y_values = [coordinates[i, 1] for i, item_group in enumerate(groups) if item_group == group]
                if not x_values:
                    continue
                axis.scatter(
                    x_values,
                    y_values,
                    s=42,
                    alpha=0.9,
                    color=palette[index % len(palette)],
                    label=group,
                )
        else:
            axis.scatter(
                coordinates[:, 0],
                coordinates[:, 1],
                s=42,
                alpha=0.9,
                color="#2563EB",
            )

        if arguments.show_labels:
            for index, row in enumerate(parsed_rows):
                axis.text(
                    float(coordinates[index, 0]) + 0.02,
                    float(coordinates[index, 1]) + 0.02,
                    str(row["sample_id"]),
                    fontsize=8,
                )

        pc1_var = float(explained[0] * 100) if explained.size > 0 else 0.0
        pc2_var = float(explained[1] * 100) if explained.size > 1 else 0.0
        axis.set_xlabel(f"PC1 ({pc1_var:.1f}% variance)")
        axis.set_ylabel(f"PC2 ({pc2_var:.1f}% variance)")
        axis.set_title(arguments.title or f"PCA plot: {data_path.stem}")
        axis.grid(linestyle="--", alpha=0.35)
        if arguments.color_by_column is not None:
            axis.legend(frameon=False, title=arguments.color_by_column)

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
                f"Saved PCA plot to {output_path}\n"
                f"Plotted {len(parsed_rows)} samples using {len(feature_columns)} features "
                f"(skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "sample_count": len(parsed_rows),
                "feature_count": len(feature_columns),
                "skipped_rows": skipped_rows,
                "sample_id_column": arguments.sample_id_column,
                "color_by_column": arguments.color_by_column,
                "feature_columns": feature_columns,
                "scale_features": arguments.scale_features,
                "pc1_explained_variance_pct": pc1_var,
                "pc2_explained_variance_pct": pc2_var,
            },
        )


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(f"Unsupported file type for pca_plot: {path.suffix or '(no suffix)'}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        return reader.fieldnames, list(reader)


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_pca_plot.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

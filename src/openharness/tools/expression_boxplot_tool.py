"""Tool for drawing expression boxplots from tidy expression tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ExpressionBoxplotToolInput(BaseModel):
    """Arguments for expression boxplot generation."""

    data_path: str = Field(
        description="Path to a CSV or TSV tidy expression table containing gene, group, and expression columns"
    )
    gene: str = Field(description="Gene or feature to plot")
    gene_column: str = Field(default="gene", description="Column containing gene or feature identifiers")
    group_column: str = Field(default="group", description="Column containing sample grouping labels")
    expression_column: str = Field(
        default="expression",
        description="Column containing numeric expression values",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_<gene>_boxplot.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")
    show_points: bool = Field(
        default=True,
        description="Whether to overlay individual sample points on top of the boxplot",
    )


class ExpressionBoxplotTool(BaseTool):
    """Draw an expression boxplot for one gene or feature."""

    name = "expression_boxplot"
    description = "Draw a grouped expression boxplot for one gene from a CSV or TSV tidy table."
    input_model = ExpressionBoxplotToolInput

    async def execute(
        self,
        arguments: ExpressionBoxplotToolInput,
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
                arguments.gene_column,
                arguments.group_column,
                arguments.expression_column,
            )
            if column not in fieldnames
        ]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        selected_rows: list[dict[str, str | float]] = []
        skipped_rows = 0
        group_order: list[str] = []
        gene_normalized = arguments.gene.strip().lower()

        for row in rows:
            raw_gene = str(row.get(arguments.gene_column, "")).strip()
            if raw_gene.lower() != gene_normalized:
                continue

            raw_group = str(row.get(arguments.group_column, "")).strip()
            try:
                raw_expression = float(str(row[arguments.expression_column]).strip())
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            if not raw_group or not math.isfinite(raw_expression):
                skipped_rows += 1
                continue

            if raw_group not in group_order:
                group_order.append(raw_group)

            selected_rows.append(
                {
                    "gene": raw_gene,
                    "group": raw_group,
                    "expression": raw_expression,
                }
            )

        if not selected_rows:
            return ToolResult(
                output=f"No valid rows found for gene '{arguments.gene}'.",
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output=(
                    "matplotlib is required for expression_boxplot. "
                    "Install it with: pip install matplotlib"
                ),
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            import pandas as pd
        except ImportError as exc:
            return ToolResult(
                output="pandas is required for expression_boxplot. Install it with: pip install pandas",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            import seaborn as sns
        except ImportError as exc:
            return ToolResult(
                output=(
                    "seaborn is required for expression_boxplot. "
                    "Install it with: pip install seaborn"
                ),
                is_error=True,
                metadata={"exception": str(exc)},
            )

        plot_data = pd.DataFrame(selected_rows)

        figure, axis = plt.subplots(figsize=(8, 6))
        sns.boxplot(
            data=plot_data,
            x="group",
            y="expression",
            order=group_order,
            color="#93C5FD",
            linewidth=1.1,
            fliersize=0,
            ax=axis,
        )
        if arguments.show_points:
            sns.stripplot(
                data=plot_data,
                x="group",
                y="expression",
                order=group_order,
                color="#1F2937",
                alpha=0.65,
                size=4,
                jitter=0.22,
                ax=axis,
            )

        axis.set_xlabel(arguments.group_column)
        axis.set_ylabel(arguments.expression_column)
        axis.set_title(arguments.title or f"{arguments.gene.strip()} expression by {arguments.group_column}")

        figure.tight_layout()

        output_path = _resolve_output_path(
            base=context.cwd,
            input_path=data_path,
            gene=arguments.gene,
            candidate=arguments.output_path,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_path, dpi=200, bbox_inches="tight")
        plt.close(figure)

        sample_count = len(selected_rows)
        group_counts = {group: 0 for group in group_order}
        for row in selected_rows:
            group_counts[str(row["group"])] += 1

        return ToolResult(
            output=(
                f"Saved expression boxplot to {output_path}\n"
                f"Plotted gene {arguments.gene.strip()} across {len(group_order)} groups "
                f"with {sample_count} samples (skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "gene": arguments.gene.strip(),
                "sample_count": sample_count,
                "group_count": len(group_order),
                "group_order": group_order,
                "group_counts": group_counts,
                "skipped_rows": skipped_rows,
                "gene_column": arguments.gene_column,
                "group_column": arguments.group_column,
                "expression_column": arguments.expression_column,
            },
        )


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(
            f"Unsupported file type for expression_boxplot: {path.suffix or '(no suffix)'}"
        )

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        rows = list(reader)
        return reader.fieldnames, rows


def _resolve_output_path(base: Path, input_path: Path, gene: str, candidate: str | None) -> Path:
    if candidate is None:
        safe_gene = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in gene.strip())
        safe_gene = safe_gene or "gene"
        return input_path.with_name(f"{input_path.stem}_{safe_gene}_boxplot.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

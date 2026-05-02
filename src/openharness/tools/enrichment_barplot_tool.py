"""Tool for drawing enrichment barplots from enrichment result tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class EnrichmentBarplotToolInput(BaseModel):
    """Arguments for enrichment barplot generation."""

    data_path: str = Field(
        description="Path to a CSV or TSV enrichment result table"
    )
    term_column: str = Field(default="term", description="Column containing pathway or term names")
    significance_column: str = Field(
        default="fdr",
        description="Column containing FDR or adjusted p-values used for ranking and coloring",
    )
    count_column: str = Field(
        default="count",
        description="Column containing the number of genes or hits for each enriched term",
    )
    top_n: int = Field(default=10, ge=1, le=50, description="Number of top enriched terms to show")
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_enrichment_barplot.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")


class EnrichmentBarplotTool(BaseTool):
    """Draw a horizontal barplot for top enriched terms."""

    name = "enrichment_barplot"
    description = "Draw a horizontal barplot for the top enriched terms in a CSV or TSV result table."
    input_model = EnrichmentBarplotToolInput

    async def execute(
        self,
        arguments: EnrichmentBarplotToolInput,
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
                arguments.term_column,
                arguments.significance_column,
                arguments.count_column,
            )
            if column not in fieldnames
        ]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        parsed_rows: list[dict[str, float | str]] = []
        skipped_rows = 0
        for row in rows:
            term = str(row.get(arguments.term_column, "")).strip()
            try:
                significance = float(str(row[arguments.significance_column]).strip())
                count = float(str(row[arguments.count_column]).strip())
            except (TypeError, ValueError):
                skipped_rows += 1
                continue

            if not term or not math.isfinite(significance) or significance <= 0 or not math.isfinite(count):
                skipped_rows += 1
                continue

            parsed_rows.append(
                {
                    "term": term,
                    "significance": significance,
                    "count": count,
                    "neg_log10_significance": -math.log10(significance),
                }
            )

        if not parsed_rows:
            return ToolResult(
                output="No valid enrichment rows were found after parsing the requested columns.",
                is_error=True,
            )

        parsed_rows.sort(key=lambda row: (float(row["significance"]), -float(row["count"])))
        selected_rows = parsed_rows[: arguments.top_n]
        selected_rows.reverse()

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output=(
                    "matplotlib is required for enrichment_barplot. "
                    "Install it with: pip install matplotlib"
                ),
                is_error=True,
                metadata={"exception": str(exc)},
            )

        try:
            import pandas as pd
        except ImportError as exc:
            return ToolResult(
                output="pandas is required for enrichment_barplot. Install it with: pip install pandas",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        plot_data = pd.DataFrame(selected_rows)

        figure_height = max(4.5, 0.5 * len(selected_rows) + 1.5)
        figure, axis = plt.subplots(figsize=(9, figure_height))
        bars = axis.barh(
            plot_data["term"],
            plot_data["count"],
            color=plt.cm.viridis(plot_data["neg_log10_significance"] / plot_data["neg_log10_significance"].max()),
            edgecolor="#374151",
            linewidth=0.5,
        )

        for bar, neg_log10 in zip(bars, plot_data["neg_log10_significance"], strict=True):
            axis.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                f"-log10={neg_log10:.2f}",
                va="center",
                fontsize=8,
            )

        axis.set_xlabel(arguments.count_column)
        axis.set_ylabel(arguments.term_column)
        axis.set_title(arguments.title or f"Top {len(selected_rows)} enriched terms")

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
                f"Saved enrichment barplot to {output_path}\n"
                f"Plotted {len(selected_rows)} enriched terms from {len(parsed_rows)} valid rows "
                f"(skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "term_count": len(selected_rows),
                "valid_rows": len(parsed_rows),
                "skipped_rows": skipped_rows,
                "term_column": arguments.term_column,
                "significance_column": arguments.significance_column,
                "count_column": arguments.count_column,
                "top_n": arguments.top_n,
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
            f"Unsupported file type for enrichment_barplot: {path.suffix or '(no suffix)'}"
        )

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        rows = list(reader)
        return reader.fieldnames, rows


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_enrichment_barplot.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

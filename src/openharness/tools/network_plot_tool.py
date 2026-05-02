"""Tool for drawing network plots from edge list tables."""

from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult


class NetworkPlotToolInput(BaseModel):
    """Arguments for network plot generation."""

    data_path: str = Field(description="Path to a CSV or TSV edge list table")
    source_column: str = Field(default="source", description="Column containing source node IDs")
    target_column: str = Field(default="target", description="Column containing target node IDs")
    weight_column: str | None = Field(
        default=None,
        description="Optional column containing edge weights",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional output image path. Defaults to <input_stem>_network_plot.png.",
    )
    title: str | None = Field(default=None, description="Optional chart title")
    label_nodes: bool = Field(default=True, description="Whether to label nodes on the plot")
    min_edge_weight: float | None = Field(
        default=None,
        description="Optional minimum edge weight required to keep an edge",
    )
    max_nodes: int = Field(
        default=80,
        ge=2,
        le=500,
        description="Maximum number of unique nodes allowed in the rendered network",
    )


class NetworkPlotTool(BaseTool):
    """Draw a static network plot from an edge list."""

    name = "network_plot"
    description = "Draw a static network plot from a CSV or TSV edge list table."
    input_model = NetworkPlotToolInput

    async def execute(
        self,
        arguments: NetworkPlotToolInput,
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

        required_columns = [arguments.source_column, arguments.target_column]
        if arguments.weight_column is not None:
            required_columns.append(arguments.weight_column)

        missing_columns = [column for column in required_columns if column not in fieldnames]
        if missing_columns:
            return ToolResult(
                output=f"Missing required column(s): {', '.join(missing_columns)}",
                is_error=True,
            )

        edges: list[tuple[str, str, float]] = []
        skipped_rows = 0
        for row in rows:
            source = str(row.get(arguments.source_column, "")).strip()
            target = str(row.get(arguments.target_column, "")).strip()
            if not source or not target:
                skipped_rows += 1
                continue

            if arguments.weight_column is not None:
                try:
                    weight = float(str(row[arguments.weight_column]).strip())
                except (TypeError, ValueError):
                    skipped_rows += 1
                    continue
                if not math.isfinite(weight):
                    skipped_rows += 1
                    continue
            else:
                weight = 1.0

            if arguments.min_edge_weight is not None and weight < arguments.min_edge_weight:
                continue

            edges.append((source, target, weight))

        if not edges:
            return ToolResult(
                output="No valid network edges were found after parsing the requested columns.",
                is_error=True,
            )

        node_degree = Counter()
        for source, target, _weight in edges:
            node_degree[source] += 1
            node_degree[target] += 1

        nodes = sorted(node_degree, key=lambda node: (-node_degree[node], node))
        if len(nodes) > arguments.max_nodes:
            return ToolResult(
                output=(
                    f"Network has {len(nodes)} unique nodes, which exceeds max_nodes={arguments.max_nodes}. "
                    "Filter the edge list or raise max_nodes."
                ),
                is_error=True,
            )

        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ImportError as exc:
            return ToolResult(
                output="matplotlib is required for network_plot. Install it with: pip install matplotlib",
                is_error=True,
                metadata={"exception": str(exc)},
            )

        positions = _circular_layout(nodes)
        weights = [weight for _, _, weight in edges]
        weight_min = min(weights)
        weight_max = max(weights)
        weight_span = max(weight_max - weight_min, 1e-9)

        figure_size = max(7.5, min(11.0, 0.12 * len(nodes) + 7.5))
        figure, axis = plt.subplots(figsize=(figure_size, figure_size))

        for source, target, weight in edges:
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            normalized = (weight - weight_min) / weight_span if weight_max != weight_min else 1.0
            axis.plot(
                [x1, x2],
                [y1, y2],
                color="#9CA3AF",
                linewidth=0.8 + 2.0 * normalized,
                alpha=0.30 + 0.45 * normalized,
                zorder=1,
            )

        x_values = [positions[node][0] for node in nodes]
        y_values = [positions[node][1] for node in nodes]
        sizes = [90 + 30 * node_degree[node] for node in nodes]
        axis.scatter(
            x_values,
            y_values,
            s=sizes,
            color="#2563EB",
            edgecolors="white",
            linewidths=0.8,
            zorder=2,
        )

        if arguments.label_nodes:
            for node in nodes:
                x_value, y_value = positions[node]
                axis.text(
                    x_value * 1.08,
                    y_value * 1.08,
                    node,
                    fontsize=8,
                    ha="center",
                    va="center",
                    zorder=3,
                )

        axis.set_title(arguments.title or f"Network plot: {data_path.stem}")
        axis.set_aspect("equal")
        axis.axis("off")
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
                f"Saved network plot to {output_path}\n"
                f"Plotted {len(nodes)} nodes and {len(edges)} edges "
                f"(skipped {skipped_rows} invalid rows)."
            ),
            metadata={
                "output_path": str(output_path),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "skipped_rows": skipped_rows,
                "source_column": arguments.source_column,
                "target_column": arguments.target_column,
                "weight_column": arguments.weight_column,
                "min_edge_weight": arguments.min_edge_weight,
                "max_nodes": arguments.max_nodes,
            },
        )


def _circular_layout(nodes: list[str]) -> dict[str, tuple[float, float]]:
    if not nodes:
        return {}

    positions: dict[str, tuple[float, float]] = {}
    total = len(nodes)
    for index, node in enumerate(nodes):
        angle = (2 * math.pi * index) / total
        positions[node] = (math.cos(angle), math.sin(angle))
    return positions


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        delimiter = "\t"
    elif suffix == ".csv":
        delimiter = ","
    else:
        raise ValueError(f"Unsupported file type for network_plot: {path.suffix or '(no suffix)'}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Could not read header row from {path}")
        return reader.fieldnames, list(reader)


def _resolve_output_path(base: Path, input_path: Path, candidate: str | None) -> Path:
    if candidate is None:
        return input_path.with_name(f"{input_path.stem}_network_plot.png").resolve()

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

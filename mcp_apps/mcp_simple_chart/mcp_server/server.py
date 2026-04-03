"""
Visualization MCP App Server (Demo)

An MCP server that exposes chart-generating tools as MCP App tools — meaning
each tool declares ``_meta.ui.resourceUri`` so the Helix frontend can embed
the resulting chart in a sandboxed iframe rather than rendering raw JSON.

The viewer HTML is served as an MCP resource at:

    ui://charts/viewer.html

It renders a Vega-Lite chart from the ``structuredContent`` the tool returns,
via the MCP Apps AppBridge postMessage protocol.

Run:
    uv run python -m mcp_server.server
or via Docker (see docker-compose.yml in demo/mcp_apps/).
"""

import json
import logging
from typing import Any, Literal

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field
from starlette.requests import Request

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="Helix Viz Demo",
    host="0.0.0.0",
    port=3100,
)

# ---------------------------------------------------------------------------
# MCP App viewer HTML
# Served at: ui://charts/viewer.html
# The frontend embeds this in an iframe; the chart data arrives via postMessage
# from the MCP Apps AppBridge.
# ---------------------------------------------------------------------------

_VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Helix Chart Viewer</title>
  <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
  <style>
    body { margin: 0; background: transparent; font-family: sans-serif; }
    #chart { width: 100%; height: 100vh; display: flex; align-items: center; justify-content: center; }
    #error  { color: #c00; padding: 1rem; }
  </style>
</head>
<body>
  <div id="chart"></div>
  <div id="error"></div>
  <script>
    // MCP Apps AppBridge — receive toolResult from Helix host
    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (!msg || msg.type !== 'toolResult') return;

      const spec = msg.structuredContent;
      if (!spec) {
        document.getElementById('error').textContent = 'No chart spec received.';
        return;
      }

      vegaEmbed('#chart', spec, {actions: false, renderer: 'svg'}).catch((err) => {
        document.getElementById('error').textContent = 'Chart error: ' + err.message;
      });
    });

    // Signal readiness to the Helix host
    window.parent.postMessage({type: 'ready'}, '*');
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# MCP resource — the viewer HTML
# ---------------------------------------------------------------------------

@mcp.resource("ui://charts/viewer.html")
def chart_viewer() -> str:
    """The MCP App HTML viewer for charts. Helix fetches this and serves it in an iframe."""
    return _VIEWER_HTML


# ---------------------------------------------------------------------------
# MCP App tools
# ---------------------------------------------------------------------------

_MCP_APP_META = {
    "ui": {
        "resourceUri": "ui://charts/viewer.html",
    }
}


@mcp.tool(
    name="generate_bar_chart",
    description=(
        "Generate an interactive bar chart from a list of category/value pairs. "
        "Returns a Vega-Lite spec rendered in an embedded MCP App iframe."
    ),
)
def generate_bar_chart(
    title: str = Field(description="Chart title"),
    categories: list[str] = Field(description="Category labels (x-axis)"),
    values: list[float] = Field(description="Numeric values matching each category"),
    x_label: str = Field(default="Category", description="X-axis label"),
    y_label: str = Field(default="Value", description="Y-axis label"),
    ctx: Context[Any, Any, Request] = None,
) -> dict:
    """
    Returns a Vega-Lite bar chart spec as structuredContent.
    The MCP App viewer (ui://charts/viewer.html) renders it in the iframe.
    """
    if len(categories) != len(values):
        raise ValueError("'categories' and 'values' must have the same length")

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {
            "values": [{"category": c, "value": v} for c, v in zip(categories, values)]
        },
        "mark": "bar",
        "encoding": {
            "x": {"field": "category", "type": "nominal", "axis": {"title": x_label}},
            "y": {"field": "value", "type": "quantitative", "axis": {"title": y_label}},
            "color": {"field": "category", "type": "nominal", "legend": None},
            "tooltip": [
                {"field": "category", "type": "nominal"},
                {"field": "value", "type": "quantitative"},
            ],
        },
    }

    logger.info("generate_bar_chart called: title=%s, %d items", title, len(categories))
    return spec


generate_bar_chart.metadata = {"_meta": _MCP_APP_META}


@mcp.tool(
    name="generate_line_chart",
    description=(
        "Generate an interactive line chart from a series of x/y data points. "
        "Returns a Vega-Lite spec rendered in an embedded MCP App iframe."
    ),
)
def generate_line_chart(
    title: str = Field(description="Chart title"),
    x_values: list[str | float] = Field(description="X-axis values (time steps, labels, etc.)"),
    y_values: list[float] = Field(description="Y-axis values matching each x value"),
    x_label: str = Field(default="X", description="X-axis label"),
    y_label: str = Field(default="Y", description="Y-axis label"),
    ctx: Context[Any, Any, Request] = None,
) -> dict:
    """
    Returns a Vega-Lite line chart spec as structuredContent.
    """
    if len(x_values) != len(y_values):
        raise ValueError("'x_values' and 'y_values' must have the same length")

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {
            "values": [{"x": str(x), "y": y} for x, y in zip(x_values, y_values)]
        },
        "mark": {"type": "line", "point": True},
        "encoding": {
            "x": {"field": "x", "type": "ordinal", "axis": {"title": x_label}},
            "y": {"field": "y", "type": "quantitative", "axis": {"title": y_label}},
            "tooltip": [
                {"field": "x", "type": "ordinal"},
                {"field": "y", "type": "quantitative"},
            ],
        },
    }

    logger.info("generate_line_chart called: title=%s, %d points", title, len(x_values))
    return spec


generate_line_chart.metadata = {"_meta": _MCP_APP_META}


@mcp.tool(
    name="generate_pie_chart",
    description=(
        "Generate an interactive pie / donut chart from labeled slices. "
        "Returns a Vega-Lite spec rendered in an embedded MCP App iframe."
    ),
)
def generate_pie_chart(
    title: str = Field(description="Chart title"),
    labels: list[str] = Field(description="Slice labels"),
    values: list[float] = Field(description="Numeric values for each slice"),
    donut: bool = Field(default=False, description="Render as a donut chart"),
    ctx: Context[Any, Any, Request] = None,
) -> dict:
    """
    Returns a Vega-Lite arc / pie chart spec as structuredContent.
    """
    if len(labels) != len(values):
        raise ValueError("'labels' and 'values' must have the same length")

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {
            "values": [{"label": lbl, "value": v} for lbl, v in zip(labels, values)]
        },
        "mark": {"type": "arc", "innerRadius": 50 if donut else 0},
        "encoding": {
            "theta": {"field": "value", "type": "quantitative"},
            "color": {"field": "label", "type": "nominal"},
            "tooltip": [
                {"field": "label", "type": "nominal"},
                {"field": "value", "type": "quantitative"},
            ],
        },
    }

    logger.info("generate_pie_chart called: title=%s, %d slices", title, len(labels))
    return spec


generate_pie_chart.metadata = {"_meta": _MCP_APP_META}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")

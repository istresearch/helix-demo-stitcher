# Helix MCP Apps Demo

This directory demonstrates Helix's **MCP Apps** feature: MCP tools that
return interactive UI components rendered in sandboxed iframes inside the
chat conversation.

## What is an MCP App?

An MCP App is an MCP tool that declares `_meta.ui.resourceUri` in its tool
metadata.  When Helix calls such a tool it:

1. Caches the tool response (structured content + HTML viewer).
2. Emits an `mcp_app` SSE event so the frontend knows an iframe is ready.
3. Serves the HTML viewer via `GET /v1/chat/mcp-app-resource/{workflow}/{thread_id}/{tool_call_id}`.

The frontend embeds this URL in a sandboxed `<iframe>`.  The MCP Apps
**AppBridge** (`postMessage` protocol) then passes the tool's
`structuredContent` into the iframe so the viewer can render it
(e.g. draw a Vega-Lite chart).

## Demo topology

```
┌────────────┐    MCP      ┌────────────────────┐
│   Helix    │────────────▶│  mcp_simple_chart      │  port 3100
│ (chat svc) │             │  (chart tools)     │
└────────────┘             └────────────────────┘
       │                          │ registers
       │ discovers                ▼
       │                  ┌────────────────┐
       └─────────────────▶│  mcp-registry  │  port 9000
         (optional)       └────────────────┘
```

| Service        | Port | Description |
|----------------|------|-------------|
| `helix`        | 8000 | Core chat service |
| `mcp_simple_chart` | 3100 | MCP App server — bar, line, pie charts |
| `mcp-registry` | 9000 | MCP server registry (optional dynamic discovery) |

LLM requests are proxied through your external LiteLLM instance (configured in `.env`).

## Quick start

```bash
# 1. Configure your external LiteLLM credentials
cd demo/mcp_apps
cp .env.template .env   # then edit .env with your LiteLLM URL, key, and model

# 2. Start the demo stack
docker compose up -d
```

Send a chat request using the `mcp_agent` workflow:

```bash
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "mcp_agent",
    "thread_id": "demo-1",
    "messages": [{"role": "user", "content": "Show me a bar chart of monthly sales: Jan=120, Feb=95, Mar=140, Apr=160"}]
  }'
```

The SSE stream will include an `mcp_app` event carrying the iframe URL.

## MCP server connections: static vs. registry

The `mcp_agent` workflow supports two ways to wire MCP servers:

### Static (always on)

Declare servers directly in the workflow config under `mcp.connections`:

```hocon
mcp {
  enabled: true
  connections {
    "mcp_simple_chart": {
      transport: "streamable_http"
      url: "http://mcp_simple_chart:3100/mcp"
    }
  }
}
```

### Dynamic (via MCP Registry)

Enable the registry and Helix discovers servers at runtime:

```hocon
mcp {
  enabled: true
  connections {}   # static section can still coexist

  registry {
    enabled: true
    url: "http://mcp-registry:9000"
    tags_filter: ["visualization"]   # optional tag filter
  }
}
```

Enable the registry in Helix and external MCP servers self-register at startup
(see [Registering external MCP servers](#registering-external-mcp-servers) below).

Static connections always take precedence over registry entries with the same
name — explicit config wins.

## Registering external MCP servers

Any MCP server can register itself with the registry by POSTing to `POST /v1/servers`.
Re-registering with the same `name` performs an upsert — safe to call on every startup.

### Registration payload

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Logical identifier used as the connection key in Helix |
| `url` | string | yes | Full MCP endpoint URL (e.g. `http://my-server:3100/mcp`) |
| `transport` | string | no | Transport type — currently `streamable_http` (default) |
| `tags` | string[] | no | Arbitrary labels used for `tags_filter` in Helix config |
| `headers` | object | no | Static request headers forwarded on every tool call |

### curl

```bash
curl -X POST http://localhost:9000/v1/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_mcp_server",
    "url": "http://my-mcp-server:3200/mcp",
    "transport": "streamable_http",
    "tags": ["visualization", "charts"],
    "headers": {}
  }'
```

Response (201):
```json
{
  "id": "3f2a1b4c-...",
  "name": "my_mcp_server",
  "url": "http://my-mcp-server:3200/mcp",
  "transport": "streamable_http",
  "tags": ["visualization", "charts"],
  "headers": {}
}
```

Save the returned `id` if you need to unregister later (`DELETE /v1/servers/{id}`).

### Python (self-registration on startup)

Add a lifespan hook to your FastMCP / FastAPI server so it registers when it starts:

```python
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI  # or from fastmcp import FastMCP

REGISTRY_URL = "http://mcp-registry:9000"
MY_NAME      = "my_mcp_server"
MY_URL       = "http://my-mcp-server:3200/mcp"
MY_TAGS      = ["visualization"]

async def _register():
    payload = {"name": MY_NAME, "url": MY_URL, "tags": MY_TAGS}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{REGISTRY_URL}/v1/servers", json=payload)
        resp.raise_for_status()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _register()
    except Exception as exc:
        print(f"[warn] Could not register with MCP registry: {exc}")
    yield  # server runs here
```

If registration fails (e.g. registry not yet up), the server still starts normally.
Helix will simply not discover it via the registry; static connections are unaffected.

### Verifying registration

```bash
# List all registered servers
curl http://localhost:9000/v1/servers

# Filter by tag
curl "http://localhost:9000/v1/servers?tags=visualization"

# Health check (shows total count)
curl http://localhost:9000/healthz
```

## Building your own MCP App tool

1. Declare a resource at a `ui://` URI:

```python
@mcp.resource("ui://my-app/viewer.html")
def viewer() -> str:
    return "<html>...</html>"
```

2. Attach `_meta.ui.resourceUri` to your tool:

```python
@mcp.tool(name="my_tool", description="...")
def my_tool(...) -> dict:
    return {...}   # structuredContent

my_tool.metadata = {"_meta": {"ui": {"resourceUri": "ui://my-app/viewer.html"}}}
```

3. In the iframe viewer, listen for `toolResult` messages via the AppBridge:

```js
window.addEventListener('message', (e) => {
  if (e.data.type === 'toolResult') {
    const data = e.data.structuredContent;
    // render your UI with data
  }
});
window.parent.postMessage({type: 'ready'}, '*');
```

## Directory structure

```
demo/mcp_apps/
├── README.md               ← you are here
├── docker-compose.yml      ← full demo stack
├── .env.template           ← copy to .env and fill in LiteLLM credentials
├── config/
│   └── workflows/
│       └── mcp_agent.conf  ← demo workflow config (mcp_simple_chart wired)
├── mcp_simple_chart/           ← demo MCP App server (bar, line, pie charts)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── mcp_server/
│       └── server.py
└── mcp_query_duckdb/           ← demo DuckDB query server
    ├── Dockerfile
    ├── pyproject.toml
    └── mcp_server/
```

## Feature code (not demo)

The MCP Apps feature itself lives in the main codebase:

| Path | Description |
|------|-------------|
| `chat/chat_service/workflow/workflow.py` | `AgentWorkflow.get_mcp_app_resource()` protocol |
| `chat/chat_service/routes.py` | `GET /v1/chat/mcp-app-resource/…` endpoint |
| `chat/chat_service/models/events.py` | `McpAppEvent`, `McpAppCitationContent` |
| `chat_examples/workflow/langgraph/middleware/tools.py` | `ToolResponseCachingMiddleware` (MCP App detection + HTML fetch) |
| `chat_examples/workflow/langgraph/mcp/registry_client.py` | MCP Registry client |
| `chat_examples/workflow/langgraph/agent_utils.py` | `init_mcp_connections()` (static + registry merge) |
| `chat_examples/workflow/langgraph/workflows/mcp_agent/` | `McpAgent` workflow class + default config |
| `helix-mcp-registry` (separate repo) | MCP Registry service |

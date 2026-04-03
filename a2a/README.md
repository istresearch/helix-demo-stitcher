# Helix A2A Demo

Demonstrates two Helix instances collaborating over the [A2A protocol](https://google.github.io/A2A/). **Helix-A** has no domain-specific tools and delegates weather and currency queries to **Helix-B**, which coordinates two leaf agents.

```
User → Helix-A ──(A2A)──▶ Helix-B ──(A2A)──▶ weather-agent
                                     └──(A2A)──▶ currency-agent
         ▲                    │
         └────────────────────┘  (cycle prevention blocks this path)

           Both Helix instances self-register with the A2A Registry on startup.
           Helix-A discovers Helix-B by querying the registry (tag filter: "helix").
           Leaf agents are configured statically on Helix-B — they do not self-register.
```

## Services

| Service | Host port | Purpose |
|---|---|---|
| `helix-a` | 8000 | User-facing Helix. No domain tools; delegates via A2A. |
| `helix-b` | 8001 | Helix with weather + currency leaf agents. |
| `registry` | 8100 | A2A Registry — agent card discovery. |
| `weather-agent` | 10010 | Leaf agent: current weather (simulated). |
| `currency-agent` | 10000 | Leaf agent: currency exchange rates (simulated). |
| `langfuse-web` | 3000 | Observability UI. |

## Prerequisites

- Docker with Compose v2
- An OpenAI-compatible LLM endpoint (LiteLLM, AWS Bedrock, etc.)

## Setup

```bash
cd demo/a2a
cp .env.template .env
# Edit .env and set AGENT_MODEL, AGENT_MODEL_API_KEY, AGENT_MODEL_BASE_URL
```

`.env.template`:

```env
AGENT_MODEL=claude-sonnet-4-5-20250929
AGENT_MODEL_API_KEY=<your-api-key>
AGENT_MODEL_BASE_URL=https://litellm.dev.example.com
```

## Running

```bash
# Build images and start the full stack
docker compose up --build

# Or start only the core A2A components (skip Langfuse)
docker compose up --build registry helix-a helix-b weather-agent currency-agent
```

Both Helix instances will log `Registered with A2A registry` during startup. Confirm the registry has both instances:

```bash
curl http://localhost:8100/v1/agents | jq '.agents[].card.url'
```

## Trying it out

Send a chat completion request to Helix-A (port 8000):

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "helix",
    "workflow": "deep_a2a_agent",
    "stream": false,
    "messages": [{"role": "user", "content": "What is the weather in Tokyo and convert 100 USD to JPY?"}]
  }' | jq '.choices[0].message.content'
```

Helix-A will call `list_remote_agents`, discover Helix-B, delegate both subtasks, and synthesize the results.

## Observability

Langfuse traces all agent activity. Browse to [http://localhost:3000](http://localhost:3000) and log in with:

- Email: `admin@helix.local`
- Password: `password`

Each request produces a unified trace showing the full delegation chain.

---

## Architecture

### Agent cards and self-registration

Each Helix instance exposes an A2A server at `/a2a`. On FastAPI startup (lifespan), each instance POSTs its own agent card to the registry:

```
POST http://registry:8100/v1/agents
{
  "card": { "name": "Helix-A", "url": "http://helix-a:8000/a2a", "skills": [...] },
  "tags": ["helix"],
  "ttl_seconds": null
}
```

`A2A_PUBLIC_URL` must be set to a hostname routable by peer agents (e.g. `http://helix-a:8000/a2a`). If omitted, the bind address (`0.0.0.0`) is used and peers cannot connect.

### Discovery

At the start of each `deep_a2a_agent` workflow request, `RemoteAgentToolProvider` collects agent URLs from:

1. **Static list** — `remote_agents.static` in the workflow conf (always resolved first).
2. **Registry** — `GET /v1/agents?tags=helix&active_only=true` if `remote_agents.registry.enabled = true`.

The resolved agents are injected into the supervisor's tool set as `list_remote_agents` and `send_message_to_agent`.

### Workflow configuration per instance

Helix-A and Helix-B each mount their own workflow config via a Docker volume override, pointing at `config/helix-{a,b}/workflows/`. Both load `deep_a2a_agent.conf` with instance-specific settings:

| Setting | Helix-A | Helix-B |
|---|---|---|
| `remote_agents.static` | `[]` | `[weather-agent, currency-agent]` |
| `remote_agents.registry.enabled` | `true` | `false` |
| `remote_agents.registry.tags_filter` | `["helix"]` | — |

---

## Cycle prevention

Without safeguards, A→B→A delegation would loop infinitely. Four complementary layers prevent this:

### Layer 1 — Self-exclusion (structural)

`RemoteAgentToolProvider` always adds `A2A_PUBLIC_URL` to its excluded-URL set. An agent is never returned from discovery as a tool target for itself, regardless of what the registry contains.

### Layer 2 — Call chain propagation (structural)

Every outbound A2A message carries an `x-helix-call-chain` metadata header containing all agent URLs already in the request path:

```
x-helix-call-chain: http://helix-a:8000/a2a,http://helix-b:8000/a2a
```

When a Helix instance receives an A2A request:
1. `HelixWorkflowExecutor` reads `x-helix-call-chain` from the message metadata and stores it in `SessionContext.A2A_CALL_CHAIN`.
2. `DeepA2AAgent` reads the chain from the session and passes it as `upstream_urls` to `RemoteAgentToolProvider`.
3. `RemoteAgentToolProvider` merges `upstream_urls` with its own URL into `excluded_urls` and filters both static and registry results against that set.
4. Before sending, `send_message_to_agent` appends the full `excluded_urls` set to the outbound `x-helix-call-chain` header.

This means every agent in the chain is permanently excluded from delegation targets for the lifetime of that request, regardless of depth.

### Layer 3 — Prompt instruction

Both Helix-A and Helix-B system prompts include:

> Never delegate a task back to an agent that originally sent you this request.

This gives the LLM an explicit rule to follow even in edge cases the structural layers don't cover.

### Layer 4 — LLM reasoning (backstop)

Well-instructed models will naturally avoid nonsensical circular delegation. This is the weakest layer but acts as a backstop for unexpected configurations or prompt injection attempts.

Together, Layers 1 and 2 make cycles **structurally impossible** for correctly configured deployments, regardless of LLM behavior.

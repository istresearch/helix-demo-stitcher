# Helix Demo Stitcher

Standalone orchestration repo for Helix demos. External repos (including the
Helix source on branch `demo_mcp_apps_a2a`) are fetched automatically at
startup. Runtime demo configuration is owned locally by this repo. One-command
startup is the primary path.

> **Required Secrets** — The RAG Knowledge Base services depend on an internal
> IST Python package (`pyst-utils`) hosted on a private PyPI registry. Before
> building, set `REPO_UN` and `REPO_PW` in [`a2a/.env`](a2a/.env) with valid
> credentials for `repo.istresearch.com`. Contact **Don Krapohl** or
> **Andrew Philpot** to obtain these credentials.

## Directory Structure

```
helix-demo-stitcher/
├── helix/              ← Local runtime config (application.conf, workflows/, prompts/)
├── a2a/                ← A2A demo (Helix-A, Helix-B, leaf agents, Langfuse)
├── mcp_apps/           ← MCP tool servers (charts, DuckDB)
├── mcp_registry/       ← MCP server registry
├── agent_registry/     ← A2A agent registry
├── rag_kb/             ← RAG Knowledge Base services
├── external/           ← Cloned automatically by startup_demo.sh
│   ├── helix/          ← Helix source (build context for Docker images)
│   ├── helix-ui/       ← Web UI
│   ├── helix-map/      ← Geospatial visualization
│   ├── helix-mcp-demo/ ← MCP protocol demos
│   └── ...
├── startup_demo.sh     ← One-command startup
├── shutdown_demo.sh    ← Teardown
└── docker-compose.yml  ← Unified composition (includes all sub-composes)
```

---

## Quick Requirements Checklist

Before running the demo, ensure you have all of the following:

- **Docker & Docker Compose** installed and logged in (`docker login`)
- **Git** installed and authenticated with GitHub (see [Git Authentication Setup](#git-authentication-setup))
- **`.env` file** in `a2a/` with `AGENT_MODEL_API_KEY` and `AGENT_MODEL_BASE_URL`
- **`REPO_UN` and `REPO_PW`** set in `a2a/.env` for the IST private PyPI registry (contact Don Krapohl or Andrew Philpot)
- **DuckDB database** — Auto-generated during startup from datasets
- **OpenAI-compatible LLM endpoint** configured (e.g., LiteLLM with valid API key)
- **Command-line tools** available: `git`, `docker`, `nc` (netcat)
- **GNU coreutils** installed (macOS/Linux)

---


## Prerequisites

- Docker Compose v2
- An OpenAI-compatible LLM endpoint (e.g., LiteLLM) with a valid API key
- `git`, `docker`, and `nc` (netcat) commands available in your shell
- For macOS/Linux: GNU coreutils
- **Git authentication configured** — Required to clone external GitHub projects

### Git Authentication Setup

The startup script clones external projects from GitHub (istresearch organization). You must configure Git authentication before running the script:

#### Option 1: GitHub CLI (Recommended)

```bash
# Install GitHub CLI if not already installed
# macOS: brew install gh
# Linux: sudo apt-get install gh (or other package manager)
# Windows: choco install gh

# Authenticate with GitHub
gh auth login

# Choose:
# - What is your preferred protocol for Git operations? → HTTPS
# - Authenticate with your GitHub credentials? → Yes
# - How would you like to authenticate GitHub CLI? → Login with a web browser
```

This is the easiest method and works seamlessly with the script.

#### Option 2: Personal Access Token (PAT) via HTTPS

1. Create a Personal Access Token on GitHub:
   - Go to https://github.com/settings/tokens/new
   - Select `repo` scope
   - Copy the token

2. Store the token securely:
   ```bash
   # macOS/Linux: Store in ~/.netrc
   cat >> ~/.netrc << EOF
   machine github.com
   login YOUR_GITHUB_USERNAME
   password YOUR_PERSONAL_ACCESS_TOKEN
   EOF
   chmod 600 ~/.netrc
   ```

   Or use Git credential store:
   ```bash
   git config --global credential.helper store
   git clone https://github.com/istresearch/helix-mcp-demo.git
   # When prompted, use your GitHub username and personal access token as password
   ```

#### Option 3: SSH Keys

1. Generate SSH key if you don't have one:
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

2. Add key to SSH agent:
   ```bash
   ssh-add ~/.ssh/id_ed25519
   ```

3. Add public key to GitHub:
   - Go to https://github.com/settings/keys
   - Click "New SSH key"
   - Paste your public key (from `~/.ssh/id_ed25519.pub`)

**Note:** The startup script uses HTTPS by default. For SSH, configure Git:
```bash
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

#### Verify Git Authentication

Test your Git authentication:
```bash
git clone https://github.com/istresearch/helix-mcp-demo.git /tmp/test-auth
# If successful, you're ready to run the startup script
rm -rf /tmp/test-auth
```

---

## Quick Start — Automated (Recommended)

The fastest way to get the entire demo running is to use the automated startup script:

```bash
chmod +x startup_demo.sh
./startup_demo.sh
```

The `startup_demo.sh` script automates all the following steps:

1. **Fetches** all three external GitHub projects from istresearch
2. **Builds** all Docker images (internal and external)
3. **Starts** all services (Helix A2A stack, MCP Apps, and external projects)
4. **Health checks** all services to ensure they're running correctly
5. **Displays** a summary of all available endpoints
6. **Opens** the dashboard in your default browser

The script includes:
- Automatic prerequisite checks (Docker, Docker Compose, Git)
- Colored status output showing progress
- Health checks for all 11 services
- Automatic browser opening of the dashboard
- Clear error messages if any step fails

**Expected completion time:** 3-5 minutes (depending on internet speed and system resources)

---

## Building Docker Images

Each demo subdirectory contains its own `Dockerfile` and `docker-compose.yml`. Additionally, this demo integrates three external GitHub projects from [istresearch](https://github.com/istresearch):
- **helix-mcp-demo** — MCP server showcase with multiple MCP tools and web interfaces
- **helix-map** — Map visualization service for geographic data
- **helix-ui** — Interactive user interface with chat and visualization integration

### ⚠️ Important: Images Must Be Built Locally

**No pre-built images are published to registries.** All Docker images must be compiled locally to:
- Match your environment configuration
- Ensure compatibility with locally modified code
- Guarantee proper dependency resolution

**Expected build time:** 5-10 minutes (first build), 1-3 minutes (subsequent builds with cached layers)

### Prerequisites: Fetch External Projects

The external GitHub projects must be cloned into `external/` before building:

```bash
cd external

# Clone all three external projects
git clone https://github.com/istresearch/helix-mcp-demo.git
git clone https://github.com/istresearch/helix-map.git
git clone https://github.com/istresearch/helix-ui.git

cd ..
```

### Quick Build: All Images at Once (Recommended)

For building all images in the correct dependency order:

```bash

# Build internal services (A2A, MCP Apps, Helix)
# ⏱️  Estimated time: 3-5 minutes
docker compose build

# Build external services (helix-mcp-demo, helix-map, helix-ui)
# ⏱️  Estimated time: 3-5 minutes (helix-mcp-demo takes longest)
docker compose --profile external build
```

Or, build everything in a single command:

```bash
# ⏱️  Total estimated time: 5-10 minutes
docker compose --profile external build
```

**Order of builds** (automatically managed by `docker compose`):
1. `local/helix:latest` — Helix core service (base for Helix-A and Helix-B)
2. `local/helix-examples:latest` — Example workflows
3. `demo-a2a-agent:latest` — Weather and currency agents
4. `demo-mcp-registry:latest` — MCP server registry
5. `demo-mcp_simple_chart:latest` — Chart tool MCP server
6. `demo-mcp_query_duckdb:latest` — DuckDB query MCP server
7. `helix-mcp-demo:latest` — External GitHub project (complex, multi-stage build)
8. `helix-map:latest` — External GitHub project
9. `helix-ui:local` — External GitHub project

### Build Images Individually

If you need to rebuild specific services without rebuilding everything, use individual commands below:

#### 1. Build the shared Helix image

Required by all demos. Builds the core Helix chat service with FastAPI backend.

```bash
cd helix
# ⏱️  Estimated time: 2-3 minutes
docker compose build
```

This produces:
- `local/helix:latest` — Helix core service (runs FastAPI on port 8000)
- `local/helix-examples:latest` — Example workflows and agents

**What it includes:**
- Python FastAPI server with OpenAI-compatible `/v1/chat/completions` endpoint
- LangGraph workflow engine
- Chat history persistence with PostgreSQL
- Artifact storage (artifacts, citations, prompts)
- A2A protocol support
- HOCON workflow configuration

#### 2. Build A2A demo images

Required if running the A2A (Agent-to-Agent) demo. Includes specialized agents for weather and currency.

```bash
cd a2a
# ⏱️  Estimated time: 2-3 minutes
docker compose build
```

This produces:
- `local/helix:latest` — Helix-A and Helix-B instances (reuses base image from Step 1)
- `local/helix-examples:latest` — A2A workflow examples
- `demo-a2a-agent:latest` — Shared agent base image
- `demo-weather-agent:latest` — Weather forecasting leaf agent (port 10010)
- `demo-currency-agent:latest` — Currency exchange leaf agent (port 10000)

**What it includes:**
- Helix-A: User-facing supervisor agent with A2A delegation
- Helix-B: Backend Helix with weather/currency tool integrations
- Weather & Currency agents: Specialist leaf agents responding to tool calls
- A2A Registry: Agent discovery service (port 8100)
- Langfuse: Observability and tracing (port 3000)

#### 3. Build MCP Apps demo images

Required if running the MCP Apps (interactive chart tools) demo.

```bash
cd mcp_apps
# ⏱️  Estimated time: 1-2 minutes
docker compose build
```

This produces:
- `demo-mcp-registry:latest` — MCP server registry for dynamic discovery (port 9000)
- `demo-mcp_simple_chart:latest` — Chart visualization MCP App server (port 3131)
  - Supports bar charts, line charts, pie charts
  - Integrates with Helix workflows
- `demo-mcp_query_duckdb:latest` — DuckDB query MCP App server (port 3099)
  - SQL query interface
  - Requires `demo.duckdb` database file

**What it includes:**
- MCP protocol implementation for tool discovery
- Tool registration with type-safe parameter schemas
- Resource management for data persistence
- Health checks for service availability

#### 4. Build external GitHub project: helix-mcp-demo

Demonstrates advanced MCP server integration with multiple example servers.

```bash
cd external/helix-mcp-demo
# ⏱️  Estimated time: 3-5 minutes (longest build due to multi-stage compilation)
docker build -t helix-mcp-demo .
cd ../../..
```

This produces:
- `helix-mcp-demo:latest` — Comprehensive MCP demo server showcasing various implementations

**Ports exposed:**
| Port Range | Purpose |
|---|---|
| 3100-3130 | MCP example servers and tools (31 different servers) |
| 3150 | Additional service endpoints |
| 4325 | Aggregator server (default PORT) |
| 8080-8081 | Web interfaces and viewers |

**What it includes:**
- TypeScript/JavaScript MCP server examples
- Python server implementations (QR code generator, etc.)
- Interactive web viewers for MCP tools
- Database query tools
- File manipulation tools
- Multiple protocol implementations

**Build details:**
- Uses multi-stage Docker build with Bun runtime
- Compiles TypeScript and JavaScript servers
- Installs Python virtual environment for Python servers
- Handles build failures gracefully (some example servers may have optional dependencies)

#### 5. Build external GitHub project: helix-map

Map visualization and geographic data service.

```bash
cd external/helix-map
# ⏱️  Estimated time: 1-2 minutes
docker build -t helix-map .
cd ../../..
```

This produces:
- `helix-map:latest` — Map service with geographic visualization

**Ports exposed:**
| Port | Purpose |
|---|---|
| 3132 | Map visualization API and UI |

**What it includes:**
- Node.js/Express backend for map data
- MapBox or similar visualization library
- Geographic data processing
- REST API for map queries

#### 6. Build external GitHub project: helix-ui

Interactive user interface with chat integration and workflow support.

```bash
cd external/helix-ui
# ⏱️  Estimated time: 2-3 minutes
docker build -t helix-ui:local -f Dockerfile .
cd ../../..
```

This produces:
- `helix-ui:local` — Interactive UI service

**Ports exposed:**
| Port | Purpose |
|---|---|
| 5000 | UI frontend with chat interface |

**Configuration:**
- Built with `WORKFLOW=deep_wired` by default
- Supports real-time chat streaming
- Integrates with Helix backend services
- Interactive visualization of agent responses

**What it includes:**
- React/Vue frontend (Node.js-based)
- WebSocket support for real-time updates
- Chat interface with message history
- Visualization components for agent responses

---

---

## Unified Docker Compose Stack (`docker-compose.yml`)

The `docker-compose.yml` file orchestrates all services using composition includes. This structure allows for modular management of different service groups while enabling a unified full-stack deployment.

### Composition Structure

The root `docker-compose.yml` uses `include` directives to import service definitions from subdirectories:

```yaml
include:
  - path: ./a2a/docker-compose.yml      # A2A agents, Helix instances, registry
  - path: ./mcp_apps/docker-compose.yml # MCP servers and registries
```

This approach provides:
- **Modularity** — Each service group is independently configurable
- **Reusability** — Subdirectories can be started in isolation
- **Profiles** — Services can be selectively enabled/disabled
- **Networking** — Shared Docker networks for service communication

### Service Groups

#### Internal Services (Always Included)

These services are started by default and form the core infrastructure:

| Service | Port | Purpose | Image |
|---------|------|---------|-------|
| helix-a | 8000 | User-facing Helix (A2A demo) | `local/helix-examples:latest` |
| helix-b | 8001 | Backend Helix (A2A delegation) | `local/helix-examples:latest` |
| registry | 8100 | A2A agent discovery | `demo-registry:latest` |
| weather-agent | 10010 | Weather specialist agent | `demo-weather-agent:latest` |
| currency-agent | 10000 | Currency exchange agent | `demo-currency-agent:latest` |
| mcp-registry | 9000 | MCP server discovery | `demo-mcp-registry:latest` |
| mcp_simple_chart | 3131 | Chart visualization tools | `demo-mcp_simple_chart:latest` |
| mcp_query_duckdb | 3099 | SQL query interface | `demo-mcp_query_duckdb:latest` |
| langfuse-web | 3000 | Observability/tracing UI | `langfuse/langfuse:3` |
| langfuse-worker | 3030 | Langfuse background worker | `langfuse/langfuse-worker:3` |
| postgres | 5432 | PostgreSQL database | `postgres:17` |
| redis | 6379 | Redis cache | `redis:7` |
| minio | 9090, 9091 | S3-compatible object storage | `chainguard/minio` |
| clickhouse | 8123 | ClickHouse analytics DB | `clickhouse/clickhouse-server` |

#### External Services (Profile: `external`)

These services are from external GitHub projects and are only started when explicitly requested:

```bash
# Start only internal services (default)
docker compose up -d

# Start internal + external services
docker compose --profile external up -d
```

| Service | Port | Purpose | Image |
|---------|------|---------|-------|
| helix-mcp-demo | 3100-3130, 3150, 4325, 8080-8081 | Multi-MCP server showcase | `helix-mcp-demo:latest` |
| helix-map | 3132 | Geographic visualization | `helix-map:latest` |
| helix-ui | 5000 | Chat UI with integrations | `helix-ui:local` |

### Network Topology

All services communicate via a shared Docker network (`helix-demo_default`):

```
┌─────────────────────────────────────────────────────┐
│         Docker Network: helix-demo_default          │
│                                                     │
│  ┌──────────────┐    ┌──────────────┐              │
│  │  Helix-A     │    │  Helix-B     │              │
│  │  (8000)      │◄──►│  (8001)      │              │
│  └──────────────┘    └──────────────┘              │
│         │                   │                       │
│         └───────────┬───────┘                       │
│                     │                               │
│         ┌───────────▼───────────┐                   │
│         │  A2A Registry (8100)  │                   │
│         └───────────────────────┘                   │
│                     │                               │
│     ┌───────────────┼───────────────┐               │
│     │               │               │               │
│  ┌──▼──────┐   ┌────▼─────┐   ┌───▼────┐           │
│  │Weather  │   │Currency  │   │Langfuse│           │
│  │Agent    │   │Agent     │   │(3000)  │           │
│  │(10010)  │   │(10000)   │   └────────┘           │
│  └─────────┘   └──────────┘                        │
│                                                     │
│  ┌──────────────┬──────────────┬──────────────┐    │
│  │ MCP Registry │ MCP Chart    │ MCP DuckDB   │    │
│  │ (9000)       │ (3131)       │ (3099)       │    │
│  └──────────────┴──────────────┴──────────────┘    │
│                                                     │
│  [External Services - with --profile external]     │
│  ┌──────────────┬──────────────┬──────────────┐    │
│  │ helix-mcp    │ helix-map    │ helix-ui     │    │
│  │ demo         │ (3132)       │ (5000)       │    │
│  │ (8080-8081)  │              │              │    │
│  └──────────────┴──────────────┴──────────────┘    │
│                                                     │
│  Supporting Services (Internal)                    │
│  ┌──────────────┬──────────────┬──────────────┐    │
│  │ PostgreSQL   │ Redis        │ MinIO        │    │
│  │ (5432)       │ (6379)       │ (9090)       │    │
│  └──────────────┴──────────────┴──────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Configuration Management

Each service group can have its own `.env` file for configuration:

- **`a2a/.env`** — LLM credentials, A2A registry settings, Langfuse configuration
- **`mcp_apps/.env`** (if needed) — MCP-specific settings
- **`external/.env`** (if needed) — External project settings

### Viewing Composition

To see all composed services:

```bash
docker compose --profile external config  # View merged compose configuration
docker compose ps                         # List running services
docker compose logs -f service_name       # View logs for a service
```

---

## Demo Data

The demo includes synthetic telecommunications data generated on startup for use with the MCP DuckDB query service.

### Available Datasets

Four regional datasets are available, each with synthetic CDR (Call Detail Records), MAID (Mobile Advertising IDs), and correlation data:

| Dataset | Region | Countries | Records | Use Case |
|---------|--------|-----------|---------|----------|
| **hormuz** (default) | Middle East / Persian Gulf | Iran, UAE, Oman | 300 CDR, 450-600 MAID | Strait of Hormuz telecom analysis |
| **caribbean** | Caribbean Sea | Cuba, Jamaica, Haiti, Dominican Republic, Puerto Rico | 500 CDR, 750-1000 MAID | Maritime communications |
| **ukraine** | Eastern Europe | Ukraine | 100 CDR, 150-300 MAID | Regional telecom analysis |
| **south_china_sea** | Southeast Asia | Vietnam, Philippines, Thailand, Singapore, Malaysia | 500 CDR, 750-1000 MAID | Regional maritime telecom |

### Switching Datasets

#### Option 1: Via `.env` File (RECOMMENDED)

Edit `a2a/.env` to set the dataset:

```bash
# Add this line to a2a/.env
DEMO_DATASET=caribbean
```

Then run the startup script normally:

```bash
./startup_demo.sh
```

#### Option 2: Via Environment Variable

Set `DEMO_DATASET` before running the startup script:

```bash
# Use Hormuz dataset (default)
./startup_demo.sh

# Use Caribbean dataset
DEMO_DATASET=caribbean ./startup_demo.sh

# Use Ukraine dataset
DEMO_DATASET=ukraine ./startup_demo.sh

# Use South China Sea dataset
DEMO_DATASET=south_china_sea ./startup_demo.sh
```

### Data Generation

Data is **automatically generated on first startup** if it doesn't already exist:

1. `startup_demo.sh` calls `build_demo_datasets()` function
2. Checks for existing database file in `mcp_apps/mcp_query_duckdb/data/databases/`
3. If not found:
   - Runs the data generator for the selected dataset
   - Generates 3 CSV files (CDR, MAID, connections)
   - Imports them into a DuckDB database
   - Saves to `mcp_apps/mcp_query_duckdb/data/databases/{dataset}.duckdb`

Subsequent startups reuse the cached database (instant load).

### Regenerating Data

To rebuild a dataset from scratch:

```bash
# Rebuild with defaults (hormuz)
REBUILD_DATA=true ./startup_demo.sh

# Rebuild specific dataset
REBUILD_DATA=true DEMO_DATASET=caribbean ./startup_demo.sh
```

### Manual Data Generation

To generate data without running the full startup:

```bash
# Generate default Hormuz dataset
cd assets/datasets/hormuz
python gen_hormuz_data.py --count 100 --seed 42 --db ../../databases/hormuz.duckdb

# Generate Caribbean dataset
cd assets/datasets/caribbean
python gen_caribbean_data.py --count 150 --seed 99 --db ../../databases/caribbean.duckdb

# Generate with custom parameters
python gen_south_china_sea_data.py --countries Vietnam Philippines --count 200 \
  --db ../../databases/south_china_sea.duckdb
```

### Data Specifications

Each dataset includes three tables:

#### 1. CDR (Call Detail Records)

Telecommunications events with location and network information:

```sql
SELECT * FROM cdr LIMIT 5;
-- Fields: callingNumber, calledNumber, IMSI, eventTime, recordType
--         LAT, LON, CGI, MCC, MNC, LAC, CID
```

#### 2. MAID (Mobile Advertising IDs)

Device location pings with device and signal information:

```sql
SELECT * FROM maid LIMIT 5;
-- Fields: ID, ID_TYPE, TIMESTAMP, LATITUDE, LONGITUDE
--         DEVICE_MAKE, DEVICE_MODEL, DEVICE_OS, DERIVED_COUNTRY
--         RSRP, DBM, RSRQ, CONNECTION_METHOD, etc.
```

#### 3. Connections with Confidence

Links between MAID and CDR records with confidence scores:

```sql
SELECT * FROM connections_with_confidence LIMIT 5;
-- Fields: maid_id, phone_number, distance (meters)
--         maid_timestamp, cdr_timestamp, confidence (high/medium/low)
```

### Example Queries

#### Query all CDR records from a specific country

```bash
curl -s http://localhost:3099/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT COUNT(*) as count FROM cdr"
  }' | jq
```

#### Find high-confidence MAID-CDR connections

```bash
curl -s http://localhost:3099/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM connections_with_confidence WHERE confidence = '"'"'high'"'"' LIMIT 20"
  }' | jq
```

### Data Characteristics

All datasets maintain realistic correlations:

- **Location accuracy:** MAID records within ±100-150m of CDR locations
- **Temporal accuracy:** MAID timestamps within ±60 seconds of CDR times
- **Signal strength:** Realistic RSRP (-140 to -90 dBm) and other signal metrics
- **Device diversity:** Mixed OS (iOS, Android), manufacturers, and models
- **Connection types:** 4G LTE, 5G, WiFi, 3G

This results in **70-90% high-confidence connections** — realistic for real-world data linking scenarios.

### Dataset Configuration Files

Each dataset has a configuration file documenting its specifications:

```bash
# View dataset configuration
cat mcp_apps/mcp_query_duckdb/data/datasets/caribbean/config.yaml
cat mcp_apps/mcp_query_duckdb/data/datasets/south_china_sea/config.yaml
```

---

For step-by-step manual control, you can run each step individually. This approach is useful for debugging or understanding each step:

```bash

# 1. Fetch external GitHub projects (first time only)
mkdir -p external
cd external
git clone https://github.com/istresearch/helix-mcp-demo.git
git clone https://github.com/istresearch/helix-map.git
git clone https://github.com/istresearch/helix-ui.git
cd ..

# 2. Set up environment
cp a2a/.env.template a2a/.env
# Edit a2a/.env with your LLM credentials and API keys

# 3. Build all images (internal and external)
docker compose build                                    # Build internal services
docker compose --profile external build               # Build external services

# 4. Start the full stack
docker compose up -d
docker compose --profile external up -d
```

This will start:
- Helix-A (port 8000) — A2A demo primary
- Helix-B (port 8001) — A2A demo secondary
- A2A Registry (port 8100) — agent discovery
- Weather Agent (port 10010)
- Currency Agent (port 10000)
- MCP Registry (port 9000)
- MCP Chart Server (port 3131)
- Langfuse (port 3000) — observability
- **helix-mcp-demo** (ports 3100-3130, 3150, 4325, 8080, 8081) — MCP server showcase
- **helix-map** (port 3132) — Map visualization
- **helix-ui** (port 5000) — Interactive UI

### Stop the entire stack

```bash
# Stop all services (preserves data)
./shutdown_demo.sh

# Stop all services AND remove volumes (deletes persistent data)
./shutdown_demo.sh --remove-all
```

---

## Individual Demos

For fine-grained control, you can start each demo separately (see sections below).

### Step 1 — Build and start the shared Helix instance

All demos require a running Helix service. `helix/` builds the shared
images and runs Helix on **port 8000**.

```bash
cd helix
cp .env.template .env          # fill in your LLM credentials
# Edit .env to set AGENT_MODEL_API_KEY and AGENT_MODEL_BASE_URL
docker compose up -d --build
```

Helix is now available at `http://localhost:8000`.
All workflows in `helix/config/workflows/` are loaded automatically.

> **Note:** `helix/` also produces `local/helix:latest` and
> `local/helix-examples:latest` used by the a2a demo. Always build it
> before starting `a2a/`.

---

## Demo: MCP Apps

Demonstrates Helix with interactive chart tools served by an MCP App server.

**Workflows used:** `mcp_agent`, `deep_wired`

### Start

```bash
# 1. Ensure helix/ is running, then enable MCP in its .env:
#    AGENT_MCP_ENABLED=true
#    MCP_REGISTRY_ENABLED=true
#    (restart helix/ after editing .env)

# 2. Start the MCP supporting services:
cd mcp_apps
docker compose up -d
```

**Services started:**

| Service       | Port | Purpose                              |
|---------------|------|--------------------------------------|
| mcp-registry  | 9000 | Dynamic MCP server discovery         |
| mcp_simple_chart  | 3131 | Chart tool MCP server (bar/line/pie) |

Helix (from `helix/`) connects to these services via `host.docker.internal`.

### Stop

```bash
cd mcp_apps && docker compose down
```

---

## Demo: A2A (Agent-to-Agent)

Demonstrates a two-Helix hierarchy communicating over the A2A protocol.
Helix-A delegates weather and currency queries to Helix-B, which in turn
delegates to specialist leaf agents.

**Architecture:**

```
User → Helix-A (port 8000) → Helix-B (port 8001) → weather-agent (port 10010)
                                                   → currency-agent (port 10000)
       A2A Registry (port 8100) — agent discovery
       Langfuse (port 3000) — tracing
```

**Workflows used:** `deep_a2a_agent` (helix-a) and `deep_a2a_agent_b` (helix-b), both in `helix/config/workflows/`

> **Note:** This demo runs its own Helix-A and Helix-B instances on ports
> 8000 and 8001. Stop `helix/` first if it is already using port 8000.

### Setup

```bash
cd a2a
cp .env.template .env          # fill in LLM credentials
```

### Build images

Build the shared helix images first (if not already done):

```bash
cd helix && docker compose build && cd -
```

### Start

```bash
cd a2a
docker compose up -d
```

**Services started:**

| Service        | Port  | Purpose                               |
|----------------|-------|---------------------------------------|
| helix-a        | 8000  | User-facing Helix, delegates to B     |
| helix-b        | 8001  | Weather + currency capable Helix      |
| registry       | 8100  | A2A agent discovery registry          |
| weather-agent  | 10010 | Leaf agent: weather forecasts         |
| currency-agent | 10000 | Leaf agent: currency exchange         |
| langfuse-web   | 3000  | Observability UI (admin/password)     |

### Verify

```bash
curl http://localhost:8100/agents
```

Both `Helix-A` and `Helix-B` should appear in the registry.

### Example query

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "workflow": "deep_a2a_agent",
    "messages": [{"role": "user", "content": "What is the weather in Tokyo and convert 1000 JPY to USD?"}],
    "stream": false
  }' | jq '.choices[0].message.content'
```

### Stop

```bash
cd a2a && docker compose down
```

---

## Workflow Reference

| Workflow            | Description                                                       |
|---------------------|-------------------------------------------------------------------|
| `basic_agent`       | Simple ReAct agent with file tools                                |
| `mcp_agent`         | ReAct agent + MCP chart tools (requires mcp_apps/)           |
| `deep_wired`        | Full capability: subagents + MCP charts + A2A remote agents       |
| `deep_a2a_agent`    | Supervisor with A2A delegation — Helix-A role (delegates out)     |
| `deep_a2a_agent_b`  | Supervisor with A2A delegation — Helix-B role (weather + currency)|

### deep_wired capabilities

The `deep_wired` workflow combines everything:

- **story_writer** subagent — writes short stories
- **editor** subagent — reviews and approves stories
- **visualization_agent** subagent — generates interactive charts via MCP
- **A2A remote agents** — weather and currency (enabled via env vars)

To run `deep_wired` with all features:

```bash
# In helix//.env:
AGENT_MCP_ENABLED=true
MCP_SIMPLE_CHART_URL=http://host.docker.internal:3131/mcp
MCP_REGISTRY_ENABLED=true
A2A_REGISTRY_ENABLED=true
A2A_REGISTRY_URL=http://host.docker.internal:8100

# Start mcp_apps/ and a2a/ first, then restart helix/
```

---

## Troubleshooting

### Services Not Responding After Startup

**Problem:** The startup script reports services as "not responding" after health checks.

**Solution:**
- Some services take longer to become ready (especially on first run)
- Check service logs: `docker compose logs service_name`
- Wait an additional 30-60 seconds and check again: `docker compose ps`
- Verify specific service health:
  ```bash
  curl http://localhost:8000/health      # Helix
  curl http://localhost:8100/agents      # A2A Registry
  curl http://localhost:9000/health      # MCP Registry
  ```

### Port Conflicts

**Problem:** "Port already in use" error during service startup.

**Solution:**
```bash
# Find which process is using the port (e.g., port 8000)
lsof -i :8000

# Stop conflicting service or Docker container
docker ps | grep <service_name>
docker stop <container_id>

# Or use a different Docker Compose project name
docker compose -p my_demo up -d
```

### Docker Build Failures

**Problem:** `docker compose build` fails with compilation errors.

**Cause:** Complex projects like `helix-mcp-demo` have many optional dependencies. Some example servers may fail to build.

**Solution:**
- The build is designed to tolerate failures (` || true` in Dockerfile)
- Check the build output for specific failing servers
- Most failures are optional and won't affect core functionality
- Verify the main application works: `curl http://localhost:8080`

### Out of Disk Space

**Problem:** Docker build fails due to insufficient disk space.

**Solution:**
```bash
# Free up disk space
docker system prune -a --volumes  # Remove unused images and volumes (CAUTION: destructive)

# Or build only specific services needed:
cd mcp_apps && docker compose build
```

### Git Authentication Fails During Startup

**Problem:** "Authentication failed" or "Invalid username or token" when cloning external projects.

**Solution:**
1. Verify Git is configured:
   ```bash
   git config --global user.name
   git config --global user.email
   ```

2. Test authentication manually:
   ```bash
   git clone https://github.com/istresearch/helix-mcp-demo.git /tmp/test
   ```

3. Set up GitHub CLI authentication (recommended):
   ```bash
   gh auth login
   # Follow interactive prompts
   ```

4. Or store credentials in `~/.netrc` (see Git Authentication Setup section above)

### Services Crashing After Startup

**Problem:** Services appear to start but crash soon after.

**Cause:** Usually missing environment variables or configuration files.

**Solution:**
1. Check the `.env` file exists:
   ```bash
   ls -la a2a/.env
   ```

2. Verify required environment variables:
   ```bash
   docker compose logs helix-a | head -50
   ```

3. Common missing configs:
   - `a2a/.env` — Must contain `AGENT_MODEL_API_KEY` and `AGENT_MODEL_BASE_URL`
   - `mcp_apps/mcp_query_duckdb/data/demo.duckdb` — DuckDB database file

### MCP Services Showing "Unhealthy"

**Problem:** `mcp_query_duckdb` shows "unhealthy" status.

**Cause:** Health check requires valid database and configuration.

**Solution:**
1. Verify database file exists:
   ```bash
   ls -la mcp_apps/mcp_query_duckdb/data/demo.duckdb
   ```

2. Check service logs:
   ```bash
   docker compose logs mcp_query_duckdb
   ```

3. Restart the service:
   ```bash
   docker compose restart mcp_query_duckdb
   ```

### Seeing Service Logs

**View logs for a specific service:**
```bash
docker compose logs -f helix-a                    # Follow logs
docker compose logs helix-a --tail 50             # Last 50 lines
docker compose logs helix-a -f --timestamps       # With timestamps
```

**View logs for all services:**
```bash
docker compose logs -f
```

### Graceful Shutdown

**Stop all services (preserves data):**
```bash
./shutdown_demo.sh
```

**Stop and remove all containers and volumes (destructive):**
```bash
./shutdown_demo.sh --remove-all
```

**Manual cleanup:**
```bash
docker compose down                              # Stop services
docker compose --profile external down           # Stop external services too
docker system prune                              # Remove unused images
```

### Verifying Full Stack Health

**Quick health check of all services:**
```bash
#!/bin/bash
services=(
  "Helix-A:8000"
  "Helix-B:8001"
  "A2A Registry:8100"
  "Weather Agent:10010"
  "Currency Agent:10000"
  "MCP Registry:9000"
  "MCP Chart Server:3131"
  "MCP DuckDB:3099"
)

for service in "${services[@]}"; do
  IFS=':' read -r name port <<< "$service"
  if nc -z localhost "$port" 2>/dev/null; then
    echo "✓ $name (port $port) is responding"
  else
    echo "✗ $name (port $port) is NOT responding"
  fi
done
```

---

## Resource Requirements

- **CPU:** 4+ cores recommended
- **Memory:** 8GB+ recommended (4GB minimum)
- **Disk:** 10GB+ for Docker images and containers
- **Network:** Stable internet connection for downloading base images

**On first startup, the demo will download:**
- Base images for Python, Node.js, Bun
- LLM client libraries
- Database images (PostgreSQL, Redis, ClickHouse, MinIO)
- Total download size: ~3-5GB

---

## Getting Help

If you encounter issues not covered in troubleshooting:

1. **Check startup script output** — Run with verbose logging:
   ```bash
   bash -x ./startup_demo.sh 2>&1 | tee demo_startup.log
   ```

2. **Review service logs** — Look for errors in specific services
3. **Verify prerequisites** — Ensure Docker, Docker Compose, and Git are properly installed
4. **Check GitHub issues** — Visit https://github.com/istresearch/helix/issues

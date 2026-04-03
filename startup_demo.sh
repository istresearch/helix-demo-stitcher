#!/bin/bash

##############################################################################
# Helix Demo Startup Script
#
# This script automates the complete demo setup:
# 1. Fetches external GitHub projects (helix, helix-agent-registry, helix-mcp-registry, helix-mcp-demo, helix-map, helix-ui, rag-knowledge-base)
# 2. Stops any conflicting separately-started compose projects
# 3. Builds all Docker images (internal and external)
# 4. Starts all services:
#      - agent_registry/ (A2A agent registry, port 8100)
#      - mcp_registry/   (MCP server registry, port 9000)
#      - a2a/            (Helix-A, Helix-B, leaf agents, Langfuse)
#      - mcp_apps/       (MCP tool servers: charts, DuckDB)
#      - rag_kb/         (RAG Knowledge Base: API, MCP, UI, Qdrant, Redis, PostgreSQL)
#      - External:       helix-mcp-demo, helix-map, helix-ui, helix-agent-registry, helix-mcp-registry, rag-knowledge-base
# 5. Performs health checks on all services
# 6. Opens the dashboard in a browser
#
# Usage:
#   chmod +x startup_demo.sh
#   ./startup_demo.sh
#
##############################################################################

# Don't exit on errors - allow script to continue and report what actually started
# set -e

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTERNAL_DIR="$DEMO_DIR/external"
SCRIPT_DIR="$DEMO_DIR"

# Load DEMO_DATASET from a2a/.env if it exists
if [ -f "$DEMO_DIR/a2a/.env" ]; then
    # Source only DEMO_DATASET if it exists in the file
    DEMO_DATASET_FROM_ENV=$(grep "^DEMO_DATASET=" "$DEMO_DIR/a2a/.env" | cut -d'=' -f2)
    if [ -n "$DEMO_DATASET_FROM_ENV" ]; then
        export DEMO_DATASET="$DEMO_DATASET_FROM_ENV"
    fi

    # Load DEMO_REPEATABLE_SEED if it exists in the file
    DEMO_REPEATABLE_SEED_FROM_ENV=$(grep "^DEMO_REPEATABLE_SEED=" "$DEMO_DIR/a2a/.env" | cut -d'=' -f2)
    if [ -n "$DEMO_REPEATABLE_SEED_FROM_ENV" ]; then
        export DEMO_REPEATABLE_SEED="$DEMO_REPEATABLE_SEED_FROM_ENV"
    fi
fi

# ── External project repos and branches ──────────────────────────────────
# Edit these to change which branches are cloned into demo/external/.
EXTERNAL_PROJECTS=(
    "helix                  demo_mcp_apps_a2a"
    "helix-agent-registry   develop"
    "helix-mcp-registry     develop"
    "helix-mcp-demo         IRAD1-256_mcp_ui_demo-1"
    "helix-map              develop"
    "helix-ui               feature/create-chart-mcp-ui-cleanup"
    "rag-knowledge-base     develop"
)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    log_success "Docker found"

    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose plugin is not installed. Please install Docker Compose first."
        exit 1
    fi
    log_success "Docker Compose found"

    if ! command -v git &> /dev/null; then
        log_error "Git is not installed. Please install Git first."
        exit 1
    fi
    log_success "Git found"

    # Check Git authentication
    log_info "Checking Git authentication..."
    if ! git ls-remote https://github.com/istresearch/helix-mcp-demo.git &> /dev/null; then
        log_error "Git authentication failed. Cannot access GitHub repositories."
        log_error ""
        log_error "Please configure Git authentication. Options:"
        log_error "  1. GitHub CLI:       gh auth login"
        log_error "  2. Personal Token:   Store in ~/.netrc or use 'git config credential.helper store'"
        log_error "  3. SSH Keys:         Add public key to https://github.com/settings/keys"
        log_error ""
        log_error "See README for detailed setup instructions."
        exit 1
    fi
    log_success "Git authentication verified"
}

# Check configuration files
check_config_files() {
    # ...existing code...
    log_info "Checking configuration files..."

    # Check for .env file in a2a directory
    local env_file="$DEMO_DIR/a2a/.env"
    if [ ! -f "$env_file" ]; then
        log_error ".env file not found at $env_file"
        log_info "Creating .env from template..."
        if [ -f "$DEMO_DIR/a2a/.env.template" ]; then
            cp "$DEMO_DIR/a2a/.env.template" "$env_file"
            log_success ".env created from template"
            log_warning "Please edit $env_file with your LLM credentials and API keys"
            return 1
        else
            log_error ".env.template not found at $DEMO_DIR/a2a/.env.template"
            exit 1
        fi
    fi
    log_success ".env file found"

    # Check for .duckdb file in mcp_query_duckdb/data/databases/ directory
    local duckdb_dir="$DEMO_DIR/mcp_apps/mcp_query_duckdb/data/databases"
    if [ ! -d "$duckdb_dir" ]; then
        log_info "No databases/ directory yet — will be created in Phase 1"
    else
        local duckdb_file=$(find "$duckdb_dir" -name "*.duckdb" -type f 2>/dev/null | head -1)
        if [ -z "$duckdb_file" ]; then
            log_info "No .duckdb files found yet — will be built in Phase 1"
        else
            log_success ".duckdb file found: $(basename "$duckdb_file")"
        fi
    fi
}

# Ensure Docker Desktop Model Runner has required models
ensure_docker_models() {
    log_info "Checking Docker Desktop Model Runner models..."

    # Required models for the demo stack
    local -a required_models=(
        "ai/embeddinggemma"    # RAG Knowledge Base — 768-dim embeddings
    )

    if ! docker model list &> /dev/null; then
        log_warning "Docker Model Runner not available (requires Docker Desktop with Model Runner enabled)"
        log_warning "RAG Knowledge Base embedding/search will not work without it"
        return 0
    fi

    for model in "${required_models[@]}"; do
        if docker model list 2>/dev/null | grep -q "$model"; then
            log_success "Model already available: $model"
        else
            log_info "Pulling model: $model (this may take a few minutes on first run)..."
            if docker model pull "$model" 2>&1 | tail -1; then
                log_success "Model pulled: $model"
            else
                log_warning "Failed to pull model: $model"
                log_warning "RAG Knowledge Base embedding/search may not work"
            fi
        fi
    done
}

# Build demo datasets
build_demo_datasets() {
    log_info "Building demo datasets for MCP DuckDB queries..."

    local DEMO_DATASET="${DEMO_DATASET:-hormuz}"
    local DATASETS_DIR="$DEMO_DIR/mcp_apps/mcp_query_duckdb/data/datasets"
    local DB_DIR="$DEMO_DIR/mcp_apps/mcp_query_duckdb/data/databases"
    local REBUILD_DATA="${REBUILD_DATA:-false}"

    # Ensure database directory exists
    mkdir -p "$DB_DIR"

    local DB_FILE="$DB_DIR/${DEMO_DATASET}.duckdb"

    # Check if we need to build
    if [ -f "$DB_FILE" ] && [ "$REBUILD_DATA" != "true" ]; then
        log_success "Using existing dataset: ${DEMO_DATASET}"
    else
        if [ "$REBUILD_DATA" = "true" ] && [ -f "$DB_FILE" ]; then
            log_info "Rebuilding dataset: ${DEMO_DATASET}"
            rm -f "$DB_FILE"
        else
            log_info "Building dataset: ${DEMO_DATASET}"
        fi

        # Check for generator
        local GENERATOR="$DATASETS_DIR/$DEMO_DATASET/gen_${DEMO_DATASET}_data.py"
        if [ ! -f "$GENERATOR" ]; then
            log_warning "Generator not found: $GENERATOR"
            # Check if an existing .duckdb file exists for this dataset
            if [ -f "$DB_FILE" ]; then
                log_success "Using existing database file: ${DEMO_DATASET}.duckdb (generator not available)"
                export ACTIVE_DATASET="$DEMO_DATASET"
                export DB_PATH="$DB_FILE"
                return 0
            else
                log_warning "No database file found and no generator available (skipping dataset build)"
                return 0
            fi
        fi

        # Run generator (Phase 1: Generate CSVs)
        echo ""
        echo "════════════════════════════════════════════════════════════"
        log_info "PHASE 1: Generating CSV files from dataset"
        echo "════════════════════════════════════════════════════════════"
        echo ""
        log_info "Generating data for $DEMO_DATASET..."

        # Generator outputs to ./generated/ subdirectory
        local CSV_OUTPUT_DIR="$DATASETS_DIR/$DEMO_DATASET/generated"

        # Detect available Python binary
        local PYTHON_BIN
        if command -v python3 &> /dev/null; then
            PYTHON_BIN="python3"
        elif command -v python &> /dev/null; then
            PYTHON_BIN="python"
        else
            log_warning "Python not found. Cannot generate dataset."
            return 1
        fi

        # Build generator command with optional seed parameter
        local GENERATOR_CMD="$PYTHON_BIN gen_${DEMO_DATASET}_data.py --output-dir ."
        if [ -n "${DEMO_REPEATABLE_SEED}" ] && [ "${DEMO_REPEATABLE_SEED}" != "0" ]; then
            GENERATOR_CMD="$GENERATOR_CMD --seed ${DEMO_REPEATABLE_SEED}"
            log_info "Using seed: ${DEMO_REPEATABLE_SEED} (repeatable generation)"
        fi

        (cd "$DATASETS_DIR/$DEMO_DATASET" && eval "$GENERATOR_CMD") || {
            log_warning "Failed to generate CSV files for dataset $DEMO_DATASET"
            return 1
        }

        # Convert CSVs to DuckDB (Phase 2: CSV to DuckDB)
        echo ""
        echo "════════════════════════════════════════════════════════════"
        log_info "PHASE 2: Converting CSV files to DuckDB"
        echo "════════════════════════════════════════════════════════════"
        echo ""

        # Ensure duckdb Python package is available
        if ! $PYTHON_BIN -c "import duckdb" 2>/dev/null; then
            log_info "Installing duckdb Python package..."
            if $PYTHON_BIN -m pip install duckdb --quiet 2>/dev/null; then
                log_success "duckdb installed"
            else
                log_warning "Failed to install duckdb. Install manually: pip install duckdb"
                return 1
            fi
        fi

        log_info "Converting CSV files to DuckDB..."

        # Ensure database directory exists
        mkdir -p "$DB_DIR"

        (cd "$DATASETS_DIR/$DEMO_DATASET" && \
         $PYTHON_BIN ../../csv_to_duckdb.py \
            --directory "." \
            --db "$DB_FILE") || {
            log_warning "Failed to convert CSV to DuckDB for dataset $DEMO_DATASET"
            return 1
        }

        echo ""
        echo "════════════════════════════════════════════════════════════"
        log_success "Dataset built: ${DEMO_DATASET}"
        echo "════════════════════════════════════════════════════════════"
        echo ""
    fi

    # Export for services
    export ACTIVE_DATASET="$DEMO_DATASET"
    export DB_PATH="$DB_FILE"
}

# Display the external projects and branches that will be used
show_external_projects() {
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  External Projects                                         ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    for entry in "${EXTERNAL_PROJECTS[@]}"; do
        local project branch
        read -r project branch <<< "$entry"
        printf "║  %-30s  %-24s ║\n" "$project" "$branch"
    done
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Edit EXTERNAL_PROJECTS in startup_demo.sh to change branches."
}

# Fetch external projects
fetch_external_projects() {
    log_info "Fetching external GitHub projects..."

    mkdir -p "$EXTERNAL_DIR"

    for entry in "${EXTERNAL_PROJECTS[@]}"; do
        local project branch
        read -r project branch <<< "$entry"

        if [ -d "$EXTERNAL_DIR/$project" ]; then
            local current_branch
            current_branch=$(git -C "$EXTERNAL_DIR/$project" branch --show-current 2>/dev/null)
            if [ "$current_branch" = "$branch" ]; then
                log_info "$project already on branch $branch"
            else
                log_warning "$project is on branch '$current_branch', expected '$branch'. Re-cloning..."
                rm -rf "$EXTERNAL_DIR/$project"
                git clone --depth 1 --branch "$branch" "https://github.com/istresearch/$project.git" "$EXTERNAL_DIR/$project"
                log_success "Re-cloned $project on branch $branch"
            fi
        else
            log_info "Cloning $project (branch: $branch)..."
            git clone --depth 1 --branch "$branch" "https://github.com/istresearch/$project.git" "$EXTERNAL_DIR/$project"
            log_success "Cloned $project"
        fi
    done
}


# Verify Helix source and local config are present after clone
verify_helix_paths() {
    log_info "Verifying Helix source and local config paths..."

    local errors=0

    # External Helix source (needed for Docker image builds)
    local helix_src="$EXTERNAL_DIR/helix"
    if [ ! -f "$helix_src/chat/Dockerfile" ]; then
        log_error "Missing: $helix_src/chat/Dockerfile (needed to build local/helix:latest)"
        errors=$((errors + 1))
    else
        log_success "Found external/helix/chat/Dockerfile"
    fi

    if [ ! -f "$helix_src/chat_examples/Dockerfile" ]; then
        log_error "Missing: $helix_src/chat_examples/Dockerfile (needed to build local/helix-examples:latest)"
        errors=$((errors + 1))
    else
        log_success "Found external/helix/chat_examples/Dockerfile"
    fi

    # Local config root (mounted into containers at runtime)
    if [ ! -f "$DEMO_DIR/helix/config/application.conf" ]; then
        log_error "Missing: helix/config/application.conf (runtime config)"
        errors=$((errors + 1))
    else
        log_success "Found helix/config/application.conf"
    fi

    if [ ! -d "$DEMO_DIR/helix/config/workflows" ]; then
        log_error "Missing: helix/config/workflows/ directory"
        errors=$((errors + 1))
    else
        log_success "Found helix/config/workflows/"
    fi

    if [ ! -d "$DEMO_DIR/helix/config/prompts" ]; then
        log_error "Missing: helix/config/prompts/ directory"
        errors=$((errors + 1))
    else
        log_success "Found helix/config/prompts/"
    fi

    if [ $errors -gt 0 ]; then
        log_error "$errors path(s) missing. Cannot proceed with build."
        log_info "Ensure the helix repo was cloned to external/helix (branch demo_mcp_apps_a2a)"
        log_info "and that helix/config/ in this repo has application.conf, workflows/, and prompts/."
        exit 1
    fi
}

# Stop containers from separate compose projects that conflict with the
# unified compose (same ports, same network names but different labels).
cleanup_conflicting_projects() {
    log_info "Stopping any separately-started compose projects..."

    local compose_files=(
        "$DEMO_DIR/agent_registry/docker-compose.yml"
        "$DEMO_DIR/mcp_registry/docker-compose.yml"
        "$DEMO_DIR/mcp_apps/docker-compose.yml"
        "$DEMO_DIR/a2a/docker-compose.yml"
    )

    for cf in "${compose_files[@]}"; do
        if [ -f "$cf" ] && docker compose -f "$cf" ps -q 2>/dev/null | grep -q .; then
            local project=$(basename "$(dirname "$cf")")
            log_info "Stopping $project project..."
            docker compose -f "$cf" down 2>/dev/null
            log_success "Stopped $project"
        fi
    done

    # Remove stale networks that were created by separate projects —
    # the unified compose needs to recreate them with its own labels.
    docker network rm helix-mcp-apps-demo_default 2>/dev/null && \
        log_info "Removed stale network helix-mcp-apps-demo_default" || true
    docker network rm a2a_default 2>/dev/null && \
        log_info "Removed stale network a2a_default" || true
}

# Build Docker images
build_docker_images() {
    log_info "Building Docker images..."

    cd "$DEMO_DIR"

    # Build the base Helix images first (must be sequential).
    # helix-examples Dockerfile does FROM local/helix:latest which is
    # produced by helix-base, so helix-base must complete first.
    log_info "Building helix-base image (local/helix:latest)..."
    if ! docker compose --profile build build helix-base 2>&1 | tail -5; then
        log_error "Failed to build helix-base. Aborting."
        return 1
    fi
    log_success "helix-base built"

    log_info "Building helix-examples image (local/helix-examples:latest)..."
    if ! docker compose --profile build build helix-examples-build 2>&1 | tail -5; then
        log_error "Failed to build helix-examples. helix-a/helix-b will not start."
        return 1
    fi
    log_success "helix-examples built"

    # All remaining builds are independent — run them in parallel.
    log_info "Building all remaining services in parallel..."

    local build_log_dir
    build_log_dir=$(mktemp -d)
    local pids=()
    local svc_names=()

    # Internal services (A2A registry, MCP registry, MCP Apps, agents)
    (docker compose build > "$build_log_dir/internal.log" 2>&1) &
    pids+=($!)
    svc_names+=("internal services")

    # External services
    for svc in helix-mcp-demo helix-map helix-ui rag-kb-api rag-kb-mcp rag-kb-ui rag-kb-ingest; do
        (docker compose --profile external build "$svc" > "$build_log_dir/$svc.log" 2>&1) &
        pids+=($!)
        svc_names+=("$svc")
    done

    log_info "Waiting for ${#pids[@]} parallel builds to complete..."

    # Wait for all builds and report results
    local log_names=("internal" "helix-mcp-demo" "helix-map" "helix-ui" "rag-kb-api" "rag-kb-mcp" "rag-kb-ui" "rag-kb-ingest")
    local failed=0
    for i in "${!pids[@]}"; do
        if wait "${pids[$i]}"; then
            log_success "${svc_names[$i]} built"
        else
            log_warning "${svc_names[$i]} failed to build (skipping)"
            grep -i "error\|failed" "$build_log_dir/${log_names[$i]}.log" 2>/dev/null | tail -3
            failed=$((failed + 1))
        fi
    done

    rm -rf "$build_log_dir"

    if [ $failed -gt 0 ]; then
        log_warning "$failed build(s) failed — see warnings above"
    else
        log_success "All images built successfully"
    fi
}

# Start services
start_services() {
    log_info "Starting services..."

    cd "$DEMO_DIR"

    # Start internal services first (creates networks, starts helix, agents, registries).
    log_info "Starting internal services..."
    local int_output
    int_output=$(docker compose up -d 2>&1)
    if echo "$int_output" | grep -qi "error\|failed"; then
        log_warning "Some internal services may have issues:"
        echo "$int_output" | grep -i "error\|failed" | head -5
    else
        log_success "Internal services started"
    fi

    # Start external services independently so one failure doesn't block the rest.
    log_info "Starting external services..."
    # Start RAG KB infrastructure first (redis, postgres, qdrant need to be healthy
    # before api/mcp/ui/ingest can start).
    for svc in rag-kb-redis rag-kb-postgres rag-kb-qdrant; do
        log_info "Starting $svc..."
        local svc_output
        svc_output=$(docker compose --profile external up -d "$svc" 2>&1)
        if [ $? -ne 0 ]; then
            log_warning "$svc failed to start:"
            echo "$svc_output" | tail -3
        else
            log_success "$svc started"
        fi
    done

    for svc in helix-mcp-demo helix-map helix-ui rag-kb-api rag-kb-mcp rag-kb-ui rag-kb-ingest; do
        log_info "Starting $svc..."
        local svc_output
        svc_output=$(docker compose --profile external up -d "$svc" 2>&1)
        if [ $? -ne 0 ]; then
            log_warning "$svc failed to start:"
            echo "$svc_output" | tail -3
        else
            log_success "$svc started"
        fi
    done
}

# Fetch logs for a service (by service name or port)
fetch_service_logs() {
    local service_name=$1
    local port=$2
    local log_lines=5

    # Map service names to container name patterns
    local container_pattern=""
    case "$service_name" in
        "Helix-A") container_pattern="helix-a" ;;
        "Helix-B") container_pattern="helix-b" ;;
        "A2A Registry") container_pattern="registry" ;;
        "Weather Agent") container_pattern="weather-agent" ;;
        "Currency Agent") container_pattern="currency-agent" ;;
        "MCP Registry") container_pattern="mcp-registry\|mcp_registry" ;;
        "MCP Chart Server") container_pattern="mcp_simple_chart" ;;
        "MCP DuckDB") container_pattern="mcp_query_duckdb" ;;
        "Langfuse") container_pattern="langfuse" ;;
        "helix-mcp-demo") container_pattern="helix-mcp-demo" ;;
        "helix-map") container_pattern="helix-map" ;;
        "helix-ui") container_pattern="helix-ui" ;;
        "RAG KB API") container_pattern="rag-kb-api" ;;
        "RAG KB MCP") container_pattern="rag-kb-mcp" ;;
        "RAG KB UI") container_pattern="rag-kb-ui" ;;
        "RAG KB Qdrant") container_pattern="rag-kb-qdrant" ;;
        *) container_pattern="$service_name" ;;
    esac

    # Find container ID matching the pattern
    local container_id=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i "$container_pattern" | head -1)

    if [ -z "$container_id" ]; then
        # Try by port
        local container_id=$(docker ps -a --format '{{.Names}}:{{.Ports}}' 2>/dev/null | grep ":$port" | cut -d':' -f1 | head -1)
    fi

    if [ -n "$container_id" ]; then
        log_info "Recent logs for $service_name (container: $container_id):"
        docker logs "$container_id" 2>/dev/null | tail -n $log_lines | sed 's/^/    /'
    else
        log_warning "Could not find container for $service_name"
    fi
}

# Health check for a service
check_service_health() {
    local service_name=$1
    local port=$2
    local max_attempts=10
    local attempt=1

    log_info "Checking $service_name (port $port)..."

    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost "$port" 2>/dev/null; then
            log_success "$service_name is healthy"
            return 0
        fi

        echo -ne "${BLUE}${attempt}/${max_attempts}${NC}\r"
        attempt=$((attempt + 1))
        sleep 2
    done

    log_warning "$service_name did not respond after ${max_attempts} attempts"
    return 1
}

# Perform health checks
perform_health_checks() {
    log_info "Performing health checks on all services..."

    local -a services=(
        "Helix-A:8000"
        "Helix-B:8001"
        "A2A Registry:8100"
        "Weather Agent:10010"
        "Currency Agent:10000"
        "MCP Registry:9000"
        "MCP Chart Server:3131"
        "Langfuse:3000"
        "helix-mcp-demo:8080"
        "helix-map:3132"
        "helix-ui:5000"
        "RAG KB API:8200"
        "RAG KB MCP:8201"
        "RAG KB UI:3200"
        "RAG KB Qdrant:6333"
    )

    local healthy_services=()
    local failed_services=()

    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        if check_service_health "$name" "$port"; then
            healthy_services+=("$name")
        else
            failed_services+=("$name")
        fi
    done

    echo ""
    echo "════════════════════════════════════════════"
    echo "Health Check Summary:"
    echo "════════════════════════════════════════════"

    if [ ${#healthy_services[@]} -gt 0 ]; then
        log_success "Running services (${#healthy_services[@]}):"
        for svc in "${healthy_services[@]}"; do
            echo "  ✓ $svc"
        done
    fi

    if [ ${#failed_services[@]} -gt 0 ]; then
        echo ""
        log_warning "Not responding (${#failed_services[@]}):"
        for svc in "${failed_services[@]}"; do
            echo "  ✗ $svc"
        done
        echo ""
        log_info "Fetching logs for failed services to assist with troubleshooting:"
        echo ""

        # Fetch logs for each failed service
        for service in "${services[@]}"; do
            IFS=':' read -r name port <<< "$service"
            # Check if this service is in the failed list
            for failed_svc in "${failed_services[@]}"; do
                if [ "$name" = "$failed_svc" ]; then
                    fetch_service_logs "$name" "$port"
                    echo ""
                fi
            done
        done

        log_info "This could be due to:"
        log_info "  - Port conflicts (already in use)"
        log_info "  - Services still starting"
        log_info "  - Missing dependencies"
        echo ""
    fi
    echo "════════════════════════════════════════════"
    echo ""

    # Return success if at least some services are running
    if [ ${#healthy_services[@]} -gt 0 ]; then
        return 0
    else
        return 1
    fi
}

# Wait for all services with retries
wait_for_services() {
    local max_retries=2
    local retry=1

    while [ $retry -le $max_retries ]; do
        log_info "Health check attempt $retry of $max_retries..."
        if perform_health_checks; then
            return 0
        fi
        retry=$((retry + 1))
    done

    log_warning "Some services are still not responding, but proceeding..."
    return 0
}

# Verify MCP Registry has loaded servers from config
verify_mcp_registry_loaded() {
    log_info "Verifying MCP Registry has loaded server definitions..."

    local server_count=$(curl -s http://localhost:9000/v1/servers 2>/dev/null | grep -c "url" 2>/dev/null)
    server_count=${server_count:-0}

    if [ "$server_count" -gt 0 ]; then
        log_success "MCP Registry has $server_count server(s) loaded"
    else
        log_warning "MCP Registry appears empty. This may indicate:"
        log_warning "  - Config file not found or not properly mounted"
        log_warning "  - Registry not fully started yet"
        log_info "Check with: docker logs demo-mcp-registry-1"
        log_info "Or verify: curl http://localhost:9000/v1/servers"
        return 1
    fi

    # Verify helix-a can reach the MCP registry from inside its container
    log_info "Verifying helix-a can reach MCP Registry over Docker network..."
    local helix_a_container=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "helix-a" | head -1)
    if [ -n "$helix_a_container" ]; then
        local reach_test
        reach_test=$(docker exec "$helix_a_container" python3 -c "
import urllib.request, json
try:
    resp = urllib.request.urlopen('http://mcp-registry:9000/v1/servers', timeout=5)
    servers = json.loads(resp.read())
    print(f'OK:{len(servers)}')
except Exception as e:
    print(f'FAIL:{e}')
" 2>/dev/null)

        if echo "$reach_test" | grep -q "^OK:"; then
            local count=$(echo "$reach_test" | sed 's/OK://')
            log_success "helix-a can reach MCP Registry ($count server(s) visible)"
        else
            log_warning "helix-a CANNOT reach MCP Registry: $reach_test"
            log_warning "This means MCP tools will not load. Check:"
            log_warning "  - helix-a and mcp-registry share the mcp-apps network"
            log_warning "  - docker network inspect helix-mcp-apps-demo_default"
        fi
    else
        log_warning "helix-a container not found — cannot verify MCP connectivity"
    fi

    return 0
}

# Verify A2A agents are registered with the registry
verify_a2a_agents_registered() {
    log_info "Verifying A2A agents are registered with the registry..."

    local max_retries=3
    local retry=1
    local agent_count=0

    while [ $retry -le $max_retries ]; do
        agent_count=$(curl -s http://localhost:8100/v1/agents?active_only=true 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null)
        agent_count=${agent_count:-0}

        if [ "$agent_count" -ge 2 ]; then
            log_success "A2A Registry has $agent_count agent(s) registered"
            return 0
        fi

        if [ $retry -lt $max_retries ]; then
            log_info "Found $agent_count agents. Waiting and retrying... (attempt $retry/$max_retries)"
            sleep 10
        fi

        retry=$((retry + 1))
    done

    # Final attempt
    agent_count=$(curl -s http://localhost:8100/v1/agents?active_only=true 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null)
    agent_count=${agent_count:-0}

    if [ "$agent_count" -ge 2 ]; then
        log_success "A2A Registry has $agent_count agent(s) registered"
        return 0
    fi

    log_warning "A2A Registry has $agent_count agents registered (expected at least 2)."
    log_info ""
    log_info "Collecting diagnostics..."
    log_info ""

    # Show registry response
    log_info "Registry response:"
    curl -s http://localhost:8100/v1/agents?active_only=true 2>/dev/null | head -c 500
    echo ""
    echo ""

    # Show Helix-A logs
    log_info "Helix-A registration logs:"
    docker logs demo-helix-a-1 2>/dev/null | grep -i "registry" | tail -5 || echo "  (no registry logs found)"
    echo ""

    # Show Helix-B logs
    log_info "Helix-B registration logs:"
    docker logs demo-helix-b-1 2>/dev/null | grep -i "registry" | tail -5 || echo "  (no registry logs found)"
    echo ""

    log_warning "This may indicate:"
    log_warning "  - Network connectivity issue (agents can't reach registry at http://registry:8100)"
    log_warning "  - A2A_REGISTRY_ENABLED not set to true in docker-compose"
    log_warning "  - Service startup timing issue"
    log_info ""
    log_info "Try these manual diagnostic commands:"
    log_info "  curl http://localhost:8100/v1/agents?active_only=true"
    log_info "  docker logs demo-helix-a-1 | grep -i 'a2a\\|registry'"
    log_info "  docker logs demo-helix-b-1 | grep -i 'a2a\\|registry'"
    log_info "  docker exec demo-helix-a-1 env | grep A2A"
    log_info "  docker exec demo-helix-b-1 env | grep A2A"
    return 1
}

# Open dashboard
open_dashboard() {
    log_info "Opening dashboard..."

    local dashboard_path="$DEMO_DIR/dashboard.html"

    if [ ! -f "$dashboard_path" ]; then
        log_warning "Dashboard file not found at $dashboard_path"
        return 1
    fi

    # Try different browsers depending on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "$dashboard_path"
        log_success "Dashboard opened in default browser"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v xdg-open &> /dev/null; then
            xdg-open "$dashboard_path"
            log_success "Dashboard opened in default browser"
        else
            log_warning "Could not open dashboard. Please open $dashboard_path manually."
        fi
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Windows
        start "$dashboard_path"
        log_success "Dashboard opened in default browser"
    else
        log_warning "Unknown OS. Please open $dashboard_path manually."
    fi
}

# Main execution
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           Helix Demo - Complete Startup Script              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Show which dataset will be used
    local active_dataset="${DEMO_DATASET:-hormuz}"
    log_info "Using dataset: $active_dataset"
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 0: Configuration & Prerequisites
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 0: Configuration & Prerequisites"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    show_external_projects
    echo ""

    check_prerequisites
    echo ""

    check_config_files
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 1: Prepare Demo Data & Embeddings
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 1: Prepare Demo Data & Embeddings"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    build_demo_datasets
    echo ""

    ensure_docker_models
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 2: Fetch External Projects
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 2: Fetch External Projects"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    fetch_external_projects
    echo ""

    # Ensure helix-ui .env exists (it's .gitignored, so won't be in the clone)
    local helix_ui_env="$EXTERNAL_DIR/helix-ui/.env"
    if [ -d "$EXTERNAL_DIR/helix-ui" ] && [ ! -f "$helix_ui_env" ]; then
        touch "$helix_ui_env"
        log_info "Created empty $helix_ui_env (all vars set in docker-compose.yml)"
    fi

    # Verify Helix source paths and local config are present
    verify_helix_paths
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 3: Clean Up Conflicting Services
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 3: Clean Up Conflicting Services"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    cleanup_conflicting_projects
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 4: Build Docker Images
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 4: Build Docker Images"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    build_docker_images
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 5: Start Services
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 5: Start Services"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    start_services
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 6: Verify Service Health
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    log_info "PHASE 6: Verify Service Health"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    log_info "Waiting for MCP Registry to be healthy..."
    local mcp_registry_healthy=false
    local retry=0
    while [ $retry -lt 10 ]; do
        if curl -s http://localhost:9000/healthz >/dev/null 2>&1; then
            mcp_registry_healthy=true
            log_success "MCP Registry is healthy"
            break
        fi
        log_info "MCP Registry not ready yet... (attempt $((retry+1))/10)"
        sleep 3
        retry=$((retry+1))
    done
    if [ "$mcp_registry_healthy" = false ]; then
        log_warning "MCP Registry did not become healthy."
    fi
    echo ""

    log_info "Waiting for A2A Registry to be healthy..."
    local registry_healthy=false
    retry=0
    while [ $retry -lt 10 ]; do
        if curl -s http://localhost:8100/healthz >/dev/null 2>&1; then
            registry_healthy=true
            log_success "A2A Registry is healthy"
            break
        fi
        log_info "A2A Registry not ready yet... (attempt $((retry+1))/10)"
        sleep 3
        retry=$((retry+1))
    done
    if [ "$registry_healthy" = false ]; then
        log_warning "A2A Registry did not become healthy."
    fi
    echo ""

    log_info "Waiting for remaining services to initialize (10 seconds)..."
    sleep 10

    wait_for_services
    echo ""

    verify_mcp_registry_loaded
    echo ""

    log_info "Allowing time for A2A agents to self-register (10 seconds)..."
    sleep 10
    echo ""

    verify_a2a_agents_registered
    echo ""

    # ────────────────────────────────────────────────────────────────
    # PHASE 7: Startup Complete
    # ────────────────────────────────────────────────────────────────
    echo "════════════════════════════════════════════════════════════"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo -e "║ ${GREEN}✓ Helix Demo Startup Complete!${NC}                              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    log_success "Demo services are starting. Available endpoints:"
    echo ""
    echo "  Internal Services:"
    echo "    • Helix-A (A2A primary):        http://localhost:8000"
    echo "    • Helix-B (A2A secondary):      http://localhost:8001"
    echo "    • A2A Registry:                 http://localhost:8100"
    echo "    • Weather Agent:                http://localhost:10010"
    echo "    • Currency Agent:               http://localhost:10000"
    echo "    • MCP Registry:                 http://localhost:9000"
    echo "    • MCP Chart Server:             http://localhost:3131"
    echo "    • Langfuse (observability):     http://localhost:3000"
    echo ""
    echo "  External Services:"
    echo "    • helix-mcp-demo:               http://localhost:8080"
    echo "    • helix-map:                    http://localhost:3132"
    echo "    • helix-ui:                     http://localhost:5000"
    echo ""
    echo "  RAG Knowledge Base:"
    echo "    • RAG KB UI:                    http://localhost:3200"
    echo "    • RAG KB API (Swagger):         http://localhost:8200/docs"
    echo "    • RAG KB MCP Server:            http://localhost:8201"
    echo "    • Qdrant Dashboard:             http://localhost:6333/dashboard"
    echo ""
    log_info "Note: Some services may take time to become responsive"
    log_info "Check health summary above - services marked ✓ are ready to use"
    echo ""

    sleep 2
    open_dashboard

    echo ""
    log_success "Startup complete!"
}

# Run main function
main "$@"

#!/bin/bash

##############################################################################
# Helix Demo Shutdown Script
#
# This script stops all demo services:
# 1. Stops external services (helix-mcp-demo, helix-map, helix-ui, rag-knowledge-base)
# 2. Stops internal services (Helix, A2A, MCP Apps, agents)
# 3. Optionally removes containers and volumes
#
# Usage:
#   chmod +x demo/shutdown_demo.sh
#   ./demo/shutdown_demo.sh              # Stop all containers
#   ./demo/shutdown_demo.sh --remove-all # Stop and remove containers/volumes
#
##############################################################################

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Main execution
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           Helix Demo - Complete Shutdown Script             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Check if user wants to remove volumes
    local remove_volumes=""
    if [ "$1" = "--remove-all" ] || [ "$1" = "-r" ]; then
        remove_volumes="-v"
        log_warning "Removing all containers and volumes (data will be deleted)"
    else
        log_info "Stopping containers (data will be preserved)"
        log_info "Use './shutdown_demo.sh --remove-all' to also delete volumes"
    fi

    echo ""

    # Change to demo directory
    cd "$DEMO_DIR"

    # Stop external services first
    log_info "Stopping external services (helix-mcp-demo, helix-map, helix-ui, rag-knowledge-base)..."
    if docker compose --profile external down $remove_volumes 2>&1 | grep -q "error\|Error"; then
        log_warning "Some external services may not have stopped cleanly"
    else
        log_success "External services stopped"
    fi

    echo ""

    # Stop internal services
    log_info "Stopping internal services (Helix, A2A, MCP, agents)..."
    if docker compose down $remove_volumes 2>&1 | grep -q "error\|Error"; then
        log_warning "Some internal services may not have stopped cleanly"
    else
        log_success "Internal services stopped"
    fi

    echo ""

    # Show summary
    echo "╔════════════════════════════════════════════════════════════╗"
    echo -e "║ ${GREEN}✓ Helix Demo Shutdown Complete!${NC}                             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Show what was stopped
    log_success "All services have been stopped:"
    echo ""
    echo "  Internal Services (Stopped):"
    echo "    • Helix-A"
    echo "    • Helix-B"
    echo "    • A2A Registry"
    echo "    • Weather Agent"
    echo "    • Currency Agent"
    echo "    • MCP Registry"
    echo "    • MCP Chart Server"
    echo "    • Langfuse"
    echo "    • PostgreSQL"
    echo "    • Redis"
    echo "    • ClickHouse"
    echo "    • MinIO"
    echo ""
    echo "  External Services (Stopped):"
    echo "    • helix-mcp-demo"
    echo "    • helix-map"
    echo "    • helix-ui"
    echo ""
    echo "  RAG Knowledge Base (Stopped):"
    echo "    • RAG KB API"
    echo "    • RAG KB MCP Server"
    echo "    • RAG KB UI"
    echo "    • RAG KB Qdrant"
    echo "    • RAG KB Ingest Worker"
    echo "    • RAG KB Redis"
    echo "    • RAG KB PostgreSQL"
    echo ""

    # Show data status
    if [ -n "$remove_volumes" ]; then
        log_warning "Data volumes have been removed"
        echo "    • All persistent data has been deleted"
        echo "    • Databases reset"
        echo "    • Cache cleared"
        echo ""
        log_info "To restart fresh: ./startup_demo.sh"
    else
        log_success "Data has been preserved"
        echo "    • Persistent data retained in Docker volumes"
        echo "    • Can restart without losing data: ./startup_demo.sh"
        echo ""
        log_info "To remove data as well: ./shutdown_demo.sh --remove-all"
    fi

    echo ""
    log_success "Shutdown complete!"
    echo ""
}

# Run main function
main "$@"


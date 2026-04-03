# Quick Reference - Demo Startup

This repo is **standalone orchestration**. External repos (including the Helix
source on branch `demo_mcp_apps_a2a`) are fetched automatically. Runtime demo
config is owned locally by this repo under `helix/config/`.

## Prerequisites

Before running the startup script, ensure:
- ✓ Docker and Docker Compose installed
- ✓ Git installed
- ✓ **Git authentication configured** (required to clone GitHub repos)

### Quick Git Authentication Setup

```bash
# Easiest: Use GitHub CLI
gh auth login
# Choose HTTPS when prompted, then authenticate via web browser

# Or use personal access token
git config --global credential.helper store
# Will prompt for token on first clone
```

---

## One-Command Startup

```bash
chmod +x startup_demo.sh && ./startup_demo.sh
```

## What Gets Done Automatically

The `startup_demo.sh` script handles all of these steps:

1. ✓ Checks for Docker, Docker Compose, Git
2. ✓ **Verifies Git authentication** works
3. ✓ Clones external repos (`helix`, `helix-agent-registry`, `helix-mcp-registry`, `helix-mcp-demo`, `helix-map`, `helix-ui`, `rag-knowledge-base`) from istresearch
4. ✓ Builds all internal Docker images
5. ✓ Builds all external Docker images
6. ✓ Starts all internal services (Helix A2A, MCP, registry, etc.)
7. ✓ Starts all external services
8. ✓ Checks for .env file and .duckdb database file
9. ✓ Health checks all 11 services
10. ✓ Displays all available endpoints
11. ✓ Opens the dashboard in your browser

## Services That Will Be Running

After the script completes, these endpoints will be available:

**Internal Services:**
- Helix-A: http://localhost:8000 (primary A2A)
- Helix-B: http://localhost:8001 (secondary A2A)
- A2A Registry: http://localhost:8100
- Weather Agent: http://localhost:10010
- Currency Agent: http://localhost:10000
- MCP Registry: http://localhost:9000
- MCP Chart Server: http://localhost:3131
- Langfuse: http://localhost:3000 (observability)

**External Services:**
- helix-mcp-demo: http://localhost:8080
- helix-map: http://localhost:3132
- helix-ui: http://localhost:5000

## First Time Setup Note

### Git Authentication Error

If you see: `Invalid username or token. Password authentication is not supported for Git operations.`

This means you need to configure Git authentication:

```bash
# Option 1: GitHub CLI (recommended)
gh auth login

# Option 2: Personal Access Token
git config --global credential.helper store
# Then re-run the startup script

# Option 3: SSH Keys
# Add your SSH public key to https://github.com/settings/keys
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

Then re-run: `./startup_demo.sh`

### LLM Credentials

If you haven't configured LLM credentials yet, you may need to:
1. Stop the script with Ctrl+C once services start failing
2. Edit `a2a/.env` with your LLM API key and endpoint
3. Run the script again (it will skip re-fetching and re-building)

Or configure credentials before running:
```bash
cp a2a/.env.template a2a/.env
# Edit a2a/.env with your credentials
chmod +x startup_demo.sh
./startup_demo.sh
```

## If Something Fails

The script provides clear error messages. Common issues:

1. **"Docker is not installed"** → Install Docker Desktop
2. **"Git authentication failed"** → See "Git Authentication Error" section above
3. **"Permission denied"** → Run `chmod +x startup_demo.sh` first
4. **Services timeout** → May need more system resources, wait longer, or check firewall
5. **Network issues** → Check internet connection for git cloning
6. **Port conflicts** → Ensure ports 3000-5000, 8000-8100, 10000-10010 are free

## Stopping the Demo

### Stop Services (Preserve Data)
```bash
./shutdown_demo.sh
```

All containers stop but data is retained in Docker volumes. You can restart and data will still be there.

### Stop Services + Delete Data
```bash
./shutdown_demo.sh --remove-all
```

Removes all containers and volumes. Fresh start next time you run startup script.

---

To completely rebuild from scratch:
```bash
# Remove all containers
docker compose down -v
docker compose --profile external down -v

# Remove external project directories (optional)
rm -rf external/

# Run startup script again
./startup_demo.sh
```

## Manual Alternative

If you prefer step-by-step control, see "Quick Start ��� Unified Stack (Manual Setup)" in the README.

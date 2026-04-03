# Helix Demo - Quick Commands Reference

## 🚀 Quick Start Commands

### One-Command Startup (Recommended)
```bash
chmod +x startup_demo.sh
./startup_demo.sh
```

### Manual Startup
```bash

# Build all images
docker compose build
docker compose --profile external build

# Start all services
docker compose up -d
docker compose --profile external up -d

# Wait for services to be ready
sleep 30

# Verify services are running
docker compose --profile external ps
```

---

## 🛑 Stop Services

### Stop All (Preserve Data)
```bash
./shutdown_demo.sh
```

### Stop All (Delete Everything)
```bash
./shutdown_demo.sh --remove-all
```

### Manual Stop
```bash
docker compose down
docker compose --profile external down
```

---

## 🔍 View Logs

### View All Logs (Live)
```bash
docker compose --profile external logs -f
```

### View Specific Service Logs
```bash

# Helix-A
docker compose logs -f helix-a

# External service
docker compose --profile external logs -f helix-mcp-demo

# Show last 50 lines
docker compose logs helix-a --tail 50

# With timestamps
docker compose logs helix-a -f --timestamps
```

---

## ✅ Health Checks

### Check All Services Status
```bash
docker compose --profile external ps
```

### Quick Port Check
```bash
for port in 8000 8001 8100 10000 10010 3131 9000 3132 5000; do
  echo -n "Port $port: "
  nc -z localhost $port 2>/dev/null && echo "✓" || echo "✗"
done
```

### Test Specific Services
```bash
# Helix-A
curl http://localhost:8000/v1/models

# A2A Registry
curl http://localhost:8100/agents

# MCP Registry
curl http://localhost:9000/

# helix-ui
curl http://localhost:5000

# helix-map
curl http://localhost:3132
```

---

## 🏗️ Build Commands

### Build Everything (Recommended)
```bash
docker compose --profile external build
```

### Build Individual Services
```bash
# Helix core
cd helix && docker compose build && cd ..

# A2A agents
cd a2a && docker compose build && cd ..

# MCP Apps
cd mcp_apps && docker compose build && cd ..

# helix-mcp-demo (external)
cd external/helix-mcp-demo && docker build -t helix-mcp-demo . && cd ../../..

# helix-map (external)
cd external/helix-map && docker build -t helix-map . && cd ../../..

# helix-ui (external)
cd external/helix-ui && docker build -t helix-ui:local -f Dockerfile . && cd ../../..
```

### Force Rebuild (No Cache)
```bash
docker compose build --no-cache
docker compose --profile external build --no-cache
```

---

## 🔧 Troubleshooting Commands

### Check Service Status
```bash
docker compose --profile external ps
```

### Restart a Service
```bash
docker compose restart helix-a
docker compose --profile external restart helix-ui
```

### Rebuild and Restart a Service
```bash
docker compose up -d --build helix-a
docker compose --profile external up -d --build helix-ui
```

### Clean Up (Remove Stopped Containers)
```bash
docker container prune -f
```

### Remove Unused Images
```bash
docker image prune -a -f
```

### Free Disk Space (Caution: Destructive)
```bash
docker system prune -a --volumes
```

---

## 📊 Monitor Services

### Real-Time Resource Usage
```bash
docker stats
```

### Detailed Container Info
```bash
docker inspect helix-a
docker compose --profile external config
```

### Network Inspection
```bash
docker network ls
docker network inspect helix-demo_default
```

---

## 🧪 Test Workflows

### Chat with Helix-A (A2A Demo)
```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "workflow": "deep_a2a_agent",
    "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
    "stream": false
  }' | jq '.choices[0].message.content'
```

### List Available Workflows
```bash
curl -s http://localhost:8000/v1/workflows | jq .
```

### List A2A Agents
```bash
curl -s http://localhost:8100/agents | jq .
```

### Query MCP Registry
```bash
curl -s http://localhost:9000/ | jq .
```

---

## 🔐 Default Credentials

| Service | Username | Password | Notes |
|---------|----------|----------|-------|
| helix-ui | admin | admin | Change in production |
| Langfuse | admin | admin | Change in production |
| Auth | N/A | N/A | Demo uses UNPW mode |

---

## 🌐 Service Ports Reference

```
Internal Services:
  8000 - Helix-A (User-facing)
  8001 - Helix-B (Backend delegation)
  8100 - A2A Registry
  10000 - Currency Agent
  10010 - Weather Agent
  9000 - MCP Registry
  3131 - MCP Chart Server
  3000 - Langfuse Web
  5432 - PostgreSQL
  6379 - Redis
  9090 - MinIO

External Services (with --profile external):
  8080-8081 - helix-mcp-demo web interfaces
  3100-3130 - helix-mcp-demo MCP servers
  3132 - helix-map
  5000 - helix-ui
```

---

## 📝 Environment Files

Location: `a2a/.env`

Required variables:
```
AGENT_MODEL_API_KEY=your-api-key
AGENT_MODEL_BASE_URL=http://litellm:4000
```

Optional variables:
```
LOG_LEVEL=INFO
LANGFUSE_ENABLED=true
```

---

## 💾 Data Persistence

### Database Location
```bash
# PostgreSQL data
docker exec postgres psql -U postgres

# Redis data
docker exec redis redis-cli

# DuckDB file
ls -la mcp_apps/mcp_query_duckdb/data/
```

### Backup Services
```bash
# Create backup
docker exec postgres pg_dump -U postgres > backup.sql

# List volumes
docker volume ls

# Inspect volume
docker volume inspect demo_postgres_data
```

---

## 🔄 Update Services

### Pull Latest Code
```bash
cd external/helix-mcp-demo && git pull origin main && cd ../../
cd external/helix-map && git pull origin main && cd ../../
cd external/helix-ui && git pull origin main && cd ../../
```

### Rebuild After Updates
```bash
docker compose --profile external build --no-cache
docker compose --profile external up -d
```

---

## 🐛 Debug Commands

### Enter Container Shell
```bash
docker exec -it helix-a bash
docker exec -it helix-ui sh
```

### View Full Logs (All Output)
```bash
docker logs helix-a > helix-a.log
```

### Network Debug
```bash
# Test connectivity from container
docker exec helix-a curl http://helix-b:8000/health

# DNS resolution
docker exec helix-a nslookup redis
```

### Environment Variables in Container
```bash
docker exec helix-a env | sort
```

---

## 📚 Documentation Links

- Full README: `README.md` (951 lines)
- Completion Summary: `COMPLETION_SUMMARY.md`
- Docker Compose Reference: `docker-compose.yml`
- Startup Script: `startup_demo.sh`
- Shutdown Script: `shutdown_demo.sh`

---

## 💡 Tips & Best Practices

1. **Always check logs first** when services fail
2. **Use `--profile external`** to control which services start
3. **Build images locally** - they're not pre-published
4. **Wait 30-60 seconds** after startup for all services to be ready
5. **Use `nc -z`** for quick port availability checks
6. **Monitor disk space** during first build (~10GB needed)
7. **Check `.env` files** when services crash at startup
8. **Use `docker-compose config`** to validate configuration

---

## 🆘 Common Issues & Quick Fixes

### Issue: "Port already in use"
```bash
# Find process using port
lsof -i :8000

# Stop Docker service using it
docker stop <container_id>

# Use different project name
docker compose -p helix_demo2 up -d
```

### Issue: "Out of memory"
```bash
# Check resource usage
docker stats

# Reduce services
docker compose down
docker compose up -d  # Internal only, no external
```

### Issue: "Service not responding after startup"
```bash
# Check logs
docker compose logs <service_name>

# Wait longer (services need time to start)
sleep 60

# Restart service
docker compose restart <service_name>
```

### Issue: "Git authentication failed"
```bash
# Test authentication
git clone https://github.com/istresearch/helix-mcp-demo.git /tmp/test

# Set up GitHub CLI
gh auth login

# Or use SSH
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

---

Last Updated: 2026-03-30
Version: 1.0


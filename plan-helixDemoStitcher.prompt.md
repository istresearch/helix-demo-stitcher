## Plan: Pushbutton Standalone With Shallow Mounts

This repo remains the orchestration owner: it composes external repos for code/images, but runtime configs come from this repo in a simple shallow structure so startup is predictable and independent.

**Steps**
1. Phase 1: Keep external code external, keep demo config local
2. Add `helix demo_mcp_apps_a2a` to `startup_demo.sh` external project list so Helix source is always cloned into this repo’s `external/`.
3. Update Helix image build contexts in `a2a/docker-compose.yml` and `helix/docker-compose.yml` to `../external/helix`.
4. Keep Helix runtime config mounted from this repo (not deep external paths), using a shallow root mount strategy for both agents:
5. Mount one directory root (e.g., `../helix/config:/app/config:ro`) for `helix-a` and `helix-b` instead of multiple deep path mounts.
6. Ensure `APP_CONFIG_FILE`, `WORKFLOWS_DIR`, and `PROMPTS_DIR` align with the single mounted root.
7. Phase 2: Simplify config path structure in-repo
8. Verify `helix/config/` in this repo remains canonical and complete (`application.conf`, `workflows/`, `prompts/`) for all demo scenarios.
9. If needed, normalize any odd nesting under `helix/config/workflows` to keep paths straightforward for operators.
10. Phase 3: Pushbutton startup hardening
11. Add deterministic preflight checks in `startup_demo.sh` for external Helix source paths after clone (`chat/Dockerfile`, `chat_examples/Dockerfile`) and local config root presence (`helix/config/application.conf`, `helix/config/workflows`, `helix/config/prompts`).
12. Keep startup non-interactive once prerequisites are present: fetch external repos, build in dependency order, start services, health-check, verify registry connectivity, open dashboard.
13. Preserve existing auto-bootstrap helpers (`a2a/.env` template copy, `external/helix-ui/.env` creation) and keep errors actionable.
14. Phase 4: Compatibility boundaries and docs
15. Do not modify any files in `/Users/donald.krapohl/Documents/GitHub/helix`; this guarantees the original demo startup there continues to work unchanged.
16. Update README/QUICK_REF/COMMANDS_REFERENCE wording to state clearly:
17. This repo is standalone orchestration.
18. External repos (including Helix branch pin) are fetched automatically.
19. Runtime demo config is owned locally by this repo.
20. One-command startup is the primary path.

**Relevant files**
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/startup_demo.sh` — clone matrix, preflight checks, pushbutton flow
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/a2a/docker-compose.yml` — external Helix build context + shallow config root mount for helix-a/helix-b
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/helix/docker-compose.yml` — same external Helix build context + local config convention
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/helix/config/` — canonical runtime config source
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/README.md` — canonical startup docs
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/QUICK_REF.md` — quick pushbutton flow
- `/Users/donald.krapohl/Documents/GitHub/helix-demo-stitcher/COMMANDS_REFERENCE.md` — manual fallback consistency

**Verification**
1. `docker compose config` at repo root succeeds with new mount/build paths.
2. `a2a/docker-compose.yml` shows shallow mount (`../helix/config:/app/config:ro`) for both helix agents.
3. Startup prints Helix external branch `demo_mcp_apps_a2a` and succeeds from a clean `external/` directory.
4. If external clone fails or local config root is incomplete, script exits early with clear remediation.
5. No file changes occur in the original helix repo path.

**Decisions**
- Included: externalize Helix source/build only; keep runtime config local to this repo.
- Included: simplify mount paths with a single config-root mount per Helix agent.
- Included: preserve standalone pushbutton startup behavior.
- Excluded: any modification to the original helix repo.

**Further Considerations**
1. Option A (recommended): keep branch pin fixed (`demo_mcp_apps_a2a`) for reproducibility; Option B: optional env override for scenario branches later.
2. Optionally add `./startup_demo.sh --validate-only` later for fast CI preflight without launching containers.

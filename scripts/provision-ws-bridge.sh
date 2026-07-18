#!/usr/bin/env bash
# Provision Vault role + secrets for the ws-bridge (Tata telephony WebSocket bridge).
# Run ON the VPS (mirrors scripts/provision-ai-collections.sh conventions).
#
#   bash scripts/provision-ws-bridge.sh
#
# Reads the Vault root token from /root/vault-init-keys.json (same as the original
# provision script). Reuses the listening-agent's LiveKit credentials so the bridge
# joins the SAME LiveKit project as the agent. Also:
#   - flips livekit_egress_enabled=false (Tata records calls now; call SID → next-action)
#   - sets call_mode=tata on the backend config
#   - generates WS_BRIDGE_AUTH_TOKEN (the ?token= Tata must echo back) unless one exists
set -euo pipefail

log()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m OK\033[0m %s\n" "$*"; }

VAULT_NS="${VAULT_NS:-platform}"
VAULT_POD="vault-0"
APP_NS="app-services"

VAULT_TOKEN="${VAULT_TOKEN:-$(python3 -c "import json; print(json.load(open('/root/vault-init-keys.json'))['root_token'])")}"

vault_exec() {
    kubectl exec -n "$VAULT_NS" "$VAULT_POD" -- env VAULT_TOKEN="$VAULT_TOKEN" vault "$@"
}

# ── 1. ServiceAccount + Vault role ───────────────────────────────────────────
log "Provisioning Vault role for: ws-bridge"
kubectl create serviceaccount ws-bridge -n "$APP_NS" --dry-run=client -o yaml | kubectl apply -f -
vault_exec write auth/kubernetes/role/ws-bridge \
    bound_service_account_names="ws-bridge" \
    bound_service_account_namespaces="$APP_NS" \
    policies="app-services" \
    ttl=1h
ok "Vault role 'ws-bridge' ready"

# ── 2. Seed ws-bridge secret (LiveKit creds copied from listening-agent) ─────
log "Reading LiveKit creds + agent name from listening-agent config"
LK_URL=$(vault_exec kv get -field=livekit_url secret/app-services/listening-agent/config)
LK_KEY=$(vault_exec kv get -field=livekit_api_key secret/app-services/listening-agent/config)
LK_SECRET=$(vault_exec kv get -field=livekit_api_secret secret/app-services/listening-agent/config)
AGENT_NAME=$(vault_exec kv get -field=agent_name secret/app-services/listening-agent/config)

# Keep an existing auth token if the secret was seeded before (Tata portal already has it).
WS_TOKEN=$(vault_exec kv get -field=ws_bridge_auth_token secret/app-services/ws-bridge/config 2>/dev/null || true)
if [ -z "$WS_TOKEN" ]; then
    WS_TOKEN=$(openssl rand -hex 24)
    log "Generated new WS_BRIDGE_AUTH_TOKEN"
else
    log "Reusing existing WS_BRIDGE_AUTH_TOKEN"
fi

# Backend X-API-KEY gate (optional — only if the backend has one configured)
BACKEND_API_KEY=$(vault_exec kv get -field=api_key secret/app-services/backend/config 2>/dev/null || true)

if [ -n "$BACKEND_API_KEY" ]; then
    vault_exec kv put secret/app-services/ws-bridge/config \
        livekit_url="$LK_URL" \
        livekit_api_key="$LK_KEY" \
        livekit_api_secret="$LK_SECRET" \
        agent_name="$AGENT_NAME" \
        ws_bridge_auth_token="$WS_TOKEN" \
        backend_api_key="$BACKEND_API_KEY"
else
    vault_exec kv put secret/app-services/ws-bridge/config \
        livekit_url="$LK_URL" \
        livekit_api_key="$LK_KEY" \
        livekit_api_secret="$LK_SECRET" \
        agent_name="$AGENT_NAME" \
        ws_bridge_auth_token="$WS_TOKEN"
fi
ok "ws-bridge secrets seeded at secret/app-services/ws-bridge/config"

# ── 3. Egress OFF (Tata records the call; call SID goes to next-action) ─────
log "Setting livekit_egress_enabled=false on listening-agent config"
vault_exec kv patch secret/app-services/listening-agent/config livekit_egress_enabled="false"
ok "LiveKit egress disabled"

# ── 4. Backend: tata mode ────────────────────────────────────────────────────
log "Setting call_mode=tata on backend config"
vault_exec kv patch secret/app-services/backend/config call_mode="tata"
ok "backend call_mode=tata"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Tata portal VOICE Bot WebSocket URL:"
echo ""
echo "  wss://aiassistant.yutrix.io/telephony/stream?token=$WS_TOKEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

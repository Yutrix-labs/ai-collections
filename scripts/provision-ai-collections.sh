#!/usr/bin/env bash
# Provision Vault roles, ServiceAccounts, and GHCR pull secret for ai-collections.
# Run once on the VPS (or any machine with kubectl + vault access).
#
# Prerequisites:
#   - kubectl configured: export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
#   - Vault running:       kubectl get pod vault-0 -n platform
#   - export VAULT_TOKEN=<root_token>
#     (read from VPS: python3 -c "import json; print(json.load(open('/root/vault-init-keys.json'))['root_token'])")
#   - export GITHUB_PAT=<pat_with_read:packages_scope>
#     (or set GITHUB_USER and GITHUB_PAT)
#
# Usage:
#   VAULT_TOKEN=hvs.xxxx GITHUB_PAT=ghp_xxxx bash scripts/provision-ai-collections.sh
set -euo pipefail

log()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m OK\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33mWARN\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31mERR\033[0m %s\n" "$*" >&2; exit 1; }

VAULT_TOKEN="${VAULT_TOKEN:?Set VAULT_TOKEN to your Vault root token}"
GITHUB_PAT="${GITHUB_PAT:?Set GITHUB_PAT to a GitHub PAT with read:packages scope}"
GITHUB_USER="${GITHUB_USER:-dipanshu}"
VAULT_NS="${VAULT_NS:-platform}"
VAULT_POD="vault-0"
APP_NS="app-services"

vault_exec() {
    kubectl exec -n "$VAULT_NS" "$VAULT_POD" -- env VAULT_TOKEN="$VAULT_TOKEN" vault "$@"
}

# ── 1. GHCR image pull secret ────────────────────────────────────────────────
log "Creating GHCR image pull secret in $APP_NS"
kubectl create secret docker-registry ghcr-pull-secret \
    --docker-server=ghcr.io \
    --docker-username="$GITHUB_USER" \
    --docker-password="$GITHUB_PAT" \
    --namespace "$APP_NS" \
    --dry-run=client -o yaml | kubectl apply -f -
ok "ghcr-pull-secret ready"

# ── 2. Vault role: backend ───────────────────────────────────────────────────
log "Provisioning Vault role for: backend"
kubectl create serviceaccount backend -n "$APP_NS" --dry-run=client -o yaml | kubectl apply -f -
vault_exec write auth/kubernetes/role/backend \
    bound_service_account_names="backend" \
    bound_service_account_namespaces="$APP_NS" \
    policies="app-services" \
    ttl=1h
ok "Vault role 'backend' ready"

# ── 3. Vault role: listening-agent ───────────────────────────────────────────
log "Provisioning Vault role for: listening-agent"
kubectl create serviceaccount listening-agent -n "$APP_NS" --dry-run=client -o yaml | kubectl apply -f -
vault_exec write auth/kubernetes/role/listening-agent \
    bound_service_account_names="listening-agent" \
    bound_service_account_namespaces="$APP_NS" \
    policies="app-services" \
    ttl=1h
ok "Vault role 'listening-agent' ready"

# ── 4. Seed backend secrets ──────────────────────────────────────────────────
log "Seeding backend secrets from current application.yml values"

# Read values from the current docker deployment environment.
# These match what was previously hardcoded in application.yml.
# Edit these values before running if you've already rotated credentials.
vault_exec kv put secret/app-services/backend/config \
    aws_access_key_id="${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID}" \
    aws_secret_access_key="${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY}" \
    aws_region="${AWS_REGION:-ap-south-1}" \
    openai_api_key="${OPENAI_API_KEY:?Set OPENAI_API_KEY}" \
    gcp_project_id="${GCP_PROJECT_ID:-placeholder}" \
    gcp_location="${GCP_LOCATION:-us-central1}" \
    exotel_account_sid="${EXOTEL_ACCOUNT_SID:-fintaar2m}" \
    exotel_auth_key="${EXOTEL_AUTH_KEY:?Set EXOTEL_AUTH_KEY}" \
    exotel_auth_token="${EXOTEL_AUTH_TOKEN:?Set EXOTEL_AUTH_TOKEN}" \
    exotel_caller_id="${EXOTEL_CALLER_ID:-02247790123}" \
    livekit_url="${LIVEKIT_URL:?Set LIVEKIT_URL}" \
    livekit_api_key="${LIVEKIT_API_KEY:?Set LIVEKIT_API_KEY}" \
    livekit_api_secret="${LIVEKIT_API_SECRET:?Set LIVEKIT_API_SECRET}"
ok "backend secrets seeded at secret/app-services/backend/config"

# ── 5. Seed listening-agent secrets ─────────────────────────────────────────
log "Seeding listening-agent secrets from backend/listening-agent/.env"

# Source the .env file if it exists (run from the repo root on the VPS)
ENV_FILE="${ENV_FILE:-backend/listening-agent/.env}"
if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    set -a; . "$ENV_FILE"; set +a
    warn "Loaded secrets from $ENV_FILE"
else
    warn "$ENV_FILE not found — using environment variables directly"
fi

vault_exec kv put secret/app-services/listening-agent/config \
    livekit_url="${LIVEKIT_URL:?Set LIVEKIT_URL}" \
    livekit_api_key="${LIVEKIT_API_KEY:?Set LIVEKIT_API_KEY}" \
    livekit_api_secret="${LIVEKIT_API_SECRET:?Set LIVEKIT_API_SECRET}" \
    deepgram_api_key="${DEEPGRAM_API_KEY:?Set DEEPGRAM_API_KEY}" \
    anthropic_api_key="${ANTHROPIC_API_KEY:-}" \
    openai_api_key="${OPENAI_API_KEY:-}" \
    aws_access_key_id="${AWS_ACCESS_KEY_ID:-}" \
    aws_secret_access_key="${AWS_SECRET_ACCESS_KEY:-}" \
    aws_region="${AWS_REGION:-ap-south-1}" \
    gcp_project_id="${GCP_PROJECT_ID:-}" \
    gcp_location="${GCP_LOCATION:-us-central1}" \
    gemini_model="${GEMINI_MODEL:-gemini-2.0-flash}" \
    cerebras_api_key="${CEREBRAS_API_KEY:-}" \
    cerebras_model="${CEREBRAS_MODEL:-}" \
    ai_provider="${AI_PROVIDER:-cerebras}" \
    copilot_mode="${COPILOT_MODE:-collections}" \
    agent_name="${AGENT_NAME:-}" \
    sip_mobile_number="${SIP_MOBILE_NUMBER:-}"
ok "listening-agent config secrets seeded"

# ── 6. Seed GCP service account JSON ────────────────────────────────────────
GCP_SA_FILE="${GOOGLE_APPLICATION_CREDENTIALS:-}"
if [ -n "$GCP_SA_FILE" ] && [ -f "$GCP_SA_FILE" ]; then
    log "Seeding GCP service account JSON from $GCP_SA_FILE"
    GCP_SA_JSON=$(cat "$GCP_SA_FILE")
    # Store as single 'json' field — Vault template writes it verbatim to /vault/secrets/gcp-sa.json
    kubectl exec -n "$VAULT_NS" "$VAULT_POD" -- \
        env VAULT_TOKEN="$VAULT_TOKEN" \
        vault kv put secret/app-services/listening-agent/gcp-sa \
        json="$GCP_SA_JSON"
    ok "GCP SA seeded at secret/app-services/listening-agent/gcp-sa"
else
    warn "GOOGLE_APPLICATION_CREDENTIALS not set or file not found — skipping GCP SA seed"
    warn "Seed manually: kubectl exec -n platform vault-0 -- env VAULT_TOKEN=\$VAULT_TOKEN vault kv put secret/app-services/listening-agent/gcp-sa json='\$(cat /path/to/sa.json)'"
fi

# ── 7. KUBECONFIG_B64 GitHub secret instructions ─────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NEXT: Add KUBECONFIG_B64 to GitHub Actions secrets"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Run this on the VPS to generate the value:"
echo ""
echo '    sed "s|127.0.0.1|147.93.106.171|g" /etc/rancher/k3s/k3s.yaml | base64 -w 0'
echo ""
echo "  Then add it as secret KUBECONFIG_B64 in:"
echo "    GitHub → Settings → Secrets and variables → Actions"
echo ""
echo "  Also ensure port 6443 is open on the VPS firewall:"
echo "    ufw allow 6443/tcp"
echo ""
echo "  Also ensure NEXT_PUBLIC_API_URL GitHub secret is set to:"
echo "    https://aiassistant.yutrix.io/collassistantapi"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  First-time K8s deployment (run once):"
echo "    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
echo "    kubectl apply -f k8s/backend/deployment.yaml"
echo "    kubectl apply -f k8s/frontend/deployment.yaml"
echo "    kubectl apply -f k8s/listening-agent/deployment.yaml"
echo "    kubectl apply -f k8s/ingress.yaml"
echo ""
echo "  Stop old Docker Compose services after K8s is healthy:"
echo "    cd /opt/deployment/code-base/ai-collections"
echo "    docker compose down"
echo ""
log "Provision complete."

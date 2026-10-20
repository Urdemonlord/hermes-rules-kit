# Docker Rollback by Container Name (Registry-Less)

This reference documents the registry-less Docker deploy pattern used when Compose state is inconsistent (containers from a different working directory or mismatched project name).

## When to use this pattern

- Docker Compose containers exist but `docker-compose ps` returns empty (wrong project name/directory)
- Container labels show `com.docker.compose.project: security-gateway` but the repo is at `/home/user/security-gateway-src` (different directory)
- You want to deploy without rebuilding compose state

## How it works

1. CI builds images (GitHub runner)
2. `docker save <image> | gzip > image.tar.gz`
3. Tarballs + deploy script are shipped to VPS via SCP
4. VPS script does:

```bash
# Capture old image IDs before loading new ones
OLD_GATEWAY="$(docker inspect --format '{{.Image}}' security-gateway-gateway 2>/dev/null || true)"
OLD_ML="$(docker inspect --format '{{.Image}}' security-gateway-ml-service 2>/dev/null || true)"

# Load new images
gunzip -c security-gateway-gateway-image.tar.gz | docker load
gunzip -c security-gateway-ml-service-image.tar.gz | docker load

# Recreate ML service
docker rm -f security-gateway-ml-service 2>/dev/null || true
docker run -d \
  --name security-gateway-ml-service \
  --network security-gateway_default \
  --restart unless-stopped \
  -e ML_SERVICE_LOG_LEVEL=info \
  -e ML_SERVICE_MODEL_DIR=/app/models/indobert-agentwa \
  security-gateway-ml-service

# Wait for container health, then recreate gateway
docker rm -f security-gateway-gateway 2>/dev/null || true
docker run -d \
  --name security-gateway-gateway \
  --network security-gateway_default \
  --restart unless-stopped \
  -p 8080:8080 \
  -e SECURITY-GATEWAY__ML_SERVICE__URL=http://security-gateway-ml-service:8000 \
  security-gateway-src-gateway:latest

# Rollback on failure
rollback() {
  run_ml_service "$OLD_ML"
  wait_for_health
  run_gateway "$OLD_GATEWAY"
  wait_for_health
}
```

## Key details

- **ML service first, gateway second**: Start the dependency before the dependent
- **Network**: Extract network name from `docker inspect` of existing containers (`security-gateway_default`)
- **Env vars**: Extract from existing containers: `docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' container-name`
- **Image references**: Use `{{.Image}}` for old image IDs (SHA256 hashes), use image tags (`security-gateway-ml-service:latest`) for new images
- **Port mapping**: Mirror the existing container's `HostConfig.PortBindings`
- **Rollback scope**: Both containers must rollback — if only ML service fails, both ML and gateway rollback

## Pitfall: compose project name mismatch

When `docker-compose ps` shows no containers but `docker ps` shows your containers with compose labels:
```json
{"com.docker.compose.project":"security-gateway","com.docker.compose.service":"gateway"}
```
The compose project name doesn't match the current working directory. `docker-compose -p security-gateway ps` may still fail if the config file path differs. Fix: use direct `docker run` as shown above instead of trying to fix compose.

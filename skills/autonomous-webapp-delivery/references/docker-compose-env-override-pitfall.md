# Docker Compose Env Override Pitfall

## Problem
Docker Compose reads environment variables from shell **before** `.env` file. If a variable is exported in the shell, `.env` value is silently ignored.

## Diagnosis
```bash
# Container shows old/wrong value despite correct .env
docker inspect <container> --format '{{json .Config.Env}}' | jq | grep KEY

# Shell env has a stale value
echo $SOME_KEY

# .env has the correct value
grep SOME_KEY .env
```

## Root cause
Shell profile (~/.bashrc, ~/.profile) exports a variable that overrides .env.

```bash
# Check where it's set
grep -rn 'SOME_KEY' ~/.bashrc ~/.profile ~/.zshrc
```

## Fix (three places)
```bash
# 1. Update .env (source of truth for the project)
echo 'SOME_KEY=newvalue' >> .env

# 2. Update ~/.bashrc and ~/.profile (source of truth for shell sessions)
sed -i "s|export SOME_KEY='.*'|export SOME_KEY='newvalue'|" ~/.bashrc
sed -i "s|export SOME_KEY='.*'|export SOME_KEY='newvalue'|" ~/.profile

# 3. Export in current shell before docker compose
export SOME_KEY=newvalue
docker compose up -d --force-recreate

# Or unset it so compose reads .env
unset SOME_KEY
docker compose up -d --force-recreate
```

## Prevention
- Never export sensitive/service keys in shell profiles unless needed by other tools
- Prefer project-local `.env` files as single source of truth
- Document in `compose.yaml` which env vars come from shell vs .env

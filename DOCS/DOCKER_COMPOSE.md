Using docker-compose (podman-compose) with Redis and Web UI

This project ships a `docker-compose.yml` that defines the `webui` service and a `myai-redis` Redis service (persistent volume `redis_data`). Use the compose file to bring up both in a reproducible way.

Start services (web UI + Redis):

```bash
podman-compose up -d --build webui myai-redis
```

Verify Redis is running and healthy:

```bash
podman ps --filter name=myai-redis
podman logs myai-redis --tail 50
```

Notes

- The web UI will attempt to use Redis when the `REDIS_URL` environment variable is set (e.g. `redis://myai-redis:6379/0`). When running via compose both services are attached to the `myai-net` network so the web UI can reach `myai-redis` by name.
- The compose file creates a named volume `redis_data` which persists Redis data across restarts.
- For production, run the stack behind a reverse proxy and configure TLS and resource limits.

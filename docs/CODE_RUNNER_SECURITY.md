# Isolated Python runner

The optional Python execution service fails closed: if its token, Docker daemon, gVisor `runsc` runtime, or sandbox image is unavailable, Practice Lab reports Python as unavailable. JavaScript practice continues to use its disposable browser Worker.

## Security boundary

Every request creates a new `aia-python-sandbox:3.12` container using the explicitly configured `runsc` runtime. There is no fallback to Docker's default runtime. Each sandbox is:

- non-root (`65534:65534`) with all capabilities dropped and `no-new-privileges`;
- networkless, read-only, and limited to a 16 MB `noexec,nosuid,nodev` temporary filesystem;
- limited to 128 MB RAM, 0.25 CPU (at most two CPU-seconds over the maximum wall time), 32 processes, 64 file descriptors, 1 MB files, eight seconds, and bounded output;
- created without host mounts, the Docker socket, application data, environment secrets, or cloud credentials;
- destroyed after every execution, including timeout paths.

Source and simulated stdin are bounded, authenticated, and sent over stdin as JSON. Source is never placed in a shell command, Docker argument, bind mount, or application log. A fixed launcher compiles it only inside gVisor.

The small `code-runner` orchestrator mounts `/var/run/docker.sock`, which grants that service control of Docker. It is internal-only, has no published host port, contains no application secrets, and must never be exposed to users. Untrusted child sandboxes do **not** receive the socket. Higher-assurance or multi-tenant deployments should place the runner on a separate worker host or use a dedicated microVM execution service.

## Deployment

1. Install gVisor and register Docker's `runsc` runtime using the official gVisor Docker quick-start. Confirm `docker info` lists `runsc`.
2. Copy `.env.example` to `.env`, generate a unique token such as `openssl rand -hex 32`, and store it as `CODE_RUNNER_TOKEN`. Never commit `.env`.
3. Keep `CODE_RUNNER_URL=http://code-runner:8081`. Plain HTTP is accepted only for local/internal single-label hosts; use HTTPS for a remote runner.
4. Run `docker compose --profile code-runner up --build -d`.
5. Open Practice Lab. The badge should say **Isolated Python runner ready**. Otherwise inspect `docker compose logs code-runner` and verify the runtime and image.

Pin and update Docker, gVisor, builder, Alpine, and Python images in production. Use host firewalling so port 8081 is not externally reachable. Monitor aggregate counts and failures without retaining source by default.

No hostile-code system can promise absolute security. This design combines independent controls and a stronger syscall boundary than a normal `runc` container; deployment owners must still patch and monitor the host.

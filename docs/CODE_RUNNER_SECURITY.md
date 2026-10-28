# Isolated code-runner contract

The API deliberately does not execute candidate code. Configure `AIA_CODE_RUNNER_URL` and
`AIA_CODE_RUNNER_TOKEN` only when a separately administered runner implements `POST /run`.

The request contains `language`, `code`, `stdin` and mandatory policy values: `network=false`,
`read_only=true`, `memory_mb=128`, `cpu_seconds=2`, `pids=32`, and `timeout_seconds`.
The response is JSON with `exit_code`, `stdout`, `stderr`, and `timed_out`.

The runner must enforce—not merely trust—these controls:

- create a fresh disposable sandbox for every execution;
- run as a non-root UID with no Linux capabilities and `no-new-privileges`;
- disable all network interfaces and DNS;
- use a read-only root filesystem plus a small temporary working directory;
- enforce memory, CPU, process, output, wall-clock and file-size limits at the kernel/hypervisor layer;
- ship no cloud credentials, host mounts, Docker socket, SSH keys or application secrets into the sandbox;
- use a restrictive seccomp/AppArmor profile and destroy the sandbox after execution;
- authenticate the application token with constant-time comparison and expose the service only over an internal network or HTTPS;
- log metadata, limits and outcomes, but do not retain submitted source code by default.

Do not mount `/var/run/docker.sock` into the public application backend. A container alone is not a
complete hostile-code boundary; use a hardened runner such as a dedicated microVM/gVisor/nsjail
deployment that has been reviewed for your environment.

import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field


@dataclass
class HostedSpec:
    image: str
    container_port: int
    env: dict = field(default_factory=dict)
    data_host_dir: str | None = None
    data_mount_path: str = "/data"
    ready_path: str | None = None
    ready_timeout: int = 180
    extra_args: list = field(default_factory=list)
    name: str = "ae_target"
    confine: bool = True
    host_port: int | None = None


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _docker_cmd(spec, host_port):
    cmd = ["docker", "run", "-d", "--rm", "--name", spec.name,
           "-p", f"127.0.0.1:{host_port}:{spec.container_port}",
           "--add-host", "host.docker.internal:host-gateway"]
    if spec.confine:
        cmd += ["--security-opt", "no-new-privileges",
                "--memory", "2g", "--pids-limit", "512", "--cpus", "2"]
    for k, v in spec.env.items():
        cmd += ["-e", f"{k}={v}"]
    if spec.data_host_dir:
        cmd += ["-v", f"{spec.data_host_dir}:{spec.data_mount_path}"]
    cmd += spec.extra_args
    cmd.append(spec.image)
    return cmd


def _tcp_ready(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _http_ready(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def _running(cid):
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", cid],
                       capture_output=True, text=True)
    return r.stdout.strip() == "true"


def _logs(cid):
    r = subprocess.run(["docker", "logs", "--tail", "60", cid],
                       capture_output=True, text=True)
    return (r.stdout or "") + (r.stderr or "")


def stop(cid):
    subprocess.run(["docker", "rm", "-f", cid], capture_output=True)


def launch(spec: HostedSpec) -> dict:
    subprocess.run(["docker", "rm", "-f", spec.name], capture_output=True)
    preferred = spec.host_port or spec.container_port
    cid, host_port, last_err = None, None, ""
    for candidate in (preferred, _free_port()):
        r = subprocess.run(_docker_cmd(spec, candidate), capture_output=True, text=True)
        if r.returncode == 0:
            cid, host_port = r.stdout.strip(), candidate
            break
        last_err = r.stderr.strip()
        subprocess.run(["docker", "rm", "-f", spec.name], capture_output=True)
    if not cid:
        raise RuntimeError(f"docker run a échoué : {last_err}")
    base = f"http://127.0.0.1:{host_port}"
    ready_url = base + spec.ready_path if spec.ready_path else None
    deadline = time.time() + spec.ready_timeout
    while time.time() < deadline:
        ok = _http_ready(ready_url) if ready_url else _tcp_ready(host_port)
        if ok:
            return {"url": base, "container_id": cid, "port": host_port}
        if not _running(cid):
            raise RuntimeError(f"le conteneur s'est arrêté :\n{_logs(cid)[-600:]}")
        time.sleep(2)
    stop(cid)
    raise TimeoutError(f"cible pas prête après {spec.ready_timeout}s")
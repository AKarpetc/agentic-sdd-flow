#!/usr/bin/env python3
"""Query the Roslyn navigator against any solution, without rebinding the MCP server.

The cwm-roslyn-navigator MCP server binds one solution at launch and exposes no
per-call solution parameter, so a review of a project other than the pinned one
gets empty results. This script launches its own navigator process per solution,
keeps it alive as an idle-timeout daemon behind a unix socket, and forwards
tools/call requests to it — so any project can be analysed at review time.

  roslyn-query.py <project-or-solution> <tool> ['<json-args>']
  roslyn-query.py <project-or-solution> --list-tools | --status | --stop | --restart
"""
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import asf_config  # noqa: E402

ROOT = asf_config.find_project_root()
RESOLVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roslyn-resolve.sh")
NAVIGATOR = os.environ.get("ROSLYN_NAVIGATOR_BIN", os.path.expanduser("~/.dotnet/tools/cwm-roslyn-navigator"))
DOTNET_ROOT = os.environ.get("DOTNET_ROOT", "/usr/local/share/dotnet")
IDLE_TIMEOUT = int(os.environ.get("ROSLYN_DAEMON_IDLE", "1800"))
LOAD_TIMEOUT = int(os.environ.get("ROSLYN_LOAD_TIMEOUT", "300"))
SOCKET_DIR = os.path.join(tempfile.gettempdir(), "roslyn-nav")


def resolve_solution(target):
    """Maps a project short name, directory or solution path to one absolute .sln/.slnx."""
    proc = subprocess.run(
        ["bash", "-c", 'source "$1"; roslyn_resolve_solution "$2" "$3"', "_", RESOLVER, ROOT, target],
        capture_output=True, text=True)
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        raise SystemExit(f"roslyn-query: cannot resolve '{target}': {out or proc.stderr.strip()}")
    return out


def socket_path(solution):
    digest = hashlib.sha1(solution.encode()).hexdigest()[:12]
    return os.path.join(SOCKET_DIR, f"{os.path.basename(solution)}-{digest}.sock")


def ensure_navigator_installed():
    """Installs the CWM.RoslynNavigator global tool on first use so no pre-install is needed."""
    if os.path.exists(NAVIGATOR):
        return
    subprocess.run(["dotnet", "tool", "install", "--global", "CWM.RoslynNavigator"],
                   capture_output=True, text=True, env=dict(os.environ, DOTNET_ROOT=DOTNET_ROOT))
    if not os.path.exists(NAVIGATOR):
        raise RuntimeError("CWM.RoslynNavigator is not installed and `dotnet tool install` failed")


class Navigator:
    """One cwm-roslyn-navigator process, bound to a solution and spoken to over MCP stdio."""

    def __init__(self, solution):
        env = dict(os.environ, DOTNET_ROOT=DOTNET_ROOT)
        self.proc = subprocess.Popen([NAVIGATOR, "--solution", solution],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        self.next_id = 0
        self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "roslyn-query", "version": "1"}})
        self._notify("notifications/initialized")

    def _send(self, payload):
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def _notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _request(self, method, params):
        self.next_id += 1
        wanted = self.next_id
        self._send({"jsonrpc": "2.0", "id": wanted, "method": method, "params": params})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("navigator exited unexpectedly")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == wanted:
                return message

    def call(self, tool, arguments):
        message = self._request("tools/call", {"name": tool, "arguments": arguments})
        if "error" in message:
            raise RuntimeError(json.dumps(message["error"]))
        result = message.get("result", {})
        text = "\n".join(b.get("text", "") for b in result.get("content", [])) or json.dumps(result)
        if result.get("isError"):
            raise RuntimeError(text)
        return text

    def list_tools(self):
        return [t["name"] for t in self._request("tools/list", {}).get("result", {}).get("tools", [])]

    def wait_until_loaded(self):
        """Blocks until the MSBuild workspace has finished loading, or the load times out."""
        deadline = time.time() + LOAD_TIMEOUT
        while time.time() < deadline:
            text = self.call("get_project_graph", {})
            if '"State":"Loading"' not in text:
                return text
            time.sleep(1.5)
        raise RuntimeError(f"solution still loading after {LOAD_TIMEOUT}s")

    def stop(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def serve(solution, sock_path):
    os.makedirs(SOCKET_DIR, exist_ok=True)
    if os.path.exists(sock_path):
        os.unlink(sock_path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(8)
    server.settimeout(IDLE_TIMEOUT)

    navigator = None
    started = time.time()
    try:
        ensure_navigator_installed()
        navigator = Navigator(solution)
        navigator.wait_until_loaded()
    except Exception as exc:
        ready_error = f"{type(exc).__name__}: {exc}"
    else:
        ready_error = None
    load_seconds = round(time.time() - started, 1)

    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                return
            with conn:
                data = conn.makefile("r").readline()
                if not data:
                    continue
                request = json.loads(data)
                command = request.get("command", "call")
                try:
                    if navigator is None and command != "stop":
                        raise RuntimeError(ready_error or "navigator unavailable")
                    if command == "stop":
                        conn.sendall((json.dumps({"ok": True, "text": "stopped"}) + "\n").encode())
                        return
                    if command == "status":
                        payload = {"ok": ready_error is None, "text": json.dumps(
                            {"solution": solution, "pid": os.getpid(), "loadSeconds": load_seconds,
                             "error": ready_error})}
                    elif command == "list-tools":
                        payload = {"ok": True, "text": json.dumps(navigator.list_tools(), indent=2)}
                    else:
                        payload = {"ok": True, "text": navigator.call(request["tool"], request.get("args") or {})}
                except Exception as exc:
                    payload = {"ok": False, "text": f"{type(exc).__name__}: {exc}"}
                conn.sendall((json.dumps(payload) + "\n").encode())
    finally:
        if navigator is not None:
            navigator.stop()
        if os.path.exists(sock_path):
            os.unlink(sock_path)


def connect(sock_path):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(LOAD_TIMEOUT + 60)
    client.connect(sock_path)
    return client


def ensure_daemon(solution, sock_path):
    """Returns a connection to this solution's daemon, spawning it if it is not already up."""
    if os.path.exists(sock_path):
        try:
            return connect(sock_path)
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            os.unlink(sock_path)
    os.makedirs(SOCKET_DIR, exist_ok=True)
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--daemon", solution, sock_path],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    deadline = time.time() + 60
    while time.time() < deadline:
        if os.path.exists(sock_path):
            try:
                return connect(sock_path)
            except OSError:
                pass
        time.sleep(0.3)
    raise SystemExit("roslyn-query: daemon failed to start")


def send(solution, request, spawn=True):
    sock_path = socket_path(solution)
    if not spawn and not os.path.exists(sock_path):
        return {"ok": True, "text": json.dumps({"solution": solution, "running": False})}
    client = ensure_daemon(solution, sock_path)
    with client:
        client.sendall((json.dumps(request) + "\n").encode())
        return json.loads(client.makefile("r").readline())


def main(argv):
    if len(argv) >= 2 and argv[0] == "--daemon":
        serve(argv[1], argv[2])
        return 0
    if not argv:
        print(__doc__)
        return 1

    solution = resolve_solution(argv[0])
    rest = argv[1:] or ["--status"]
    flag = rest[0]

    if flag in ("--status", "--stop", "--list-tools", "--restart"):
        if flag == "--restart":
            send(solution, {"command": "stop"}, spawn=False)
            time.sleep(0.5)
            flag = "--status"
        response = send(solution, {"command": flag.lstrip("-")}, spawn=(flag != "--stop"))
    else:
        arguments = json.loads(rest[1]) if len(rest) > 1 else {}
        response = send(solution, {"command": "call", "tool": flag, "args": arguments})

    print(response["text"])
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

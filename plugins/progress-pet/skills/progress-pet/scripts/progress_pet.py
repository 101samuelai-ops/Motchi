#!/usr/bin/env python3
"""Local project checklist and pet panel. Python standard library only."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import fcntl

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MAX_BODY = 256_000


def validate(state):
    if not isinstance(state, dict) or not isinstance(state.get("name"), str):
        raise ValueError("Invalid project file: a project name is required")
    if not 1 <= len(state["name"].strip()) <= 100:
        raise ValueError("Project name must be 1–100 characters")
    tasks = state.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > 1000:
        raise ValueError("Project must contain a list of at most 1,000 tasks")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Invalid task")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id or task_id in ids:
            raise ValueError("Task IDs must be unique strings")
        ids.add(task_id)
        if not isinstance(task.get("title"), str) or not 1 <= len(task["title"].strip()) <= 300:
            raise ValueError("Task titles must be 1–300 characters")
        if type(task.get("done")) is not bool:
            raise ValueError("Task completion must be true or false")
    if type(state.get("revision", 0)) is not int or state.get("revision", 0) < 0:
        raise ValueError("Invalid project revision")
    return state


class Store:
    def __init__(self, project):
        self.project = Path(project).expanduser().resolve()
        if not self.project.is_dir():
            raise ValueError("Project directory does not exist")
        self.path = self.project / ".progress-pet.json"
        self.lock = threading.Lock()

    def read(self):
        if not self.path.exists():
            return {"name": "My project", "tasks": [], "revision": 0}
        try:
            return validate(json.loads(self.path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError("Project file is invalid JSON; repair it before saving") from exc

    def change(self, update, revision=None):
        # A file lock coordinates CLI updates with all panel processes on macOS/Linux.
        with self.lock, (self.project / ".progress-pet.lock").open("a") as lockfile:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
            state = self.read()
            if revision is not None and revision != state.get("revision", 0):
                raise Conflict("Checklist changed elsewhere. Please try again.")
            update(state)
            state["revision"] = state.get("revision", 0) + 1
            validate(state)
            fd, name = tempfile.mkstemp(dir=self.project, prefix=".progress-pet-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    json.dump(state, out, ensure_ascii=False, indent=2)
                    out.write("\n")
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            return state


class Conflict(ValueError):
    pass


def summary(state):
    total = len(state["tasks"])
    completed = sum(task["done"] for task in state["tasks"])
    return {**state, "total": total, "completed": completed,
            "percent": math.floor(completed / total * 100 + 0.5) if total else 0}


def apply_action(state, action):
    kind = action.get("action")
    if kind == "add":
        title = action.get("title")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 300:
            raise ValueError("Enter a task between 1 and 300 characters")
        state["tasks"].append({"id": uuid.uuid4().hex[:12], "title": title.strip(), "done": False})
    elif kind == "rename":
        name = action.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("Enter a project name between 1 and 100 characters")
        state["name"] = name.strip()
    elif kind == "set_done":
        if type(action.get("done")) is not bool:
            raise ValueError("Completion must be true or false")
        task = next((t for t in state["tasks"] if t["id"] == action.get("id")), None)
        if task is None:
            raise ValueError("Task not found")
        task["done"] = action["done"]
        task["manualOverride"] = True
    else:
        raise ValueError("Unknown action")


def serve(store, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, mime="application/json; charset=utf-8"):
            if isinstance(body, dict):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            host = self.headers.get("Host", "")
            valid = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in valid:
                self.send(403, {"error": "Loopback host required"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{item}" for item in valid}:
                self.send(403, {"error": "Cross-origin requests are not allowed"})
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            path = urlsplit(self.path).path
            if path == "/api/project":
                try:
                    self.send(200, summary(store.read()))
                except (ValueError, OSError) as exc:
                    self.send(500, {"error": str(exc)})
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in files:
                self.send(404, {"error": "Not found"})
                return
            filename, mime = files[path]
            self.send(200, (ASSETS / filename).read_bytes(), mime)

        def do_POST(self):
            if not self.allowed():
                return
            if self.path != "/api/project":
                self.send(404, {"error": "Not found"})
                return
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("JSON required")
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("Invalid request size")
                action = json.loads(self.rfile.read(length))
                if not isinstance(action, dict) or type(action.get("revision")) is not int:
                    raise ValueError("A project revision is required")
                self.send(200, summary(store.change(lambda s: apply_action(s, action), action["revision"])))
            except Conflict as exc:
                self.send(409, {"error": str(exc)})
            except (ValueError, UnicodeError) as exc:
                self.send(400, {"error": str(exc)})
            except OSError:
                self.send(500, {"error": "Could not save the project file"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Progress Pet: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Tracking: {store.project}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project directory to track")
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    sub.add_parser("status")
    sub.add_parser("add").add_argument("title")
    sub.add_parser("rename").add_argument("name")
    for command in ("done", "reopen"):
        sub.add_parser(command).add_argument("id")
    args = parser.parse_args()
    try:
        store = Store(args.project)
        if args.command == "serve":
            serve(store, args.port)
            return
        if args.command == "status":
            state = store.read()
        else:
            action = {"action": args.command}
            if args.command == "add":
                action["title"] = args.title
            elif args.command == "rename":
                action["name"] = args.name
            else:
                action.update(action="set_done", id=args.id, done=args.command == "done")
            state = store.change(lambda s: apply_action(s, action))
        print(json.dumps(summary(state), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"Progress Pet: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

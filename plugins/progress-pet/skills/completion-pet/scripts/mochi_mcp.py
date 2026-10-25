#!/usr/bin/env python3
"""MCP clarification tool: return a human's Mochi reply to the calling Codex run."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from dog_bridge import atomic_json, hub_dir

OWNER = uuid.uuid4().hex

TOOL = {
    "name": "ask_user",
    "description": "Ask the user an ordinary project clarification through Mochi, their desktop dog. Returns their reply to this exact Codex run. If status is waitingForReply, keep calling wait_for_reply with the returned question_id until answered or expired. Use when Progress Dog is active. Do not use for permissions, authentication, purchases, or approval decisions; keep those in Codex's own approval UI. The Mac companion must be running. Closing the popup does not answer the question.",
    "inputSchema": {"type": "object", "properties": {
        "project_path": {"type": "string", "description": "Absolute current project directory."},
        "project_name": {"type": "string", "maxLength": 100},
        "question": {"type": "string", "minLength": 1, "maxLength": 3000},
        "options": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 6},
        "thread_id": {"type": "string", "description": "Current Codex chat UUID, only if known. Never guess."}
    }, "required": ["project_path", "project_name", "question"], "additionalProperties": False},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
}


def ask_user(args, cancel=None, root=None, timeout=540):
    if not isinstance(args, dict):
        raise ValueError("Question arguments must be an object.")
    path = args.get("project_path")
    question = args.get("question")
    name = args.get("project_name")
    options = args.get("options", [])
    if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_dir():
        raise ValueError("Choose an existing absolute project directory.")
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 3000:
        raise ValueError("A question must have 1–3,000 characters.")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Provide a project name of 1–100 characters.")
    if not isinstance(options, list) or len(options) > 6 or any(not isinstance(o, str) or not 1 <= len(o) <= 200 for o in options):
        raise ValueError("Provide at most six short text options.")
    tid = args.get("thread_id")
    if tid:
        uuid.UUID(tid)
    root = root or hub_dir()
    requests = root / "questions"
    requests.mkdir(mode=0o700, exist_ok=True)
    key = uuid.uuid4().hex
    record = {"id": key, "cwd": str(Path(path).resolve()), "title": name.strip(),
              "threadId": tid or None, "question": question.strip(), "options": options,
              "createdAt": time.time(), "expiresAt": time.time() + timeout, "status": "pending", "source": "mochi", "owner": OWNER}
    target = requests / (key + ".json")
    response = requests / (key + ".reply.json")
    atomic_json(target, record)
    return wait_for_reply(key, cancel, root, min(45, timeout))


WAIT_TOOL = {
    "name": "wait_for_reply",
    "description": "Continue waiting for a Mochi ask_user question. Call again whenever status is waitingForReply; do not guess or end the project turn while the user is still deciding. Each wait is shorter than Codex's default tool timeout. Use only the question_id returned by your own ask_user call.",
    "inputSchema": {"type": "object", "properties": {"question_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"}}, "required": ["question_id"], "additionalProperties": False},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
}


def wait_for_reply(key, cancel=None, root=None, wait_seconds=45):
    import re
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{32}", key):
        raise ValueError("Use the exact question_id returned by ask_user.")
    root = root or hub_dir()
    folder = root / "questions"
    target, response = folder / (key + ".json"), folder / (key + ".reply.json")
    record = json.loads(target.read_text())
    if record.get("status") != "pending":
        raise ValueError("This question has already been answered or closed.")
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if cancel and cancel.is_set():
            record["status"] = "closed"
            atomic_json(target, record)
            raise RuntimeError("The Codex question was cancelled. No answer was submitted.")
        if time.time() >= record["expiresAt"]:
            break
        if response.exists():
            with (folder / (key + ".lock")).open("a") as lock:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX)
                record = json.loads(target.read_text())
                if record.get("status") != "pending":
                    raise ValueError("This question has already been answered or closed.")
                reply = json.loads(response.read_text())
                if reply.get("questionId") == key and isinstance(reply.get("text"), str) and reply["text"].strip():
                    record.update(status="answered", answeredAt=time.time())
                    atomic_json(target, record)
                    response.unlink(missing_ok=True)
                    return {"answer": reply["text"], "project": record["title"], "question": record["question"]}
        if cancel:
            cancel.wait(.1)
        else:
            time.sleep(.1)
    if time.time() < record["expiresAt"]:
        return {"status": "waitingForReply", "question_id": key,
                "instruction": "The user has not answered yet. Call wait_for_reply with this question_id. Do not guess the answer or create another question."}
    record["status"] = "closed"
    atomic_json(target, record)
    response.unlink(missing_ok=True)
    raise TimeoutError("Mochi received no reply before the question expired. Ask in Codex instead.")


def main():
    lock = threading.Lock()
    active = {}
    workers = ThreadPoolExecutor(max_workers=8)
    def emit(value):
        with lock:
            print(json.dumps({"jsonrpc": "2.0", **value}, ensure_ascii=False), flush=True)
    def answer(rid, params, cancel):
        try:
            name = params.get("name")
            if name == "ask_user":
                result = ask_user(params.get("arguments", {}), cancel)
            elif name == "wait_for_reply":
                result = wait_for_reply(params.get("arguments", {}).get("question_id"), cancel)
            else:
                raise ValueError("Unknown Mochi tool.")
            emit({"id": rid, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}})
        except Exception as exc:
            emit({"id": rid, "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}})
        finally:
            active.pop(rid, None)
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                rid, method, params = request.get("id"), request.get("method"), request.get("params") or {}
                if method == "notifications/cancelled":
                    flag = active.get(params.get("requestId"))
                    if flag:
                        flag.set()
                elif rid is None:
                    continue
                elif method == "initialize":
                    emit({"id": rid, "result": {"protocolVersion": params.get("protocolVersion", "2024-11-05"),
                          "capabilities": {"tools": {}}, "serverInfo": {"name": "mochi", "version": "0.10.0"}}})
                elif method == "ping":
                    emit({"id": rid, "result": {}})
                elif method == "tools/list":
                    emit({"id": rid, "result": {"tools": [TOOL, WAIT_TOOL]}})
                elif method == "tools/call":
                    if len(active) >= 8 or rid in active:
                        emit({"id": rid, "error": {"code": -32000, "message": "Mochi has too many pending questions. Try again later."}})
                        continue
                    cancel = threading.Event()
                    active[rid] = cancel
                    workers.submit(answer, rid, params, cancel)
                else:
                    emit({"id": rid, "error": {"code": -32601, "message": "Unknown method"}})
            except (ValueError, TypeError, AttributeError):
                emit({"id": None, "error": {"code": -32700, "message": "Invalid JSON-RPC request"}})
    finally:
        for cancel in list(active.values()):
            cancel.set()
        workers.shutdown(wait=True)
        for path in (hub_dir() / "questions").glob("*.json"):
            if path.name.endswith(".reply.json"):
                continue
            try:
                record = json.loads(path.read_text())
                if record.get("owner") == OWNER and record.get("status") == "pending":
                    record["status"] = "closed"
                    atomic_json(path, record)
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    main()

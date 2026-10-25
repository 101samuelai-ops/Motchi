#!/usr/bin/env python3
"""Build and run the local macOS cursor completion companion."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--pet", choices=("dog",), default="dog", help="Dog animation (only supported companion)")
    parser.add_argument("--report-on-start", action="store_true", help="Open the live cursor progress report after starting")
    parser.add_argument("--report", action="store_true", help="Ask this project's running watcher to show its live progress report")
    parser.add_argument("--self-test", action="store_true", help="Check the native double right-click recognizer")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--preview-on-start", action="store_true", help="Show a labeled preview, then keep watching")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--prepare-app", action="store_true", help="Prepare a double-clickable Mac app instead of running in this terminal")
    parser.add_argument("--replace", action="store_true", help="Replace an older watcher for this same project")
    parser.add_argument("--stop", action="store_true", help="Ask this project's dog watcher to stop")
    parser.add_argument("--render-preview", help="Export the animation frames for visual review")
    parser.add_argument("--duration", type=float, default=1.5, help="Total announcement lifetime including animation (default 1.5; 0.5–60)")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    if sys.platform != "darwin":
        parser.error("The desktop companion requires macOS")
    if not project.is_dir():
        parser.error("Project directory does not exist")
    if not 0.5 <= args.duration <= 60:
        parser.error("Duration must be between 0.5 and 60 seconds")
    cache = Path(tempfile.gettempdir()) / f"progress-pet-desktop-{os.getuid()}"
    cache.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(str(project).encode()).hexdigest()[:24]
    if args.stop:
        (cache / "hub.lock.stop").write_text("stop\n")
        (cache / f"{key}.lock.stop").write_text("stop\n")
        print("Stop request sent to this project's Progress Dog watcher.")
        return
    if args.report:
        (cache / "hub.lock.report").write_text("report\n")
        print("Report request sent. The project's Progress Dog watcher must be running.")
        return
    compiler = shutil.which("swiftc")
    if not compiler:
        parser.error("Swift is unavailable. Apple's command line tools are required.")
    source = Path(__file__).with_name("CompletionPet.swift")
    digest = hashlib.sha256(b"".join(source.with_name(n).read_bytes() for n in ("CompletionPet.swift", "dog_bridge.py", "dialog.html", "codex_control.py", "checklist_sync.py", "hook_approvals.py")) + (source.parent.parent.parent / "progress-pet/scripts/progress_pet.py").read_bytes()).hexdigest()[:16]
    build = cache / digest
    bundle = build / "Mochi.app"
    binary = bundle / "Contents" / "MacOS" / "CompletionPet"
    with (cache / "build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not binary.exists():
            binary.parent.mkdir(parents=True, exist_ok=True)
            print("Building desktop companion (first launch)…", flush=True)
            temporary = binary.with_suffix(".building")
            subprocess.run([compiler, str(source), "-module-cache-path", str(cache / "modules"),
                            "-o", str(temporary)], check=True)
            info = {"CFBundleIdentifier": "local.progress-pet.completion.dog", "CFBundleName": "Mochi",
                    "CFBundleExecutable": "CompletionPet", "CFBundlePackageType": "APPL", "LSUIElement": True,
                    "NSHighResolutionCapable": True}
            (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
            temporary.replace(binary)
    if args.self_test:
        os.execv(str(binary), [str(binary), "--self-test"])
    if args.render_preview:
        os.execv(str(binary), [str(binary), "--render-preview", str(Path(args.render_preview).resolve())])
    if args.prepare_app:
        app_key = "hub.dog" + ("-preview" if args.preview else "")
        app = cache / "apps" / app_key / digest / "Mochi.app"
        executable = app / "Contents" / "MacOS" / "CompletionPet"
        resources = app / "Contents" / "Resources"
        executable.parent.mkdir(parents=True, exist_ok=True)
        resources.mkdir(parents=True, exist_ok=True)
        staged = executable.with_suffix(".new")
        shutil.copy2(binary, staged)
        staged.replace(executable)
        info = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
        info["CFBundleIdentifier"] = "local.progress-pet.hub.v" + digest[:8]
        (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
        for asset in ("dog_bridge.py", "dialog.html", "codex_control.py", "checklist_sync.py", "hook_approvals.py"):
            shutil.copy2(source.with_name(asset), resources / asset)
        shutil.copy2(source.parent.parent.parent / "progress-pet/scripts/progress_pet.py", resources / "progress_pet.py")
        configuration = {"--project": str(project), "--pet": args.pet, "--duration": str(args.duration),
                         "--lock": str(cache / "hub.lock"), "--preview": args.preview, "--once": args.once,
                         "--preview-on-start": args.preview_on_start, "--report-on-start": args.report_on_start,
                         "--replace": args.replace, "--replace-prefix": "local.progress-pet.hub", "--python": sys.executable,
                         "--log": str(app.parent / "events.log")}
        (resources / "launch.json").write_text(json.dumps(configuration), encoding="utf-8")
        print(f"Desktop app ready: {app}", flush=True)
        print("Open this app to start. Use its dog menu to preview or quit.", flush=True)
        return
    command = [str(binary), "--project", str(project), "--pet", args.pet,
               "--duration", str(args.duration), "--lock", str(cache / "hub.lock"),
               "--replace-prefix", "local.progress-pet.hub", "--python", sys.executable,
               "--bridge", str(source.with_name("dog_bridge.py")), "--dialog", str(source.with_name("dialog.html"))]
    for flag in ("preview", "once", "preview-on-start", "report-on-start", "replace"):
        if getattr(args, flag.replace("-", "_")):
            command.append(f"--{flag}")
    os.execv(str(binary), command)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        sys.exit("Progress Pet: Swift compilation failed; see the compiler diagnostics above.")
    except OSError as exc:
        sys.exit(f"Progress Pet: {exc}")

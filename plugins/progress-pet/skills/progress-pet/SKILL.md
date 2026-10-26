---
name: progress-pet
description: Maintain a project checklist and open a clickable anime dog with a circular completion meter when the user asks to use Progress Dog or track project completion with it.
---

Use `scripts/progress_pet.py` relative to this skill folder. It needs Python 3.9+ and no packages. Resolve the user's current project directory; never use this plugin's installation directory as the project by default. If no project is attached or identifiable, ask which directory to track.

The state is `<project>/.progress-pet.json`. Run all commands with an absolute project path:

```sh
python3 /absolute/path/to/skill/scripts/progress_pet.py --project /absolute/project status
python3 /absolute/path/to/skill/scripts/progress_pet.py --project /absolute/project add "Implement sign in"
python3 /absolute/path/to/skill/scripts/progress_pet.py --project /absolute/project done TASK_ID
python3 /absolute/path/to/skill/scripts/progress_pet.py --project /absolute/project reopen TASK_ID
python3 /absolute/path/to/skill/scripts/progress_pet.py --project /absolute/project rename "My project"
python3 /absolute/path/to/skill/scripts/progress_pet.py --project /absolute/project serve
```

When opening, start the server as a persistent terminal process, read its printed loopback URL, and use `open_in_codex` with a browser target if available. Otherwise return the URL. Reuse an existing server for the same project when known. Each project can use a different `serve --port NUMBER`; `--port 0` chooses a free port.

Plan tasks with a concrete definition of done. Reuse existing tasks and IDs; check status before adding duplicates. Mark a task complete only when the work and relevant checks are finished, and reopen it if new evidence invalidates completion. While the user is using Progress Dog on a project, update its checklist as the agreed tasks change. Do not treat lack of activity, elapsed time, message counts, or lines of code as completion.

When setting up Progress Dog on macOS, start the bundled `completion-pet` companion unless the user requests only the panel. It slowly pulls an anime dog out at the primary screen’s top right when all tasks finish. Double right-click anywhere on the Mac to open its interactive dog dialog at the primary screen’s top right. Click outside to dismiss. Auto follows working local Codex chats; naming a project in a question routes to that topic. Picker changes pin a project. Progress questions read actual checklists, current Codex task plans, and visible assistant updates without a model call. Newly observed tasks trigger a brief tracking popup with a ground line, leap, landing, and return animation. Keep whole-project checklist scope separate from a single turn’s plan. Approval attention alerts need the user to review and trust the bundled hooks in Codex. When the user wants a secondary Codex question window, use the plugin’s available mochi.ask_user tool for ordinary project clarification; its Reply box returns the answer to the calling run. A waitingForReply result requires mochi.wait_for_reply, not a guessed answer. For tasks started in Motchi, dedicated real approval buttons are supported; other chats keep approvals in Codex. Read that sibling skill for routing limits, launch, shortcut, and preview instructions. Its watcher reads this same checklist, so keep the project name descriptive and leave the watcher running while completing the agreed tasks. The browser panel does not need to remain open for desktop celebrations.

The percentage is rounded completed / total × 100 with equal task weights. Zero tasks is displayed as “No tasks yet”, not as complete. Explain that this measures checklist completion, so changes in task scope can change the percentage. The panel polls the shared file every two seconds; the pet in this panel is separate from any built-in Codex pet. This skill cannot attach a handler to Codex's native pet or permanently change its interface.

Motchi 0.10 adds a collapsible Project checklist with editable boxes and chat/plan reconciliation. Add work to Codex appends user-authorized work to a live owned chat, asking Same task / Different task when similar. Automatic inference never sends prompts. Manual box edits override automatic completion; use the existing locked Store and preserve Motchi source/evidence metadata. Read the sibling completion-pet skill for delivery scope, background inference limits and uncertainty handling.


## History review and progress (0.12)

Motchi queues the available visible local chat history outside the project in `~/Library/Application Support/Mochi/visible-history.sqlite3` (owner-only database access). Review resumes from project checkpoints; the latest-message display window does not limit extraction. One worker reviews bounded batches, retaining failed/unreviewed history for retry. Show the panel's reviewed/available section counts, missing/partial sources and last review time; never imply coverage beyond discovered local chats. Reasoning, general tool output and injected context are excluded; structured user replies retain their question context. Normal signed-in provider usage applies.

Explain automatic additions/completions using their source quotes and chat identity. The checklist panel exposes sources and a revision-checked Undo; manual corrections remain protected. Automatic inference never sends instructions. Progress briefings include remaining tasks, the next unchecked item, recorded user-input blockers and freshness. Do not invent priority, milestone, release readiness or missing blockers. Separate idea/decision storage, lifecycle replacements and user-correctable project grouping remain planned. Keep the existing approval routing limits and never restart a running companion with active work just to activate an update.

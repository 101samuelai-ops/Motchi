# Progress Dog · Mochi 0.11.0

Mochi is a dog-only Mac companion and Codex plugin. Double right-click to open Mochi at the primary screen’s top-right corner, independently of your mouse position. A ground line appears first; the dog leaps out, lands, and sits before translucent chat cards unfold, with no solid enclosing background. Click outside to dismiss: the chat fades, Mochi crouches and hops back into its ground line, then the ground line retracts before the window closes. Close, Escape and the menu use the same 780 ms dismissal. Reopening cancels any old close timer. The native desktop has transparent space around the dog; the development preview uses a checkerboard to show that space.

## Install and start

```sh
codex plugin marketplace add /absolute/path/to/mochi
codex plugin add progress-pet@progress-dog-local
```

Start a new Codex project chat and say: **Use Progress Dog to track this project. Ask clarification questions through Mochi.** The new session loads the plugin's local MCP question tools and skills. This is a separate desktop companion, not a modification of Codex's built-in pet.

The supplied **Mochi.app** is built for this Mac (`Progress Dog.app` is a compatibility copy). For another Mac, prepare it with Python 3.9+ and Apple's Swift command line tools:

```sh
python3 skills/completion-pet/scripts/completion_pet.py --project /absolute/project --prepare-app --replace --report-on-start
```

Open the printed app. One hub handles local projects. Its dog menu shows/hides chat, toggles double right-click, previews completion, and quits. The normal app build does not register startup; the optional Mochi Launcher below does. `--report` reopens the hub; `--stop` stops it. Project discovery and conversational companion answers use the installed Codex CLI and its existing sign-in/provider. Normal provider usage applies to model answers.

## A secondary Codex question window

The plugin supplies **mochi.ask_user**. Codex can call it for an ordinary clarification, with a question, project name/path, and optional choices. The dog opens automatically. Type a reply or click a choice: that answer returns to the **same Codex run** as the tool result. It can continue its work with your answer.

**Reply ↑** identifies a direct question from Codex. **Ask ↑** is the separate read-only companion conversation. The connection does not inject messages into arbitrary already-running desktop chats. A new chat must load the updated plugin, and Codex must ask through Mochi for a reply to return through this channel.

Questions remain pending when the window is dismissed. Reopen with double right-click. Calls wait in intervals below Codex's default tool timeout; the model uses **mochi.wait_for_reply** if you need longer. Questions expire after nine minutes or close when cancelled. Mochi never fabricates an answer.

The ordinary MCP clarification tool is not an approval channel. Real permission replies use the dedicated live task integration below; desktop-only notifications still link to Codex.

## Run Codex and approve inside Mochi

Choose a project, click **Start Codex task**, describe your task, then **Start task ↑**. This creates a separate real Codex chat in that project using your existing sign-in/provider/model. Work uses workspace-write sandboxing and user-reviewed, on-request approvals. It does not transfer an existing desktop chat into Mochi.

When that task needs permission, Mochi shows the exact request with **Allow once**, **Deny**, and **Ask about this request**. Ask as many follow-up questions as needed; the original request stays pending. Only clicking a decision button sends the real app-server reply. Native filesystem/network grants include only the captured requested access for this turn. Command/file approvals return the real supported decision, with no new always-allow rule. Typing “yes”, dismissing the dog, or a model explanation never approves anything.

Use **Add work to Codex** for additional work in an active or idle Mochi task, or **Ask Mochi** for a read-only companion question. **Stop task** interrupts the connected turn. Built-in ordinary questions from these live tasks are also answerable here. Opening the chat in Codex is supported; do not start a second client working on the same chat concurrently.

Keep Mochi open while its tasks run. Restarting/quitting closes their control connection, invalidates pending approval IDs, and never replays an old decision. Saved Mochi tasks appear disconnected after restart; explicitly send a new instruction to resume their history. Runtime approval contents/commands are not stored in Mochi’s registry. Explanation-provider failure leaves the original request pending with an explicit error.

**Existing chats can reply through a trusted synchronous PermissionRequest hook.** Mochi shows the exact tool input, **Allow once**, **Deny**, and **Ask about this request**. The choice is returned by the original waiting hook, so no new chat or trip back to Codex is needed for supported requests. One-time exact hook review in Codex `/hooks` and session reload are required. Installation does not grant trust. No global approval policy or trust records are changed. An already displayed native card cannot be taken over retroactively. Native `functions.request_permissions` card coverage remains unverified: log-only requests retain Review in Codex. This CLI version labels its native permission tool under development; Mochi enables that feature only in its own process.

## Additional work and the project checklist

Open **Project checklist** to see and edit the boxes. The progress ring uses completed / total project tasks. **＋ Checklist task** adds an item without sending work. **Add work to Codex** saves a task and sends its full instructions into the selected Mochi-owned chat: `turn/steer` targets the exact active turn, or `turn/start` starts a follow-up in the same idle chat. If that turn ends before steering is accepted, Mochi does not silently send it to another turn. Timeouts are marked uncertain and never retried automatically. Existing desktop-only chats support checklist edits and **Open in Codex**, but cannot receive injected prompts on this installation.

Similar additions pause with **Same task**, **Different task**, or **Skip**. Same reuses the existing ID and reopens a completed item when the user is adding work. Different adds a separate item. Only explicit additional-work submissions deliver prompts; automatic checklist inference never instructs Codex to execute something. Pending approvals/questions must be answered before more work is sent. A confirmed unsent prompt stays in the checklist panel with **Send saved task**; uncertain deliveries must be checked in Codex.

Mochi reconciles recorded Codex plans and the recent visible chat history in each local project. Structured plans update immediately; a background read-only Codex extraction handles conversational tasks and semantic similarity using the existing provider/sign-in. Normal model usage applies. It coalesces unchanged histories, uses one background worker, and limits each project to one attempt per minute. It reads up to 24 recent messages per chat and 32 messages per project batch; it does not claim to reconstruct arbitrarily old or unavailable history. Reasoning and general tool outputs are excluded. Model failure leaves recorded plans and manual edits available, with a visible sync notice.

Completion needs an explicit completed plan step or a matching assistant statement confirming that task finished. Intentions, silence and turn completion do not check boxes. Historical finished work can be reconstructed with its completion evidence. Manually checked/unchecked boxes are preserved against automatic changes. Task evidence can be viewed by hovering its title. Similar automatic proposals ask before merging. Checklist IDs, decisions, evidence snippets and delivery state persist under `.progress-pet.json`; full transcripts remain in memory. Plan steps retain their own source identities so polling cannot create duplicates. Store locking and revision checks coordinate the companion, CLI and browser checklist.

## Existing question and approval alerts

Codex requires you to review and trust plugin hooks before they run. Use **/hooks** in the Codex CLI to review this plugin's definitions, then start/reload the sessions you want connected. [Official hook review documentation](https://developers.openai.com/codex/hooks#review-and-trust-hooks). New or changed definitions require review again; installation alone does not trust them.

Once loaded and trusted, hooks mirror permission requests, supported built-in user-input tools, and final assistant messages ending in a question. Mochi opens the named project with a link to answer/review **in Codex**. These hooks always return `{}`; they never approve/deny actions or change Codex's tools. They do not capture every possible natural-language or remote/cloud prompt. The direct Mochi MCP clarification tool works independently of hook trust once enabled and loaded.

Recognized built-in question calls in validated local session logs also trigger Mochi without hook trust. Async delivery acknowledgements keep requests pending; matching user replies clear them. New alerts take priority over the selected chat while preserving drafts and in-flight replies. If permission and clarification requests coexist, both remain visible. Built-in questions are answered in Codex; direct Mochi questions accept replies in the popup.

Native **“Allow ChatGPT to edit the contents of …?”** filesystem requests and network-access requests now also trigger Mochi from validated local logs, without requiring hook trust. The dog shows the reason and requested access with **Review in Codex**. It remains an interactive alert, not a 1.5-second announcement: use Codex’s actual Allow/Deny card. Matching granted/denied results, interruption, or task ending clear the request. An exec “still running” acknowledgement keeps it pending. Dismissing the dog hides the view; double right-click reopens it.

This compatibility adapter supports direct `request_permissions` calls and a standalone `text(await tools.request_permissions({...}));` or `await tools.request_permissions({...});` exec call containing only a literal argument object (double-quoted strings). It never evaluates JavaScript or searches arbitrary scripts for permission-like text. Permission requests hidden inside variable-driven or multi-statement scripts are not covered by this adapter; supported trusted approval hooks remain available. Remote/cloud-only requests are not covered.

Local temporary question records hold the question/choices and routing metadata needed for replies. Hook records hold short question/approval text and project/session activity; they do not copy full transcripts, commands, or credentials. Cancelling or resolving a request clears its popup state. Dismissed pending requests do not repeatedly reopen.

## Projects, progress, and companion chat

**Auto** follows the latest working local Codex chat by default. No picker is required. Mention an exact chat/project title in your question to select it automatically: **“what has World Trigger done?”** A picker change pins that project; click Auto to resume. Typing and in-flight answers hold routine selection, and an answered conversation stays on its topic until a newly observed task begins. Project histories and drafts stay separate.

The catalog reads up to 100 non-archived local chats from Codex's metadata API. Its catalog-provided local session files supply explicit task starts/stops, visible assistant updates, update_plan steps, and recognized built-in question requests. The reader validates each path and chat ID and ignores reasoning and general command arguments/results. Only recognized question fields, literal permission reasons/scopes, matching response IDs and the execution-status header for known permission calls are read for input alerts. This log adapter is version-dependent, reads without resuming or modifying chats, and falls back to trusted hooks when available. Remote/cloud-only work and the currently focused Codex window are not detected. The catalog refreshes about every fifteen seconds, and known local task activity every two seconds.

A newly observed ongoing task makes a compact dog notification appear at the **top right of the primary display**, say **“I’m tracking the progress of [project]”**, and hop back into its ground line after its short message. All automatic popups now appear at the top right, including permission/question prompts, returned answers and project completion. Manual shortcut chat also opens at the top right. Tracking announcements last **1.5 seconds total**, including a 280 ms entrance and a 200 ms fade. Their timer starts when the window becomes visible, after page loading. Notifications are deduplicated per turn. They do not replace an open conversation or question, and old exit timers cannot close a manually opened dialog. Keep the companion running while Codex works, or enable the optional launcher below.

The ring uses completed tasks ÷ total tasks from the project checklist or the current Codex task plan. Task-plan progress is clearly labeled and never counted as whole-project completion. Missing or invalid plans/checklists do not imply completion; activity and recorded updates remain available.

**Progress**, **What's left?**, **Catch me up**, and natural questions such as **“what has been done?”** use recorded project facts directly. They work without waiting for a model, including when a checklist is absent. Other questions use the configured Codex provider in an ephemeral read-only context-only conversation. A final result is consumed immediately rather than waiting for CLI shutdown. On connection failure/delay, Mochi returns an explicitly labeled latest recorded update. That fallback does not pretend to answer a question whose answer is unavailable. Ask mode never modifies or steers the actual project run. If you dismiss Mochi while it is answering, the answer or connection error reopens that project’s conversation at the top right. It also cancels an in-progress dismissal. Returned answer dialogs remain open for reading; permission/question dialogs wait for your input. A visible conversation receives its answer in place, and pending permission/question requests take priority over queued answer popups. Enter sends; Shift+Enter inserts a newline.

## Appearance and completion

The native window, web canvas, and space around the dog are transparent. A ground line expands at the top-right corner, the dog leaps out and lands over 1.42 seconds, then chat cards appear at 1.48 seconds. Tracking announcements use a 280 ms entrance and a 200 ms exit fade within their 1.5-second lifetime. Reduce Motion shows them directly. The original right-click events are passed through, so the underlying app may also show a context menu. The popup stays where it opened; it does not follow cursor movement or monitor global keystrokes.

Finishing any observed local project's nonempty checklist triggers the 350 ms dog reveal at the top right with **“Project name” is done!** The whole announcement lasts **1.5 seconds**, including its 350 ms reveal and final 200 ms fade. `--duration` overrides the total lifetime if desired. Celebrations wait while chat, another celebration, or a permission/question request is open. Completion receipts prevent repeated celebrations. Observing an incomplete checklist rearms it.

## Checklist and original panel

```sh
python3 skills/progress-pet/scripts/progress_pet.py --project /absolute/project status
python3 skills/progress-pet/scripts/progress_pet.py --project /absolute/project rename "Website launch"
python3 skills/progress-pet/scripts/progress_pet.py --project /absolute/project add "Finish sign in"
python3 skills/progress-pet/scripts/progress_pet.py --project /absolute/project done TASK_ID
python3 skills/progress-pet/scripts/progress_pet.py --project /absolute/project reopen TASK_ID
python3 skills/progress-pet/scripts/progress_pet.py --project /absolute/project serve --port 0
```

The original clickable dog browser panel and desktop companion share `<project>/.progress-pet.json`. IDs come from status. Optionally ignore `.progress-pet.json`, `.progress-pet.lock`, and `.progress-pet-completion.json` in Git.

## Validation

Run `tests/check_behavior.py`, `tests/check_dog_hub.py`, `tests/check_codex_questions.py`, `tests/check_auto_tracking.py`, `tests/check_attention.py`, `tests/check_permissions.py`, `tests/check_codex_control.py`, `tests/check_control_http.py`, and `tests/check_checklists.py`. They cover incremental task observation, partial log appends, task/project isolation, automatic topic routing, resilient replies, persistence, request validation, project/reply isolation, hooks that never make decisions, deduplication, cancellation/expiry, and MCP discovery. The native `--self-test` verifies double-click recognition, corner placement, the 1.5-second announcement timing, answer routing after dismissal, duplicate suppression and concurrent reply isolation. Both skills pass Codex skill validation. Live validation sent a real question from Codex through the installed MCP tool, typed its answer into Mochi, and confirmed that exact answer returned to Codex. Use `dog_bridge.py --project /absolute/project --preview-server` for the local development preview.

## Activate existing-chat decisions

1. Open the packaged Mochi 0.11.0 app and update the Progress Dog plugin.
2. In Codex CLI, open `/hooks` and review/trust Mochi's user **PermissionRequest** command (`--permission-hook`, timeout 600). This user review is mandatory in Codex.
3. Start/reload the relevant Codex session. Future supported permission requests can wait in Mochi for up to nine minutes.
4. Click **Allow once** or **Deny**, or use **Ask about this request** before choosing. Closing the dog never approves.

The implemented hook path covers documented shell, apply_patch, MCP and managed-network approvals when Codex invokes it. Separate desktop filesystem/network permission cards are not yet verified to invoke it. The hook transport is tested with real separate waiting processes, not claimed as a completed desktop end-to-end test.

### User hook registration

Run `python3 /absolute/installed/plugin/skills/completion-pet/scripts/install_approval_hook.py` once after updating the plugin. It merges the dedicated synchronous PermissionRequest command into `~/.codex/hooks.json`, preserving other hooks and backing up an existing file. It never trusts hooks or alters approval policy. This registration is necessary on installations where the CLI does not discover bundled plugin hooks. The plugin bundle intentionally omits PermissionRequest to avoid duplicate handlers. Review the exact user hook in `/hooks`; non-permission bundled hooks are observation only.

## Live verification, 2026-10-22

The registered user PermissionRequest hook is now trusted and enabled. A real shell escalation request reached Mochi and its Deny button resolved the original waiting hook; the originating Codex task resumed and confirmed denial. The separate built-in request_permissions filesystem test bypassed the hook. Native filesystem/network permission cards remain Review in Codex; they are not made answerable by this hook registration.

## Open Mochi automatically with Codex

The optional **Mochi Launcher** is a small, local macOS helper. It starts at login, watches for the Codex desktop app, and quietly opens Mochi. It preserves an already-running companion and its live tasks. Closing Codex leaves Mochi running. If you quit Mochi manually, it stays closed until Codex opens again. No Accessibility permission is required.

Build and install the stable helper and companion copies:

```sh
python3 skills/completion-pet/scripts/install_autolaunch.py --install --login-app --app /absolute/path/Mochi.app
```

In **System Settings → General → Login Items & Extensions → Open at Login**, add `~/Library/Application Support/Mochi/Mochi Launcher.app`. Open that helper once to enable it immediately; subsequent logins start it automatically. Register the login helper separately on each Mac. Its first live launch on the development Mac detected Codex and opened Mochi successfully.

The installed app is `~/Library/Application Support/Mochi/Mochi.app`. Launcher status is in `~/Library/Application Support/Mochi/Launcher/status.json`; local logs are in `~/Library/Logs/Mochi/launcher.log`. The launcher only detects the desktop bundle `com.openai.codex`, not arbitrary CLI processes. To disable startup, remove **Mochi Launcher** from Open at Login; logging out stops the current helper. This does not uninstall Mochi or change approval hooks.

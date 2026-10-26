# Checklist review milestone — Motchi 0.12

Implemented and checked during 2026-10-25–27. The user selected reliable chat-derived checklist updates and better progress discussion before character customization. This is source and prepared-build verification; the installed companion has not been restarted or replaced.

## What changed

The previous extractor only saw the last 24 visible messages per chat and 32 messages per project batch. The new adapter queues available visible messages from the beginning of each discovered local rollout, then follows append operations. Question-answer messages retain the question and answer; injected workspace/browser context, reasoning and arbitrary tool results are excluded.

A private owner-readable SQLite database lives in the existing Mochi application-support folder, outside source repositories. Log byte positions remain in memory and can be reconstructed after restart. Stable message section identities deduplicate the replay. A database generation plus monotonic queue sequence forms the persisted project review checkpoint; newly discovered old messages are not skipped because their timestamps are old. If the private queue is recreated, generation mismatch causes available history to be reviewed again while checklist source identities preserve existing decisions.

One worker processes bounded batches: up to 12 new sections, up to 24,000 new characters, plus three reviewed sections for context. Long messages have overlapping sections rather than a discarded beginning. Only a successful, structurally valid inference and applied reconciliation advance the checkpoint. Failures retain unreviewed history and show a retry notice. The model uses the user's configured signed-in provider in an ephemeral read-only Codex run. A final output file is consumed immediately; CLI shutdown is no longer required before accepting a result. This follows the documented [Codex noninteractive structured-output interface](https://developers.openai.com/codex/noninteractive/).

The extractor is instructed to compare all supplied sections and existing tasks, distinguish explicit requests from ideas/questions/rejected suggestions, and require exact source quotes. Runtime validation checks quote identity, source role, manual overrides, task identity and completion chronology. Identical task titles reuse an existing item; ambiguous overlap still needs a user choice. No inferred task can send an execution prompt.

The checklist panel exposes evidence and source-chat controls, history review counts, unavailable/partial sources and last successful review. The native app can open a source chat if it is still in the catalog; the browser preview disables that control. Automatic additions and completions have a compact audit trail. Undo uses the current revision and task contents, preserves checkbox corrections, and prevents replay from re-adding an undone source. Only changes still matching the current task expose Undo. Up to 100 changes are retained, with 12 shown.

Progress briefings answer what remains, show the next unchecked item without inventing priority, list recorded approvals/questions needing the user, include recent source quotes, and explain coverage and freshness. They distinguish checklist percentages from verified release readiness. Richer read-only discussion receives the checklist evidence, review state and pending inputs as context.

## Verified behavior

- All 12 Python `check_*.py` suites passed. The new history suite covers 25 cases, including an 81-message conversation beyond the old window, persisted backlog/checkpoints, completion binding, replay, project isolation, long-message sections, failed/malformed inference, late discovery of older history, source-backed briefings, Undo and protected corrections.
- Both bundled skills pass Codex skill validation.
- Native `CompletionPet --self-test`: 19 shortcut, placement, answer delivery and announcement timing checks passed.
- Browser verification used an isolated synthetic project and the real HTTP controls: evidence and review counts were visible; Undo changed 1/2 completed tasks to 0/2 and marked the correction protected. No live project, approval or instruction was changed.
- A synthetic 12-message model evaluation is provided at `plugins/progress-pet/tests/evaluate_checklist_model.py`. It measures expected/missed actions, false additions, duplicate actions, invalid evidence and unsupported completion claims. In this development sandbox Codex failed to initialize its in-process app-server client with `Operation not permitted`, including after runtime-file access was granted. **No live model accuracy score is claimed.** Run the optional evaluation from an ordinary local terminal before relying on a model-quality claim.

## Remaining boundaries

- Coverage means available history from the up-to-100 discovered non-archived local chats, grouped by exact project folder. Missing, remote/cloud-only and archived conversations are not reconstructed. Oversized/unreadable log records or incomplete appends are reported as partial coverage. Logs and provider availability remain version-dependent.
- Model output can still omit or misclassify requirements. Transport/persistence regressions passing does not establish model accuracy. The checklist remains inspectable and correctable.
- Separate persistent idea/decision collections, scope replacement/deferral/reopening, expand/replace overlap choices, named milestone memory and verified/accepted completion remain planned. CHK-01, CHK-02, CHK-03, PRG-01, PRG-02, CHAT-05 and QA-01 are not marked fully complete.
- Progress only reports recorded questions/approvals as immediate blockers; it states that other blockers or priorities are unknown. A finished turn is not project completion.
- The local queue retains visible history until its database is removed; a user-facing history retention/forget control is not yet implemented. Removing it triggers reconstruction from available local logs. Do not commit it or private checklist evidence.
- Existing approval trust, supported reply routes, launch-helper configuration, top-right placement and 1.5-second routine announcements are unchanged. Do not restart an active companion solely to activate this build.

# Persistent Motchi project memory

Updated: 2026-10-25. This file is durable project memory for future development sessions; it does not implement a user-facing memory engine by itself.

## Product intent

The user wants Motchi to analyze each project's progress, discuss status, accept additional work through conversation, and continually recognize checklist commitments and completion evidence in available project conversations. The experience should reduce manual project management while making corrections easy.

## Agreed next work

The user approved converting the preceding product analysis into the progress checklist in `../ROADMAP.md`. Priorities: P1 trustworthy understanding; P2 natural discussion and delivery; P3 returning to work and multiple projects; P4 deeper personalization and optional weighting/forecasting. Saving this roadmap is not authorization to implement every item in this setup turn.

## Existing user preferences

- Dog-only anime companion; transparent space around the dog.
- Popups at the primary screen's top right; ground line, leap, landing, then chat; animated return on dismissal.
- Double right-click opens the companion; click outside dismisses it.
- Routine tracking/completion announcements last 1.5 seconds. Questions, approvals and returned answers remain available for reading and action.
- If dismissed while answering, return the answer at the top right.
- Follow the appropriate project automatically and preserve project-specific conversations and drafts.
- Supported real approvals should be answerable in Motchi, with a way to ask about the request first. Never fabricate an approval path for unsupported native cards.
- Launch Motchi automatically when Codex desktop opens. The installed login helper was verified on 2026-10-24.

## Product decisions

- Capture commitments, ideas and unresolved decisions separately. Brainstorming alone does not add committed scope.
- Preserve stable task identities; resolve overlap as expand, replace, separate or skip.
- Keep source evidence, manual corrections and an undoable change history.
- Explain progress through milestone scope, blockers and freshness; task counts are not precise effort estimates.
- Separate implemented, verified and accepted states when the project requires them.
- Observing and extracting tasks must not silently instruct Codex to execute them. Work delivery follows an explicit user instruction and reports actual transport status.
- Memory must be inspectable, correctable, forgettable and scoped. Do not infer sensitive personal traits as preferences.
- Use incremental observations and persistent task/decision records; do not imply complete history coverage when only recent local chats are available.
- Keep routine updates quiet and aggregate nonurgent changes. Maintain an inbox for dismissed actionable items.

## Current limits to preserve in explanations

The existing source already has local project discovery, recent-history checklist inference, similarity clarification, read-only answers and additional-work delivery to Motchi-owned chats. These are foundations, not proof that the new roadmap acceptance criteria pass. Arbitrary existing desktop chats cannot universally be steered. Native filesystem/network cards still need their native approval interface when no supported live reply route exists. Do not modify Codex hook trust or weaken approval rules.

## Repository and maintenance

Requested GitHub account: the authenticated `101samuelai-ops` account. Canonical repository: https://github.com/101samuelai-ops/Motchi (public, created by the user). On 2026-10-25 the user chose the product name Motchi and this repository in place of the earlier private mochi repository. Preserve the user-created initial commit. Future commits go to Motchi. The initial commit records the roadmap and memory; the next imports the source baseline. Preserve project scope and integration limits in future changes. Follow `../AGENTS.md`; update memory only with actual user decisions and verified results.

The local canonical repository folder is `Motchi/` in the parent workspace. Legacy protocol/storage identifiers are retained for compatibility; product/display branding is Motchi. The 29 roadmap items are future feature work, not completed by this repository setup.

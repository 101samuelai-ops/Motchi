# Motchi

Repository: [101samuelai-ops/Motchi](https://github.com/101samuelai-ops/Motchi).

A personal dog companion for understanding project progress, discussing work, and maintaining a checklist from project conversations.

## Start here

- [Product roadmap and acceptance checklist](ROADMAP.md)
- [Persistent project memory and decisions](docs/MEMORY.md)
- [Existing implementation and integration limits](docs/BASELINE.md)
- [Research sources](docs/RESEARCH.md)

Formerly called Mochi. The repository is public, as created by the user.

The roadmap was agreed on 2026-10-25. All new roadmap items start unchecked. Existing features are documented separately so historical implementation does not inflate future roadmap progress.

Current source is in `plugins/progress-pet/`; see its README for Mac companion setup and Codex integration. This repository is also a local plugin marketplace through `.agents/plugins/marketplace.json` once the source baseline is added.

## Progress tracking

The repository `.progress-pet.json` tracks the same roadmap task IDs as `ROADMAP.md`. A percentage means completed checklist items divided by total items; it is not an estimate of elapsed effort or a delivery date. P4 contains later optional enhancements. Implement one agreed milestone at a time.

Private runtime state, chat transcripts, credentials, built apps and compiler caches are not part of this repository.

## Compatibility after the rename

The product is now **Motchi**. New companion builds and visible chat labels use that name. Existing technical names such as the `mochi` MCP namespace, `progress-pet` plugin ID, `MochiLauncher.swift`, `local.mochi.*` job IDs, and macOS `Application Support/Mochi` storage are retained for compatibility. The rename does not reinstall the already-running Mac companion or change its trusted approval-hook definition.

# Mochi

A personal dog companion for understanding project progress, discussing work, and maintaining a checklist from project conversations.

## Start here

- [Product roadmap and acceptance checklist](ROADMAP.md)
- [Persistent project memory and decisions](docs/MEMORY.md)
- [Existing implementation and integration limits](docs/BASELINE.md)
- [Research sources](docs/RESEARCH.md)

The roadmap was agreed on 2026-10-25. All new roadmap items start unchecked. Existing features are documented separately so historical implementation does not inflate future roadmap progress.

Current source is in `plugins/progress-pet/`; see its README for Mac companion setup and Codex integration. This repository is also a local plugin marketplace through `.agents/plugins/marketplace.json` once the source baseline is added.

## Progress tracking

The repository `.progress-pet.json` tracks the same roadmap task IDs as `ROADMAP.md`. A percentage means completed checklist items divided by total items; it is not an estimate of elapsed effort or a delivery date. P4 contains later optional enhancements. Implement one agreed milestone at a time.

Private runtime state, chat transcripts, credentials, built apps and compiler caches are not part of this repository.

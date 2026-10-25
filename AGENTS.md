# Motchi development context

Before changing the product, read `docs/MEMORY.md`, `ROADMAP.md`, and `docs/BASELINE.md`.

- Treat `ROADMAP.md` as the agreed future-work checklist. Preserve stable task IDs and acceptance criteria. Work on the scope the user requests; do not start every roadmap item automatically.
- Keep roadmap checkboxes and this repository's `.progress-pet.json` in sync. Mark complete only after implementation and appropriate verification, with evidence. Saving a plan does not complete its tasks.
- Source lives in `plugins/progress-pet`. Preserve routing and approval limitations. Never write trust records or create synthetic approval buttons for unsupported requests.
- Update `docs/MEMORY.md` with real user decisions and verified changes; separate current facts from proposals. This file is project memory, not a claim of application memory functionality.
- Do not commit private runtime state, chat transcripts, machine paths, credentials, caches, or built apps. Use isolated temporary projects for tests.
- The old generated `outputs` directories in the parent workspace are historical packaging; this repository is the source for new work.

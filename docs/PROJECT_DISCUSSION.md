# History-backed project discussion — 0.17

Questions from the main composer and addressed voice now share one read-only discussion path. Motchi can discuss a named project, select distinctive checklist topics, ask when the name is ambiguous, compare several projects or give an overview of all available projects. General conversation does not require a project. A project follow-up keeps its context; explicit references can switch it. The model can resolve a question to a supplied project after reading its work history, with IDs validated against the local catalog.

Before generating a project answer, the bridge captures available conversation changes, requests an evidence-backed checklist review, and retrieves initial requirements, recent AI updates and question-relevant evidence. Each folder supplies one checklist even when several chats refer to it. Claims should distinguish implementation, testing and user acceptance. A finished AI turn alone does not complete a project. Existing exact-quote validation, revision checks, manual overrides and Undo remain in effect.

The main animated character section contains the question, answer, selected scope and history coverage. This stage remains visible on project pages. Microphone settings open only when requested; replies do not open a separate voice communication panel. Project controls still provide distinct Ask, Save comment and explicit Send to Codex actions.

## Retrieval limits

Every history query includes the exact canonical project folder. Retrieval searches up to 600 recent stored message sections, adds the first three available user sections, and selects bounded relevant/recent snippets. A project answer receives up to 18,000 history characters; multi-project context receives up to 4,500 per project, across at most 20 projects. At most 300 checklist tasks per project enter the answer context; omission counts are supplied. Missing local logs cannot be analyzed.

Checklist review waits at most eight seconds in total, with at most three seconds per project. A running review retains ownership and can finish afterward. The answer receives pending/freshness information and must disclose missing or omitted history. Counts shown in the speech bubble describe retrieved sections, while checklist coverage separately describes reviewed stored history. Neither indicates that every conversation was read in full.

Answers use the configured Codex answer provider with read-only isolation and structured project routing. Provider failure returns clearly labelled recorded counts/coverage, without pretending an AI history analysis succeeded. An invalid model-selected project produces clarification. Authentication, certificate pinning, revocation and stable asynchronous operation IDs apply to general questions too.

Questions may cause evidence-based checklist reconciliation, but cannot execute implementation instructions or grant approvals. General chat and proposed ideas must not silently submit work. Existing comments and work transport rules remain unchanged.

## Checks

`check_project_discussion.py` covers project grouping, name/topic routing, macro/general scope, ambiguity, exact history isolation, bounded retrieval, review-before-answer, evidence-backed check-offs, stale identity rejection, model-selected IDs and wake-only voice. The authenticated portal suite covers general discussion without a project, single-operation retries and separation from work execution. Existing checklist suites verify manual corrections and completion evidence.

The release record in ANDROID_VERIFICATION.md distinguishes fixture checks, synthetic speech and actual calendar/provider checks. Broader milestone/lifecycle memory and human recognition quality remain roadmap work.

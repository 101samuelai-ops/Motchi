# Selected milestone and follow-up

User selection: prioritize reliable conversation-to-checklist updates and better progress discussion. This supersedes the earlier character-first recommendation. Interchangeable characters remain a user requirement, deferred until this workflow is dependable.

## Current implementation

Motchi 0.12 implements durable incremental history review and source-backed automatic checklist changes with Undo (SYNC-01, CHK-04). Progress briefings now expose evidence, recorded pending inputs and review freshness/coverage. See [implementation and verification](CHECKLIST_REVIEW.md). The installed app has not been replaced during active work.

## Recommended follow-up

1. Run the supplied synthetic live-model evaluation in a normal terminal; expand it with reviewed real-world examples. Transport checks pass, but live model accuracy is unmeasured in this sandbox.
2. Finish CHK-01 and CHK-02: separate ideas/decisions and reconcile changed requirements, deferrals and regressions. Keep stable IDs and history; do not count deferred/superseded scope as active work.
3. Finish MEM-02, PRG-01 and CHAT-05: agreed goals, named milestones and completion criteria for richer source-backed project discussion.
4. Return to CHAR-01 through CHAR-03 after agreeing the initial roster. Keep the dog as default and share one project/controller implementation.

## Character design boundaries

- All characters share the same project facts, checklist and supported Codex connections.
- Character switching does not create a new agent, reset a discussion, reconnect an approval or change its meaning.
- Keep the transparent background, ground-line entrance, top-right placement, 1.5-second routine announcements and existing dismissal behavior.
- First agree a coherent visual style and small roster. Custom imports, elaborate personalities and additional species are later extensions.

## Model recommendation

Official OpenAI guidance reviewed on 2026-10-25: [Models](https://learn.chatgpt.com/docs/models?surface=cli).

- **For developing the next version:** GPT-6.1 Sol (`gpt-6.1-sol`) is the recommended balance for complex coding. Start with the client default effort; High is a reasonable choice for the character/controller refactor and integration checks.
- **For unusually difficult architecture or approval-routing debugging:** consider GPT-6 Astra (`gpt-6-astra`). Reserve it for work where stronger sustained reasoning is worth the extra usage.
- **For future repeatable extraction/classification inside Motchi:** evaluate GPT-6 Luna (`gpt-6-luna`) against the checklist accuracy cases before adopting it. The development model and the model used by the companion at runtime are separate choices.

These are recommendations, not changes to the user's model or provider settings. Availability depends on account/client access. A final runtime model choice needs measured accuracy and latency on Motchi's actual examples.

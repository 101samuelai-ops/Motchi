# Recommended next milestone

Recommendation prepared on 2026-10-25. Interchangeable characters are a user requirement. The sequence and suggested roster below are proposals awaiting the user's choice; no application changes are implemented by this document.

## Suggested sequence

1. **Interchangeable characters:** CHAR-01, CHAR-02 and CHAR-03. Retain the dog as the default, agree one additional character first, and use a reusable character registry rather than separate companion applications. A cat is the suggested first addition; a robot can follow. Start with global character selection. Per-project overrides and custom artwork imports can be considered later.
2. **Reliable conversation-to-checklist updates:** CHK-01 and CHK-04, with the relevant QA-01 cases. Distinguish explicit tasks from ideas and decisions, show why an item changed, preserve manual corrections and allow Undo.
3. **A useful project briefing:** MEM-02, PRG-01 and CHAT-05. Show the goal, current milestone, completed tasks, blocker, next decision, evidence and update time.
4. **Broader project memory:** MEM-01, MEM-03 and MEM-04. Expand after the small end-to-end workflow is dependable.

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

# Research informing the roadmap

Reviewed for the product analysis preceding roadmap agreement on 2026-10-25.

- [Microsoft Research: Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/) — communicate capabilities and limits; support invocation, dismissal and correction; explain behavior; remember interactions and adapt cautiously with user control. Supports inspectable memory, evidence and Undo.
- [Linear: Project graph](https://linear.app/docs/project-graph) — distinguish scope, started and completed work, show scope changes, and base forecasting on sufficient historical velocity. Supports milestone-aware progress and optional evidence-based forecasting.
- [Apple Human Interface Guidelines: Notifications](https://developer.apple.com/design/human-interface-guidelines/notifications) — concise, timely, high-value information; avoid duplicate notifications and unnecessary foreground interruption; offer meaningful actions. Supports selective interruptions and a recoverable attention inbox.

The detailed roadmap is a product recommendation and user-approved plan, not a claim that these sources validate Motchi's implementation or guarantee particular outcomes.


## User-supplied conversation articles — 2026-11-02

Read [The interruption problem](https://www.eecommerceai.com/post/the-interruption-problem-how-voice-ai-learns-when-to-speak-and-when-to-listen) and [How interview AI detects questions](https://copilotinterview.com/blog/how-ai-detects-interview-questions). Their shared design guidance is acoustic plus sentence/context signals, short turns, visible captions, indirect-request detection, and recovery when a speaker continues. Neither supplies a reproducible implementation or evidence of Motchi's performance; the second advertises its own product. Applied source changes and actual measurements are recorded in [local conversation](LOCAL_CONVERSATION.md). Speaker-separated audio and echo-aware barge-in remain unimplemented acceptance work.

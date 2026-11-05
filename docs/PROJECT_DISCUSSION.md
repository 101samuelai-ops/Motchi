# History-backed project discussion — 0.17

## Concise assessments — 0.17.1

The paired dashboard's typed and voiced answers now lead with a short natural assessment: what works, the important remaining issue and its practical meaning. A separate next step is a suggestion, not a submitted instruction. Important caveats remain visible. Supporting explanation, exact source quotes and history coverage live in a collapsed **Why this assessment** section in the main character bubble. General conversation does not display unrelated project coverage. All three retained layouts share this presentation.

The structured provider contract separates `text`, `details`, `nextStep`, `caveat` and `evidence`. The bridge checks every returned reference against the exact project/chat/message and verbatim retrieved snippet. A wrong explicit project, invalid quote or oversized summary discards the generated assessment and displays labelled recorded counts instead. Only validated displayed output enters follow-up context. Reference integrity is not proof that every interpretation is correct; model quality still needs broader evaluation.

The prompt prioritizes later user-reported failures over earlier AI success claims, separates checkmarks from tested/user-confirmed outcomes, and forbids invented deadlines or readiness percentages. A live configured-provider test correctly identified an unresolved tablet failure despite an earlier passing-test claim, in a short answer with matching evidence. This is one synthetic conflict case, not a general accuracy benchmark. Project discussion regressions now include 34 checks.

Voice transcription and turn-taking are unchanged in this patch. See [the proposed natural voice milestone](VOICE_CONVERSATION_PLAN.md) for the fixed-silence diagnosis and free/local versus optional GPT-Live options.

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


## Conversational answers and Codex work drafts — 2026-11-05

The main character section now answers ordinary questions, explains project decisions, discusses ideas and recommends next steps. The configured read-only answer model receives the actual question kind and recent discussion. General explanations/capabilities avoid unrelated project-history retrieval, and general follow-ups retain a stable conversation even when retrieval needs change. Project explanations and short follow-ups retain exact project identity. Recommendations should lead with a useful conclusion and practical reason, with supporting explanation and references collapsed below. Failed general answers no longer substitute checklist counts.

The structured answer includes semantic intent. A concrete change request can prepare the user's original words as an editable **Work draft** in the main section. Imperative detection supplies a conservative fallback; hypothetical, rejected and quoted ideas stay discussion. Any answer also offers **Draft work for Codex** for wording the classifier missed. An existing draft is preserved across further questions; the user can explicitly replace it with the latest request. Preparing/discussing a draft never delivers work.

Each draft shows exact project and chat, the original editable instruction and current connection capability. **Send to Codex** uses the existing authenticated operation transport. A Motchi-controlled active chat receives `turn/steer` with its exact expected turn; idle controlled chats receive a new turn. Tracked desktop-only chats require confirmation to start a new connected chat in that same project folder. Ordinary desktop chat injection is not supported. Permissions remain on the Mac.

A stable operation ID is saved before transmission. The main section retains the destination, edited text and delivery receipt; queued/running, failed, accepted and uncertain results remain distinct from implementation completion. A lost/uncertain receipt offers Check receipt, never automatic resend. Double clicks and later UI project changes cannot change the captured destination or duplicate the send. Private comments remain a separate explicit action.

The local preview stays read-only by default. `preview.py --live --work-controls` explicitly enables authenticated send/start/comment actions from the loopback page. The same host, origin, nonce and field restrictions remain; credentials stay outside the page. The illustrative preview cannot execute work. No calendar APK rollout is part of this update.

Source checks: 67 project discussion/routing/evidence cases; 16 latency/isolation checks; shipped UI draft/target/confirmation/receipt/duplicate/offline tests; 35 existing checklist and active/idle Codex steering checks; 26 Android routing and 24 appearance checks. HTTP transport tests and installed live verification are recorded below after completion. These fixtures do not establish universal intent accuracy or human conversational quality.


Verification update: 44 loopback preview HTTP/voice/work-boundary checks and 42 authenticated portal checks pass, including exact destinations, stable retry IDs, confirmation, revocation and rejection of unsupported actions. The two modified Python modules are installed in the existing Mac app, byte-equal to source, with a recoverable backup and verified signature. Normal restart was requested, but its service did not open before the startup check ended; desktop control explicitly reports the Mac is locked. Installed live Q&A/draft verification remains pending. No calendar update.


Live Mac check after unlock: the refreshed preview connected to nine project groups. A Chinese general question about caching returned a direct explanation and everyday example without project counts. The next question used “it” without naming caching and the provider correctly explained stale data/storage tradeoffs and when accuracy requires fresh data. A real Motchi change request selected the correct tracked chat and displayed an editable main-section draft. Editing, reloading and cancelling the new-chat confirmation retained the exact instruction; no send/start/comment operation was created by these checks.

Those checks exposed and fixed two integration details: restored drafts now re-enable after reconnecting without replacing their edited text, and the answer model receives the exact destination capability/action, so a tracked chat is described as Start connected chat. The dog stays aligned beside the conversation/draft. Sixty-seven discussion and sixteen latency cases plus shipped draft/UI regression checks pass. The final modules are installed/signed and source-equal, and the new service is running; final preview reconnect/wording check follows below.


Final running-build verification: the installed provider now correctly names **Start connected chat** for the selected tracked Motchi chat, and the main section shows the same enabled action. The edited instruction remains intact across the restart. The new-chat confirmation names the exact destination, and cancelling it creates no work operation. The preview remains open with explicit work controls. These live read-only/draft checks plus the authenticated/protocol delivery regressions complete CHAT-08; no new implementation task was sent merely to test it. Main-speaker identity, full duplex and broader voice acceptance remain outside this milestone.

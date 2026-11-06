# Answer connection recovery

Updated 2026-11-07. Mac-only correction; calendar rollout is deferred.

## Diagnosis

The screenshot's recognized words had reached discussion, but the answer connection returned an unavailable placeholder. The installed service reproduced both the project-list failure and an ordinary greeting/capabilities failure. The configured Codex model/provider needed an environment credential available in the user's interactive shell but absent from the GUI-launched companion. Removing that variable in an isolated CLI check reproduced `Missing environment variable` and exit 1 in 0.31 seconds. With the configured environment, the same provider returned a valid answer.

The generic presentation fallback obscured authentication, connection, timeout and invalid-output failures behind one message. It also could not answer the simple Chinese project-inventory question from already available local data.

## Correction

`provider_access.py` reads only the active provider's `env_key` name from the user Codex configuration, honoring the selected user profile. An existing process value wins. When missing, a bounded invocation of the user's standard login shell retrieves that one value through a framed private pipe. It is cached in memory for up to five minutes, or fifteen seconds after failure, and passed to the existing Codex subprocesses. No key is written to the repository, application resources, logs, command-line arguments or a new credential store. Project files cannot nominate extra credentials. Unsupported shells, missing/invalid configuration and shell failures preserve normal failure handling.

The same child environment applies to project answers, checklist inference, catalog and explicit Motchi-controlled chats. The configured provider, model, approval rules and hook trust remain as previously selected. This fixes GUI access to existing credentials; it does not install a second AI provider. Shell startup is bounded to five seconds and is not a general environment import.

Provider error events reduce to safe categories: authentication, rate limit, connection, configuration, timeout or unavailable. Invalid generated content retains a distinct validation failure. Raw errors and credentials do not enter displayed answers. Source/evidence and exact-project validation remain intact.

Simple catalog questions such as “我们现在的项目还有哪些？” and “What projects do we have?” are answered from grouped local project data without waiting for inference or checklist reconciliation. This route does not claim a model assessment or full-history review, and cannot create work or grant approvals. Progress and implementation questions still use their existing evidence-backed discussion paths.

## Verification

The release tree, excluding unrelated pending spoken-reply edits, passed 185 checks: 30 credential/fallback, 67 discussion/routing, 16 latency, 37 controlled Codex and 35 checklist/delivery checks. They cover credential precedence, concurrency, no parent-environment mutation, malformed configuration, no secret in argv, selected profile, startup noise, project grouping, intent exclusions, identity validation and safe subprocess error propagation.

A real GUI-environment reproduction recovered a value equal to the already-configured credential without printing it, and produced a Chinese general answer in 11.3 seconds through the configured model. This measures that one request, not a general response-time guarantee.

The signed app update is installed. The Mac is confirmed locked; normal startup is held while reading the saved project file in Documents; the final authenticated live-service check awaits the user's existing file-access prompt. Do not report runtime recovery until that check succeeds. Broader microphone accuracy and human conversational latency remain AND-10.

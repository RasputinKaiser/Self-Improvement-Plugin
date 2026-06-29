# Capability Map

What a maximally-capable self-improving agent harness should have.
Used by `/brainstorm` to identify gaps and prioritize the next build.

## Tier 1 — Core lifecycle (SHIPPED)

- [x] Pre-edit risk gate (autonomy_gate.py)
- [x] Memory recall at prompt time (memory_fabric_prompt_search.py)
- [x] Memory recall at edit time (memory_fabric_preflight.py)
- [x] Session continuity across compaction (compact_continuity.py)
- [x] Outcome tracking (task_outcome_tracker.py)
- [x] Self-correction journal (self_correct.py + improvements.md)
- [x] Snapshot/rollback safety (snapshot_harness.py + restore_harness.py)
- [x] Plugin drift detection (install.sh + PluginMirrorStore)
- [x] Hook event observation (hook_event_tap.py + HookEventStore)
- [x] Delegation agents (escalate, repo-scout, memory-curator, test-author)
- [x] Weekly self-improvement cron sweep

## Tier 2 — Interactive GUI (SHIPPED)

- [x] Native macOS SwiftUI app (harness-app)
- [x] Project navigator (three-column: projects → sessions → chat)
- [x] Live NCode chat bridge (--print stream-json IPC)
- [x] Session transcript viewer (historical JSONL loading)
- [x] Hook event feed (live tailing with outcome classification)
- [x] Snapshot catalog with diff detection
- [x] Memory Fabric explorer (search/filter/sort/archive)
- [x] Plugin manifest viewer (hooks/agents/commands)
- [x] Companion browser (WKWebView inside ChatSplitView)
- [x] Tests runner with live output

## Tier 3 — Agentic surfaces (PARTIAL)

- [x] Agent definitions (4 subagents with model:inherit)
- [x] Slash command surface (7 commands + /brainstorm = 8)
- [x] In-app browser USE (the agent can navigate/click/extract from WKWebView)
- [x] Vision (screenshot capture + VLM analysis via browser_see)
- [x] Computer use (mac-cua click/type/scroll integration from the app)
- [x] Live session attach (fork-continue via --resume --include-partial-messages)
- [x] Multi-agent orchestration dashboard (Agents pane)
- [x] Plan approval UI (structured plan dialog with accept/reject/modify)

## Tier 4 — Advanced (PARTIAL — LAST GAP)

- [x] Worktree-aware harness (scopes mapped via `git rev-parse --absolute-git-dir`; 8 hook scripts route through `worktree_scope.resolve_scope`)
- [x] Cost/budget tracking per session with real-time warnings
- [x] Prompt template library + hot-swap
- [x] Skill marketplace mirror (browse/installed skills from the app)
- [x] MCP server browser (list from .config.json + settings.local.json)
- [x] Cross-machine sync (plugin code via private git — DONE; session/memory data sync deferred per plan)
- [ ] Evaluation harness (run benchmark cases against the current model config) — deferred per separate project
- [x] Telemetry dashboard (session usage data visualized from ~/.ncode/usage-data/)
- [x] Voice input (hold-to-talk via SFSpeechRecognizer + AVAudioEngine)
- [ ] Scheduled task visualizer (cron jobs with next-fire timestamps)

## Capability areas for gap analysis

When brainstorming, consider these dimensions:

1. **Observation** — what can the harness SEE? (hooks, transcripts, memory, drift)
2. **Action** — what can the harness DO? (edit, run, snapshot, restore, delegate)
3. **Recall** — what can the harness REMEMBER? (memory fabric, journal, patterns)
4. **Interaction** — how does the user TALK to the harness? (chat, commands, GUI)
5. **Self-improvement** — how does the harness get BETTER? (self_correct, tests, cron)
6. **External surfaces** — what can the harness REACH? (browser, screen, filesystem, MCP)
7. **Multi-agent** — how do agents COORDINATE? (escalate, fan-out, lesson capture)
8. **Safety** — what PREVENTS harm? (autonomy_gate, snapshots, rollback, provenance)
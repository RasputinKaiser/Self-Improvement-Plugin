# SIPS visual evidence and retrieval explanations

The adaptation `visual` read view returns a compact episode diagram plus a bounded
artifact dependency diagram. Use it for in-stream explanations:

```sh
python3 scripts/adaptation.py show --episode EPISODE --view visual
```

MCP uses the same view through `homebase_adaptation_read`. Render `visual.mermaid`
in a Mermaid fence. For drift analysis, render `dependency_mermaid`; its fixed node
identifiers are separate from escaped artifact labels. At most 24 dependency nodes
are shown, prioritizing affected nodes. `dependency_nodes_omitted` makes truncation
explicit. Underlying events, receipts, dependencies, opportunities and diffs remain
the authoritative evidence. Reading these views creates no events or directories.

Diagrams report the episode's actual state and local evaluator finding. A passing
candidate is not an activated change or proof of general transfer. Missing evidence
and unmeasured effectiveness must remain visible. Show experiment results with
numbers from the saved receipts; do not turn four shared tasks into sixteen
independent observations or infer total model cost from evaluator duration.

The existing HTML inline widget mechanism is host-specific. Returning HTML or a
preview directive does not prove that Codex rendered it. Use Mermaid and ordinary
local image embeds where that integration is unavailable. No visualization library
or background server is required by the new runtime view.

The `procedures` view now includes `retrieval_audit`:
- eligible: existing compatibility-filtered proposals, retaining unknown effectiveness;
- rejected: identities with expired, source_changed_or_unavailable,
  applicability_mismatch, known_negative_context, or unrelated reasons;
- artifact_rejections: scoped procedure artifacts rejected before retrieval, such
  as mutated candidates or drifted source evidence.

Rejected procedures score zero. These are explicit contract/freshness decisions,
not learned causal judgments. Legacy callers of `retrieve` retain their list result.

For future SIPS progress updates, use a small evidence-linked flow diagram or chart
when it clarifies diagnosis, drift, review or experiment results. A text summary must
still report failures, limitations, activation state and current-task freshness.

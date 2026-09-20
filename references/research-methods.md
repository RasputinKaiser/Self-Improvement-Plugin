# Advisory research methods — API v1

Use `python3 <plugin-root>/scripts/research_methods.py METHOD --request-file input.json` or MCP `homebase_method` with `method` and JSON-encoded `request_json`. These pure methods execute no commands and create no files. Receipts include an input digest, `acceptance: not_evaluated`, and `activation: none`.

To retain a receipt in an episode, use adaptation write action `analyze`, supplying `method`, `input`, `episode`, `expected_revision`, and `idempotency_key`. The controller appends at most 32 receipts and preserves the episode state. Standalone reads remain non-persistent. Invalid input is an error, not a negative experimental result.

## Diagnosis

```json
{"hypotheses":["implementation","environment"],"probes":[{"id":"replay","cost_seconds":2,"predictions":{"implementation":"failed","environment":"passed"}}],"budget_seconds":120}
```

Selects a deterministic greedy set cover of hypothesis pairs, ranked by new distinctions per estimated second. All predictions must be supplied. `unavailable` never distinguishes a pair. Reports remaining ambiguity and pairs no supplied probe can separate. Up to 32 hypotheses, 64 probes and 600 seconds; default 120. Predictions and costs are human/agent assumptions, not calibrated probabilities. Execute probes through the existing investigation controller to obtain actual evidence. This advisory planner does not implement optimal experimental design or causal inference.

## Coverage and morphology

```json
{"factors":{"host":["codex","claude"],"schema":[1,2],"dependency":["fresh","stale"]},"forbidden":[{"host":"claude","schema":1}],"strength":2,"max_cases":16}
```

`coverage` covers feasible t-way interactions. `morphology` returns proposed alternatives plus a no-change comparator. Up to eight factors, eight scalar levels each, 4,096 Cartesian configurations, strength 1–3 and 128 selected cases. Exclusions are designer-supplied partial assignments. Report incomplete coverage and infeasible designs explicitly. Coverage is a property of the supplied model; it supplies neither an executable test nor an oracle. Morphological exclusions should state whether they are logical, empirical, or preference-based in the accompanying work package.

## Assumptions

```json
{"facts":{"dependency_current":{"state":"supported","evidence":["receipt:dependency-hash"]}},"rules":[{"id":"reuse","premises":{"dependency_current":true},"conclusion":"reuse_applicable","value":true}]}
```

Four states: supported, refuted, unknown, inconsistent. Rules require every premise. Unseeded cycles stay unknown. Evidence-free facts stay unknown. Recompute the complete request after retracting an assumption. Contradictions remain local; they do not prove unrelated propositions. This is bounded support propagation, **not a full assumption-based truth-maintenance system**. References are not fetched or verified; a supported result remains conditional. A conclusion can inherit disputed premises: inspect inconsistent claims and source evidence before relying on it. Maximum 128 facts, 128 rules, 256 propositions.

## Drift

```json
{"baseline":[9,10,11,10,10],"samples":[10,null,12,15],"weight":0.2,"baseline_identity":"metric+environment-v1","sample_identity":"metric+environment-v1"}
```

Exploratory EWMA with three-standard-deviation startup limits. Requires 5–1,000 baseline observations, at most 1,000 samples and matching declared identities. Missing samples remain unavailable and do not advance the observation count. Constant baselines yield unavailable limits. Stable representative baseline, approximately independent observations, and appropriate distributional assumptions are required to interpret limits statistically. A signal prompts investigation; it does not identify a cause or establish an optimization win. Optimize's matched measurement receipts and SIPS independent acceptance remain authoritative.

## Sources and boundaries

- [NIST combinatorial testing, 2010](https://csrc.nist.gov/pubs/sp/800/142/final): interaction coverage motivates coverage planning.
- [NIST EWMA handbook, Roberts 1959 lineage](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm): process monitoring motivates drift analysis.
- [General morphological analysis](https://www.swemorph.com/ma.html): explicit dimensions and consistency constraints motivate idea exploration.
- [de Kleer, 1986](https://www.sciencedirect.com/science/article/pii/0004370286900809): assumption-sensitive reasoning motivates conditional memory interpretation.
- [NASA fault-management objectives, 2012](https://ntrs.nasa.gov/citations/20120004211): diagnostic effort should serve explicit operational objectives.

These implementations are adaptations, not reproductions of source algorithms or published performance. No held-out agent effectiveness result is claimed.

# SIPS 0.9: semantic contracts and evidence-aware diagnostic branches

SIPS 0.9 adds a small semantic contract vocabulary, a dependency-validity view,
and bounded executable diagnostic graphs. These are functioning local mechanisms.
They do not establish improved agent effectiveness or automatic learning.

## Semantic tool contracts

` sips.tool-contract.v3 ` uses the v2 structural contract with optional `semantic`
constraints at any schema node. V1 helpers remain directly callable; v2 remains
accepted. The schema extension is additive and also understood in v2 contracts.

```json
{"type":"number","semantic":{"role":"duration","unit":"seconds","minimum":0,"maximum":120,"context":{"clock":"monotonic"}}}
```

A producer must declare every role, unit, and context identity required by its
consumer. Numeric producer bounds must fit within consumer bounds. Missing
metadata cannot satisfy a requirement. Values are checked against numeric bounds
at runtime. Units, roles, and context identities are declarations: SIPS cannot
prove that a number physically represents seconds or that a declared origin is
true. Use independent consumer checks for those claims. There is no implicit unit
conversion, arbitrary predicate language, SMT solver, or full refinement typing.
The semantic implementation is included in evaluator identities and frozen copies.

## Dependency validity

```sh
python3 scripts/adaptation.py show --episode EPISODE --view dependencies
```

MCP: `homebase_adaptation_read` with `episode` and `view: "dependencies"`.
The view compares frozen baseline, fixture and evaluator manifests, scoped source
files, suite criteria, candidate contents, evaluation receipts, composition registry
identities, and linked later-use receipts. Additions inside frozen directories
invalidate their aggregate manifests. It returns nodes, `requires` edges, changed
roots, transitive affected nodes, explanations, and revalidation requirements.

This is a read-only projection over durable records, rebuilt on request. It does
not create events, rewrite historical successes, or maintain a background index.
The invalidation closure is incremental in dependency structure; the filesystem
scan is not yet an incremental build engine. Composition registry invalidation is
conservative and may invalidate a plan when an unrelated registry entry changes.
Only recorded workspace scope is checked; unrecorded environmental changes remain
outside this projection. Existing controller checks still enforce activation.

## Branching diagnostic policy candidates

Use the existing observe/propose/build/artifact workflow. A candidate policy remains
one JSON file under `sips-artifacts/policy/`. Example:

```json
{
  "schema":"sips.policy.v2", "kind":"diagnosis", "scope":"diagnosis",
  "version":"1", "inputs":["probe_outcomes"], "outputs":["intervention"],
  "entry":"replay", "assumptions":[],
  "nodes":{
    "replay":{"probe":"original-replay","on":{"passed":"done","failed":"repair","unavailable":"inspect"}},
    "done":{"intervention":"stop","rationale":"No reproduced failure"},
    "repair":{"intervention":"repair_interface","rationale":"Failure reproduced"},
    "inspect":{"intervention":"gather_evidence","rationale":"Environment remains unknown"}
  }
}
```

Invoke `policy_trial` on the registered policy episode with `target_episode` naming
an investigation episode. The controller reads its executed durable probe receipts,
pins the source revision and event digest, checks recorded evidence validity, and
traverses the policy. Caller-supplied outcome maps do not replace those receipts.
Missing outcomes return `needs_evidence`; a measured unavailable outcome follows
its own explicit branch. Changed source evidence returns `inapplicable`.
A terminal returns a proposed intervention. The active task agent decides and
uses normal lifecycle actions; this does not execute commands or activate policy.

All three outcome branches are required. Cycles, unreachable nodes, more than
32 nodes, and evaluator/permission/activation/budget actions are rejected. V1
weighted ranking policies remain supported. Defaults for candidate attempts,
composition steps, and evaluation budgets remain unchanged.

An assumption is `{"path":"relative/file","sha256":"<64 hex>","valid_until":1790000000}`.
All assumptions must match their content hash and remain unexpired at execution.
Missing files, changed content, and symlinks make the policy inapplicable. No
embedding service or model process is involved.

## Independent behavioral evaluation

Use frozen `policy_cases` checks in the original, regression, and counterexample
suite groups. Candidate files cannot supply their expected answers:

```json
{"kind":"policy_cases","path":"sips-artifacts/policy/diagnosis.json","cases":[
  {"outcomes":{"original-replay":"failed"},"now":0,
   "expected":{"status":"proposed","intervention":"repair_interface"}},
  {"outcomes":{},"now":0,"expected":{"status":"needs_evidence","probe":"original-replay"}}
]}
```

Cases run under the frozen external evaluator and interpreter. Assumption files
resolve within frozen fixtures for evaluation, and within the target workspace for
foreground trials. Empty cases or missing policy files are unavailable; incorrect
answers fail. Frozen synthetic outcomes test interpreter/policy behavior, not real
agent transfer. Baseline and candidate use the same cases. A missing baseline is
unavailable and cannot establish improvement. Preserve original requirements when
adding counterexamples. Passing evaluation stops at `ready_for_review`.

## Migration and research boundaries

The new evaluator identity makes older validation receipts stale until revalidated.
Old episode evaluators and evidence remain intact. No generated policy is installed
as the default diagnosis policy. Optimize stays at 0.6.0 with advisory comparisons;
this release makes no timing, token, transfer, or frontier claim.

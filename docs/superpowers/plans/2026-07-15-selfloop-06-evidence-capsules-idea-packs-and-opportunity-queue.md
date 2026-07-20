# Evidence Capsules, Idea Packs, and Opportunity Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first persistent research inputs: bounded evidence capsules, one immutable idea pack per generation, validated experiment cards, and a restart-safe opportunity queue.

**Architecture:** Evolvable compilation and proposal code lives in `scripts/selfloop_strategy/` and runs only through the Plan 05 JSON subprocess boundary. Protected code in `scripts/selfloop_supervisor/` validates identities, source links, bounds, hashes, immutability, deduplication, and replacement-pack authorization before committing artifacts and events to the anchored SQLite ledger.

**Tech Stack:** Python 3.10+, standard-library `dataclasses`, `hashlib`, `json`, `pathlib`, SQLite ledger from Plan 05, pytest 8+.

## Global Constraints

- Normative contract: `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- Every capsule, pack, and card carries `rootId`, `campaignId`, `generationId`, schema ID, stable object ID, and content digest.
- The controller reserves and journals capsule, pack, card, and call IDs before the corresponding side effect. Phase keys derive from the P05 `MutationSession`, so restart reuses the same IDs and persisted raw receipts instead of generating duplicate objects or provider calls.
- Receipt JSON is discriminated by required `kind` and `stage` fields and parsed through an exact `(kind, stage)` registry. Raw, final, and terminal-failed payloads use distinct dataclasses; optional-field supersets are forbidden.
- Capsules link full artifacts and store bounded excerpts; default log projection preserves both head, tail, error, and terminal summary.
- Capsules include release identity, relevant failures, prior mechanisms, lineage/operator statistics, protected families, full evaluator/runtime identity, and unresolved conflicts.
- One planning call creates one idea pack per generation. A replacement requires an empty queue, champion/evidence invalidation, or inability to meet exploration quota, with a ledger reason.
- The seven requested categories are targeted fix, distinct root cause, simplification, repair, combination, structural, and meta; unsupported categories carry an omission reason.
- Cards are immutable after persistence. Status changes are ledger events; rewording cannot erase duplicate mechanism history.
- The normative `QueueStatus` enum is exactly `queued`, `selected`, `implemented`, `invalidated`, and `archived`, matching section 8.3. Experiment outcomes and receipt stages are separate fields and may not be written into queue status.
- Strategy output is untrusted JSON. Only protected validation may persist it; strategy receives no sealed paths, credentials, ledger handle, or supervisor path.
- Every P06 budget grant and reconciliation is a P05 session-capability mutation and its `BudgetReceipt` is appended to the canonical ledger before success or failure is returned. A failed preparation always appends one terminal-failed generation receipt linked to raw calls and budget events.
- This plan does not implement selection or execute experiments and therefore does not advertise C2.

---

### Task 1: Define and validate bounded evidence capsules

**Files:**
- Create: `scripts/selfloop_supervisor/receipt_contract.py`
- Create: `scripts/selfloop_supervisor/evidence_contract.py`
- Create: `scripts/selfloop_supervisor/artifacts.py`
- Create: `scripts/selfloop_strategy/evidence_compiler.py`
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Test: `tests/selfloop/test_evidence_capsule.py`

**Interfaces:**
- Produces common `ReceiptKind` values `evidence-capsule`, `idea-pack`, `generation-preparation`, `lineage-proposal`, `selection`, `budget`, `research-invocation`, `diagnose-experiment`, `candidate-experiment`, `repair-experiment`, `review`, and `conformance`; `ReceiptStage` values `raw`, `final`, and `terminal-failed`; and `parse_receipt(payload: Mapping[str, Any]) -> TypedReceipt` dispatching by their exact pair.
- Produces: `compile_capsule(request: Mapping[str, Any], artifact_reader: ArtifactReader, max_excerpt_bytes: int = 8192) -> dict[str, Any]` in strategy, `validate_capsule(payload: Mapping[str, Any], expected: ObjectScope, expected_capsule_id: str) -> EvidenceCapsule`, `ArtifactStore.stage_inputs(root_id: str, sources: Sequence[SourceArtifact], capability: MutationCapability) -> tuple[ArtifactInputReceipt, ...]`, and `ArtifactStore.persist_json(root_id: str, kind: str, artifact_id: str, payload: Mapping[str, Any], digest: str, capability: MutationCapability) -> ArtifactReceipt` in supervisor.
- `ObjectScope` contains exact `root_id`, `campaign_id`, and `generation_id` values supplied by the controller.
- `ArtifactStore` writes atomically below `${SIPS_HOME}/selfloop/roots/<root-id>/artifacts/`; every write verifies an `ARTIFACT_STAGE` or `ARTIFACT_PERSIST` capability for the exact root/object/phase. The strategy receives only allowlisted release-root or artifact inputs selected by the supervisor.
- Every concrete receipt fixes `kind` and `stage` as class constants and defines exact allowed fields. `parse_receipt` rejects an unknown pair, fields from another stage, and a payload whose class discriminants do not match; `QueueStatus` is not a receipt-stage alias.

- [ ] **Step 1: Write failing boundedness, identity, conflict, and source-link tests**

```python
def test_capsule_is_bounded_source_linked_and_preserves_conflict(tmp_path):
    log = tmp_path / "failure.log"
    log.write_text("HEAD\n" + "x" * 20000 + "\nERROR boom\nTERMINAL failed\n")
    reader = FakeArtifactReader({"input-1": log.read_bytes()})
    payload = compile_capsule({
        "schema": "selfloop.evidence-request.v1",
        "rootId": "root-1", "campaignId": "campaign-1", "generationId": "generation-1",
        "stableChampion": {"releaseId": "release-1", "sourceDigest": "a" * 64},
        "sources": [{
            "artifactId": "artifact-1", "handle": "input-1", "kind": "failure-log",
            "contentDigest": hashlib.sha256(log.read_bytes()).hexdigest(),
        }],
        "failedMechanisms": ["context-overload"], "lineageStats": {}, "operatorStats": {},
        "protectedFamilies": ["memory-recall"], "provenance": complete_provenance(),
        "conflicts": [{"claim": "recall improved", "against": "holdout regressed"}],
    }, artifact_reader=reader, max_excerpt_bytes=1024)
    capsule = validate_capsule(
        payload, ObjectScope("root-1", "campaign-1", "generation-1"), expected_capsule_id="capsule-1",
    )
    assert len(capsule.sources[0].excerpt.encode()) <= 1024
    assert "HEAD" in capsule.sources[0].excerpt and "TERMINAL failed" in capsule.sources[0].excerpt
    assert capsule.conflicts[0]["against"] == "holdout regressed"

def test_receipt_parser_dispatches_kind_and_stage_without_optional_superset():
    parsed = parse_receipt(raw_evidence_receipt(kind="evidence-capsule", stage="raw"))
    assert isinstance(parsed, RawEvidenceReceipt)
    with pytest.raises(ReceiptSchemaError, match="field finalDigest is not valid for raw"):
        parse_receipt({**raw_evidence_receipt(), "finalDigest": "a" * 64})
    with pytest.raises(ReceiptSchemaError, match="unknown receipt kind/stage"):
        parse_receipt({"kind": "evidence-capsule", "stage": "implemented"})
```

The strategy request contains only stable handles and content digests, never filesystem paths. `ArtifactStore.stage_inputs` verifies each source digest, copies it into a content-addressed read-only input directory, writes a protected handle manifest, and returns the exact paths only to P05 `StrategyClient.artifact_inputs`. The worker constructs `ArtifactReader` from that protected manifest and refuses unknown handles or digest mismatches.

- [ ] **Step 2: Run and verify the missing compiler failure**

Run: `python3 -m pytest -q tests/selfloop/test_evidence_capsule.py`

Expected: collection fails with missing `evidence_compiler`.

- [ ] **Step 3: Implement deterministic excerpting, canonical hashing, and exact-key validation**

```python
def bounded_excerpt(text: str, limit: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    marker = b"\n[... bounded ...]\n"
    important = b"\n".join(
        line for line in encoded.splitlines()
        if b"ERROR" in line.upper() or b"TERMINAL" in line.upper()
    )[:max(0, limit // 3)]
    separators = marker + (b"\n" + important if important else b"")
    remaining = max(0, limit - len(separators))
    head_bytes = remaining // 2
    tail_bytes = remaining - head_bytes
    projected = encoded[:head_bytes] + separators + encoded[-tail_bytes:]
    return projected[:limit].decode("utf-8", "ignore")

def capsule_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

RECEIPT_TYPES = {
    ("evidence-capsule", "raw"): RawEvidenceReceipt,
    ("evidence-capsule", "final"): FinalEvidenceReceipt,
    ("generation-preparation", "terminal-failed"): FailedPreparationReceipt,
}

def parse_receipt(payload):
    receipt_type = RECEIPT_TYPES.get((payload.get("kind"), payload.get("stage")))
    if receipt_type is None:
        raise ReceiptSchemaError("unknown receipt kind/stage")
    return receipt_type.parse_exact(payload)
```

P07 and P08 register their concrete classes in this same parser rather than weakening it. The registry module contains only protected receipt schemas and exact dispatch; it never imports evolvable strategy code.

- [ ] **Step 4: Run the evidence tests**

Run: `python3 -m pytest -q tests/selfloop/test_evidence_capsule.py`

Expected: `7 passed`.

- [ ] **Step 5: Commit evidence contracts**

```bash
git add scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/evidence_contract.py scripts/selfloop_supervisor/artifacts.py scripts/selfloop_strategy/evidence_compiler.py scripts/selfloop_supervisor/contracts.py tests/selfloop/test_evidence_capsule.py
git commit -m "feat(selfloop): add bounded evidence capsules"
```

### Task 2: Generate and persist exactly one complete idea pack

**Files:**
- Create: `scripts/selfloop_strategy/idea_pack.py`
- Modify: `scripts/selfloop_strategy/worker.py`
- Create: `scripts/selfloop_supervisor/model_broker.py`
- Create: `scripts/selfloop_supervisor/idea_pack_contract.py`
- Test: `tests/selfloop/test_idea_pack.py`

**Interfaces:**
- Produces pure strategy functions `build_idea_prompt(capsule: Mapping[str, Any]) -> PromptEnvelope` and `finalize_idea_pack(capsule: Mapping[str, Any], model_output: Mapping[str, Any], pack_id: str, card_ids: Sequence[str]) -> dict[str, Any]`, protected `PlannerBroker.generate(prompt: PromptEnvelope, grant: BudgetGrant) -> RawPlannerReceipt`, and `validate_idea_pack(payload: Mapping[str, Any], capsule: EvidenceCapsule, expected_pack_id: str, expected_card_ids: Sequence[str]) -> IdeaPack`.
- `PlannerBroker.generate` is called exactly once per journaled pack ID and owns provider credentials. It always returns `kind="idea-pack", stage="raw"`, including provider failures; callers persist it through `PhaseJournal.persist_raw(..., capability=RECEIPT_PERSIST)` and reconcile before `require_success()`. The broker itself has no ledger handle. It records provider-reported usage when available or the supervisor's reserved tokenizer/output-cap bound otherwise; strategy self-reports are ignored. Protected validation emits a separate final receipt, while Task 4 emits terminal-failed preparation receipts.

- [ ] **Step 1: Write failing single-call and category-accounting tests**

```python
def test_one_planning_call_accounts_for_all_categories(capsule, fake_broker, grant):
    fake_broker.result = {
        "cards": [card("targeted-fix", "reduce-duplicate-context")],
        "omissions": [
            {"category": name, "reason": "capsule has no supporting evidence"}
            for name in ["distinct-root-cause", "simplification", "repair", "combination", "structural", "meta"]
        ],
    }
    prompt = build_idea_prompt(capsule.to_dict())
    call = fake_broker.generate(prompt, grant)
    pack = validate_idea_pack(
        finalize_idea_pack(capsule.to_dict(), call.payload, pack_id="pack-1", card_ids=("card-1",)),
        capsule, expected_pack_id="pack-1", expected_card_ids=("card-1",),
    )
    assert fake_broker.calls == 1
    assert call.usage_receipt.source == "provider"
    assert pack.pack_id == "pack-1"
    assert tuple(card.card_id for card in pack.cards) == ("card-1",)
    assert {card.category for card in pack.cards} | {item.category for item in pack.omissions} == REQUIRED_CATEGORIES
    assert pack.capsule_hash == capsule.digest
```

- [ ] **Step 2: Run and confirm the generator is absent**

Run: `python3 -m pytest -q tests/selfloop/test_idea_pack.py`

Expected: collection fails with missing `idea_pack`.

- [ ] **Step 3: Implement one-call generation and supervisor validation**

```python
REQUIRED_CATEGORIES = frozenset({
    "targeted-fix", "distinct-root-cause", "simplification", "repair",
    "combination", "structural", "meta",
})

def finalize_idea_pack(capsule, model_output, pack_id, card_ids):
    if len(card_ids) != len(model_output.get("cards", [])):
        raise IdeaPackSchemaError("one protected card ID required per raw card")
    return {
        "schema": "selfloop.idea-pack.v1",
        "packId": pack_id,
        "rootId": capsule["rootId"], "campaignId": capsule["campaignId"],
        "generationId": capsule["generationId"], "capsuleHash": capsule["digest"],
        "cards": [
            {**{k: v for k, v in card.items() if k != "cardId"}, "cardId": card_ids[index]}
            for index, card in enumerate(model_output.get("cards", []))
        ],
        "omissions": model_output.get("omissions", []),
    }
```

`build_idea_prompt` returns canonical prompt bytes plus schema and digest; it does not call a model. The controller journals `packId` before `PlannerBroker.generate`, then journals one deterministic protected card ID per raw card before finalization. The broker validates the grant, enforces the output cap, makes exactly one provider request, and persists payload plus an authoritative raw receipt. Reconcile the grant before accepting `finalize_idea_pack` output, and require its pack/card IDs to match the journaled values; strategy-supplied card IDs are discarded. The strategy subprocess never receives credentials or invokes a provider directly.

- [ ] **Step 4: Run idea-pack tests**

Run: `python3 -m pytest -q tests/selfloop/test_idea_pack.py`

Expected: `8 passed`.

- [ ] **Step 5: Commit one-call idea-pack generation**

```bash
git add scripts/selfloop_strategy/idea_pack.py scripts/selfloop_strategy/worker.py scripts/selfloop_supervisor/model_broker.py scripts/selfloop_supervisor/idea_pack_contract.py tests/selfloop/test_idea_pack.py
git commit -m "feat(selfloop): generate one validated idea pack"
```

### Task 3: Add immutable experiment cards and persistent opportunity queue

**Files:**
- Create: `scripts/selfloop_supervisor/opportunity_queue.py`
- Test: `tests/selfloop/test_opportunity_queue.py`

**Interfaces:**
- Produces normative `QueueStatus(str, Enum)` values `QUEUED="queued"`, `SELECTED="selected"`, `IMPLEMENTED="implemented"`, `INVALIDATED="invalidated"`, and `ARCHIVED="archived"`; `OpportunityQueue.persist_pack(pack: IdeaPack, capability: MutationCapability) -> QueueReceipt`, `list(generation_id: str, statuses: set[QueueStatus]) -> tuple[ExperimentCard, ...]`, and `transition(card_id: str, status: QueueStatus, reason: str, capability: MutationCapability) -> EventRecord`.
- Queue writes require session-derived `QUEUE_PERSIST` or `QUEUE_TRANSITION` capabilities whose resource is the exact pack/card ID and whose phase key is their idempotency key; string keys are not accepted separately.
- Card fingerprint covers normalized problem, mechanism, operator, affected components, and expected behavior change.
- Allowed transitions are explicit (`queued -> selected|invalidated|archived`, `selected -> implemented|invalidated|archived`, terminal statuses do not transition). Receipt stages and experiment outcomes never enter this enum.

- [ ] **Step 1: Write failing restart, immutability, and semantic-dedup tests**

```python
def test_cards_survive_restart_and_rewording_does_not_reset_history(queue_factory, pack):
    first = queue_factory().persist_pack(pack, queue_capability("persist:pack-1", resource=pack.pack_id))
    reopened = queue_factory()
    assert reopened.list(pack.generation_id, {QueueStatus.QUEUED})[0].card_id == first.card_ids[0]
    duplicate = replace(pack.cards[0], card_id="card-2", problem="  SAME   problem ")
    with pytest.raises(DuplicateCard, match=first.card_ids[0]):
        reopened.persist_pack(
            replace(pack, pack_id="pack-2", cards=(duplicate,)),
            queue_capability("persist:pack-2", resource="pack-2"),
        )

def test_queue_status_is_the_normative_five_value_enum(queue, selected_card):
    assert {item.value for item in QueueStatus} == {
        "queued", "selected", "implemented", "invalidated", "archived",
    }
    with pytest.raises(ValueError):
        queue.transition(
            selected_card.card_id, "failed", "experiment failed",
            queue_capability("transition:failed", resource=selected_card.card_id),
        )
```

- [ ] **Step 2: Run and verify the queue is red**

Run: `python3 -m pytest -q tests/selfloop/test_opportunity_queue.py`

Expected: collection fails with missing `opportunity_queue`.

- [ ] **Step 3: Implement immutable card rows plus status events**

```python
def card_fingerprint(card: ExperimentCard) -> str:
    normalized = {
        "problem": " ".join(card.problem.lower().split()),
        "mechanism": card.mechanism,
        "operator": card.operator,
        "affectedComponents": sorted(card.affected_components),
        "expectedBehaviorChange": " ".join(card.expected_behavior_change.lower().split()),
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()

ALLOWED_QUEUE_TRANSITIONS = {
    QueueStatus.QUEUED: {QueueStatus.SELECTED, QueueStatus.INVALIDATED, QueueStatus.ARCHIVED},
    QueueStatus.SELECTED: {QueueStatus.IMPLEMENTED, QueueStatus.INVALIDATED, QueueStatus.ARCHIVED},
    QueueStatus.IMPLEMENTED: set(), QueueStatus.INVALIDATED: set(), QueueStatus.ARCHIVED: set(),
}
```

- [ ] **Step 4: Run queue tests**

Run: `python3 -m pytest -q tests/selfloop/test_opportunity_queue.py`

Expected: `9 passed`.

- [ ] **Step 5: Commit the opportunity queue**

```bash
git add scripts/selfloop_supervisor/opportunity_queue.py tests/selfloop/test_opportunity_queue.py
git commit -m "feat(selfloop): persist immutable opportunity cards"
```

### Task 4: Integrate capsule and pack lifecycle with the protected controller

**Files:**
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_supervisor/budget.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_supervisor/strategy_rpc.py`
- Modify: `scripts/selfloop_supervisor/model_broker.py`
- Test: `tests/selfloop/test_research_preparation.py`

**Interfaces:**
- Adds protected `SelfloopController.prepare_generation(session: MutationSession) -> FinalPreparationReceipt | FailedPreparationReceipt`; only `SelfloopController.handle` creates the session. Both receipt classes fix `kind="generation-preparation"` and respectively `stage="final"` or `stage="terminal-failed"`.
- Produces `PreparationReceiptRepository.commit_final(session, receipt, capability: MutationCapability) -> FinalPreparationReceipt` and `commit_failed(session, receipt, capability: MutationCapability) -> FailedPreparationReceipt`. Each requires `RECEIPT_PERSIST` for the exact reserved pack ID and phase; the repository, strategy, broker, and caller cannot mint capabilities.
- Consumes P05 `PhaseJournal.reserve_id(session, phase, kind)`, capability-scoped `BudgetMeter`, `StrategyClient.call_with_receipt`, and P06 `PlannerBroker`. Every strategy subprocess and the single planning request has its own persisted grant and reconciliation.
- Every phase mutation receives a distinct session capability: artifact input staging, raw receipt persistence, capsule persistence, budget grant/reconcile, and queue pack persistence. No P06 controller path passes a naked idempotency string to a mutator.
- `FinalPreparationReceipt` names reserved capsule/pack/card IDs and hashes, queued card IDs, raw/final receipt event digests, three strategy-call receipts, planner call/usage receipt, four grant event digests, four terminal budget-reconciliation event digests, and omission reasons. `FailedPreparationReceipt` names the same reserved IDs, last completed phase, raw call/artifact/event digests, all started budget receipts, and structured error.
- `PhaseJournal.reserve_id` appends `object.id.reserved` before effects and returns the existing ID on replay. `run_phase` persists raw phase output before advancing. Resume never repeats the planner call or changes capsule, pack, or card IDs.

- [ ] **Step 1: Write failing persistence-before-selection and replacement-authorization tests**

```python
def test_prepare_persists_pack_before_returning_and_rejects_unjustified_replacement(controller):
    receipt = controller.handle(v2_request("advance", "prepare-1")).receipt
    assert controller.ledger.event_sequence("idea-pack.persisted") < controller.ledger.event_sequence("generation.prepared")
    denied = controller.handle(v2_request("advance", "prepare-2")).receipt
    assert denied.kind == "generation-preparation" and denied.stage == "terminal-failed"
    assert denied.error.code == "replacement-pack-denied"
    assert receipt.queued_card_ids

def test_prepare_persists_every_budget_receipt_and_single_planning_call(controller):
    receipt = controller.handle(v2_request("advance", "prepare-metered-1")).receipt
    assert receipt.kind == "generation-preparation" and receipt.stage == "final"
    assert len(receipt.budget_reconciliation_event_digests) == 4
    assert all(
        controller.ledger.event_by_digest(digest).event_type == "budget.reconciled"
        for digest in receipt.budget_reconciliation_event_digests
    )
    assert controller.planner_broker.calls == 1
    assert receipt.planner_usage.source in {"provider", "conservative-reservation"}

def test_crash_reuses_reserved_ids_and_raw_planner_receipt(controller_factory):
    first = controller_factory(crash_after="planner-raw-persisted")
    with pytest.raises(SimulatedCrash):
        first.handle(v2_request("advance", "prepare-replay-1"))
    reserved = first.ledger.reserved_ids("prepare-replay-1")
    resumed = controller_factory().handle(v2_request("advance", "prepare-replay-1")).receipt
    assert (resumed.capsule_id, resumed.pack_id, *resumed.queued_card_ids) == reserved
    assert controller_factory().planner_broker.calls == 1

def test_provider_failure_reconciles_then_appends_terminal_failed_receipt(controller):
    controller.planner_broker.fail_with_unknown_usage()
    response = controller.handle(v2_request("advance", "prepare-failed-1"))
    assert response.status == "failed"
    assert response.receipt.kind == "generation-preparation"
    assert response.receipt.stage == "terminal-failed"
    assert response.receipt.budget_reconciliation_event_digests
    assert controller.ledger.last_event("root-1", "generation.preparation.failed").digest == response.receipt.event_digest
```

- [ ] **Step 2: Run and observe the missing lifecycle**

Run: `python3 -m pytest -q tests/selfloop/test_research_preparation.py`

Expected: fails because `prepare_generation` is undefined.

- [ ] **Step 3: Implement ID-first replayable phases, persisted metering, and final-or-failed receipts**

```python
def run_metered_phase(self, session, phase, request, invoke):
    grant = self.budget.authorize(
        request, session.issue(MutationOperation.BUDGET_GRANT, phase, f"{phase}:grant"),
    )
    raw_call = self.recovery.run_phase(
        session, f"{phase}:call",
        capability=session.issue(MutationOperation.RECEIPT_PERSIST, phase, f"{phase}:raw-receipt"),
        effect=lambda: invoke(grant),
    )
    budget_receipt = self.budget.reconcile(
        grant.grant_id, raw_call.usage_receipt,
        session.issue(MutationOperation.BUDGET_RECONCILE, grant.grant_id, f"{phase}:reconcile"),
    )
    raw_call.require_success()
    return raw_call, budget_receipt

def prepare_generation(self, session):
    scope = session.scope
    capsule_id = self.phases.reserve_id(session, "capsule-id", "capsule")
    pack_id = self.phases.reserve_id(session, "pack-id", "idea-pack")
    try:
        input_receipts = self.artifacts.stage_inputs(
            scope.root_id, selected_evidence_sources,
            session.issue(MutationOperation.ARTIFACT_STAGE, capsule_id, "evidence-inputs"),
        )
        capsule_call, evidence_budget = self.run_metered_phase(
            session, "compile-evidence", UsageRequest.for_tool(scope, "compile-evidence", 1),
            lambda grant: self.strategy.call_with_receipt(
                "compile-evidence", self.strategy_root,
                strategy_request(scope, "compile-evidence", grant, evidence_payload(capsule_id)),
                artifact_inputs=tuple(row.path for row in input_receipts),
            ),
        )
        capsule = validate_capsule(capsule_call.payload, scope, expected_capsule_id=capsule_id)
        self.artifacts.persist_json(
            scope.root_id, "evidence-capsule", capsule_id, capsule.to_dict(), capsule.digest,
            session.issue(MutationOperation.ARTIFACT_PERSIST, capsule_id, "persist-capsule"),
        )
        prompt_call, prompt_budget = self.run_metered_phase(
            session, "build-idea-prompt", UsageRequest.for_tool(scope, "build-idea-prompt", 1),
            lambda grant: self.strategy.call_with_receipt(
                "build-idea-prompt", self.strategy_root,
                strategy_request(scope, "build-idea-prompt", grant, {"capsule": capsule.to_dict()}),
            ),
        )
        model_call, planning_budget = self.run_metered_phase(
            session, "plan-idea-pack", UsageRequest.for_proposal(scope, "idea-pack", prompt_call.payload),
            lambda grant: self.planner_broker.generate(PromptEnvelope.from_dict(prompt_call.payload), grant),
        )
        card_ids = tuple(
            self.phases.reserve_id(session, f"card-id:{index}", "card")
            for index, _ in enumerate(model_call.payload.get("cards", []))
        )
        pack_call, finalize_budget = self.run_metered_phase(
            session, "finalize-idea-pack", UsageRequest.for_tool(scope, "finalize-idea-pack", 1),
            lambda grant: self.strategy.call_with_receipt(
                "finalize-idea-pack", self.strategy_root,
                strategy_request(scope, "finalize-idea-pack", grant, {
                    "capsule": capsule.to_dict(), "modelOutput": model_call.payload,
                    "packId": pack_id, "cardIds": card_ids,
                }),
            ),
        )
        pack = validate_idea_pack(pack_call.payload, capsule, pack_id, card_ids)
        queue = self.opportunities.persist_pack(
            pack, session.issue(MutationOperation.QUEUE_PERSIST, pack_id, "persist-pack"),
        )
        final = FinalPreparationReceipt.from_parts(
            capsule, pack, queue, raw_calls=(capsule_call, prompt_call, model_call, pack_call),
            budgets=(evidence_budget, prompt_budget, planning_budget, finalize_budget),
        )
        return self.preparation_receipts.commit_final(
            session, final,
            session.issue(MutationOperation.RECEIPT_PERSIST, pack_id, "persist-preparation-final"),
        )
    except BaseException as error:
        failed = FailedPreparationReceipt.from_journal(session, self.phases, error)
        return self.preparation_receipts.commit_failed(
            session, failed,
            session.issue(MutationOperation.RECEIPT_PERSIST, pack_id, "persist-preparation-failed"),
        )
```

The prompt-building and pack-finalization subprocess calls are deterministic tool calls, but each still has a distinct single-use grant, raw process receipt, and persisted reconciliation. Only `PlannerBroker.generate` is the one planning/model call. `run_phase` returns its persisted raw receipt on replay, so a crash after a provider response cannot repeat the provider call. `FailedPreparationReceipt.from_journal` includes every reserved ID, raw artifact, completed phase, and budget event; it never deletes a partially built pack. No usage field returned by strategy is accepted as the meter of record.

- [ ] **Step 4: Run focused and adjacent tests**

Run: `python3 -m pytest -q tests/selfloop/test_research_preparation.py tests/selfloop/test_ledger.py tests/selfloop/test_strategy_boundary.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit generation preparation**

```bash
git add scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/strategy_rpc.py scripts/selfloop_supervisor/model_broker.py tests/selfloop/test_research_preparation.py
git commit -m "feat(selfloop): prepare persistent research generations"
```

### Task 5: Roll the P06 protected bundle through the active P05 controller

**Files:**
- Modify: `scripts/selfloop_supervisor/runtime_registry.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_cli.py`
- Test: `tests/selfloop/test_p06_supervisor_rollover.py`

**Interfaces:**
- Consumes the currently active, rehash-verified P05 `SupervisorBundleReceipt`, P02 `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, P05 `MutationSession`, `SupervisorUpgradeService.authorize/prepare`, `SupervisorRuntimeRegistry.stage/activate/resolve_bundle`, and typed authorize/prepare/activate requests.
- Reuses P05's three-phase `SupervisorUpgradeService.authorize/prepare/resolve_pending` and `SupervisorRuntimeRegistry.activate` without adding a combined or source-callable roll-forward mutator. Produces a protected host-load proof naming `bundle_digest`, resolved bundle path, source release ID, manifest digest, source-attestation digest, path-independent release-bundle `receipt_digest`, and loaded module paths.
- P06 source has no activation authority. The active P05 bundle parses and authorizes the request, resolves the verified release byte handle, issues separate `SUPERVISOR_STAGE`/`SUPERVISOR_ACTIVATE` capabilities, and retains P05 as rescue until the P06 host proof passes.

- [ ] **Step 1: Write failing exact-content, replay, path, authority, and rollback tests**

```python
def test_active_p05_rolls_to_exact_p06_bundle(p05_controller, p06_release_bundle):
    prior = p05_controller.runtime.load_active("root-1")
    p05_controller.tty.confirm_commit(p06_release_bundle.release_identity.commit_sha)
    authorization = p05_controller.handle(authorize_upgrade_request(
        source_commit=p06_release_bundle.release_identity.commit_sha,
        release_id=p06_release_bundle.release_identity.release_id,
        source_attestation_digest=p06_release_bundle.source_attestation_digest,
        idempotency_key="authorize-p06",
    )).receipt
    assert authorization.release_bundle_receipt_digest == p06_release_bundle.receipt_digest
    pending = p05_controller.handle(prepare_upgrade_request(
        authorization_receipt_digest=authorization.event_digest,
        expected_prior_digest=prior.bundle_digest, idempotency_key="prepare-p06",
    )).receipt
    request = activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=prior.bundle_digest, idempotency_key="activate-p06:commit",
    )
    first = p05_controller.handle(request).receipt
    replay = p05_controller.handle(request).receipt
    active = p05_controller.runtime.load_active("root-1")
    assert replay == first
    assert first.prior_bundle_digest == prior.bundle_digest
    assert active.bundle_digest == first.active_bundle_digest
    assert active.path == p05_controller.runtime.bundles_root / active.bundle_digest
    assert active.path.joinpath("scripts/selfloop_supervisor/receipt_contract.py").is_file()
    assert first.host_load_proof.bundle_digest == active.bundle_digest
    assert first.host_load_proof.loaded_module_root == active.path

def test_p06_source_cannot_self_authorize_and_failed_host_proof_restores_p05(
    p05_controller, p06_release_bundle,
):
    with pytest.raises(MutationDenied, match="active controller session required"):
        p06_source_runtime().roll_forward(p06_release_bundle)
    prior = p05_controller.runtime.load_active("root-1")
    p05_controller.host_probe.fail_with("receipt parser imported from source checkout")
    p05_controller.tty.confirm_commit(p06_release_bundle.release_identity.commit_sha)
    authorization = p05_controller.handle(authorize_upgrade_request(
        source_commit=p06_release_bundle.release_identity.commit_sha,
        release_id=p06_release_bundle.release_identity.release_id,
        source_attestation_digest=p06_release_bundle.source_attestation_digest,
        idempotency_key="authorize-p06-failed",
    )).receipt
    pending = p05_controller.handle(prepare_upgrade_request(
        authorization_receipt_digest=authorization.event_digest,
        expected_prior_digest=prior.bundle_digest, idempotency_key="prepare-p06-failed",
    )).receipt
    failed = p05_controller.handle(activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=prior.bundle_digest, idempotency_key="activate-p06-failed:commit",
    ))
    assert failed.status == "failed"
    assert p05_controller.runtime.load_active("root-1").bundle_digest == prior.bundle_digest
    assert failed.receipt.stage == "terminal-failed"
```

- [ ] **Step 2: Run and confirm the P06 rollover proof is red**

Run: `python3 -m pytest -q tests/selfloop/test_p06_supervisor_rollover.py`

Expected: tests fail because the active P05 bundle lacks the P06 receipt/evidence/queue modules and no P06 host-load proof exists.

- [ ] **Step 3: Implement old-runtime-authorized build, activation, host proof, and compensation**

Route the TTY-only `authorize-supervisor-upgrade` through the active P05 dispatcher; its injected TTY adapter verifies direct confirmation, resolves the already materialized P02 receipt with `open_verified(release_id, source_attestation_digest)`, verifies `receipt_digest`, and binds commit, release ID, manifest, source-attestation, path-independent release-bundle receipt, and active P05 digest. Route `prepare-supervisor-upgrade` with only that authorization event digest and expected prior digest. It reopens the same verified bytes, verifies `receipt_digest`, stages under `SUPERVISOR_STAGE`, and persists `PendingSupervisorUpgrade`. A separate `activate-supervisor` request supplies only the pending ID/expected prior digest; `handle` resolves it and activates under `SUPERVISOR_ACTIVATE`. Resolve the active path from `SIPS_HOME`, rehash it, and run status plus imports for `receipt_contract`, `evidence_contract`, `idea_pack_contract`, and `opportunity_queue` from that path.

Persist the raw host proof before accepting the rollover. A digest, path, source-release, or loaded-module-root mismatch executes the P05 compensation path, restores the prior pointer, appends `supervisor.activation.failed` with `kind="conformance", stage="terminal-failed"`, and leaves P05 authoritative. A matching proof appends `supervisor.host-load.proved`; replay returns the original activation/host receipts without staging again.

- [ ] **Step 4: Run rollover plus preparation and recovery tests**

Run: `python3 -m pytest -q tests/selfloop/test_p06_supervisor_rollover.py tests/selfloop/test_research_preparation.py tests/selfloop/test_recovery.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit the P06 protected-bundle rollover**

```bash
git add scripts/selfloop_supervisor/runtime_registry.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_cli.py tests/selfloop/test_p06_supervisor_rollover.py
git commit -m "feat(selfloop): activate protected P06 research runtime"
```

## Plan Verification

- [ ] Run `python3 -m pytest -q tests/selfloop/test_evidence_capsule.py tests/selfloop/test_idea_pack.py tests/selfloop/test_opportunity_queue.py tests/selfloop/test_research_preparation.py tests/selfloop/test_p06_supervisor_rollover.py`; expected: all pass.
- [ ] Run `python3 scripts/selfloop_cli.py status --root . --json`; expected: capsule/pack/queue counts are visible, conformance remains `C1`, and no experiment is claimed.
- [ ] Verify status reports the active P06 `bundle_digest`, the resolved content-addressed path, source release ID, host-load proof digest, and retained P05 rescue digest; source presence alone is reported as non-authoritative.
- [ ] Run `python3 scripts/validate_v2.py --check-eval && git diff --check`; expected: both exit `0` and diff check emits no output.

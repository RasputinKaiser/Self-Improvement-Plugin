# Lineages, Selector, Operators, and Budgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent search lineages, versioned mechanisms/operators, cost-aware selection with enforced diversity, change-scale escalation, and protected token/tool/concurrency budgets.

**Architecture:** Evolvable statistics and ranking live in `scripts/selfloop_strategy/`; they consume an authorized bounded snapshot and return a schema-validated selection proposal over JSON subprocess. Protected modules in `scripts/selfloop_supervisor/` independently enforce lineage counts, exploration credit, mechanism streaks, scale locks, budget tranches, concurrency, and grants before recording a selected card.

**Tech Stack:** Python 3.10+, standard-library `dataclasses`, `decimal`, `json`, `statistics`, Plan 05 SQLite ledger, Plan 06 opportunity queue, pytest 8+.

## Global Constraints

- Normative contract: `SELFLOOP_ADAPTIVE_HARNESS_SPEC.md`, `selfloop.spec.v1`, approved digest `e9468f045c820d2b287a88e3ffbe75e62aba7f92a7c20071239fa6436dda3a38`.
- Standard mode keeps exactly three live lineage theories after the first pack; deep mode keeps four. Champion and exploration are always present.
- The initial operators are `DIAGNOSE`, `IMPROVE`, `DEBUG`, `SIMPLIFY`, `REDESIGN`, `COMBINE`, `TOOL_BUILD`, and `META`, each with version `1`.
- At least 15% of each rolling 20 eligible attempts explores an under-tested approach; before 20 attempts, exploration credit must be spent no later than attempt seven.
- The same normalized mechanism cannot be approved more than twice consecutively.
- Selection uses positive expected-token floor and records selector version, coefficients, input statistics, score components, and reason.
- Two distinct failed smaller mechanisms against the same evidenced cause unlock the next scale. Large unlocks after those failures or after a missing cross-component capability is proven, and its evidence capsule must identify the cross-component cause. `META` requires its section 18 trigger.
- Standard budget is soft `60000`, hard `120000`, candidates `3`, repairs `2`, builders `1`, concurrent agents `2`, lineages `3`.
- Deep budget is soft `150000`, hard `300000`, candidates `8`, repairs `4`, builders `1`, concurrent agents `2`, lineages `4`.
- Hard-cap tranches are 30%, 35%, 35%; tranche two needs G1 improvement or a newly supported distinct cause, and tranche three needs a G2 survivor.
- Unknown usage is never zero. A call without authoritative usage or a conservative enforceable reservation is denied before execution.
- `propose-lineages` is a P05 operation-policy entry and always runs through `StrategyClient` with a distinct controller-issued grant, raw receipt persistence capability, and ledger-persisted `BudgetReceipt`; direct in-process proposal is unit-test-only.
- The controller journals lineage IDs, selection ID, grant IDs, and reservation IDs before their side effects. Restart reuses each ID and raw phase receipt. Every P07 success or failure returns a `kind`/`stage`-discriminated final or terminal-failed receipt.
- Candidate, repair, builder, and agent reservations are separate protected ledger objects with profile caps, exact scope/resource/purpose, session capabilities, and terminal release/reconciliation receipts. They are acquired before P08 worktree/process effects and are never represented by counters alone.
- Crossing the soft budget requires a persisted `BudgetContinuationReceipt` with surviving-gate event digest, selector-justification digest, policy/profile/state revision, and `continue|stop` decision. It does not raise the hard cap or unlock a tranche.

---

### Task 1: Persist the required distinct lineage inventory

**Files:**
- Create: `scripts/selfloop_strategy/lineages.py`
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Create: `scripts/selfloop_supervisor/lineage_contract.py`
- Modify: `scripts/selfloop_supervisor/contracts.py`
- Test: `tests/selfloop/test_lineages.py`

**Interfaces:**
- Produces untrusted `propose_lineages(pack: Mapping[str, Any], profile: str) -> dict[str, Any]`, protected `validate_lineages(payload: Mapping[str, Any], profile: BudgetProfile, expected_lineage_ids: Sequence[str]) -> tuple[Lineage, ...]`, and `LineageRegistry.persist(lineages: Sequence[Lineage], capability: MutationCapability) -> FinalLineageProposalReceipt`.
- Registers `RawLineageProposalReceipt(kind="lineage-proposal", stage="raw")`, `FinalLineageProposalReceipt(kind="lineage-proposal", stage="final")`, and `FailedLineageProposalReceipt(kind="lineage-proposal", stage="terminal-failed")` with P06 exact receipt dispatch. Strategy output contains theories but no authoritative IDs; protected validation assigns the pre-journaled IDs by position and rejects a count mismatch.
- Every lineage records ID, kind, theory, immutable base release, ancestry, mechanism history, task families, gate outcomes, resources, and status.

- [ ] **Step 1: Write failing standard/deep, distinct-theory, and ancestry-cycle tests**

```python
@pytest.mark.parametrize(("profile", "count"), [("standard", 3), ("deep", 4)])
def test_profile_retains_distinct_required_lineages(pack, profile, count):
    expected_ids = tuple(f"lineage-{index}" for index in range(count))
    lineages = validate_lineages(
        propose_lineages(pack, profile), budget_profile(profile), expected_lineage_ids=expected_ids,
    )
    assert len(lineages) == count
    assert tuple(item.lineage_id for item in lineages) == expected_ids
    assert {item.kind for item in lineages} >= {"champion", "exploration"}
    assert len({item.theory_fingerprint for item in lineages}) == count

def test_ancestry_must_be_acyclic():
    with pytest.raises(InvalidLineage, match="ancestry cycle"):
        validate_ancestry({"lineage-a": "lineage-b", "lineage-b": "lineage-a"})

def test_lineage_registry_requires_exact_session_capability(lineage_registry, validated_lineages):
    with pytest.raises(MutationDenied, match="LINEAGE_PERSIST capability required"):
        lineage_registry.persist(validated_lineages, capability=None)
```

- [ ] **Step 2: Run and confirm the lineage modules are missing**

Run: `python3 -m pytest -q tests/selfloop/test_lineages.py`

Expected: collection fails with missing `lineages`.

- [ ] **Step 3: Implement deterministic theory fingerprints and profile counts**

```python
def theory_fingerprint(kind: str, theory: str, mechanism: str) -> str:
    normalized = {"kind": kind, "theory": " ".join(theory.lower().split()), "mechanism": mechanism}
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()

def required_lineage_kinds(profile: str, cards: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    kinds = {card["lineageKind"] for card in cards}
    third = "repair" if "repair" in kinds else "structural" if "structural" in kinds else "exploration"
    standard = ("champion", "exploration", third)
    fourth = "structural" if third != "structural" and "structural" in kinds else "exploration"
    return standard if profile == "standard" else standard + (fourth,)
```

The P05 strategy operation policy fixes `propose-lineages` to read-only strategy/artifact inputs and disposable scratch. Production code invokes it only through the metered controller integration in Task 5. `LineageRegistry.persist` appends the exact validated lineages and final receipt in one ledger transaction keyed by the session capability.

- [ ] **Step 4: Run lineage tests**

Run: `python3 -m pytest -q tests/selfloop/test_lineages.py`

Expected: `8 passed`.

- [ ] **Step 5: Commit lineage persistence**

```bash
git add scripts/selfloop_strategy/lineages.py scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/lineage_contract.py scripts/selfloop_supervisor/contracts.py tests/selfloop/test_lineages.py
git commit -m "feat(selfloop): persist distinct search lineages"
```

### Task 2: Add normalized mechanisms and versioned operator statistics

**Files:**
- Create: `references/selfloop/policies/mechanism-taxonomy-v1.json`
- Create: `scripts/selfloop_strategy/mechanisms.py`
- Create: `scripts/selfloop_strategy/operators.py`
- Create: `scripts/selfloop_supervisor/operator_contract.py`
- Test: `tests/selfloop/test_operators.py`

**Interfaces:**
- Consumes immutable `mechanism-taxonomy-v1.json`, whose digest is pinned in generation state and whose canonical dimensions are operator, affected interface, causal-hypothesis ID, and behavior-change type. Problem/solution wording is descriptive only and never changes mechanism identity.
- Produces: `classify_mechanism(card: Mapping[str, Any], taxonomy: MechanismTaxonomy) -> str`, `OperatorRegistry.record(result: AttemptResult) -> OperatorStats`, and `OperatorRegistry.is_dormant(operator: str, task_fingerprint: str) -> bool`.

- [ ] **Step 1: Write failing normalization and dormancy tests**

```python
def test_rewording_keeps_mechanism_identity():
    first = card(
        problem="Reduce duplicated context", operator="SIMPLIFY",
        affected_interface="context-builder", causal_hypothesis_id="duplicate-inputs",
        behavior_change_type="delete-redundancy",
    )
    reworded = replace(first, problem="Remove repeated prompt material", solution="Use a smaller projection")
    assert classify_mechanism(first, taxonomy_v1) == classify_mechanism(reworded, taxonomy_v1)
    assert classify_mechanism(
        replace(first, causal_hypothesis_id="stale-cache"), taxonomy_v1
    ) != classify_mechanism(first, taxonomy_v1)

def test_operator_dormancy_requires_all_thresholds(registry):
    for index in range(12):
        registry.record(result(operator="SIMPLIFY", family=f"family-{index % 3}", g1=True, g2=index < 6, gain=0.0))
    assert registry.is_dormant("SIMPLIFY", "tasks-v1") is True
    registry.record(result(operator="SIMPLIFY", family="family-1", g1=True, g2=True, gain=0.01))
    assert registry.is_dormant("SIMPLIFY", "tasks-v1") is False

def test_recent_six_for_dormancy_are_eligible_trials_not_only_g1_completions(registry):
    history = twelve_g1_complete_trials(no_g2_survivors=True)
    history += [result(eligible=True, g1=False, g2=True) for _ in range(6)]
    assert dormant(history) is False
```

- [ ] **Step 2: Run and observe missing modules**

Run: `python3 -m pytest -q tests/selfloop/test_operators.py`

Expected: collection fails with missing `mechanisms`.

- [ ] **Step 3: Implement the registry and exact dormancy predicate**

```python
OPERATORS = {name: "1" for name in (
    "DIAGNOSE", "IMPROVE", "DEBUG", "SIMPLIFY", "REDESIGN", "COMBINE", "TOOL_BUILD", "META"
)}

def dormant(results: Sequence[AttemptResult]) -> bool:
    g1 = [item for item in results if item.g1_complete]
    recent = [item for item in results if item.eligible_attempt][-6:]
    return (
        len(g1) >= 12 and len({item.task_family for item in g1}) >= 3
        and len(recent) == 6 and not any(item.g2_survived for item in recent)
        and statistics.median(item.normalized_gain for item in g1) <= 0
    )
```

Load and digest the taxonomy from the pinned supervisor bundle; reject unknown dimensions instead of falling back to free text. `classify_mechanism` canonicalizes only the four taxonomy dimensions and hashes them with taxonomy version/digest. Add an adversarial test proving edits to problem, implementation prose, and expected-benefit wording cannot reset the two-attempt mechanism streak.

- [ ] **Step 4: Run operator tests**

Run: `python3 -m pytest -q tests/selfloop/test_operators.py`

Expected: all operator/mechanism tests pass and pytest exits `0`.

- [ ] **Step 5: Commit operators and mechanism taxonomy**

```bash
git add references/selfloop/policies/mechanism-taxonomy-v1.json scripts/selfloop_strategy/mechanisms.py scripts/selfloop_strategy/operators.py scripts/selfloop_supervisor/operator_contract.py tests/selfloop/test_operators.py
git commit -m "feat(selfloop): track mechanisms and operator survival"
```

### Task 3: Rank cards with cost-aware diversity and stall handling

**Files:**
- Create: `scripts/selfloop_strategy/selector.py`
- Create: `scripts/selfloop_supervisor/selection_policy.py`
- Test: `tests/selfloop/test_selector.py`

**Interfaces:**
- Produces: `rank_candidates(snapshot: Mapping[str, Any]) -> dict[str, Any]` and `SelectionPolicy.approve(proposal: Mapping[str, Any], snapshot: SelectionSnapshot) -> SelectionReceipt`.
- Strategy response schema is `selfloop.selection-proposal.v1`; only IDs present in the supplied snapshot are eligible.

- [ ] **Step 1: Write failing priority, exploration, streak, and stall tests**

```python
def test_selector_uses_positive_cost_floor_and_supervisor_rejects_third_mechanism(policy):
    ranked = rank_candidates(snapshot(cards=[candidate("a", tokens=0), candidate("b", tokens=1000)]))
    assert all(item["components"]["tokenCost"] >= 1 for item in ranked["ranking"])
    with pytest.raises(SelectionDenied, match="same mechanism more than twice"):
        policy.approve(proposal("a", mechanism="context-pruning"), selection_snapshot(streak=2))

def test_exploration_credit_is_spent_by_seventh_eligible_attempt(policy):
    receipt = policy.approve(proposal("explore-card"), selection_snapshot(eligible_attempts=6, exploration_attempts=0))
    assert receipt.exploration is True

def test_every_rolling_twenty_contains_three_exploration_attempts(policy):
    receipts = [policy.approve(next_proposal(index), rolling_snapshot(index)) for index in range(40)]
    for start in range(21):
        assert sum(item.exploration for item in receipts[start:start + 20]) >= 3

def test_dormant_operator_probe_occurs_once_per_window_or_distribution_change(policy):
    first = policy.approve(dormant_probe_proposal(), selection_snapshot(window=1, task_distribution="a"))
    assert first.dormant_operator_probe is True
    with pytest.raises(SelectionDenied, match="dormant probe already spent"):
        policy.approve(dormant_probe_proposal(), selection_snapshot(window=1, task_distribution="a"))
    changed = policy.approve(dormant_probe_proposal(), selection_snapshot(window=1, task_distribution="b"))
    assert changed.dormant_operator_probe is True

def test_stall_ignores_cancelled_infrastructure_and_incomplete_attempts():
    history = [cancelled_attempt(operator="DEBUG"), infrastructure_failure(operator="REDESIGN")]
    assert lineage_stalled(history) is False
    history += [completed_failure(operator="DEBUG"), completed_failure(operator="REDESIGN")]
    assert lineage_stalled(history) is True
```

- [ ] **Step 2: Run and verify selector tests fail**

Run: `python3 -m pytest -q tests/selfloop/test_selector.py`

Expected: collection fails with missing `selector`.

- [ ] **Step 3: Implement recorded score components and protected overrides**

```python
def priority(card: CandidateStats) -> ScoreComponents:
    token_cost = max(1, card.expected_tokens)
    exploitation = card.expected_survival * card.expected_gain / token_cost
    return ScoreComponents(exploitation, card.uncertainty_bonus, card.novelty_bonus, token_cost)

def lineage_stalled(results: Sequence[AttemptResult]) -> bool:
    completed = [item for item in results if item.completed_attempt]
    recent = completed[-4:]
    last_two = completed[-2:]
    distinct_operator_failure = len(last_two) == 2 and len({item.operator for item in last_two}) == 2 and not any(item.g2_survived for item in last_two)
    flat_scores = len(recent) == 4 and all(item.comparable and item.development_delta <= 0 for item in recent)
    return distinct_operator_failure or flat_scores
```

The protected override scheduler enforces at least three exploration selections in every completed rolling window of twenty eligible attempts, forces the first credit no later than attempt seven, and schedules one eligible dormant-operator probe per exploration window. A changed task-distribution fingerprint resets only the dormant-probe opportunity, not exploration or mechanism history.

- [ ] **Step 4: Run selector tests**

Run: `python3 -m pytest -q tests/selfloop/test_selector.py`

Expected: all selector tests pass and pytest exits `0`.

- [ ] **Step 5: Commit selection policy**

```bash
git add scripts/selfloop_strategy/selector.py scripts/selfloop_supervisor/selection_policy.py tests/selfloop/test_selector.py
git commit -m "feat(selfloop): enforce cost-aware diverse selection"
```

### Task 4: Meter protected budgets, tranches, scale, and concurrency

**Files:**
- Modify: `scripts/selfloop_supervisor/budget.py`
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Create: `scripts/selfloop_supervisor/change_scale.py`
- Test: `tests/selfloop/test_budget.py`

**Interfaces:**
- Extends the P05 `BudgetMeter` and ledger-backed `BudgetGrant(grant_id, root_id, campaign_id, category, purpose, reserved_tokens, tool_call_cap, expires_at)`; it does not create a parallel meter.
- Produces capability-scoped `BudgetMeter.authorize(request, capability) -> BudgetGrant`, `reconcile(grant_id, usage, capability) -> BudgetReceipt`, `unlock(scope, evidence_event_digest, capability) -> TrancheReceipt`, `review_soft_continuation(scope, surviving_gate_event_digest, selector_justification_digest, decision, capability) -> BudgetContinuationReceipt`, `reserve_candidate(scope, candidate_id, capability)`, `reserve_repair(scope, repair_id, parent_experiment_id, capability)`, `acquire_builder(scope, builder_id, purpose, capability)`, `acquire_agent(scope, agent_id, purpose, capability)`, and `release_reservation(reservation_id, usage, capability) -> ReservationReceipt`; plus `ChangeScalePolicy.approve(card, history) -> ScaleReceipt`.
- Every method appends its typed receipt to the canonical ledger before returning. Grants use `kind="budget", stage="final"`; denied/failed reconciliation uses `kind="budget", stage="terminal-failed"`. Reservation receipts carry `reservation_kind=candidate|repair|builder|agent`, exact root/campaign/resource/purpose/profile cap, state, and event digest.
- A reservation is single-use and session-bound. Candidate/repair limits count reserved plus terminally consumed entries; builder/agent limits count active entries. Restart and abort reconcile unknown active use conservatively and append release receipts before the root lock may be released.

- [ ] **Step 1: Write failing profile, tranche, unknown-usage, scale, and concurrency tests**

```python
def test_standard_tranches_and_unknown_usage_fail_closed(meter, gate_events):
    assert meter.available_tokens("root-1") == 36000
    with pytest.raises(BudgetDenied, match="authoritative usage or conservative bound required"):
        meter.authorize(UsageRequest(
            root_id="root-1", campaign_id="campaign-1", category="proposal",
            purpose="idea-pack", estimated_tokens=None, output_cap=None, tool_call_cap=0,
        ), budget_capability("unknown-grant"))
    tranche_two = meter.unlock(
        scope(), gate_events.distinct_root_cause.digest, budget_capability("unlock-tranche-2"),
    )
    assert meter.available_tokens("root-1") == 78000
    tranche_three = meter.unlock(
        scope(), gate_events.g2_survivor.digest, budget_capability("unlock-tranche-3"),
    )
    assert meter.available_tokens("root-1") == 120000
    assert all(meter.ledger.event_by_digest(row.event_digest) for row in (tranche_two, tranche_three))

@pytest.mark.parametrize("category", ["model", "subagent", "memory", "proposal", "evaluation", "judge", "tool"])
def test_every_nondeterministic_category_requires_a_grant(meter, category):
    grant = meter.authorize(UsageRequest(
        root_id="root-1", campaign_id="campaign-1", category=category,
        purpose=f"test-{category}", estimated_tokens=100, output_cap=50, tool_call_cap=1,
    ), budget_capability(f"grant:{category}"))
    assert grant.category == category

def test_soft_budget_requires_persisted_continuation_receipt(meter, gate_events, selector_event):
    meter.force_actual_usage("root-1", 60000)
    with pytest.raises(BudgetDenied, match="soft-budget continuation review required"):
        meter.authorize(UsageRequest(
            root_id="root-1", campaign_id="campaign-1", category="proposal",
            purpose="replacement-pack", estimated_tokens=100, output_cap=50, tool_call_cap=0,
        ), budget_capability("grant:before-review"))
    continuation = meter.review_soft_continuation(
        scope(), gate_events.g1_survivor.digest, selector_event.digest, "continue",
        budget_capability("soft-review:continue"),
    )
    assert continuation.decision == "continue"
    assert meter.ledger.event_by_digest(continuation.event_digest).event_type == "budget.soft-continuation.reviewed"
    grant = meter.authorize(
        UsageRequest.for_proposal(scope(), "replacement-pack", estimated_tokens=100, output_cap=50),
        budget_capability("grant:after-review"),
    )
    assert grant.continuation_receipt_digest == continuation.event_digest

def test_soft_budget_stop_receipt_blocks_further_calls(meter, gate_events, selector_event):
    meter.force_actual_usage("root-1", 60000)
    stopped = meter.review_soft_continuation(
        scope(), gate_events.g1_survivor.digest, selector_event.digest, "stop",
        budget_capability("soft-review:stop"),
    )
    assert stopped.decision == "stop"
    with pytest.raises(BudgetDenied, match="continuation review stopped campaign"):
        meter.authorize(
            UsageRequest.for_tool(scope(), "after-stop", tool_call_cap=1),
            budget_capability("grant:after-stop"),
        )

def test_large_change_unlocks_by_either_normative_evidence_branch(scale_policy):
    failed = scale_policy.approve(
        card(change_scale="large", cross_component_cause="routing-boundary"),
        two_failed_smaller_mechanisms(same_evidenced_cause=True),
    )
    missing = scale_policy.approve(
        card(
            change_scale="large", cross_component_cause="missing-ledger-adapter",
            missing_cross_component_capability=True,
        ),
        no_failed_smaller_mechanisms(),
    )
    assert failed.unlock_reason == "two-distinct-smaller-mechanisms-failed"
    assert missing.unlock_reason == "missing-cross-component-capability-proven"

def test_large_change_without_either_branch_or_cross_component_capsule_is_denied(scale_policy):
    with pytest.raises(ScaleDenied, match="large-change evidence"):
        scale_policy.approve(card(change_scale="large"), one_failed_mechanism())

def test_profile_caps_candidates_repairs_builders_and_agents(meter):
    candidate_receipts = [
        meter.reserve_candidate(scope(), f"candidate-{index}", reservation_capability("candidate", index))
        for index in range(3)
    ]
    with pytest.raises(BudgetDenied, match="candidate cap"):
        meter.reserve_candidate(scope(), "candidate-4", reservation_capability("candidate", 4))
    repair_receipts = [
        meter.reserve_repair(
            scope(), f"repair-{index}", "experiment-parent", reservation_capability("repair", index),
        )
        for index in range(2)
    ]
    with pytest.raises(BudgetDenied, match="repair cap"):
        meter.reserve_repair(scope(), "repair-3", "experiment-parent", reservation_capability("repair", 3))
    builder = meter.acquire_builder(scope(), "builder-1", "candidate-1", reservation_capability("builder", 1))
    with pytest.raises(BudgetDenied, match="builder cap"):
        meter.acquire_builder(scope(), "builder-2", "candidate-2", reservation_capability("builder", 2))
    agents = [
        meter.acquire_agent(scope(), f"agent-{index}", "review", reservation_capability("agent", index))
        for index in (1, 2)
    ]
    with pytest.raises(BudgetDenied, match="concurrent agent cap"):
        meter.acquire_agent(scope(), "agent-3", "review", reservation_capability("agent", 3))
    assert {row.reservation_kind for row in (*candidate_receipts, *repair_receipts, builder, *agents)} == {
        "candidate", "repair", "builder", "agent",
    }
    assert all(meter.ledger.event_by_digest(row.event_digest) for row in (*candidate_receipts, *repair_receipts, builder, *agents))

def test_failed_call_without_authoritative_usage_charges_full_reservation(meter):
    grant = meter.authorize(UsageRequest(
        root_id="root-1", campaign_id="campaign-1", category="judge",
        purpose="g4-grader", estimated_tokens=600, output_cap=400, tool_call_cap=0,
    ), budget_capability("grant:g4-grader"))
    receipt = meter.reconcile(
        grant.grant_id, UsageReceipt(status="failed", actual_tokens=None),
        budget_capability("reconcile:g4-grader"),
    )
    assert receipt.charged_tokens == 1000
    assert meter.ledger.event_by_digest(receipt.event_digest).event_type == "budget.reconciled"
```

- [ ] **Step 2: Run and confirm budget tests are red**

Run: `python3 -m pytest -q tests/selfloop/test_budget.py`

Expected: tests fail because P05 budgeting lacks profiles/tranches/cap enforcement and `change_scale` does not exist.

- [ ] **Step 3: Implement immutable profiles, persisted continuation review, and transactional reservations**

```python
PROFILES = {
    "standard": BudgetProfile(60000, 120000, 3, 2, 1, 2, 3),
    "deep": BudgetProfile(150000, 300000, 8, 4, 1, 2, 4),
}

def tranche_cap(profile: BudgetProfile, unlocked: int) -> int:
    return (profile.hard_tokens * (30 if unlocked == 1 else 65 if unlocked == 2 else 100)) // 100

def review_soft_continuation(self, scope, gate_event_digest, selector_event_digest, decision, capability):
    capability.require(MutationOperation.BUDGET_CONTINUATION, resource_id=scope.campaign_id)
    gate = self.ledger.require_event(scope, gate_event_digest, allowed_types={"gate.g1.completed", "gate.g2.completed"})
    selector = self.ledger.require_event(scope, selector_event_digest, allowed_types={"selection.justified"})
    receipt = BudgetContinuationReceipt.derive(
        scope=scope, profile=self.profile(scope), state_revision=self.state.revision(scope),
        surviving_gate_event_digest=gate.digest, selector_justification_digest=selector.digest,
        decision=ContinuationDecision(decision), policy_digest=self.policy_digest,
    )
    event = self.ledger.append(
        scope.root_id, scope.campaign_id, "budget.soft-continuation.reviewed",
        receipt.to_dict(), capability.idempotency_key,
    )
    return receipt.bind_event(event)

def reserve(self, scope, kind, resource_id, purpose, capability):
    capability.require(MutationOperation.BUDGET_RESERVE, resource_id=resource_id)
    with self.ledger.immediate_transaction():
        self._require_profile_capacity(scope, kind)
        return self._append_reservation(scope, kind, resource_id, purpose, capability.idempotency_key)
```

`ChangeScalePolicy` begins at the smallest plausible class. It unlocks the next class after two completed smaller attempts with distinct normalized mechanisms fail against the same evidenced cause. For `large`, it accepts either that branch or an evidence-capsule proof of a specifically missing cross-component capability; in both branches the capsule must name the cross-component cause and affected interfaces. It records which branch, attempt IDs, mechanism IDs, cause evidence digest, and capsule digest authorized the scale. One failure, relabeled mechanisms, unrelated causes, or a caller boolean without the verified capsule is denied.

`authorize` checks the latest matching continuation receipt when actual plus reserved use reaches the soft cap. `continue` permits spending only within the already unlocked tranche/hard cap; `stop` blocks new grants. A changed profile, policy, state revision, selector justification, or surviving-gate event makes the receipt stale. Grant, reconciliation, tranche, continuation, reservation, and release methods all verify the exact `MutationOperation`/resource/session and append their receipts in the same `BEGIN IMMEDIATE` transaction as state changes. Recovery charges unknown grant use at the full reservation and conservatively consumes any candidate/repair reservation whose external work may have begun.

- [ ] **Step 4: Run budget and adjacent selector tests**

Run: `python3 -m pytest -q tests/selfloop/test_budget.py tests/selfloop/test_selector.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit protected budgeting**

```bash
git add scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_supervisor/change_scale.py tests/selfloop/test_budget.py
git commit -m "feat(selfloop): enforce budget tranches and change scale"
```

### Task 5: Integrate approved selection and grants with the controller

**Files:**
- Modify: `scripts/selfloop_supervisor/receipt_contract.py`
- Modify: `scripts/selfloop_supervisor/lineage_contract.py`
- Modify: `scripts/selfloop_supervisor/budget.py`
- Modify: `scripts/selfloop_supervisor/opportunity_queue.py`
- Modify: `scripts/selfloop_supervisor/recovery.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_supervisor/strategy_rpc.py`
- Test: `tests/selfloop/test_selection_integration.py`

**Interfaces:**
- Adds private/session-bound `SelfloopController.select_next(session: MutationSession) -> FinalSelectionReceipt | FailedSelectionReceipt`; only `handle` obtains the root lock and calls it. There is no public root/key mutator. It consumes Plan 06's session-bound `prepare_generation`.
- Registers `RawSelectionProposalReceipt(kind="selection", stage="raw")`, `FinalSelectionReceipt(kind="selection", stage="final")`, and `FailedSelectionReceipt(kind="selection", stage="terminal-failed")`. The final receipt includes pre-journaled selection ID, card, lineage, operator/version, mechanism, score components, exploration decision, change scale, raw proposal event, lineage-proposal event when created, every grant/budget event digest, queue transition event, and pre-selection state revision.
- Produces `SelectionReceiptRepository.commit_final(..., capability: MutationCapability)` and `commit_failed_from_journal(..., capability: MutationCapability)`; both require `RECEIPT_PERSIST` for the exact pre-journaled selection ID and terminal phase. The repository never derives a key or mints a capability.
- When the generation lacks its required live lineages, `select_next` reserves the profile's lineage IDs, authorizes a distinct `tool` grant with purpose `propose-lineages`, invokes the P05-registered strategy operation, persists the raw receipt with a `RECEIPT_PERSIST` capability, reconciles/persists its `BudgetReceipt`, validates, and persists lineages with `LINEAGE_PERSIST`. Selection then uses a new grant; neither grant is reusable.
- Queue selection requires `session.issue(QUEUE_TRANSITION, card_id, "mark-selected")`. Any failure after the session begins reconciles started grants and appends one `selection.failed` terminal receipt with all reserved IDs/raw events; it never leaves a proposal-only success.

- [ ] **Step 1: Write a failing strategy-proposal/supervisor-approval integration test**

```python
def test_controller_records_only_supervisor_approved_selection(controller):
    receipt = controller.handle(v2_request("advance", "select-1")).receipt
    assert receipt.kind == "selection" and receipt.stage == "final"
    assert receipt.selection_id.startswith("selection-")
    assert receipt.selector_version == "cost-aware-v1"
    assert controller.ledger.last_event("root-1").event_type == "card.selected"
    assert controller.handle(v2_request("advance", "select-1")).receipt == receipt

def test_propose_lineages_has_distinct_persisted_grant_and_budget_receipt(controller):
    receipt = controller.handle(v2_request("advance", "select-lineages-1")).receipt
    assert controller.strategy.calls_for("propose-lineages") == 1
    lineage_budget = controller.ledger.event_by_digest(receipt.lineage_budget_event_digest)
    selection_budget = controller.ledger.event_by_digest(receipt.selection_budget_event_digest)
    assert lineage_budget.event_type == selection_budget.event_type == "budget.reconciled"
    assert lineage_budget.payload["grantId"] != selection_budget.payload["grantId"]
    assert controller.ledger.event_sequence("budget.granted", purpose="propose-lineages") < controller.ledger.event_sequence("lineages.persisted")

def test_lineage_proposal_failure_is_terminal_and_replayable(controller):
    controller.strategy.fail_operation("propose-lineages", unknown_usage=True)
    first = controller.handle(v2_request("advance", "select-failed-1"))
    replay = controller.handle(v2_request("advance", "select-failed-1"))
    assert first.status == "failed" and replay.receipt == first.receipt
    assert first.receipt.kind == "selection" and first.receipt.stage == "terminal-failed"
    assert first.receipt.lineage_ids
    assert controller.strategy.calls_for("propose-lineages") == 1
    assert controller.ledger.event_by_digest(first.receipt.lineage_budget_event_digest).event_type == "budget.reconciled"
```

- [ ] **Step 2: Run and verify integration is red**

Run: `python3 -m pytest -q tests/selfloop/test_selection_integration.py`

Expected: fails because `select_next` is undefined.

- [ ] **Step 3: Implement metered lineage creation, ID-first selection, and capability-gated queue transition**

```python
def select_next(self, session):
    scope = session.scope
    selection_id = self.phases.reserve_id(session, "selection-id", "selection")
    try:
        lineage_receipt = self.lineages.current(scope.generation_id)
        if lineage_receipt is None:
            lineage_ids = tuple(
                self.phases.reserve_id(session, f"lineage-id:{index}", "lineage")
                for index in range(self.budget.profile(scope).live_lineages_max)
            )
            lineage_call, lineage_budget = self.run_metered_phase(
                session, "propose-lineages",
                UsageRequest.for_tool(scope, "propose-lineages", tool_call_cap=1),
                lambda grant: self.strategy.call_with_receipt(
                    "propose-lineages", self.strategy_root,
                    lineage_request(scope, grant, self.opportunities.pack(scope.generation_id)),
                ),
            )
            proposed = validate_lineages(
                lineage_call.payload, self.budget.profile(scope), expected_lineage_ids=lineage_ids,
            )
            lineage_receipt = self.lineages.persist(
                proposed, session.issue(MutationOperation.LINEAGE_PERSIST, scope.generation_id, "persist-lineages"),
            )
        snapshot = self.selection_snapshot(scope, lineage_receipt)
        proposal_call, selection_budget = self.run_metered_phase(
            session, "select-card", UsageRequest.for_tool(scope, "selection", tool_call_cap=1),
            lambda grant: self.strategy.call_with_receipt(
                "select-card", self.strategy_root, snapshot.with_grant(grant).to_dict(),
            ),
        )
        approved = self.selection_policy.approve(proposal_call.payload, snapshot)
        scale = self.change_scale.approve(approved.card, snapshot.attempt_history)
        queue_event = self.opportunities.transition(
            approved.card.card_id, QueueStatus.SELECTED, approved.reason,
            session.issue(MutationOperation.QUEUE_TRANSITION, approved.card.card_id, "mark-selected"),
        )
        return self.selection_receipts.commit_final(
            session, selection_id, approved, scale, lineage_receipt,
            proposal_call, selection_budget, queue_event,
            session.issue(MutationOperation.RECEIPT_PERSIST, selection_id, "persist-selection-final"),
        )
    except BaseException as error:
        return self.selection_receipts.commit_failed_from_journal(
            session, selection_id, error,
            session.issue(MutationOperation.RECEIPT_PERSIST, selection_id, "persist-selection-failed"),
        )
```

`run_metered_phase` is the P06 helper: it passes `BUDGET_GRANT`, `RECEIPT_PERSIST`, and `BUDGET_RECONCILE` capabilities, persists raw output and the terminal budget event, then calls `require_success`. `commit_final` appends `selection.finalized`; `commit_failed_from_journal` appends `selection.failed`. `handle` translates only the final receipt into the P07 prepared/selected response and keeps conformance at C1.

- [ ] **Step 4: Run the complete focused stack**

Run: `python3 -m pytest -q tests/selfloop/test_lineages.py tests/selfloop/test_operators.py tests/selfloop/test_selector.py tests/selfloop/test_budget.py tests/selfloop/test_selection_integration.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit controller selection**

```bash
git add scripts/selfloop_supervisor/receipt_contract.py scripts/selfloop_supervisor/lineage_contract.py scripts/selfloop_supervisor/budget.py scripts/selfloop_supervisor/opportunity_queue.py scripts/selfloop_supervisor/recovery.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_supervisor/strategy_rpc.py tests/selfloop/test_selection_integration.py
git commit -m "feat(selfloop): authorize persistent card selection"
```

### Task 6: Roll the P07 protected bundle through the active P06 controller

**Files:**
- Modify: `scripts/selfloop_supervisor/runtime_registry.py`
- Modify: `scripts/selfloop_supervisor/kernel.py`
- Modify: `scripts/selfloop_cli.py`
- Test: `tests/selfloop/test_p07_supervisor_rollover.py`

**Interfaces:**
- Consumes the active P06 runtime receipt, P02 `ReleaseBundleStore.open_verified(release_id, source_attestation_digest)`, and P05 typed authorize/prepare/activate supervisor-upgrade actions plus session-bound stage/activate capabilities.
- Produces the exact P05 `PendingSupervisorUpgrade`, `SupervisorActivationReceipt`, and host-load proof for the resolved `bundle_digest`/path. The proof binds the source release ID, manifest digest, source-attestation digest, path-independent release-bundle `receipt_digest`, and imports `lineage_contract`, `operator_contract`, `selection_policy`, `budget`, and `change_scale` from that exact bundle with recorded module hashes.
- The active P06 controller is the sole authority for authorization, preparation, and activation. P07 source cannot mint a session, authorization, or pending receipt; P06 remains the rescue digest until host proof succeeds.

- [ ] **Step 1: Write failing P06-authority, exact-content, replay, and compensation tests**

```python
def test_active_p06_prepares_and_activates_exact_p07_bundle(p06_controller, p07_release_bundle):
    prior = p06_controller.runtime.load_active("root-1")
    p06_controller.tty.confirm_commit(p07_release_bundle.release_identity.commit_sha)
    authorization = p06_controller.handle(authorize_upgrade_request(
        source_commit=p07_release_bundle.release_identity.commit_sha,
        release_id=p07_release_bundle.release_identity.release_id,
        source_attestation_digest=p07_release_bundle.source_attestation_digest,
        idempotency_key="authorize-p07",
    )).receipt
    assert authorization.release_bundle_receipt_digest == p07_release_bundle.receipt_digest
    pending = p06_controller.handle(prepare_upgrade_request(
        authorization_receipt_digest=authorization.event_digest,
        expected_prior_digest=prior.bundle_digest, idempotency_key="prepare-p07",
    )).receipt
    assert pending.source_attestation_digest == p07_release_bundle.source_attestation_digest
    activate = activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=prior.bundle_digest, idempotency_key="activate-p07",
    )
    first = p06_controller.handle(activate).receipt
    assert p06_controller.handle(activate).receipt == first
    active = p06_controller.runtime.load_active("root-1")
    assert active.bundle_digest == first.active_bundle_digest
    assert active.path == p06_controller.runtime.bundles_root / active.bundle_digest
    assert first.host_load_proof.loaded_modules >= {
        "lineage_contract", "operator_contract", "selection_policy", "budget", "change_scale",
    }

def test_p07_host_mismatch_restores_p06_and_is_terminal(p06_controller, p07_release_bundle):
    prior = p06_controller.runtime.load_active("root-1")
    p06_controller.tty.confirm_commit(p07_release_bundle.release_identity.commit_sha)
    authorization = p06_controller.handle(authorize_upgrade_request(
        source_commit=p07_release_bundle.release_identity.commit_sha,
        release_id=p07_release_bundle.release_identity.release_id,
        source_attestation_digest=p07_release_bundle.source_attestation_digest,
        idempotency_key="authorize-p07-failed",
    )).receipt
    pending = p06_controller.handle(prepare_upgrade_request(
        authorization_receipt_digest=authorization.event_digest,
        expected_prior_digest=prior.bundle_digest, idempotency_key="prepare-p07-failed",
    )).receipt
    p06_controller.host_probe.fail_with("budget module loaded outside resolved bundle")
    failed = p06_controller.handle(activate_request(
        pending_upgrade_id=pending.pending_upgrade_id,
        expected_prior_digest=prior.bundle_digest, idempotency_key="activate-p07-failed",
    ))
    assert failed.status == "failed" and failed.receipt.stage == "terminal-failed"
    assert p06_controller.runtime.load_active("root-1").bundle_digest == prior.bundle_digest
```

- [ ] **Step 2: Run and confirm the P07 rollover is red**

Run: `python3 -m pytest -q tests/selfloop/test_p07_supervisor_rollover.py`

Expected: tests fail because the active P06 bundle does not contain P07 lineage/selection/budget implementations or a matching host-load proof.

- [ ] **Step 3: Implement pending-ID activation and exact loaded-bundle proof**

The active P06 controller verifies its injected direct-TTY dependency for authorization, binding commit/release/manifest/source-attestation/path-independent release-bundle receipt/current P06 digest. Preparation accepts that authorization event digest, calls `open_verified(release_id, source_attestation_digest)`, verifies `receipt_digest`, stages under `SUPERVISOR_STAGE`, resolves/rehashes `SupervisorBundleReceipt.bundle_digest`, and persists `PendingSupervisorUpgrade`. Activation accepts only the pending ID, resolves it inside `handle`, consumes `SUPERVISOR_ACTIVATE`, compares the expected prior digest, and records P06 as rescue.

Probe status and the five P07 protected modules from the resolved P07 path in a fresh process. Persist bundle/manifest/source-attestation/module digests and loaded paths. On any mismatch, append the raw failure receipt and compensate back to P06 before returning terminal failure; on success append `supervisor.host-load.proved`. Replay uses the prepared/activation events and does not rebuild or restage.

- [ ] **Step 4: Run rollover and the complete P07 focused stack**

Run: `python3 -m pytest -q tests/selfloop/test_p07_supervisor_rollover.py tests/selfloop/test_lineages.py tests/selfloop/test_operators.py tests/selfloop/test_selector.py tests/selfloop/test_budget.py tests/selfloop/test_selection_integration.py`

Expected: all tests pass and pytest exits `0`.

- [ ] **Step 5: Commit the P07 protected-bundle rollover**

```bash
git add scripts/selfloop_supervisor/runtime_registry.py scripts/selfloop_supervisor/kernel.py scripts/selfloop_cli.py tests/selfloop/test_p07_supervisor_rollover.py
git commit -m "feat(selfloop): activate protected P07 search runtime"
```

## Plan Verification

- [ ] Run the five focused pytest files above plus `tests/selfloop/test_p07_supervisor_rollover.py`; expected: all pass.
- [ ] Run `python3 scripts/selfloop_cli.py status --root . --json`; expected: profile, hard/soft budget, unlocked tranche, actual/reserved usage, lineage counts, exploration credit, mechanism streak, and selected card are present; conformance remains `C1` until Plan 08.
- [ ] Confirm status names the active P07 bundle digest, resolved path, source-attestation digest, host-load proof, retained P06 rescue digest, latest soft-continuation decision, and active/consumed candidate/repair/builder/agent reservations.
- [ ] Run `python3 scripts/validate_v2.py --check-eval && git diff --check`; expected: both exit `0` and diff check emits no output.

"""Bounded diagnostic experiments. Scores are heuristics, never probabilities."""
from __future__ import annotations
import copy
import math
import time
from .canonical import canonical_hash
from .evaluation import check


def investigation(hypotheses, probes):
    if not isinstance(hypotheses, list) or not hypotheses:
        raise ValueError('nonempty structured hypotheses required')
    ids = [h.get('id') for h in hypotheses]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('unique hypothesis ids required')
    ranked = []
    seen = set()
    for probe in probes:
        probe = copy.deepcopy(probe)
        if not probe.get('id') or probe['id'] in seen: raise ValueError('unique probe ids required')
        seen.add(probe['id'])
        predictions = probe.get('predictions', {})
        if set(predictions) != set(ids) or any(x not in {'passed','failed','unavailable'} for x in predictions.values()):
            raise ValueError('each hypothesis needs a predicted check outcome')
        cost = probe.get('cost_seconds', 1)
        if type(cost) not in (int,float) or not math.isfinite(cost) or cost <= 0: raise ValueError('positive finite cost required')
        if type(probe.get('reversible')) is not bool: raise ValueError('reversibility declaration required')
        pairs = sum(predictions[a] != predictions[b] and 'unavailable' not in (predictions[a],predictions[b]) for n,a in enumerate(ids) for b in ids[n+1:])
        probe['heuristic_score'] = pairs / cost * (1 if probe['reversible'] else .25)
        probe['status'] = 'proposed'
        if probe.get('check',{}).get('kind') not in {'command','artifact','sequence','pytest'}:
            raise ValueError('probe needs supported independent check')
        ranked.append(probe)
    ranked.sort(key=lambda p: (-p['heuristic_score'], p['id']))
    from .methods import diagnosis
    design = diagnosis({'hypotheses':ids,'probes':[{'id':p['id'],'predictions':p['predictions'],'cost_seconds':p.get('cost_seconds',1)} for p in ranked]})
    return {'diagnostic_design':design, 'schema':'sips.investigation.v1','hypotheses':hypotheses,'probes':ranked,
            'score_semantics':'heuristic discrimination per cost; not a probability',
            'outcome':'insufficient_evidence','results':[]}


def execute(probe, workspace, fixtures, timeout, budget, environment):
    start = time.monotonic()
    report = check(probe['check'], workspace, fixtures, min(timeout,budget))
    status = report['status']
    # Missing measurement cannot support or refute a task hypothesis.
    supported = [h for h,p in probe['predictions'].items() if p == status] if status != 'unavailable' else []
    contradicted = [h for h,p in probe['predictions'].items() if p != 'unavailable' and p != status] if status != 'unavailable' else []
    return {'schema':'sips.probe-receipt.v1','probe':probe['id'],'check':probe['check'],
            'inputs':probe.get('inputs',{}),'environment':environment,'result':report,
            'duration_seconds':time.monotonic()-start,'output_identity':canonical_hash(report),
            'supports':supported,'contradicts':contradicted,'causality':'not established'}


def reduce_failure(spec, value, workspace, fixtures, timeout, budget, max_checks=32):
    """Deterministic chunk deletion; a passing predicate means failure reproduced.

    The externally supplied command's {input} token receives the literal candidate.
    This finds a deletion-minimal example within budget, not a globally minimal one.
    """
    if not isinstance(value,str) or not value or '{input}' not in spec.get('argv',[]):
        raise ValueError('nonempty input and a literal {input} argument required')
    if type(max_checks) is not int or not 1 <= max_checks <= 32: raise ValueError('max_checks must be 1..32')
    start=time.monotonic(); receipts=[]
    def reproduces(candidate):
        remaining=budget-(time.monotonic()-start)
        if remaining <= 0 or len(receipts)>=max_checks: return None
        case=copy.deepcopy(spec);case['argv']=[candidate if a=='{input}' else a for a in case['argv']]
        result=check(case,workspace,fixtures,min(timeout,remaining))
        receipts.append({'input':candidate,'result':result,'identity':canonical_hash(result)})
        return True if result['status']=='passed' else False if result['status']=='failed' else None
    if reproduces(value) is not True:
        return {'status':'unavailable','reason':'original failure not reproduced','checks':receipts}
    current=value; width=max(1,len(current)//2); exhausted=False
    while width:
        changed=False
        for pos in range(0,len(current),width):
            candidate=current[:pos]+current[pos+width:]
            outcome=reproduces(candidate)
            if outcome is None: exhausted=True;break
            if outcome: current=candidate;changed=True;break
        if exhausted: break
        if not changed: width//=2
    return {'status':'bounded' if exhausted else 'deletion_minimal','original':value,'reduced':current,
            'checks':receipts,'duration_seconds':time.monotonic()-start,'activation':'none'}

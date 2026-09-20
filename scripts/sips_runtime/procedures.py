"""Proposed procedural memories and declarative, bounded policy artifacts."""
from __future__ import annotations
import math
import re
from .canonical import canonical_hash

POLICY_FIELDS={'schema','kind','version','inputs','outputs','scope','weights','description'}
POLICY_WEIGHTS={'diagnosis':{'discrimination','cost','reversibility'},
                'proposal':{'success','cost','complexity','coverage'},
                'retrieval':{'relevance','freshness','negative_outcomes'}}


def validate_policy(value):
    if isinstance(value, dict) and value.get("schema") == "sips.policy.v2":
        from .policy_graph import validate
        return validate(value)
    if set(value)-POLICY_FIELDS or value.get('schema')!='sips.policy.v1': raise ValueError('unsupported policy surface')
    kind=value.get('kind')
    if kind not in POLICY_WEIGHTS or value.get('scope')!=kind: raise ValueError('policy scope violation')
    if not value.get('version') or not value.get('inputs') or not value.get('outputs'): raise ValueError('policy contract missing')
    weights=value.get('weights',{})
    if set(weights)!=POLICY_WEIGHTS[kind] or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=10 for v in weights.values()):
        raise ValueError('bounded policy weights required')
    return value


def rank_policy(policy, alternatives):
    """Explicit invocation only; never edits the controller or invokes a model."""
    validate_policy(policy)
    if policy["schema"] != "sips.policy.v1": raise ValueError("branching policies use the graph interpreter")
    results=[]
    for alternative in alternatives:
        features=alternative['features']
        if set(features)!=set(policy['weights']) or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in features.values()):
            raise ValueError('normalized complete policy features required')
        score=sum(policy['weights'][k]*(-v if k in {'cost','complexity','negative_outcomes'} else v) for k,v in features.items())
        results.append({**alternative,'score':score})
    return sorted(results,key=lambda x:(-x['score'],x['id']))


def motif(actions):
    """Normalize variable bindings by first use, preserving action order and roles."""
    names={}
    def normal(value):
        if isinstance(value,str) and value.startswith('$'):
            return names.setdefault(value,'$'+str(len(names)))
        if isinstance(value,dict): return {k:normal(v) for k,v in sorted(value.items())}
        if isinstance(value,list): return [normal(v) for v in value]
        return value
    return canonical_hash(normal(actions))


def validate_procedure(value):
    required={'schema','version','task','applicability','actions','bindings','expected_evidence','failure_modes','sources','valid_until','negative_contexts'}
    if set(value)!=required or value['schema']!='sips.procedure.v1': raise ValueError('procedure contract fields required')
    for key in ('task','version','actions','expected_evidence','sources'):
        if not value[key]: raise ValueError('empty procedure '+key)
    if not isinstance(value['applicability'],dict) or not isinstance(value['bindings'],dict): raise ValueError('structural applicability and bindings required')
    if not isinstance(value['actions'],list) or any(not isinstance(a,dict) or not a.get('action') for a in value['actions']): raise ValueError('ordered actions required')
    if not isinstance(value['negative_contexts'],list) or any(not isinstance(x,dict) or not x for x in value['negative_contexts']): raise ValueError('invalid negative contexts')
    if type(value['valid_until']) not in (int,float) or not math.isfinite(value['valid_until']): raise ValueError('finite validity deadline required')
    if not isinstance(value['sources'],list) or any(not isinstance(s,dict) or set(s)!={'episode','revision','event_digest'} for s in value['sources']): raise ValueError('versioned source episode identities required')
    return value


def retrieval_audit(procedures, query, context, now, source_current):
    terms=set(re.findall(r'\w+',query.lower()))-{'a','the','to','for','and'}
    results=[];rejected=[]
    for value in procedures:
        validate_procedure(value)
        reasons=[]
        if value['valid_until']<=now: reasons.append('expired')
        if not source_current(value['sources']): reasons.append('source_changed_or_unavailable')
        if any(context.get(k)!=v for k,v in value['applicability'].items()): reasons.append('applicability_mismatch')
        if any(all(context.get(k)==v for k,v in negative.items()) for negative in value['negative_contexts']): reasons.append('known_negative_context')
        overlap=len(terms & set(re.findall(r'\w+',value['task'].lower())))
        if not overlap: reasons.append('unrelated')
        identity=canonical_hash(value)
        if reasons:
            rejected.append({'identity':identity,'reasons':reasons,'score':0})
            continue
        results.append({'procedure':value,'identity':identity,'score':overlap,
                        'freshness_seconds':value['valid_until']-now,'effectiveness':'unknown','activation':'none'})
    return {'schema':'sips.retrieval-audit.v1',
            'eligible':sorted(results,key=lambda x:(-x['score'],-x['freshness_seconds'],x['identity'])),
            'rejected':sorted(rejected,key=lambda x:x['identity']),
            'boundary':'Declared compatibility and evidence freshness, not measured effectiveness.'}


def retrieve(procedures, query, context, now, source_current):
    return retrieval_audit(procedures,query,context,now,source_current)['eligible']


def pareto(records):
    """Only complete measured records enter the frontier; unknowns remain archived."""
    keys=('success','cost','complexity','coverage')
    measured=[r for r in records if all(type(r.get(k)) in (int,float) and math.isfinite(r[k]) for k in keys)]
    def vector(r): return (r['success'],-r['cost'],-r['complexity'],r['coverage'])
    return [r for r in measured if not any(all(a>=b for a,b in zip(vector(o),vector(r))) and any(a>b for a,b in zip(vector(o),vector(r))) for o in measured)]


REFLECTION_BASELINE = {
    'schema':'sips.reflection-baseline.v1',
    'authorship':'active task agent using the same user-selected model and candidate budget',
    'steps':['Read original failure and executed trajectory',
             'State competing explanations and cite observed evidence',
             'Propose one bounded intervention without procedural-memory retrieval',
             'Author the candidate and replay the frozen evaluator'],
    'execution':'foreground only', 'effectiveness':'unmeasured'}

"""Bounded diagnostic decision graphs, with executable assumption expiry."""
import hashlib
import math
from pathlib import Path
from .canonical import canonical_hash
from .evaluation import path_in

INTERVENTIONS={'gather_evidence','refresh_context','repair_interface','reuse','compose','repair_implementation','create_tool','consolidate','stop'}


def validate(policy):
    fields={'schema','kind','scope','version','inputs','outputs','entry','nodes','assumptions'}
    if not isinstance(policy,dict) or set(policy)!=fields or policy['schema']!='sips.policy.v2' or policy['kind']!='diagnosis' or policy['scope']!='diagnosis': raise ValueError('diagnostic policy v2 contract required')
    if not isinstance(policy['version'],str) or not policy['version'] or policy['inputs']!=['probe_outcomes'] or policy['outputs']!=['intervention']: raise ValueError('fixed policy inputs/outputs required')
    nodes=policy['nodes']
    if not isinstance(nodes,dict) or not 1<=len(nodes)<=32 or any(not isinstance(k,str) or not k or len(k)>128 for k in nodes): raise ValueError('1..32 named nodes required')
    if policy['entry'] not in nodes: raise ValueError('entry missing')
    edges={}
    for name,node in nodes.items():
        if not isinstance(node,dict): raise ValueError('node object required')
        if set(node)=={'probe','on'}:
            if not isinstance(node['probe'],str) or not node['probe'] or not isinstance(node['on'],dict) or set(node['on'])!={'passed','failed','unavailable'} or any(not isinstance(v,str) or v not in nodes for v in node['on'].values()): raise ValueError('all outcome branches required')
            edges[name]=set(node['on'].values())
        elif set(node)=={'intervention','rationale'}:
            if node['intervention'] not in INTERVENTIONS or not isinstance(node['rationale'],str) or not node['rationale']: raise ValueError('valid terminal intervention required')
            edges[name]=set()
        else: raise ValueError('unsupported node; evaluator, activation, command and budget actions forbidden')
    visiting=set();visited=set()
    def visit(name):
        if name in visiting: raise ValueError('cyclic policy')
        if name in visited: return
        visiting.add(name)
        for child in edges[name]: visit(child)
        visiting.remove(name);visited.add(name)
    visit(policy['entry'])
    if visited!=set(nodes): raise ValueError('unreachable policy nodes')
    assumptions=policy['assumptions']
    if not isinstance(assumptions,list) or len(assumptions)>32: raise ValueError('bounded assumptions required')
    names=set()
    for item in assumptions:
        if not isinstance(item,dict) or set(item)!={'path','sha256','valid_until'}: raise ValueError('versioned expiring assumption required')
        name=item['path'];digest=item['sha256'];expiry=item['valid_until']
        if not isinstance(name,str) or not name or name in names or Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unique relative assumption paths required')
        names.add(name)
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest): raise ValueError('sha256 required')
        if type(expiry) not in (int,float) or not math.isfinite(expiry): raise ValueError('finite expiry required')
    return policy


def run(policy,outcomes,workspace,now):
    validate(policy)
    if not isinstance(outcomes,dict) or any(not isinstance(k,str) or v not in {'passed','failed','unavailable'} for k,v in outcomes.items()): raise ValueError('executed outcome map required')
    if type(now) not in (int,float) or not math.isfinite(now): raise ValueError('finite time required')
    receipt={'schema':'sips.policy-execution.v2','policy_digest':canonical_hash(policy),'observations_digest':canonical_hash(outcomes),'trace':[],'activation':'none','effectiveness':'unknown'}
    invalid=[]
    for a in policy['assumptions']:
        try:
            path=path_in(workspace,a['path'])
            relative=Path(a['path'])
            symlink=any((Path(workspace)/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts)+1))
            if symlink or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=a['sha256']: invalid.append({'path':a['path'],'reason':'missing_or_changed'})
        except (ValueError,OSError): invalid.append({'path':a['path'],'reason':'unavailable'})
        if now>=a['valid_until']: invalid.append({'path':a['path'],'reason':'expired'})
    if invalid: return {**receipt,'status':'inapplicable','invalid_assumptions':invalid}
    name=policy['entry']
    for _ in range(32):
        node=policy['nodes'][name]
        if 'intervention' in node: return {**receipt,'status':'proposed','decision':node,'terminal':name}
        probe=node['probe']
        if probe not in outcomes: return {**receipt,'status':'needs_evidence','probe':probe,'node':name}
        outcome=outcomes[probe];receipt['trace'].append({'node':name,'probe':probe,'outcome':outcome});name=node['on'][outcome]
    raise ValueError('policy traversal limit')

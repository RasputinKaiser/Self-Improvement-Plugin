"""Bounded AND-hypergraph planning over a conservative JSON Schema subset.

Unsupported schema keywords fail closed. This is a compiler proposal, not a
consumer-validation receipt. No schema coercion or implicit version conversion.
"""
from __future__ import annotations
import heapq
import itertools
import math
import fnmatch
from .canonical import canonical_hash

KEYS={'type','properties','required','additionalProperties','items','enum','schema_version','semantic'}
TYPES={'object','array','string','integer','number','boolean','null'}


def schema(value):
    if not isinstance(value,dict) or set(value)-KEYS or value.get('type') not in TYPES:
        raise ValueError('unsupported structural schema')
    from .semantics import validate
    validate(value.get('semantic',{}),value['type'])
    if 'enum' in value and (not isinstance(value['enum'],list) or not value['enum']): raise ValueError('nonempty enum required')
    if value['type']=='object':
        props=value.get('properties',{})
        if not isinstance(value.get('required', []), list) or any(not isinstance(k,str) for k in value.get('required',[])): raise ValueError('required must be a string array')
        if not isinstance(props,dict) or not set(value.get('required',[]))<=set(props): raise ValueError('invalid object properties')
        if type(value.get('additionalProperties',True)) is not bool: raise ValueError('boolean additionalProperties required')
        for child in props.values(): schema(child)
    if value['type']=='array': schema(value.get('items'))
    return value


def compatible(produced, required):
    schema(produced);schema(required)
    from .semantics import implies
    if not implies(produced.get('semantic',{}),required.get('semantic',{})): return False
    if produced.get('schema_version')!=required.get('schema_version') or produced['type']!=required['type']: return False
    if 'enum' in required and ('enum' not in produced or not all(any(type(x) is type(y) and x==y for y in required['enum']) for x in produced['enum'])): return False
    if produced['type']=='array': return compatible(produced['items'],required['items'])
    if produced['type']=='object':
        p,r=produced.get('properties',{}),required.get('properties',{})
        if not set(required.get('required',[]))<=set(produced.get('required',[])): return False
        if required.get('additionalProperties') is False and (produced.get('additionalProperties',True) or set(p)-set(r)): return False
        if any(k not in p or not compatible(p[k],r[k]) for k in required.get('required',[])): return False
        if any(not compatible(p[k],r[k]) for k in p.keys() & r.keys()): return False
        if set(r)-set(p) and produced.get('additionalProperties',True): return False
    return True


def validate_contract(value):
    for field in ('inputs','outputs'):
        if not isinstance(value.get(field),dict) or not value[field]: raise ValueError('named input/output schemas required')
        for s in value[field].values(): schema(s)
    for field in ('preconditions','resources','dependencies','consumers'):
        if not isinstance(value.get(field),list) or any(not isinstance(x,str) or not x for x in value[field]): raise ValueError('declared '+field+' required')
    effects=value.get('effects')
    if not isinstance(effects,dict) or set(effects)!={'reads','writes'} or any(not isinstance(v,list) or any(not isinstance(x,str) or not x for x in v) for v in effects.values()): raise ValueError('declared read/write effects required')
    if not isinstance(value.get('bindings'),dict) or set(value['bindings'])!=set(value['inputs']) or any(not isinstance(v,str) or not v for v in value['bindings'].values()): raise ValueError('explicit input argument bindings required')
    if not set(value['dependencies'])<=set(value['resources']): raise ValueError('dependencies must be content-addressed resources')
    return value


def compose(capabilities, available, required, max_steps=4, prerequisites=(), dependencies=()):
    if type(max_steps) is not int or not 0<=max_steps<=16: raise ValueError('bounded max_steps required')
    for s in [*available.values(),*required.values()]: schema(s)
    tools=[]
    for c in sorted(capabilities,key=lambda c:c['id']):
        if c.get('schema') not in {'sips.tool-contract.v2','sips.tool-contract.v3'} or c.get('validation_status')!='current': continue
        validate_contract(c)
        cost=c.get('cost',1)
        if type(cost) not in (int,float) or not math.isfinite(cost) or cost<0: raise ValueError('invalid plan cost')
        if set(c['preconditions'])<=set(prerequisites) and set(c['dependencies'])<=set(dependencies): tools.append(c)
    # Backward deficit closure: keep only tools that can produce a requested schema.
    needed=list(required.values()); selected=[]
    changed=True
    while changed:
        changed=False
        for c in tools:
            if c in selected: continue
            if any(compatible(out,want) for out in c['outputs'].values() for want in needed):
                selected.append(c);needed.extend(c['inputs'].values());changed=True
    counter=itertools.count();queue=[(0,next(counter),dict(available),[],frozenset(),frozenset())];seen=set(); explored=0
    while queue and explored<1000:
        cost,_,state,steps,reads,writes=heapq.heappop(queue);explored+=1
        identity=canonical_hash({'state':state,'tools':[x['tool'] for x in steps],'reads':sorted(reads),'writes':sorted(writes)})
        if identity in seen: continue
        seen.add(identity)
        if all(any(compatible(have,want) for have in state.values()) for want in required.values()):
            return {'schema':'sips.composition.v2','status':'proposed','steps':steps,'cost':cost,
                    'dependency_identity':canonical_hash(capabilities),'consumer_validation':'required',
                    'goals':{k:sorted(n for n,s in state.items() if compatible(s,v))[0] for k,v in required.items()}}
        if len(steps)>=max_steps: continue
        for c in selected:
            if c['id'] in {s['tool'] for s in steps}: continue
            cr,cw=set(c['effects']['reads']),set(c['effects']['writes'])
            def overlaps(left, right):
                return any(a == b or fnmatch.fnmatchcase(a,b) or fnmatch.fnmatchcase(b,a) or (any(x in a for x in '*?[') and any(x in b for x in '*?[')) for a in left for b in right)
            if overlaps(cw,writes|reads) or overlaps(cr,writes): continue
            options={name:[k for k,v in sorted(state.items()) if compatible(v,want)] for name,want in c['inputs'].items()}
            if any(not v for v in options.values()): continue
            # Ambiguous bindings are rejected; explicit source names may disambiguate.
            bindings={}
            for name,choices in options.items():
                explicit=c['bindings'][name]
                if explicit in choices: bindings[name]=explicit
                elif len(choices)==1: bindings[name]=choices[0]
                else: break
            if len(bindings)!=len(options): continue
            next_state={**state,**{c['id']+'.'+k:v for k,v in c['outputs'].items()}}
            step={'tool':c['id'],'bindings':bindings,'effects':c['effects'],'contract':canonical_hash(c)}
            heapq.heappush(queue,(cost+c.get('cost',1),next(counter),next_state,steps+[step],reads|cr,writes|cw))
    return {'schema':'sips.composition.v2','status':'insufficient_fit','steps':[], 'reason':'no acyclic compatible plan within limits','consumer_validation':'unavailable'}


def invalidated(before, after, consumers):
    affected={key for key in before.keys()|after.keys() if before.get(key)!=after.get(key)}
    while True:
        expanded=affected|{name for name,deps in consumers.items() if set(deps)&affected}
        if expanded==affected: return sorted(affected)
        affected=expanded


def accepts(contract, value):
    """Runtime value validation for the supported structural schema subset."""
    schema(contract)
    kind=contract['type']
    valid={'object':isinstance(value,dict),'array':isinstance(value,list),
           'string':isinstance(value,str),'integer':type(value) is int,
           'number':type(value) in (int,float) and math.isfinite(value),
           'boolean':type(value) is bool,'null':value is None}[kind]
    if not valid: return False
    from .semantics import accepts as semantic_accepts
    if not semantic_accepts(value,contract.get('semantic',{})): return False
    if 'enum' in contract and not any(type(value) is type(v) and value==v for v in contract['enum']): return False
    if kind=='array': return all(accepts(contract['items'],v) for v in value)
    if kind=='object':
        props=contract.get('properties',{})
        if not set(contract.get('required',[]))<=set(value): return False
        if contract.get('additionalProperties') is False and set(value)-set(props): return False
        return all(accepts(props[k],v) for k,v in value.items() if k in props)
    return True

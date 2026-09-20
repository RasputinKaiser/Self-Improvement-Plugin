"""Bounded advisory methods adapted from diagnosis, design, logic, and metrology.

No commands are executed, hypotheses are not verified, and no result can
establish acceptance or activate a candidate. See references/research-methods.md.
"""
from __future__ import annotations
import itertools
import math
import statistics
from .canonical import canonical_hash


def finite(value, name, low=0, high=1e12):
    if type(value) not in (int,float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite in [{low}, {high}]')
    return value


def identifiers(items, maximum):
    if not isinstance(items,list) or not 1<=len(items)<=maximum or any(not isinstance(x,str) or not x or len(x)>128 for x in items) or len(set(items))!=len(items):
        raise ValueError('bounded unique nonempty identifiers required')
    return items


def diagnosis(request):
    ids=identifiers(request['hypotheses'],32)
    probes=request.get('probes',[])
    if not isinstance(probes,list) or len(probes)>64: raise ValueError('at most 64 probes')
    budget=finite(request.get('budget_seconds',120),'budget',0,600)
    pairs=set(itertools.combinations(sorted(ids),2));cover={};costs={};seen=set()
    for p in probes:
        if not isinstance(p,dict) or not isinstance(p.get('predictions'),dict): raise ValueError('probe object with predictions required')
        name=p['id']
        identifiers([name],1)
        if name in seen: raise ValueError('duplicate probe')
        seen.add(name);pred=p['predictions']
        if set(pred)!=set(ids) or any(v not in {'passed','failed','unavailable'} for v in pred.values()): raise ValueError('complete probe predictions required')
        costs[name]=finite(p['cost_seconds'],'cost',.001,600)
        cover[name]={pair for pair in pairs if pred[pair[0]]!=pred[pair[1]] and 'unavailable' not in (pred[pair[0]],pred[pair[1]])}
    remaining=set(pairs);chosen=[];spent=0
    while remaining:
        options=[name for name in sorted(cover) if name not in chosen and costs[name]+spent<=budget and cover[name]&remaining]
        if not options: break
        best=min(options,key=lambda name:(-len(cover[name]&remaining)/costs[name],costs[name],name))
        chosen.append(best);spent+=costs[best];remaining-=cover[best]
    all_cover=set().union(*cover.values()) if cover else set()
    return {'status':'proposed','selected_probes':chosen,'estimated_seconds':spent,
            'distinguished_pairs':len(pairs)-len(remaining),'total_pairs':len(pairs),
            'unresolved_pairs':[list(p) for p in sorted(remaining)],
            'intrinsically_unseparated_pairs':[list(p) for p in sorted(pairs-all_cover)],
            'boundary':'Greedy set cover of supplied predictions; not an optimal design or causal proof. Unavailable is not discriminating evidence.'}


def configurations(request):
    factors=request['factors']
    if not isinstance(factors,dict) or not 1<=len(factors)<=8: raise ValueError('1..8 named factors required')
    identifiers(list(factors),8);names=sorted(factors);levels=[]
    for name in names:
        values=factors[name]
        if not isinstance(values,list) or not 1<=len(values)<=8: raise ValueError('1..8 levels required')
        for v in values:
            if v is not None and type(v) not in (str,bool,int,float): raise ValueError('scalar factor levels required')
            if isinstance(v,str) and len(v)>128: raise ValueError('level too long')
            if type(v) in (int,float): finite(v,'factor',-1e12,1e12)
        if len({canonical_hash(v) for v in values})!=len(values): raise ValueError('duplicate factor levels')
        levels.append(values)
    if math.prod(map(len,levels))>4096: raise ValueError('factor product exceeds 4096')
    forbidden=request.get('forbidden',[])
    if not isinstance(forbidden,list) or len(forbidden)>128: raise ValueError('bounded forbidden assignments required')
    for rule in forbidden:
        if not isinstance(rule,dict) or not rule or not set(rule)<=set(names): raise ValueError('invalid forbidden assignment')
        if any(canonical_hash(v) not in {canonical_hash(x) for x in factors[k]} for k,v in rule.items()): raise ValueError('unknown forbidden level')
    rows=[]
    for values in itertools.product(*levels):
        row=dict(zip(names,values))
        if not any(all(canonical_hash(row[k])==canonical_hash(v) for k,v in rule.items()) for rule in forbidden): rows.append(row)
    return names,rows


def coverage(request):
    names,rows=configurations(request);strength=request.get('strength',2);limit=request.get('max_cases',32)
    if type(strength) is not int or not 1<=strength<=min(3,len(names)): raise ValueError('strength must be 1..min(3, factors)')
    if type(limit) is not int or not 1<=limit<=128: raise ValueError('1..128 cases required')
    tuples={};sets=[]
    for row in rows:
        current=set()
        for keys in itertools.combinations(names,strength):
            values={k:row[k] for k in keys};identity=canonical_hash(values);tuples[identity]=values;current.add(identity)
        sets.append(current)
    remaining=set(tuples);chosen=[]
    while remaining and len(chosen)<limit:
        index=min(range(len(rows)),key=lambda i:(-len(sets[i]&remaining),i))
        if not (sets[index]&remaining): break
        chosen.append(index);remaining-=sets[index]
    return {'status':'no_feasible_configurations' if not rows else 'complete' if not remaining else 'bounded_incomplete',
            'cases':[rows[i] for i in chosen],'feasible_configurations':len(rows),'strength':strength,
            'covered_interactions':len(tuples)-len(remaining),'total_interactions':len(tuples),
            'uncovered':[tuples[k] for k in sorted(remaining)],
            'boundary':'Coverage of feasible model interactions only; no execution or test oracle supplied.'}


def morphology(request):
    result=coverage(request)
    alternatives=result.pop('cases')
    return {**result,'status':'proposed' if alternatives else 'no_feasible_configurations',
            'coverage_status':result['status'],'alternatives':alternatives,
            'control':{'intervention':'no_change','reason':'retain a baseline comparator'},
            'boundary':'Designer-supplied dimensions and exclusions; combinations are proposals, not novel discoveries or verified capabilities.'}


def assumptions(request):
    """Finite monotone four-valued support propagation, not a complete ATMS."""
    raw=request['facts'];rules=request.get('rules',[])
    if not isinstance(raw,dict) or len(raw)>128 or not isinstance(rules,list) or len(rules)>128: raise ValueError('bounded facts/rules required')
    support={};sources={}
    for name,value in raw.items():
        identifiers([name],1)
        if not isinstance(value,dict) or value.get('state') not in {'supported','refuted','unknown','inconsistent'}: raise ValueError('fact state required')
        evidence=value.get('evidence',[])
        if not isinstance(evidence,list) or any(not isinstance(e,str) or not e for e in evidence): raise ValueError('evidence references must be strings')
        # Referenced evidence is not read or verified by this pure analysis.
        state=value['state'] if evidence else 'unknown'
        support[name]=set({'supported':(True,), 'refuted':(False,), 'unknown':(), 'inconsistent':(True,False)}[state]);sources[name]=set(evidence)
    ids=[]
    for rule in rules:
        if not isinstance(rule,dict): raise ValueError('rule object required')
        ids.append(rule['id']);identifiers([rule['conclusion']],1)
        if type(rule['value']) is not bool or not isinstance(rule['premises'],dict) or not rule['premises'] or any(type(v) is not bool for v in rule['premises'].values()): raise ValueError('nonempty boolean premises required')
        for name in [rule['conclusion'],*rule['premises']]:
            identifiers([name],1);support.setdefault(name,set());sources.setdefault(name,set())
    if ids: identifiers(ids,128)
    if len(support)>256: raise ValueError('too many propositions')
    fired=set()
    for _ in range(2*len(support)+1):
        changed=False
        for rule in rules:
            if all(value in support[name] for name,value in rule['premises'].items()):
                conclusion=rule['conclusion'];before=(len(support[conclusion]),len(sources[conclusion]))
                support[conclusion].add(rule['value']);sources[conclusion].update(set().union(*(sources[k] for k in rule['premises'])))
                fired.add(rule['id']);changed |= before!=(len(support[conclusion]),len(sources[conclusion]))
        if not changed: break
    states={name:'inconsistent' if len(value)==2 else 'supported' if True in value else 'refuted' if False in value else 'unknown' for name,value in support.items()}
    return {'status':'advisory','claims':{name:{'state':states[name],'evidence':sorted(sources[name])} for name in sorted(states)},
            'fired_rules':sorted(fired),'inconsistent':[name for name in sorted(states) if states[name]=='inconsistent'],
            'boundary':'Conditional support under supplied assumptions; reference presence is not source verification. Recompute after retraction; contradictions do not entail unrelated claims.'}


def drift(request):
    baseline=request['baseline'];samples=request['samples'];weight=finite(request.get('weight',.2),'weight',.001,1)
    if not isinstance(baseline,list) or not 5<=len(baseline)<=1000 or not isinstance(samples,list) or len(samples)>1000: raise ValueError('5..1000 baseline and at most 1000 observations required')
    for v in baseline: finite(v,'baseline',-1e12,1e12)
    if request.get('baseline_identity')!=request.get('sample_identity') or not request.get('baseline_identity'): raise ValueError('same declared measurement identity required')
    center=statistics.mean(baseline);sigma=statistics.stdev(baseline)
    if sigma==0: return {'status':'unavailable','reason':'zero baseline variance; no calibrated control limits'}
    ewma=center;rows=[];n=0
    for index,value in enumerate(samples):
        if value is None:
            rows.append({'index':index,'status':'unavailable'});continue
        finite(value,'sample',-1e12,1e12);n+=1;ewma=weight*value+(1-weight)*ewma
        width=3*sigma*math.sqrt(weight/(2-weight)*(1-(1-weight)**(2*n)))
        rows.append({'index':index,'status':'signal' if abs(ewma-center)>width else 'within_limits','value':value,'ewma':ewma,'lower':center-width,'upper':center+width})
    return {'status':'advisory','rows':rows,'signals':sum(r['status']=='signal' for r in rows),'missing':len(samples)-n,
            'boundary':'Exploratory EWMA assumes a stable representative baseline and independent observations; signal is neither cause nor a performance win.'}


METHODS={'diagnosis':diagnosis,'coverage':coverage,'morphology':morphology,'assumptions':assumptions,'drift':drift}


def analyze(method,request):
    if method not in METHODS or not isinstance(request,dict): raise ValueError('supported method and object request required')
    if len(str(request))>200000: raise ValueError('request too large')
    result=METHODS[method](request)
    return {'schema':'sips.method-receipt.v1','method':method,'input_identity':canonical_hash(request),
            'activation':'none','acceptance':'not_evaluated',**result}

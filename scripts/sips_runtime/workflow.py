"""Resumable foreground work packets and evidence-linked outcome comparisons.

The host authors candidates. This module never launches models or activates code.
"""
from .canonical import canonical_hash


def next_packet(state, episode, revision):
    status=state['state'];action=None;kind='stopped';required=[];fixed={}
    remaining=max(0,state['limits']['evaluation_seconds']-state['evaluation_seconds'])
    if state.get('probe_running') or status=='evaluating':
        kind='recover';action='recover'
    elif status in {'diagnosing','unavailable'} and state.get('investigation',{}).get('rationale') and state['investigation'].get('outcome') in {'insufficient_evidence','environment_unavailable'}:
        kind='stopped'
    elif status in {'observed','unavailable','rejected'}:
        if state['attempts']<state['limits']['candidate_revisions'] and remaining>0:
            kind='investigate';action='investigate';required=['hypotheses','probes']
    elif status=='diagnosing':
        probes=state.get('investigation',{}).get('probes',[])
        pending=[p for p in probes if p.get('status')=='proposed']
        if pending and remaining>0:
            kind='execute_probe';action='probe';fixed={'probe':pending[0]['id']}
        elif remaining>0:
            kind='choose_intervention';action='propose';required=['intervention','rationale']
    elif status=='proposed':
        if state.get('intervention') in {'gather_evidence','refresh_context'}:
            kind='investigate';action='investigate';required=['hypotheses','probes']
        else:
            kind='isolate';action='build'
    elif status=='building':
        if remaining>0:
            kind='author_candidate';action='evaluate';required=['authorship']
    elif status=='ready_for_review': kind='review'
    elif status=='activated': kind='observe_later_use'
    packet={'schema':'sips.work-packet.v1','episode':episode,'revision':revision,'kind':kind,
            'action':action,'required_output':required,'fixed_input':fixed,'task':state['task'],
            'evidence':state['evidence'],'hypotheses':state.get('hypotheses',[]),
            'workspace':state['workspace'],'context_files':state.get('context_files',[]),
            'allowed_files':state['allowed_files'],'candidate_path':state.get('candidate_path'),
            'suite_digest':state['suite_digest'],'baseline_identity':canonical_hash(state['baseline_manifest']),
            'limits':state['limits'],'remaining_evaluation_seconds':remaining,
            'improvement_notices':len(state.get('opportunities',[])),
            'improvement_capture':{'action':'notice','when':'A reproduced tool failure, verified stale instruction, or reusable workflow gap is encountered','view':'opportunities','changes_current_scope':False},
            'authorship':'active task agent; no model invocation','activation':'explicit exact candidate only'}
    packet['packet_id']=canonical_hash(packet)
    return packet


def validate_authorship(value):
    fields={'agent','model_label','summary','evidence'}
    if not isinstance(value,dict) or set(value)!=fields:
        raise ValueError('authorship requires agent, model_label, summary and evidence')
    if any(not isinstance(value[k],str) or not value[k].strip() or len(value[k])>8000 for k in fields-{'evidence'}):
        raise ValueError('nonempty bounded authorship fields required')
    if not isinstance(value['evidence'],list) or not value['evidence'] or len(value['evidence'])>32 or any(not isinstance(x,str) or not x for x in value['evidence']):
        raise ValueError('bounded authorship evidence references required')
    return {**value,'provenance':'host-agent declaration; exact runtime model and token usage unverified', 'actual_tokens':None}


def comparison(records):
    """Summarize linked executed episodes; never turn missing arms into a win."""
    modes=('none','episodic','procedure');groups={}
    for r in records:
        groups.setdefault(r['task_identity'],{})[r['memory_mode']]=r
    complete=[g for g in groups.values() if all(m in g for m in modes)]
    gains=regressions=unavailable=0
    for group in complete:
        statuses=[group[m]['candidate_status'] for m in modes]
        if 'unavailable' in statuses: unavailable+=1;continue
        if statuses[2]=='passed' and all(s=='failed' for s in statuses[:2]): gains+=1
        if statuses[2]=='failed' and any(s=='passed' for s in statuses[:2]): regressions+=1
    return {'schema':'sips.later-use.v1','episodes':len(records),'matched_task_groups':len(complete),
            'incomplete_task_groups':len(groups)-len(complete),'observed_procedure_gains':gains,
            'observed_negative_transfer':regressions,'unavailable_groups':unavailable,
            'evaluation_seconds':sum(r['evaluation_seconds'] for r in records),
            'effectiveness':'unmeasured' if not complete else 'descriptive_matched_observations',
            'boundary':'Declared matching and memory modes; authorship conditions, independent holdout sealing and causality are not established.'}

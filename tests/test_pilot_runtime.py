"""24 public synthetic cases: runtime integrity only, no transfer claim."""
import json
import os
from pathlib import Path
import sys
import pytest
if os.environ.get('SIPS_PILOT_SOURCE'):
    sys.path.insert(0,str(Path(os.environ['SIPS_PILOT_SOURCE'])/'scripts'))
from sips_runtime.hypergraph import compatible,schema,compose
from sips_runtime.procedures import retrieve
from sips_runtime.evaluation import check
from test_transferable_core import scalar,tool,procedure
from test_adaptive_core import setup_episode,step,build

CASES=['missing_required','wrong_scalar','extra_property','schema_version','nullable_boundary','nested_array',
       'joint_inputs','write_conflict','missing_dependency','consumer_regression','cyclic_production','ambiguous_binding',
       'unrelated_query','expired_proof','negative_applicability','source_drift','cross_family_transfer','misleading_procedure',
       'missing_interpreter','timeout','dependency_drift','empty_collection','interrupted_probe','changed_fixture']

@pytest.mark.parametrize('case',CASES,ids=CASES)
def test_runtime_case(case,tmp_path):
    if case=='missing_required':
        r={'type':'object','properties':{'x':scalar()},'required':['x']}
        assert not compatible({**r,'required':[]},r)
    elif case=='wrong_scalar': assert not compatible(scalar(),scalar('integer'))
    elif case=='extra_property':
        assert not compatible({'type':'object','properties':{'x':scalar()},'additionalProperties':False},{'type':'object','additionalProperties':False})
    elif case=='schema_version': assert not compatible(scalar(version=1),scalar(version=2))
    elif case=='nullable_boundary': assert not compatible(scalar('null'),scalar())
    elif case=='nested_array': assert not compatible({'type':'array','items':scalar()},{'type':'array','items':scalar('integer')})
    elif case in {'joint_inputs','write_conflict','missing_dependency','cyclic_production','ambiguous_binding'}:
        a=tool();available={'raw':scalar()};tools=[a];required={'n':scalar('integer')}
        if case=='joint_inputs': a['inputs']['flag']=scalar('boolean');a['bindings']['flag']='flag'
        elif case=='missing_dependency':a['resources']=['dep'];a['dependencies']=['dep']
        elif case=='cyclic_production':available={}
        elif case=='ambiguous_binding':available={'a':scalar(),'b':scalar()}
        elif case=='write_conflict':
            b=tool('other',{'n':scalar('integer')},{'b':scalar('boolean')});a['effects']['writes']=['x'];b['effects']['writes']=['x'];tools.append(b);required={'b':scalar('boolean')}
        assert compose(tools,available,required,prerequisites=['local'])['status']=='insufficient_fit'
    elif case in {'unrelated_query','expired_proof','negative_applicability','source_drift','cross_family_transfer','misleading_procedure'}:
        p=procedure();query='parser';context={'schema':2};now=100;current=lambda s:True
        if case=='unrelated_query':query='banana'
        elif case=='expired_proof':now=201
        elif case=='negative_applicability':context={'schema':1}
        elif case=='source_drift':current=lambda s:False
        elif case=='cross_family_transfer':query='runtime timeout'
        elif case=='misleading_procedure':context['consumer']='unsupported'
        assert retrieve([p],query,context,now,current)==[]
    elif case=='consumer_regression':
        result=check({'kind':'command','argv':['{python}','-c','print("wrong")'],'stdout':'right\n'},tmp_path,tmp_path,1)
        assert result['status']=='failed'
    elif case=='missing_interpreter':
        assert check({'kind':'command','argv':['sips-missing-interpreter'],'stdout':''},tmp_path,tmp_path,1)['status']=='unavailable'
    elif case=='timeout':
        assert check({'kind':'command','argv':['{python}','-c','import time;time.sleep(2)'],'stdout':''},tmp_path,tmp_path,.01)['status']=='unavailable'
    elif case=='empty_collection':
        assert check({'kind':'pytest','argv':[str(tmp_path)]},tmp_path,tmp_path,10)['status']=='unavailable'
    else:
        c,r,_,_=setup_episode(tmp_path);r=build(c,r);directory=c.directory(r['episode'])
        if case=='interrupted_probe':
            from sips_runtime.events import EventStore
            r['probe_running']='x';r['probe_started_at']=0
            EventStore(directory).append('interrupted',r['episode'],{'state':r})
            r=c.read(r['episode']);r=step(c,r,'recover');assert r['state']=='unavailable'
        else:
            (directory/('fixtures/changed' if case=='changed_fixture' else 'baseline/untouched')).write_text('drift')
            with pytest.raises(ValueError,match='drift'):step(c,r,'evaluate')

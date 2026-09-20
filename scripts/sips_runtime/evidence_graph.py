"""Read-only current-validity projection; immutable events remain authoritative."""
import json
import sys
from pathlib import Path
from .canonical import canonical_hash
from .hypergraph import invalidated


def project(directory,state):
    from .adaptation import manifest,file_identity
    nodes={};deps={}
    def node(name,kind,expected,actual,requires=()):
        nodes[name]={'id':name,'kind':kind,'expected':expected,'observed':actual,'status':'current' if expected==actual else 'stale'}
        deps[name]=list(requires)
    def files(prefix,root,expected):
        for name in sorted(expected):
            try: actual=file_identity(root/name) if not (root/name).is_symlink() else None
            except OSError: actual=None
            node(prefix+':'+name,prefix,expected[name],actual)
        return [prefix+':'+n for n in sorted(expected)]
    node('environment','environment',canonical_hash(state['environment']),canonical_hash({'python':sys.version,'platform':sys.platform,'interpreter':sys.executable}))
    roots=['environment']
    for kind,field in [('baseline','baseline_manifest'),('fixtures','fixtures_manifest'),('evaluator','evaluator_manifest')]:
        children=files(kind,directory/kind,state[field])
        try: observed=canonical_hash(manifest(directory/kind))
        except (ValueError,OSError): observed=None
        node(kind+':manifest',kind,canonical_hash(state[field]),observed,children)
        roots.append(kind+':manifest')
    expected=state.get('candidate_manifest',state['baseline_manifest']) if state['state']=='activated' else state['baseline_manifest']
    scoped={name:expected.get(name) for name in set(expected)|set(state['allowed_files'])|set(state.get('context_files',[]))}
    roots+=files('workspace',Path(state['workspace']),scoped)
    try: suite=canonical_hash(json.loads((directory/state.get('suite_file','suite.json')).read_text()))
    except (ValueError,OSError): suite=None
    node('suite','criteria',state['suite_digest'],suite);roots.append('suite')
    if state.get('candidate_manifest'):
        try: observed=canonical_hash(manifest(directory/'candidate'))
        except (ValueError,OSError): observed=None
        node('candidate','candidate',canonical_hash(state['candidate_manifest']),observed,roots)
    if state.get('receipt'):
        try: observed=canonical_hash(json.loads((directory/state['receipt']).read_text()))
        except (ValueError,OSError): observed=None
        expected_receipt=state.get('receipt_digest')
        node('receipt','evaluation',expected_receipt,observed,roots+(['candidate'] if 'candidate' in nodes else []))
        if expected_receipt is None: nodes['receipt']['status']='unverified_historical'
    if state.get('composition'):
        from .capabilities import registry
        node('registry','capabilities',state['composition']['dependency_identity'],canonical_hash(registry(state['workspace'])))
        node('composition','plan',canonical_hash(state['composition']),canonical_hash(state['composition']),['registry'])
    # Later-use links preserve historical identities and expose changed supporting receipts.
    for i,use in enumerate(state.get('later_use',[])):
        identity='later-use:'+str(i)
        try:
            from .adaptation import AdaptationController
            target=AdaptationController(directory.parent.parent).read(use['target_episode'],'receipt')
            observed=canonical_hash(target['results'])
        except (ValueError,OSError,KeyError): observed=None
        node(identity,'later_use',use['receipt_digest'],observed,['receipt'] if 'receipt' in nodes else [])
    before={k:n['expected'] for k,n in nodes.items()};after={k:n['observed'] for k,n in nodes.items()}
    affected=invalidated(before,after,deps)
    for name in affected:
        if nodes[name]['status']=='current': nodes[name]['status']='stale_dependency'
    explanations={}
    def explain(name,seen):
        if name in seen: return []
        if nodes[name]['expected']!=nodes[name]['observed']: return [name]
        return sorted({reason for dep in deps[name] for reason in explain(dep,seen|{name})})
    for name in affected: explanations[name]=explain(name,set())
    return {'schema':'sips.evidence-graph.v1','nodes':[nodes[k] for k in sorted(nodes)],
            'edges':[{'from':d,'to':n,'relation':'requires'} for n in sorted(deps) for d in deps[n]],
            'affected':affected,'reasons':explanations,'revalidation_required':[n for n in affected if nodes[n]['kind'] in {'evaluation','plan','later_use'}],
            'activation':'none','boundary':'Current applicability projection, not a rewrite of historical evidence; registry invalidation is conservative.'}

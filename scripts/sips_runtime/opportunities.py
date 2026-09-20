"""Evidence-linked improvement notices; active agents author all candidates."""
from pathlib import Path
from .canonical import canonical_hash
from .evaluation import path_in

KINDS={'create_skill','extend_skill','refresh_skill','create_tool','repair_tool','compose_tools','update_behavior'}


def capture(state,request):
    from .adaptation import file_identity
    kind=request.get('kind');name=request.get('path')
    if kind not in KINDS or not isinstance(name,str) or not name or len(name)>1024: raise ValueError('improvement kind and relative target required')
    root=Path(state['workspace']);path=path_in(root,name)
    if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('relative local target required')
    if any((root/Path(*Path(name).parts[:i])).is_symlink() for i in range(1,len(Path(name).parts)+1)): raise ValueError('symlink target unsupported')
    if path.exists() and not path.is_file(): raise ValueError('target must name a file')
    if kind.endswith('skill') and (not name.startswith('skills/') or not name.endswith('/SKILL.md')): raise ValueError('skill target must be skills/name/SKILL.md')
    if kind in {'extend_skill','refresh_skill','repair_tool','update_behavior'} and not path.is_file(): raise ValueError('existing target required')
    if kind in {'create_skill','create_tool'} and path.exists(): raise ValueError('extend or repair existing target instead')
    for field in ('title','rationale'):
        if not isinstance(request.get(field),str) or not request[field].strip() or len(request[field])>4000: raise ValueError('bounded title and rationale required')
    indices=request.get('evidence_indices')
    if not isinstance(indices,list) or not 1<=len(indices)<=16 or any(type(i) is not int or i<0 or i>=len(state['evidence']) for i in indices): raise ValueError('existing episode evidence indices required')
    checks=request.get('acceptance')
    if not isinstance(checks,list) or not 1<=len(checks)<=16 or any(not isinstance(x,str) or not x.strip() or len(x)>2000 for x in checks): raise ValueError('bounded acceptance requirements required')
    record={k:request[k] for k in ('kind','path','title','rationale','acceptance')}
    record.update(schema='sips.improvement-notice.v1',source_identity=file_identity(path) if path.is_file() else None,
                  evidence=[{'index':i,'identity':canonical_hash(state['evidence'][i])} for i in sorted(set(indices))],
                  effectiveness='unknown',activation='none')
    record['id']=canonical_hash(record)
    records=state.setdefault('opportunities',[])
    if not any(r['id']==record['id'] for r in records):
        if len(records)>=64: raise ValueError('episode notice limit reached')
        records.append(record)
    return state


def project(state):
    from .adaptation import file_identity
    result=[]
    for record in state.get('opportunities',[]):
        try:
            path=path_in(state['workspace'],record['path'])
            root=Path(state['workspace']);relative=Path(record['path'])
            linked=any((root/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts)+1))
            actual='unavailable' if linked else file_identity(path) if path.is_file() else 'non_file' if path.exists() else None
        except (ValueError,OSError): actual='unavailable'
        result.append({**record,'status':'proposed' if actual==record['source_identity'] else 'stale',
                       'next_action':'Create a separate scoped episode with frozen original, regression and counterexample checks; author in its isolated candidate.',
                       'observation_template':{'workspace':state['workspace'],'task':record['title'],'allowed_files':[record['path']],
                                               'evidence':[{'notice':record['id'],'source_identity':record['source_identity'],'requirements':record['acceptance']}],
                                               'suite_required':['original','regression','counterexamples']}})
    return result

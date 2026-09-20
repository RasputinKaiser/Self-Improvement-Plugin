"""Small semantic contract vocabulary; declarations are not verified meaning."""
import math


def validate(value,kind):
    if not isinstance(value,dict) or set(value)-{'role','unit','context','minimum','maximum'}: raise ValueError('unsupported semantic constraint')
    for key in ('role','unit'):
        if key in value and (not isinstance(value[key],str) or not value[key] or len(value[key])>128): raise ValueError('bounded semantic labels required')
    if 'context' in value:
        c=value['context']
        if not isinstance(c,dict) or len(c)>16 or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in c.items()): raise ValueError('literal context identities required')
    for key in ('minimum','maximum'):
        if key in value and (kind not in {'integer','number'} or type(value[key]) not in (int,float) or not math.isfinite(value[key])): raise ValueError('finite numeric bounds required')
    if value.get('minimum',-math.inf)>value.get('maximum',math.inf): raise ValueError('empty semantic range')


def implies(produced,required):
    for key in ('role','unit'):
        if key in required and produced.get(key)!=required[key]: return False
    if any(produced.get('context',{}).get(k)!=v for k,v in required.get('context',{}).items()): return False
    if 'minimum' in required and ('minimum' not in produced or produced['minimum']<required['minimum']): return False
    if 'maximum' in required and ('maximum' not in produced or produced['maximum']>required['maximum']): return False
    return True


def accepts(value,semantics):
    return ('minimum' not in semantics or value>=semantics['minimum']) and ('maximum' not in semantics or value<=semantics['maximum'])

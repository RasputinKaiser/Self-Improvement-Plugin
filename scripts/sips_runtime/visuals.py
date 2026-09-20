"""Read-only, evidence-linked diagrams for host-rendered SIPS explanations."""
from html import escape


def episode_view(state,episode,revision,dependencies,opportunities):
    status=state['state']
    def label(text):
        return escape(str(text),quote=True).replace('\n',' ').replace('\r',' ')[:240]
    evidence=len(state.get('evidence',[]));stale=len(dependencies['affected'])
    candidate='Recorded candidate' if state.get('candidate_digest') else 'No evaluated candidate'
    # Node identifiers and connections are fixed; all user text stays in escaped labels.
    diagram='\n'.join(['flowchart LR',f'  E["{evidence} evidence records"] --> S["{label(status)}"]',
                       f'  S --> C["{candidate}"]',f'  C --> R["{label(state.get("effectiveness","unknown"))}"]',
                       f'  S --> D["{stale} affected dependency nodes"]',
                       f'  S --> N["{len(opportunities)} improvement notices"]',
                       '  R --> A["Activation requires exact candidate request"]'])
    nodes=sorted(dependencies.get('nodes',[]),key=lambda n:(n['id'] not in dependencies['affected'],n['id']))[:24]
    ids={n['id']:'d'+str(i) for i,n in enumerate(nodes)}
    dep_lines=['flowchart LR']
    for n in nodes:
        dep_lines.append(f'  {ids[n["id"]]}["{label(n["id"])}: {label(n["status"])}"]')
    for edge in dependencies.get('edges',[]):
        if edge['from'] in ids and edge['to'] in ids: dep_lines.append(f'  {ids[edge["from"]]} --> {ids[edge["to"]]}')
    return {'schema':'sips.episode-visual.v1','episode':episode,'revision':revision,'mermaid':diagram,
            'dependency_mermaid':'\n'.join(dep_lines),
            'dependency_nodes_omitted':max(0,len(dependencies.get('nodes',[]))-len(nodes)),
            'summary':{'state':status,'evidence_records':evidence,'affected_dependency_nodes':stale,
                       'notice_count':len(opportunities),'effectiveness':state.get('effectiveness','unknown')},
            'evidence_views':['events','receipt','dependencies','opportunities','diff'],
            'rendering':'Host or assistant renders Mermaid; returning source does not prove screen display.',
            'boundary':'Episode evidence only; evaluation success is not an activation or general transfer result.'}

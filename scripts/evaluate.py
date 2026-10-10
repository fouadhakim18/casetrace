"""Save actual retrieval, offline and optional live LLM results. Never fabricates a fallback."""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from casetrace.config import settings
from casetrace.documents import parse_document
from casetrace.retrieval import Index
from casetrace.workflow import run_workflow

OBJECTIVE='Check incident dates, invoice arithmetic, repeated invoice references and missing required evidence. Distinguish benign copies from unexplained inconsistencies. Cite exact source passages. Do not invent requirements beyond the supplied documents.'

def evaluate(live=False,case_filter=None,mode_filter=None):
    artifact=ROOT/'artifacts';artifact.mkdir(exist_ok=True)
    path=artifact/'evaluation.json'
    output=json.loads(path.read_text('utf-8')) if path.exists() else {'runs':[]}
    output.update(created_at=datetime.now(timezone.utc).isoformat(),status='running',
       message='Exploratory benchmark on 3 hand-authored synthetic cases. Category-level labels are coarse, not clinical or insurance validation. Agent gains are not assumed.',
       protocol={'objective':OBJECTIVE,'category_scoring':'Set comparison of issue kinds per dossier. supported findings excluded. This does not evaluate semantic correctness of every finding.','retrieval':'Recall@3 on 8 hand-authored queries; local lexical FAISS retrieval.','repetitions':1})
    retrieval=[]
    for folder in sorted((ROOT/'demo_cases').iterdir()):
        if not folder.is_dir():continue
        meta=json.loads((folder/'expected.json').read_text('utf-8'))
        documents=[parse_document(p.name,p.read_bytes()) for p in sorted(folder.glob('*.pdf'))]
        for d in documents:d['id']=hashlib.sha256((folder.name+'/'+d['name']).encode()).hexdigest()[:24]
        index=Index(documents)
        for q in meta['retrieval_queries']:
            hits=index.search(q['query'],k=3)
            retrieval.append(dict(case=folder.name,**q,found=q['expected_file'] in [h['name'] for h in hits],hits=[h['name'] for h in hits]))
        if case_filter and folder.name!=case_filter:continue
        modes=[mode_filter] if mode_filter else (['offline','baseline','agents'] if live else ['offline'])
        for mode in modes:
            if mode!='offline' and not live:continue
            entry={'case':folder.name,'mode':mode,'started_at':datetime.now(timezone.utc).isoformat(),'model':settings()['model'] if mode!='offline' else None,
                   'document_hashes':{d['name']:d['sha256'] for d in documents},'events':[],'expected_kinds':meta['expected_kinds']}
            def emit(role,kind,message,data):
                entry['events'].append({'role':role,'kind':kind,'message':message,'data':data})
                print(f'{folder.name}/{mode}: {role} {kind}',flush=True)
            start=time.perf_counter()
            try:
                result=run_workflow({'documents':documents},OBJECTIVE,mode,emit)
                entry.update(status='completed',result=result)
                expected=set(meta['expected_kinds']);predicted={f['kind'] for f in result['report']['findings'] if f['kind']!='supported'}
                entry['metrics']={'expected_kinds':sorted(expected),'predicted_kinds':sorted(predicted),'true_positive_categories':len(expected&predicted),
                    'false_positive_categories':len(predicted-expected),'missed_categories':len(expected-predicted),
                    'valid_quote_findings':sum(c['valid'] for c in result['citation_checks']),'total_findings':len(result['citation_checks'])}
            except Exception as exc:
                from casetrace.provider import ProviderError
                entry.update(status='failed',error=str(exc) if isinstance(exc,ProviderError) else type(exc).__name__)
            entry['elapsed_seconds']=round(time.perf_counter()-start,2)
            previous=[r for r in output['runs'] if (r['case'],r['mode'])==(folder.name,mode)]
            if previous:output.setdefault('development_history',[]).extend(previous)
            output['runs']=[r for r in output['runs'] if (r['case'],r['mode'])!=(folder.name,mode)]+[entry]
            output['retrieval']=retrieval;path.write_text(json.dumps(output,indent=2),encoding='utf-8')
            print(f"Result: {entry['status']} ({entry['elapsed_seconds']}s)",flush=True)
            if mode!='offline' and entry['status']=='failed':
                print('Stopping live calls after failure; no paid fallback.',flush=True)
                live=False
    output['retrieval']=retrieval
    output['status']='completed_with_failures' if any(r['status']=='failed' for r in output['runs']) else 'completed'
    output['summary']={'synthetic_cases':3,'retrieval_queries':len(retrieval),'retrieval_recall_at_3':round(sum(q['found'] for q in retrieval)/max(1,len(retrieval)),3),
        'offline_runs_completed':sum(r['mode']=='offline' and r['status']=='completed' for r in output['runs']),
        'live_runs_completed':sum(r['mode']!='offline' and r['status']=='completed' for r in output['runs']),
        'failed_runs':sum(r['status']=='failed' for r in output['runs'])}
    path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output['summary']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--case');p.add_argument('--mode',choices=['offline','baseline','agents']);args=p.parse_args()
    evaluate(args.live,args.case,args.mode)

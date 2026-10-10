"""Build result tables and a self-contained replay of recorded runs."""
import base64
import hashlib
import html
import io
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from casetrace.documents import parse_document
from casetrace.app import markdown

def build():
    evaluation=json.loads((ROOT/'artifacts/evaluation.json').read_text('utf-8'))
    rows=['# Recorded results','',f"Generated from `artifacts/evaluation.json` ({evaluation['created_at']}).",'',
      'This is a development-used, synthetic smoke benchmark with one current attempt per condition. It does not establish general agent superiority. Older available development attempts remain in the raw JSON.','',
      '| Case | Mode | Status | Matched / extra / missed categories | Quote-valid findings | Calls | Chat tokens | Seconds |',
      '|---|---|---|---|---|---:|---:|---:|']
    failures=[]
    for r in sorted(evaluation['runs'],key=lambda x:(x['case'],x['mode'])):
        m=r.get('metrics',{});u=r.get('result',{}).get('usage',{})
        cats=f"{m.get('true_positive_categories','—')} / {m.get('false_positive_categories','—')} / {m.get('missed_categories','—')}"
        quotes=f"{m.get('valid_quote_findings','—')} / {m.get('total_findings','—')}"
        rows.append(f"| {r['case']} | {r['mode']} | {r['status']} | {cats} | {quotes} | {u.get('calls','—')} | {u.get('total_tokens','—')} | {r['elapsed_seconds']} |")
        if r.get('error'):failures.append(f"- {r['case']}/{r['mode']}: {r['error']}")
    rows+=['','## Recorded failures','']+failures
    rows+=['',f"Retrieval Recall@3: {evaluation['summary']['retrieval_recall_at_3']} on {len(evaluation['retrieval'])} queries.",'',
     'A denominator of zero means no findings, not proof of perfect accuracy. Quote-valid means that listed quotes match source text, not that every interpretation is correct. Category scoring excludes supported-only findings.',
     '', 'The clean dossier illustrates an audit/cost tradeoff: a verifier can confirm the same answer as a single-pass baseline while consuming more calls and tokens. This project does not claim a demonstrated accuracy gain.',
     '', 'Execution scope: Python unit/API tests and real Gemini calls were executed. Docker, remote GitHub Actions, local Ollama and public hosting have not been validated. Browser verification status is recorded separately in `artifacts/verification.json`.',
     '', 'Free-tier quota errors during development were retained where available. Calls are not silently replaced by offline outputs.']
    (ROOT/'docs/RESULTS.md').write_text('\n'.join(rows),encoding='utf-8')

    cases=[];runs=[];downloads={}
    display_runs=list(evaluation['runs'])
    for failed in evaluation['runs']:
        if failed['status']=='completed':continue
        historical=[r for r in evaluation.get('development_history',[]) if r['case']==failed['case'] and r['mode']==failed['mode'] and r['status']=='completed']
        if historical:display_runs.append(dict(historical[-1],historical=True))
    for folder in sorted((ROOT/'demo_cases').iterdir()):
        if not folder.is_dir():continue
        meta=json.loads((folder/'expected.json').read_text('utf-8'));docs=[]
        for p in sorted(folder.glob('*.pdf')):
            d=parse_document(p.name,p.read_bytes());d['id']=hashlib.sha256((folder.name+'/'+p.name).encode()).hexdigest()[:24];docs.append(d)
            downloads[f"/api/cases/{folder.name}/documents/{d['id']}/file"]={'name':p.name,'mime':'application/pdf','base64':base64.b64encode(p.read_bytes()).decode()}
        case={'id':folder.name,'title':meta['title'],'synthetic':True,'demo_key':folder.name,'created_at':evaluation['created_at'],'documents':docs,'document_count':len(docs)};cases.append(case)
        # Current failures remain visible; an available older success is explicitly labelled.
        for r in display_runs:
            if r['case']!=folder.name:continue
            rid=folder.name+'-'+r['mode']+('-historical' if r.get('historical') else '')
            run={'id':rid,'case_id':folder.name,'case_title':meta['title'],'mode':r['mode'],'created_at':r['started_at'],'finished_at':r['started_at'],
             'status':r['status'],'objective':evaluation['protocol']['objective'],'events':[e|{'at':r['started_at']} for e in r['events']],
             'documents':[{'id':d['id'],'name':d['name'],'sha256':d['sha256']} for d in docs],
             'human_review':{'status':'unreviewed','note':''},'configuration':{'model':r['model'],'recorded_demo':True,'historical':bool(r.get('historical'))}}
            if r.get('historical'):
                run['events'].insert(0,{'at':r['started_at'],'role':'system','kind':'historical','message':'Historical successful development run. The latest attempt is separately listed and failed.','data':{}})
            if r.get('result'):run['result']=r['result']
            if r.get('error'):run['error']=r['error']
            runs.append(run)
            md=markdown(run);pdf=io.BytesIO();styles=getSampleStyleSheet()
            story=[]
            for line in md.split('\n\n'):
                style='Title' if line.startswith('# ') else 'Heading2' if line.startswith('## ') else 'BodyText'
                story.extend([Paragraph(escape(line.lstrip('# ')),styles[style]),Spacer(1,8)])
            SimpleDocTemplate(pdf,title='CaseTrace recorded investigation').build(story)
            for fmt,data,mime in [('json',json.dumps(run,indent=2).encode(),'application/json'),('md',md.encode(),'text/markdown'),('pdf',pdf.getvalue(),'application/pdf')]:
                downloads[f'/api/runs/{rid}/export/{fmt}']={'name':rid+'.'+fmt,'mime':mime,'base64':base64.b64encode(data).decode()}
    bundle={'cases':cases,'runs':runs,'evaluation':evaluation,'downloads':downloads}
    # Escape '<' to prevent embedded document text from closing a script element.
    data=json.dumps(bundle,ensure_ascii=True).replace('<','\\u003c')
    shim="""
const replay = REPLAY_DATA;
window.fetch=async function(url,opts={}){
 const path=String(url).replace(/^\\/api/,'');const method=opts.method||'GET';let result;
 if(path==='/config')result={provider:'RECORDED',model:'gemini-2.5-flash (saved execution)',embeddings:'local',max_calls:8,configured:true};
 else if(path==='/cases'||path==='/demo')result=replay.cases;
 else if(path==='/evaluation')result=replay.evaluation;
 else if(method!=='GET')return new Response(JSON.stringify({detail:'This is a recorded demonstration. Start the Python application for live calls, uploads and human review.'}),{status:400});
 else if(/^\\/cases\\/[^/]+\\/runs$/.test(path))result=replay.runs.filter(r=>r.case_id===path.split('/')[2]).sort((a,b)=>(a.mode==='agents'?-1:1));
 else if(path.startsWith('/cases/'))result=replay.cases.find(c=>c.id===path.split('/')[2]);
 else if(path.startsWith('/runs/'))result=replay.runs.find(r=>r.id===path.split('/')[2]);
 return new Response(JSON.stringify(result||{detail:'Not available in recorded demo'}),{status:result?200:404,headers:{'Content-Type':'application/json'}});
};
document.addEventListener('click',e=>{const a=e.target.closest('a');const key=a?.getAttribute('href');const d=replay.downloads[key];if(d){e.preventDefault();const bytes=Uint8Array.from(atob(d.base64),c=>c.charCodeAt(0));const u=URL.createObjectURL(new Blob([bytes],{type:d.mime}));const out=document.createElement('a');out.href=u;out.download=d.name;out.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}},true);
""".replace('REPLAY_DATA',data)
    page=(ROOT/'static/index.html').read_text('utf-8')
    page=page.replace('<link rel="stylesheet" href="/style.css">','<style>'+(ROOT/'static/style.css').read_text('utf-8')+'</style>')
    page=page.replace('<script src="/app.js" defer></script>','')
    page=page.replace('<main>','<main><div class="notice"><strong>RECORDED DEMONSTRATION</strong> · Saved Gemini executions, not live calls. Sources, findings, traces and downloads work offline. Start the Python app to investigate new documents.</div>')
    page=page.replace('href="/"','href="#"').replace('href="/openapi.json"','href="#"')
    page=page.replace('API schema ↗','Recorded demonstration')
    page=page.replace('</body>','<script>'+shim+'</script><script>'+(ROOT/'static/app.js').read_text('utf-8')+'</script></body>')
    (ROOT/'CaseTrace_Demo.html').write_text(page,encoding='utf-8')
    (ROOT/'artifacts/replay-data.json').write_text(json.dumps({'cases':cases,'runs':runs},indent=2),encoding='utf-8')
    print('Generated results table and self-contained recorded demo.')

if __name__=='__main__':build()

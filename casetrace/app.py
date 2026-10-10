"""Local single-user API. Run with uvicorn casetrace.app:app --host 127.0.0.1."""
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from . import store
from .config import ROOT, data_dir, settings
from .documents import parse_document, MAX_FILE_BYTES
from .models import InvestigationRequest, HumanReview, SearchRequest
from .workflow import run_workflow

executor = ThreadPoolExecutor(max_workers=1)
lock = threading.RLock()
cancellations = {}

@asynccontextmanager
async def lifespan(app):
    store.mark_interrupted()
    yield

app = FastAPI(title='CaseTrace', version='1.0.0', lifespan=lifespan)

@app.middleware('http')
async def local_guard(request: Request, call_next):
    host = request.url.hostname
    if host not in ('127.0.0.1', 'localhost', 'testserver'):
        return JSONResponse({'detail':'This application is for local use only.'}, status_code=403)
    origin = request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin != str(request.base_url).rstrip('/'):
        return JSONResponse({'detail':'Cross-origin writes are disabled.'},status_code=403)
    try:
        if int(request.headers.get('content-length','0')) > 26_000_000:
            return JSONResponse({'detail':'Upload limit is 25 MB per request.'},status_code=413)
    except ValueError:
        return JSONResponse({'detail':'Invalid content length.'},status_code=400)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    return response

@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse({'detail':'Requested resource not found.'},status_code=404)

@app.get('/api/config')
def config():
    s=settings()
    return {k:s[k] for k in ('provider','model','embeddings','max_calls')} | {'configured':bool(s['key']) or s['provider']=='compatible'}

@app.get('/api/cases')
def cases():
    return [{k:v for k,v in c.items() if k!='documents'} | {'document_count':len(c['documents'])} for c in store.list_cases()]

@app.get('/api/cases/{case_id}')
def case(case_id:str):
    return store.get_case(case_id)

async def ingest(files):
    if not files or len(files)>12: raise HTTPException(400,'Choose between 1 and 12 documents.')
    docs=[]
    for file in files:
        content=await file.read(MAX_FILE_BYTES+1)
        try: doc=parse_document(file.filename or 'document.txt',content)
        except Exception as exc:
            raise HTTPException(400, str(exc) if isinstance(exc,ValueError) else 'Could not extract this document.') from None
        docs.append((doc,content))
    if sum(d['characters'] for d,_ in docs)>500_000: raise HTTPException(400,'Maximum 500,000 extracted characters per case.')
    return docs

def persist_docs(case_id,parsed):
    directory=data_dir()/'files'/case_id
    directory.mkdir(parents=True,exist_ok=True)
    for doc,content in parsed:
        (directory/doc['id']).write_bytes(content)
    return [d for d,_ in parsed]

@app.post('/api/cases',status_code=201)
async def create_case(title:str=Form(...),files:list[UploadFile]=File(...)):
    if not 3<=len(title.strip())<=100: raise HTTPException(400,'Title must contain 3–100 characters.')
    parsed=await ingest(files)
    c={'id':store.uid(),'title':title.strip(),'created_at':store.now(),'synthetic':False}
    c['documents']=persist_docs(c['id'],parsed)
    return store.save_case(c)

@app.post('/api/demo')
def seed_demo():
    with lock:
        existing={c.get('demo_key'):c for c in store.list_cases()}
        for folder in sorted((ROOT/'demo_cases').iterdir()):
            if not folder.is_dir() or folder.name in existing: continue
            meta=json.loads((folder/'expected.json').read_text('utf-8'))
            c={'id':store.uid(),'title':meta['title'],'created_at':store.now(),'synthetic':True,'demo_key':folder.name}
            parsed=[(parse_document(p.name,p.read_bytes()),p.read_bytes()) for p in sorted(folder.glob('*.pdf'))]
            c['documents']=persist_docs(c['id'],parsed)
            store.save_case(c)
    return cases()

@app.get('/api/cases/{case_id}/documents/{document_id}/file')
def document_file(case_id:str,document_id:str):
    c=store.get_case(case_id)
    doc=next((d for d in c['documents'] if d['id']==document_id),None)
    if not doc: raise HTTPException(404,'Document not found.')
    return FileResponse(data_dir()/'files'/c['id']/doc['id'],filename=doc['name'],content_disposition_type='attachment')

@app.get('/api/cases/{case_id}/runs')
def runs(case_id:str):
    store.get_case(case_id)
    return store.list_runs(case_id)

def execute(run,case,cancel):
    def emit(role,kind,message,data):
        with lock:
            run['events'].append({'at':store.now(),'role':role,'kind':kind,'message':message,'data':data})
            store.save_run(run)
    try:
        run['status']='running';store.save_run(run)
        run['result']=run_workflow(case,run['objective'],run['mode'],emit,cancel.is_set)
        run['status']='cancelled' if cancel.is_set() else 'completed'
    except Exception as exc:
        from .provider import ProviderError
        run['status']='cancelled' if cancel.is_set() else 'failed'
        run['error']=str(exc) if isinstance(exc,ProviderError) else f'{type(exc).__name__}: processing failed. Check document format and model response.'
    finally:
        with lock:
            run['finished_at']=store.now();store.save_run(run)
            cancellations.pop(run['id'],None)

@app.post('/api/cases/{case_id}/runs',status_code=202)
def investigate(case_id:str,body:InvestigationRequest):
    c=store.get_case(case_id)
    s=settings()
    if body.mode!='offline' and not body.allow_external:
        raise HTTPException(400,'Confirm that the configured model may receive document excerpts.')
    if body.mode!='offline' and s['provider']=='gemini' and not s['key']:
        raise HTTPException(400,'Configure GEMINI_API_KEY in the local .env file first.')
    with lock:
        if cancellations: raise HTTPException(409,'One investigation is already running. Finish or cancel it first.')
        run={'id':store.uid(),'case_id':case_id,'case_title':c['title'],'created_at':store.now(),'status':'queued',
             'mode':body.mode,'objective':body.objective,'events':[],'human_review':{'status':'unreviewed','note':''},
             'configuration':{k:s[k] for k in ('provider','model','embeddings','max_calls','max_output_tokens')},
             'documents':[{'id':d['id'],'name':d['name'],'sha256':d['sha256']} for d in c['documents']]}
        cancel=threading.Event();cancellations[run['id']]=cancel;store.save_run(run)
        executor.submit(execute,run,c,cancel)
    return {'id':run['id'],'status':'queued'}

@app.get('/api/runs/{run_id}')
def run(run_id:str):return store.get_run(run_id)

@app.post('/api/runs/{run_id}/cancel')
def cancel(run_id:str):
    store.get_run(run_id)
    with lock:
        flag=cancellations.get(run_id)
        if flag:flag.set()
    return {'message':'Cancellation requested; any in-flight model request may finish first.'}

@app.put('/api/runs/{run_id}/review')
def review(run_id:str,body:HumanReview):
    with lock:
        r=store.get_run(run_id)
        if r['status']!='completed':raise HTTPException(409,'Only completed investigations can be reviewed.')
        r['human_review']=body.model_dump()|{'at':store.now()};store.save_run(r)
    return r['human_review']

def markdown(r):
    result=r.get('result',{});report=result.get('report',{})
    lines=[f"# CaseTrace — {r['case_title']}",f"Run: {r['id']} | {r['created_at']}",f"Mode: {r['mode']} | Status: {r['status']}",
           f"Human review: {r['human_review']['status']}",r['human_review'].get('note',''),'',report.get('summary',r.get('error','No report.'))]
    names={d['id']:d['name'] for d in r['documents']}
    for f in report.get('findings',[]):
        lines += ['',f"## {f['title']}",f"{f['kind']} · {f['severity']}",f['explanation'],f"Next check: {f['next_step']}"]
        for c in f['citations']:lines.append(f"- {names.get(c['document_id'],c['document_id'])}, p. {c['page']}: {c['quote']}")
    lines+=['','## Unanswered questions']+['- '+q for q in report.get('unanswered_questions',[])]+['',result.get('verification',''),'Decision support only; this report does not determine fraud or insurance coverage.']
    return '\n\n'.join(lines)

@app.get('/api/runs/{run_id}/export/{format}')
def export(run_id:str,format:str):
    r=store.get_run(run_id);headers={'Content-Disposition':f'attachment; filename="casetrace-{run_id[:8]}.{format}"'}
    if format=='json':return Response(json.dumps(r,indent=2),media_type='application/json',headers=headers)
    if format=='md':return Response(markdown(r),media_type='text/markdown',headers=headers)
    if format=='pdf':
        stream=io.BytesIO();styles=getSampleStyleSheet();story=[]
        for line in markdown(r).split('\n\n'):
            style='Title' if line.startswith('# ') else 'Heading2' if line.startswith('## ') else 'BodyText'
            story += [Paragraph(escape(line.lstrip('# ')),styles[style]),Spacer(1,8)]
        SimpleDocTemplate(stream,title='CaseTrace evidence report',author='CaseTrace').build(story)
        return Response(stream.getvalue(),media_type='application/pdf',headers=headers)
    raise HTTPException(404,'Supported formats: json, md, pdf.')

@app.get('/api/evaluation')
def evaluation():
    p=ROOT/'artifacts'/'evaluation.json'
    return json.loads(p.read_text('utf-8')) if p.exists() else {'status':'not_run','message':'No measured evaluation has been saved yet.'}

app.mount('/',StaticFiles(directory=ROOT/'static',html=True),name='interface')

import json
from pathlib import Path
import pytest
from casetrace.documents import parse_document, validate_citations, MAX_FILE_BYTES
from casetrace.tools import calculate, offline_report
from casetrace.retrieval import Index
from casetrace.workflow import run_workflow
from casetrace.provider import ProviderError, decode_json

ROOT=Path(__file__).resolve().parents[1]

def dossier(key='02_conflicting'):
    directory=ROOT/'demo_cases'/key
    return {'documents':[parse_document(p.name,p.read_bytes()) for p in sorted(directory.glob('*.pdf'))]}

def test_pdf_extraction_preserves_source():
    d=dossier()['documents'][0]
    assert d['pages'][0]['number']==1
    assert 'Incident date: 2026-03-12' in d['pages'][0]['text']
    assert len(d['sha256'])==64

@pytest.mark.parametrize('name,data',[('x.exe',b'a'*30),('x.pdf',b'not a pdf'),('x.txt',b'a'*(MAX_FILE_BYTES+1)),('x.txt',b'\x00'*40),('x.txt',b'short')],ids=['extension','corrupt-pdf','oversize','binary','empty'])
def test_reject_invalid_input(name,data):
    with pytest.raises(ValueError):parse_document(name,data)

def test_quotes_and_unknown_sources():
    case=dossier();report=offline_report(case['documents'])
    assert all(c['valid'] for c in validate_citations(report,case['documents']))
    report['findings'][0]['citations'][0]['quote']='This sentence was never written.'
    assert not validate_citations(report,case['documents'])[0]['valid']
    report['findings'][0]['citations'][0]['document_id']='other-case-document'
    assert not validate_citations(report,case['documents'])[0]['valid']

@pytest.mark.parametrize('key',['01_consistent','02_conflicting','03_incomplete'])
def test_template_findings_match_declared_labels(key):
    case=dossier(key)
    expected=json.loads((ROOT/'demo_cases'/key/'expected.json').read_text())
    report=offline_report(case['documents'])
    assert sorted(f['kind'] for f in report['findings'])==sorted(expected['expected_kinds'])

def test_retrieval_is_case_scoped():
    case=dossier('03_incomplete');index=Index(case['documents'])
    hits=index.search('inspection date observation',k=2)
    assert hits[0]['name']=='02_incident_report.pdf'
    assert all(h['document_id'] in {d['id'] for d in case['documents']} for h in hits)

def test_decimal_and_restricted_tools():
    assert calculate('add','0.1','0.2')['result']=='0.3'
    assert calculate('days_between','2026-03-12','2026-03-14')['result']==2
    with pytest.raises(ValueError):calculate('eval','1','2')
    with pytest.raises(ValueError):calculate('add','NaN','2')

class FakeProvider:
    def __init__(self,answers):self.answers=iter(answers);self.usage={'calls':0}
    def ask(self,*args,**kwargs):self.usage['calls']+=1;return next(self.answers)

def test_actual_graph_revision_and_independent_review():
    case=dossier();report=offline_report(case['documents']);n=len(report['findings'])
    def review(verdict):return {'summary':'Evidence assessed independently.','assessments':[{'index':i,'verdict':verdict,'reason':'Check the underlying cited evidence.'} for i in range(n)]}
    fake=FakeProvider([{'action':'calculate','args':{'operation':'subtract','a':'1250','b':'1050'}},
      {'action':'finish','report':report},review('revise'),report,review('supported')])
    events=[];out=run_workflow(case,'Check dates and invoice totals','agents',lambda *x:events.append(x),provider=fake)
    assert out['rounds']==1 and out['usage']['calls']==5
    assert sum(e[1]=='review' for e in events)==2
    assert all(c['valid'] for c in out['citation_checks'])

def test_disallowed_agent_tool_is_never_executed():
    fake=FakeProvider([{'action':'shell','args':{'command':'anything'}}])
    with pytest.raises(ProviderError,match='unsupported action'):
        run_workflow(dossier(),'Check these documents','agents',lambda *x:None,provider=fake)

def test_cancellation_before_model_call():
    with pytest.raises(ProviderError,match='cancelled'):
        run_workflow(dossier(),'Check these documents','agents',lambda *x:None,cancelled=lambda:True)

def test_json_fence():assert decode_json('```json\n{"a":1}\n```')=={'a':1}

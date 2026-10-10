import time
import pytest
from fastapi.testclient import TestClient
from casetrace.app import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('CASETRACE_DATA_DIR',str(tmp_path))
    with TestClient(app) as c:yield c

def test_full_offline_lifecycle_and_exports(client):
    response=client.post('/api/demo');assert response.status_code==200
    cases=response.json();assert len(cases)==3
    assert len(client.post('/api/demo').json())==3
    case=next(c for c in cases if c['demo_key']=='02_conflicting')
    request={'objective':'Check incident dates and invoice arithmetic','mode':'offline'}
    r=client.post(f"/api/cases/{case['id']}/runs",json=request)
    assert r.status_code==202
    run_id=r.json()['id']
    for _ in range(100):
        run=client.get('/api/runs/'+run_id).json()
        if run['status'] not in ('queued','running'):break
        time.sleep(.02)
    assert run['status']=='completed'
    assert len(run['result']['report']['findings'])==3
    assert client.put('/api/runs/'+run_id+'/review',json={'status':'needs_followup','note':'Request corrected invoice.'}).status_code==200
    for fmt in ('json','md','pdf'):
        export=client.get('/api/runs/'+run_id+'/export/'+fmt)
        assert export.status_code==200 and len(export.content)>100
        if fmt=='pdf':assert export.content.startswith(b'%PDF')

def test_upload_and_consent(client):
    response=client.post('/api/cases',data={'title':'Uploaded dossier'},files=[('files',('note.txt',b'Incident date: 2026-05-01\nDocument type: claim declaration'))])
    assert response.status_code==201
    c=response.json();doc=c['documents'][0]
    assert client.get(f"/api/cases/{c['id']}/documents/{doc['id']}/file").status_code==200
    assert client.post(f"/api/cases/{c['id']}/runs",json={'objective':'Check dates and evidence','mode':'agents'}).status_code==400

def test_sanitized_config_and_origin_protection(client):
    cfg=client.get('/api/config').json()
    assert 'key' not in cfg and 'base_url' not in cfg
    assert client.post('/api/demo',headers={'origin':'https://external.example'}).status_code==403
    assert client.get('/api/config',headers={'host':'evil.example'}).status_code==403
    assert client.get('/api/cases/nonexistent').status_code==404

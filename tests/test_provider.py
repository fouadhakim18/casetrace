import httpx
import pytest
from casetrace.provider import Provider,ProviderError,serving_schema
from casetrace.models import Report

def test_serving_schema_preserves_named_fields_and_enums():
    schema=serving_schema(Report.model_json_schema())
    assert 'title' in schema['$defs']['Finding']['properties']
    assert 'contradiction' in schema['$defs']['Finding']['properties']['kind']['enum']
    assert 'minLength' not in schema['$defs']['Finding']['properties']['title']

def test_quota_failure_does_not_retry(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    calls=[]
    def fake(*args,**kwargs):calls.append(1);return httpx.Response(429,json={'error':'quota'})
    monkeypatch.setattr(httpx,'post',fake)
    with pytest.raises(ProviderError,match='429'):Provider(lambda *x:None).ask('test','system','user')
    assert len(calls)==1

def test_native_schema_and_token_accounting(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    def fake(*args,**kwargs):
        assert kwargs['json']['response_format']['type']=='json_schema'
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"summary":"A valid report summary.","findings":[],"unanswered_questions":[]}'}}],
                    'usage':{'prompt_tokens':12,'completion_tokens':8,'total_tokens':20}})
    monkeypatch.setattr(httpx,'post',fake);p=Provider(lambda *x:None)
    assert p.ask('test','system','user',Report.model_json_schema())['findings']==[]
    assert p.usage['calls']==1 and p.usage['total_tokens']==20

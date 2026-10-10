import json
import time
import httpx
from .config import settings

class ProviderError(RuntimeError): pass

def decode_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n',1)[1].rsplit('```',1)[0].strip()
    return json.loads(text)

def serving_schema(value):
    """Keep types, enums and structure; enforce length bounds locally with Pydantic.

    Deep nested length bounds exceed Gemini's constrained-decoding state budget.
    """
    if isinstance(value,list):return [serving_schema(v) for v in value]
    if isinstance(value,dict):
        return {k:serving_schema(v) for k,v in value.items() if k not in
                ('default','minLength','maxLength','minItems','maxItems','minimum','maximum')}
    return value

class Provider:
    def __init__(self, emit, cancelled=lambda:False):
        self.cfg = settings()
        self.emit = emit
        self.cancelled = cancelled
        self.usage = {'calls':0,'input_tokens':0,'output_tokens':0,'total_tokens':0,'latency_seconds':0}

    def ask(self, role, system, user, schema=None):
        if self.cancelled(): raise ProviderError('Investigation cancelled.')
        if self.usage['calls'] >= self.cfg['max_calls']: raise ProviderError('Configured model-call budget reached.')
        if self.cfg['provider']=='gemini' and not self.cfg['key']: raise ProviderError('GEMINI_API_KEY is missing. Configure .env and restart.')
        self.usage['calls'] += 1
        self.emit(role,'model_call',f"Model request {self.usage['calls']}/{self.cfg['max_calls']}",{'model':self.cfg['model']})
        payload = {'model':self.cfg['model'],'messages':[{'role':'system','content':system},{'role':'user','content':user}],
                   'temperature':0,'max_tokens':self.cfg['max_output_tokens'],'response_format':{'type':'json_object'}}
        if schema:
            payload['response_format']={'type':'json_schema','json_schema':{'name':'casetrace_output','strict':True,'schema':serving_schema(schema)}}
        if self.cfg['provider']=='gemini': payload['reasoning_effort'] = 'none' if '2.5-flash' in self.cfg['model'] else 'low'
        headers = {'Authorization':'Bearer '+(self.cfg['key'] or 'ollama')}
        start = time.perf_counter()
        try:
            response = httpx.post(self.cfg['base_url']+'/chat/completions',headers=headers,json=payload,timeout=90,follow_redirects=False)
        except httpx.HTTPError:
            raise ProviderError('Provider connection timed out or failed. No fallback or additional charge was attempted.') from None
        if response.status_code==429: raise ProviderError('Provider quota/rate limit reached (HTTP 429). Wait or check your free quota. Billing was not changed.')
        if response.status_code!=200: raise ProviderError(f'Provider returned HTTP {response.status_code}. Check model access and local configuration.')
        result = response.json(); usage = result.get('usage',{})
        self.usage['latency_seconds'] += round(time.perf_counter()-start,3)
        self.usage['input_tokens'] += usage.get('prompt_tokens',0)
        self.usage['output_tokens'] += usage.get('completion_tokens',0)
        self.usage['total_tokens'] += usage.get('total_tokens',0)
        self.emit(role,'usage','Provider usage recorded',dict(self.usage))
        if self.cancelled(): raise ProviderError('Investigation cancelled.')
        try:
            answer=decode_json(result['choices'][0]['message']['content'])
            self.emit(role,'model_response','Structured model output',{'response':answer})
            return answer
        except (KeyError,IndexError,TypeError,ValueError): raise ProviderError('Model response was not valid JSON. The trace is preserved; no invented result was substituted.') from None

from datetime import date
from decimal import Decimal, InvalidOperation
from .models import Report

def calculate(operation, a, b):
    try:
        if operation=='days_between': return {'result':(date.fromisoformat(b)-date.fromisoformat(a)).days,'unit':'days'}
        x,y = Decimal(str(a)),Decimal(str(b))
        if not x.is_finite() or not y.is_finite(): raise ValueError('Finite numbers required')
        if operation=='add': value=x+y
        elif operation=='subtract': value=x-y
        elif operation=='multiply': value=x*y
        else: raise ValueError('Unsupported operation')
        return {'result':str(value)}
    except (InvalidOperation,TypeError,OverflowError): raise ValueError('Invalid numeric input') from None

def read_page(documents, document_id, page):
    for d in documents:
        if d['id']==document_id:
            for p in d['pages']:
                if p['number']==page: return {'document_id':d['id'],'name':d['name'],'page':page,'text':p['text'][:12000]}
    raise ValueError('Unknown document/page')

def offline_report(documents):
    """Explicit template-field checks, not an LLM and not general document understanding."""
    fields={}
    for d in documents:
        for p in d['pages']:
            for line in p['text'].splitlines():
                if ':' in line:
                    key,value=line.split(':',1)
                    fields.setdefault(key.strip().lower(),[]).append((value.strip(),{'document_id':d['id'],'page':p['number'],'quote':line.strip()}))
    findings=[]
    def finding(title,kind,explanation,items,severity='medium'):
        findings.append({'title':title,'kind':kind,'severity':severity,'explanation':explanation,
                         'citations':[v[1] for v in items],'next_step':'Ask the document owner to confirm the discrepancy and provide supporting evidence.'})
    incidents=fields.get('incident date',[])
    if len({v[0] for v in incidents})>1:
        finding('Conflicting incident dates','contradiction','The documents state different incident dates. This does not establish fraud.',incidents)
    for amount,total in zip(fields.get('invoice total eur',[]),fields.get('line items total eur',[])):
        try:
            if Decimal(amount[0])!=Decimal(total[0]):
                finding('Invoice total does not match line items','arithmetic',f'The stated invoice total and item total differ by {abs(Decimal(amount[0])-Decimal(total[0]))} EUR.',[amount,total])
        except InvalidOperation: pass
    invoices=fields.get('invoice number',[])
    for number in sorted({i[0] for i in invoices}):
        matches=[i for i in invoices if i[0]==number]
        if len(matches)>1: finding('Repeated invoice reference','duplicate','The same invoice reference appears more than once. Copies or resubmissions may explain this.',matches[:6],'info')
    unanswered=[]
    for value,cite in fields.get('required evidence',[]):
        if value.lower() not in [x[0].lower() for x in fields.get('document type',[])]:
            findings.append({'title':'Required evidence not supplied','kind':'missing_information','severity':'info',
                'explanation':f'The supplied document inventory does not include a document labelled {value}.','citations':[cite],
                'next_step':f'Request the {value} from the case owner.'})
            unanswered.append(f'Can the case owner supply the {value}?')
    return Report.model_validate({'summary':f'Offline structured-field checks completed: {len(findings)} potential issues. This mode does not answer arbitrary questions or use LLM agents. No issue found is not proof that a case is correct.',
        'findings':findings,'unanswered_questions':unanswered}).model_dump()

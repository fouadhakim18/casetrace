"""Generate reproducible, wholly synthetic PDF dossiers and hand-authored labels."""
import json
import sys
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
ROOT=Path(__file__).resolve().parents[1]

CASES={
 '01_consistent':{'title':'Harbor workshop · consistent records','expected_kinds':[], 'docs':{
  '01_declaration.pdf':['Document type: claim declaration','Claim reference: SYN-HARBOR-001','Incident date: 2026-03-12','Incident: water leak at a fictional workshop.','Required evidence: repair estimate'],
  '02_incident_report.pdf':['Document type: incident report','Claim reference: SYN-HARBOR-001','Incident date: 2026-03-12','Observation: a pipe connection leaked.','Inspection date: 2026-03-13'],
  '03_repair_estimate.pdf':['Document type: repair estimate','Invoice number: SYN-INV-001','Labour EUR: 450.00','Materials EUR: 600.00','Line items total EUR: 1050.00','Invoice total EUR: 1050.00','Tax: not applicable in this synthetic example.']}},
 '02_conflicting':{'title':'Riverside studio · conflicting records','expected_kinds':['contradiction','arithmetic','duplicate'],'docs':{
  '01_declaration.pdf':['Document type: claim declaration','Claim reference: SYN-RIVER-002','Incident date: 2026-03-12','Incident: water leak at a fictional studio.','Required evidence: repair estimate'],
  '02_incident_report.pdf':['Document type: incident report','Claim reference: SYN-RIVER-002','Incident date: 2026-03-14','Observation: ceiling water damage.','Inspection date: 2026-03-15'],
  '03_repair_estimate.pdf':['Document type: repair estimate','Invoice number: SYN-INV-002','Labour EUR: 450.00','Materials EUR: 600.00','Line items total EUR: 1050.00','Invoice total EUR: 1250.00','Tax: not applicable; no additional fees are listed.'],
  '04_invoice_copy.pdf':['Document type: invoice copy','Invoice number: SYN-INV-002','Copy label: resubmitted attachment, not a second payment request.','A repeated reference alone does not establish double billing.']}},
 '03_incomplete':{'title':'Hillcrest office · missing evidence','expected_kinds':['missing_information'],'docs':{
  '01_declaration.pdf':['Document type: claim declaration','Claim reference: SYN-HILL-003','Incident date: 2026-04-02','Incident: damaged door at a fictional office.','Required evidence: repair estimate'],
  '02_incident_report.pdf':['Document type: incident report','Claim reference: SYN-HILL-003','Incident date: 2026-04-02','Observation: the door frame is damaged.','Inspection date: 2026-04-03']}}
}

def generate():
 for key,case in CASES.items():
    directory=ROOT/'demo_cases'/key;directory.mkdir(parents=True,exist_ok=True)
    for filename,lines in case['docs'].items():
        c=canvas.Canvas(str(directory/filename),pagesize=(595,842),invariant=1)
        c.setTitle('Synthetic CaseTrace document');c.setAuthor('MAROC Abdelhakim Fouad')
        c.setFillColor(HexColor('#123C49'));c.setFont('Helvetica-Bold',22);c.drawString(48,775,'CaseTrace / synthetic dossier')
        c.setFont('Helvetica',10);c.drawString(48,748,'FICTIONAL DATA - FOR SOFTWARE DEMONSTRATION ONLY')
        c.setStrokeColor(HexColor('#11A68B'));c.line(48,725,547,725)
        c.setFillColor(HexColor('#1C2935'));c.setFont('Helvetica',11)
        for n,line in enumerate(lines):c.drawString(48,685-n*30,line)
        c.setFont('Helvetica',9);c.drawString(48,45,'No real person, insurer, customer, incident or financial transaction. / Page 1')
        c.showPage();c.save()
    meta={k:v for k,v in case.items() if k!='docs'}
    meta['retrieval_queries']=[{'query':'claim declaration incident date','expected_file':'01_declaration.pdf'},
       {'query':'inspection date observation incident report','expected_file':'02_incident_report.pdf'}]
    if '03_repair_estimate.pdf' in case['docs']:meta['retrieval_queries'].append({'query':'labour materials invoice total','expected_file':'03_repair_estimate.pdf'})
    (directory/'expected.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 print('Generated 9 synthetic PDFs across 3 cases.')

if __name__=='__main__':generate()

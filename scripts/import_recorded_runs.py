"""Import exact saved demo runs into the local workspace, labelled as recorded."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from casetrace import store
from casetrace.config import data_dir

def load():
    bundle=json.loads((ROOT/'artifacts/replay-data.json').read_text('utf-8'))
    for c in bundle['cases']:
        store.save_case(c)
        directory=data_dir()/'files'/c['id'];directory.mkdir(parents=True,exist_ok=True)
        for d in c['documents']:(directory/d['id']).write_bytes((ROOT/'demo_cases'/c['demo_key']/d['name']).read_bytes())
    for r in bundle['runs']:
        r['events'].insert(0,{'at':r['created_at'],'role':'system','kind':'recorded','message':'Imported saved evaluation run, not a new live execution.','data':{}})
        store.save_run(r)
    print('Imported recorded synthetic runs. All source data is fictional.')

if __name__=='__main__':load()

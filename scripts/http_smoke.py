"""Exercise real HTTP in one process; useful in isolated execution environments."""
import json
import sys
import threading
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from casetrace.app import app
import httpx
import uvicorn

server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8978,log_level='warning'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
for _ in range(100):
    if server.started:break
    time.sleep(.05)
results={}
try:
    with httpx.Client(base_url='http://127.0.0.1:8978',timeout=10,trust_env=False) as client:
        for path in ('/','/app.js','/style.css','/api/config','/api/cases','/api/evaluation','/openapi.json'):
            response=client.get(path);results[path]=response.status_code
            assert response.status_code==200,path
finally:
    server.should_exit=True;thread.join(timeout=5)
(ROOT/'artifacts/http-smoke.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results))

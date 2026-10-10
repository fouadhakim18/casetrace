"""Create a source release using an allowlist. Credentials and user data are excluded."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]

def package():
    dirs=['casetrace','static','demo_cases','scripts','tests','artifacts','docs','.github']
    roots=['README.md','LICENSE','requirements.txt','requirements-lock.txt','.env.example','.gitignore','.dockerignore','Dockerfile','compose.yaml','run.py','start.cmd','CaseTrace_Demo.html']
    paths=[ROOT/n for n in roots if (ROOT/n).is_file()]
    for d in dirs:
        paths.extend(p for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log') and 'private' not in p.parts)
    # Scan actual local key values in memory, never print them.
    from dotenv import dotenv_values
    secrets=[v for k,v in dotenv_values(ROOT/'.env').items() if v and ('KEY' in k or 'TOKEN' in k) and len(v)>12]
    for p in paths:
        data=p.read_bytes()
        if any(s.encode() in data for s in secrets):raise RuntimeError('A secret was detected in a release file; packaging stopped.')
        if p.name=='.env' or '.venv' in p.parts or 'data' in p.relative_to(ROOT).parts:raise RuntimeError('Excluded path selected.')
    target=ROOT.parent/'CaseTrace_Portfolio.zip'
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for p in sorted(paths):z.write(p,'casetrace/'+p.relative_to(ROOT).as_posix())
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (ROOT.parent/'CaseTrace_Portfolio.sha256').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(target),'files':len(paths),'bytes':target.stat().st_size,'secret_scan':'passed'}))

if __name__=='__main__':package()

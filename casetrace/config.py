import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)

def settings():
    provider = os.getenv('CASETRACE_PROVIDER', 'gemini')
    return {
        'provider': provider,
        'model': os.getenv('CASETRACE_MODEL', 'gemini-2.5-flash'),
        'base_url': ('https://generativelanguage.googleapis.com/v1beta/openai' if provider == 'gemini'
                     else os.getenv('CASETRACE_BASE_URL', 'http://127.0.0.1:11434/v1').rstrip('/')),
        'key': os.getenv('GEMINI_API_KEY' if provider == 'gemini' else 'CASETRACE_API_KEY', ''),
        'embeddings': os.getenv('CASETRACE_EMBEDDINGS', 'local'),
        'max_calls': min(12, max(2, int(os.getenv('CASETRACE_MAX_CALLS', '8')))),
        'max_output_tokens': min(6000, max(500, int(os.getenv('CASETRACE_MAX_OUTPUT_TOKENS', '3500')))),
    }

def data_dir():
    p = Path(os.getenv('CASETRACE_DATA_DIR', str(ROOT / 'data')))
    if not p.is_absolute(): p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p

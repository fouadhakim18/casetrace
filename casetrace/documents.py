import hashlib
import io
import re
from pathlib import Path
from pypdf import PdfReader
from .store import uid

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_CHARS = 200_000

def parse_document(filename, data):
    name = Path(filename.replace('\\', '/')).name[:160]
    suffix = Path(name).suffix.lower()
    if len(data) > MAX_FILE_BYTES: raise ValueError('Each file must be 5 MB or less.')
    if suffix == '.pdf':
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted: raise ValueError('Encrypted PDFs are not supported.')
            if len(reader.pages) > 40: raise ValueError('Maximum 40 pages per document.')
            pages = [{'number': i+1, 'text': page.extract_text() or ''} for i, page in enumerate(reader.pages)]
        except ValueError: raise
        except Exception: raise ValueError('Cannot read this PDF. Try a text-based PDF or a UTF-8 text file.') from None
    elif suffix in ('.txt', '.md', '.csv', '.eml'):
        try: text = data.decode('utf-8-sig')
        except UnicodeDecodeError: raise ValueError('Text files must be UTF-8.') from None
        if '\x00' in text: raise ValueError('Binary content is not supported.')
        pages = [{'number': 1, 'text': text}]
    else: raise ValueError('Supported formats: PDF, TXT, MD, CSV, EML.')
    total = sum(len(p['text']) for p in pages)
    if total < 20: raise ValueError('No usable text found. Scanned PDFs need OCR, which is outside this version.')
    if total > MAX_TOTAL_CHARS: raise ValueError('Extracted document text exceeds the 200,000-character limit.')
    return {'id': uid(), 'name': name, 'sha256': hashlib.sha256(data).hexdigest(), 'pages': pages,
            'characters': total, 'warnings': ['Some pages have no extractable text.'] if any(len(p['text'].strip())<10 for p in pages) else []}

def normalise(text): return re.sub(r'\s+', ' ', text).strip().casefold()

def validate_citations(report, documents):
    lookup = {d['id']: d for d in documents}
    checks = []
    for i, finding in enumerate(report['findings']):
        errors = []
        if not finding['citations'] and finding['kind'] != 'missing_information':
            errors.append('This claim has no source citation.')
        for cite in finding['citations']:
            doc = lookup.get(cite['document_id'])
            page = next((p for p in doc['pages'] if p['number']==cite['page']), None) if doc else None
            if not page: errors.append('Unknown document or page.')
            elif normalise(cite['quote']) not in normalise(page['text']): errors.append('Quoted text is not present on the cited page.')
        checks.append({'index': i, 'valid': not errors, 'errors': errors})
    return checks

"""FAISS retrieval. Local vectors are lexical, explicitly NOT neural embeddings."""
import hashlib
import math
import re
import numpy as np
import faiss
import httpx
from .config import settings

def tokens(text): return re.findall(r'[\w]+', text.casefold())

class Index:
    def __init__(self, documents, semantic=False):
        self.chunks = []
        for doc in documents:
            for page in doc['pages']:
                text = page['text']
                for start in range(0, len(text), 850):
                    chunk = text[start:start+1100]
                    if chunk.strip(): self.chunks.append({'document_id': doc['id'], 'name': doc['name'], 'page': page['number'], 'text': chunk})
        if not self.chunks: raise ValueError('No document text to index.')
        self.semantic = semantic
        self.vocab = {}
        n = len(self.chunks)
        for c in self.chunks:
            for t in set(tokens(c['text'])): self.vocab[t] = self.vocab.get(t, 0)+1
        self.idf = {t: math.log((1+n)/(1+df))+1 for t,df in self.vocab.items()}
        matrix = self.embed([c['text'] for c in self.chunks], query=False)
        self.index = faiss.IndexFlatIP(matrix.shape[1]); self.index.add(matrix)

    def embed(self, texts, query):
        if self.semantic:
            cfg = settings()
            key = cfg['key']
            if cfg['provider'] != 'gemini' or not key: raise ValueError('Gemini semantic embeddings need the Gemini provider and key.')
            vectors = []
            for offset in range(0, len(texts), 40):
                requests = [{'model':'models/gemini-embedding-001', 'content':{'parts':[{'text':t}]},
                             'taskType':'RETRIEVAL_QUERY' if query else 'RETRIEVAL_DOCUMENT', 'outputDimensionality':768}
                            for t in texts[offset:offset+40]]
                try:
                    response = httpx.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents',
                        headers={'x-goog-api-key':key}, json={'requests':requests}, timeout=60)
                except httpx.HTTPError: raise RuntimeError('Embedding provider connection failed.') from None
                if response.status_code != 200: raise RuntimeError(f'Embedding provider returned HTTP {response.status_code}. No automatic provider switch.')
                vectors.extend(e['values'] for e in response.json()['embeddings'])
            matrix = np.asarray(vectors,dtype='float32')
        else:
            matrix = np.zeros((len(texts), 2048),dtype='float32')
            for i,text in enumerate(texts):
                for term in tokens(text):
                    j = int.from_bytes(hashlib.blake2b(term.encode(),digest_size=4).digest(),'little') % 2048
                    matrix[i,j] += self.idf.get(term,1)
        faiss.normalize_L2(matrix)
        return matrix

    def search(self, query, k=5):
        vec = self.embed([query],query=True)
        scores, ids = self.index.search(vec, min(k,len(self.chunks)))
        return [dict(self.chunks[int(i)],score=round(float(score),4)) for i,score in zip(ids[0],scores[0]) if i>=0]

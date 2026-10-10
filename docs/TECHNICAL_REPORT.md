# CaseTrace — Technical report

**MAROC Abdelhakim Fouad · October 2026**

## 1. Question and scope

Can a bounded investigator–verifier workflow make a small document-consistency investigation inspectable, and what extra cost does verification add compared with a single RAG answer?

The contribution is an integrated software prototype and an explicit comparison protocol. Insurance-style dossiers provide a concrete application where provenance, arithmetic and human review matter. All supplied dossiers are fictional.

The expected user is an analyst who needs to ask for clarifications rather than make an automatic decision. The system flags differing dates, mismatched amounts, repeated references and missing explicitly required evidence. A repeated reference may be a benign copy; disagreement is not proof of deception.

## 2. Data model and provenance

A case owns an immutable list of uploaded documents. Each document has a random internal identifier, safe display filename, SHA-256 digest, extracted pages, character count and extraction warnings. Original bytes are stored under generated identifiers. Pages retain their PDF page number.

A run records case identity, objective, mode, timestamps, provider/model configuration without credentials, document hashes, events, final structured output, failure status and human review. JSON export includes these details. The generated PDF is a presentation of the final report; JSON is the richer audit record.

SQLite stores case and run JSON records, using parameterized statements and WAL. One background worker executes investigations. A lock protects application scheduling and updates; the worker cap prevents simultaneous runs from multiplying local API consumption. This is not a distributed queue. Process restart marks unfinished jobs as interrupted rather than pretending they completed.

## 3. Extraction and retrieval

`pypdf` extracts text from text-based PDFs. UTF-8 TXT, Markdown, CSV and email text are accepted as single-page text documents. Encrypted, oversized and effectively empty documents are rejected. OCR, image interpretation and complex table layout recovery are outside this version.

Pages are split into 1,100-character chunks with a stride of 850 characters, giving up to 250 characters of overlap. Chunks never cross a page boundary. Character boundaries can split a word or table; this is a simplicity/quality tradeoff. Page attribution is retained for retrieval and citations.

The default representation tokenizes Unicode words, computes per-case inverse document frequency, accumulates weighted term counts into 2,048 deterministic hash buckets, then L2-normalizes the vectors. FAISS `IndexFlatIP` performs exact inner-product search. The representation is lexical: synonyms and paraphrases can be missed, and hash collisions occur. FAISS alone does not make this semantic RAG.

An optional Gemini embedding path uses 768-dimensional `gemini-embedding-001` vectors with retrieval-specific document/query task types. It sends text externally and adds quota consumption. Indexes are rebuilt per investigation; there is no durable embedding cache in this version.

## 4. Agents and bounded control flow

The graph starts with six retrieved chunks. The investigator receives the objective, document inventory and evidence. It can choose one JSON action at a time:

1. `search`: retrieve four chunks for a new query.
2. `read_page`: fetch an identified page, bounded to 12,000 characters.
3. `calculate`: Decimal addition, subtraction, multiplication or ISO-date difference.
4. `finish`: submit a structured report.

The server validates the allowlist and executes the action. It never evaluates generated code. At most three tool actions are permitted, after which a report is requested directly. If a final investigator report violates its schema, one constrained schema-repair call is allowed. The global model-call limit remains effective, so a low configured limit may terminate a run before final verification.

The verifier is a separate model call with a different role prompt. It receives the draft, original pages fetched from cited document identifiers, initial retrieval evidence and deterministic quote checks. It assesses every finding exactly once using `supported`, `revise` or `unsupported`. This independence concerns evidence access and role instructions; the same model is used, so errors remain correlated.

When a finding fails verification or quote validation, one report revision and a second verifier pass are allowed. Remaining objections are preserved rather than concealed. Final reports are not automatically approved. Human review can accept the report, reject it or request follow-up with a saved note.

## 5. Structured outputs and reliability

Pydantic schemas define reports, finding categories, severity, citations and reviewer assessments. Gemini's JSON-schema output mode constrains report/reviewer structure. Serving schemas omit deep text/array length bounds that exceeded the provider's constrained-decoding state budget; Pydantic still enforces the complete bounds locally.

The investigator action-selection stage uses JSON-object mode and an explicit protocol. Both a valid direct report and a `finish` wrapper are accepted. Unknown actions fail closed. The recorded trace contains actions, tool results and structured answers, not requested private chain-of-thought.

HTTP failures, malformed JSON, schema failures and exhausted call budgets produce failed runs. HTTP 429 is recorded without a paid fallback or unbounded retries. Usage counters represent provider-reported chat tokens and attempted chat calls. Optional embedding requests are not included in those counters. Failed runs can retain usage events even when no final aggregate result exists.

## 6. Citation checks and their meaning

For each citation, the checker looks up the document and page, collapses whitespace, case-folds both strings and tests whether the quotation occurs in the page text. Unknown documents, unknown pages and fabricated quotations are rejected. Non-missing-information findings require at least one citation.

This establishes source-string presence only. It does not establish entity matching, causal explanation, completeness, legal meaning, date relevance or correct arithmetic. An uncited missing-information finding may pass the structural allowance; it is not thereby source-verified. The UI presents verifier comments and source passages so a person can inspect the interpretation.

## 7. Experimental protocol

Three hand-authored cases contain nine one-page PDFs:

| Case | Documents | Intended issue categories |
|---|---:|---|
| Harbor workshop | 3 | None; dates and totals agree |
| Riverside studio | 4 | Incident-date contradiction, EUR 200 arithmetic mismatch, benign repeated invoice reference |
| Hillcrest office | 2 | Explicitly requested repair estimate absent |

The expected labels sit in separate JSON files and are not included in the evidence supplied to the model. Eight lexical retrieval questions identify an expected source filename. Recall@3 records whether that file appears among the top three chunks.

Three methods are exercised: deterministic template checks, one-pass RAG, and investigator–verifier workflow. The deterministic mode is not an AI baseline for arbitrary documents; its rules mirror explicit fixture fields. It provides an executable fallback and tests the document/report plumbing.

The live comparison uses the same model, initial retrieval and task wording. It records categories, quote-check outcomes, calls, token totals and latency. Category scoring compares sets per case, excludes `supported` findings, and counts matching, extra and missed categories. It does not score every semantic claim. A benign duplicate can reasonably be described as a supported clarification, so category scoring can penalize a sensible alternative presentation. Interpretation therefore requires reviewing the findings alongside the counters.

The dataset was also used to debug implementation and schema handling. One attempt per case/mode is retained in the current result table, with available older development attempts separately recorded. This is not a held-out evaluation, not repeated-trial inference and not a statistically supported performance claim. No confidence interval is meaningful from these three constructed dossiers.

## 8. Results

The companion [RESULTS.md](RESULTS.md) is generated from the saved artifact, including failed attempts. The raw evidence is in `artifacts/evaluation.json`, and test output is in `artifacts/tests.xml`.

A successful live investigator run demonstrated selection of the calculator followed by a report and a verifier assessment. This establishes that the workflow executes real model-driven actions. It does not establish that this workflow detects more issues than a single-pass model. The baseline can cover the same simple categories at lower token cost. The measured comparison therefore supports an auditability/resource trade-off rather than an accuracy gain.

## 9. Validation boundaries and next experiments

Automated tests cover PDF extraction, rejected input, exact quotations, cross-case source references, lexical retrieval, numeric tools, graph revision, unsupported actions, cancellation, quota handling, API consent, upload, exports and human review. Model calls are mocked in these tests; actual live experiments are separate.

Potential follow-up work: add held-out dossiers with paraphrases and longer evidence chains; include ambiguous chronology and legitimate fees; compare lexical and semantic retrieval under a fixed call budget; have independent reviewers annotate individual claims; measure whether verifier objections improve precision after revision; repeat runs and report uncertainty; test prompt-injection documents explicitly; add OCR and robust table extraction where justified.

Before any real deployment, authentication, access control, protected storage, retention rules, durable queues, upload hardening and appropriate data-handling arrangements would be necessary. These controls are outside the current local prototype.

## 10. Reproducibility

Synthetic PDFs are regenerated with ReportLab's invariant output setting. Document hashes are logged. Temperature is zero, but remotely served model behavior is not guaranteed to be byte-identical or stable over time. Exact installed package versions are captured separately from broad installation ranges.

Model outputs in the artifacts are recorded executions. Validation covers the environments and scenarios listed in the saved verification record.

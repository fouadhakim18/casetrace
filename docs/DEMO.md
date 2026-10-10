# Demonstration guide

## Recorded demonstration

Open `CaseTrace_Demo.html` in a browser. The self-contained page includes saved Gemini runs, source documents, findings, traces and report downloads. It requires no API key. Uploads, new investigations and saved human reviews require the live application.

The recorded view distinguishes the latest attempts from historical successful runs. Failed attempts remain visible. It does not execute model calls.

## Live workflow

1. Complete the installation in the [README](../README.md), start `python run.py` and open `http://127.0.0.1:8768`.
2. Load the synthetic cases and select **Riverside studio**. The declaration and incident report contain different incident dates.
3. Select **Two-agent investigation**, enable consent for model transmission and start the investigation. **Agent activity** records selected actions, tool inputs, results and verifier assessments.
4. Open **Findings** and select a quotation to inspect its source page. The case includes a EUR 200 estimate mismatch and an invoice copy explicitly labelled as a resubmission.
5. Save a human review and export the report as PDF or JSON.
6. Open **Evaluation** to compare recorded outcomes, model calls and token usage with the single-pass RAG baseline.

HTTP 429 indicates a provider quota or rate-limit failure. Recorded runs remain available without new calls. The **Offline template demo** uses deterministic checks and is separate from both live methods.

## Design rationale

| Component | Purpose and boundary |
|---|---|
| Investigator and verifier | Separate investigation and challenge stages; additional accuracy must be evaluated. |
| FAISS retrieval | Exact vector search over local lexical features; semantic embeddings are a separate optional path. |
| Bounded execution | Three investigator tool actions, at most one semantic revision and a global model-call cap. |
| Decimal tools | Explicit decimal arithmetic for amount comparisons. |
| Citation checks | Confirm quotation presence on the identified page, without establishing the correctness of an interpretation. |
| Failure records | Preserve errors and available traces instead of replacing unsuccessful runs with offline output. |
| Restricted tools | Limit actions to search, page reading and calculation; prompt-injection resistance remains unevaluated. |

The three synthetic dossiers were used during development. The evaluation documents execution behavior and resource use; it does not establish real-world accuracy or general agent superiority.

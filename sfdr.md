<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# yes do it

Yes — here’s a concrete architecture and execution plan for a GenAI-based SFDR Reporting application that you can actually build as an MVP in Python. The most defensible product is an **AI-assisted compliance workspace** that converts documents into field-level SFDR evidence, drafts template-ready disclosures, and enforces validation plus reviewer sign-off.

## Product scope

SFDR requires disclosures at firm and product level through websites, pre-contractual documents, and annual or periodic reports, while the RTS specifies the exact content, methodology, and presentation of those disclosures.  Product-level disclosures use mandatory annexed templates, and entity-level principal adverse impact disclosures belong on the website, which makes a structured workflow and schema-first product a better fit than an open chatbot.[^1]

For v1, I would scope the platform to three flows:

- Entity-level PAI statement drafting and review.
- Product-level pre-contractual disclosure drafting for Article 8/9 products.[^2]
- Product-level periodic report drafting using Annex-based templates.[^3]


## System architecture

Use a modular pipeline with deterministic checks around the LLM. SFDR disclosures are standardized and template-based, so the system should extract, normalize, validate, and only then generate text for bounded fields rather than freeform narratives.

### Core modules

1. **Document ingestion**

- Upload PDFs, Word files, CSVs, Excel, website snapshots, and policy documents.
- Parse source type, reporting period, issuer, language, product, and jurisdiction.
- Store original file plus page-level metadata for auditability.

2. **Document intelligence**

- OCR and layout parsing for scanned PDFs.
- Section detection: methodology, KPIs, emissions, exclusions, governance, taxonomy, PAI indicators.
- Table extraction because ESG/SFDR data often lives in tables rather than prose.

3. **Regulation knowledge layer**

- Internal registry of SFDR obligations:
    - Entity vs product.
    - Website vs pre-contractual vs periodic.
    - Article 6/8/9 classification.
    - RTS annex template and field definitions.[^1]

4. **Evidence retrieval**

- Retrieve passages, table cells, and calculated metrics relevant to each required field.
- Return source citation, page number, confidence, and extraction method.

5. **LLM drafting engine**

- Generate only structured JSON first.
- Convert approved JSON into disclosure text in template slots.
- Force abstention when evidence is weak or missing.

6. **Validation engine**

- Required-field completeness.
- Unit normalization.
- Cross-document consistency.
- Threshold checks.
- Mandatory disclaimer checks.
- Template conformance against expected annex structure.

7. **Reviewer workspace**

- Side-by-side view: source evidence, extracted value, drafted response, validation warnings.
- Approve, edit, reject, escalate.
- Full audit trail.

8. **Export layer**

- Export Word, PDF, Excel checklist, JSON API, and machine-readable compliance package.
- Long term: direct annex-template rendering.


## Recommended tech stack

Given your Python-first preference, this stack fits well:

- Backend: FastAPI.
- Async jobs: Celery or Dramatiq with Redis.
- DB: PostgreSQL.
- Object storage: S3 or MinIO.
- Search: PostgreSQL full-text + pgvector or Elasticsearch/OpenSearch.
- Parsing: PyMuPDF, pdfplumber, unstructured, pandas, python-docx, Tesseract or PaddleOCR.
- LLM orchestration: LangChain or LlamaIndex if you want speed of development, though a thinner custom orchestration layer may be better for compliance control.
- Frontend: Streamlit for internal prototype, then React later.
- Auth: Keycloak, Auth0, or simple JWT + role-based access for MVP.


### Suggested services

- `gateway-service`: auth, orgs, products, projects.
- `ingestion-service`: file upload, parsing, OCR.
- `retrieval-service`: chunking, indexing, search.
- `compliance-service`: SFDR schema registry, rules engine.
- `generation-service`: prompts, JSON extraction, draft generation.
- `review-service`: approvals, comments, audit logs.
- `export-service`: render output docs.


## Database schema

A normalized schema will save you later.

### Main tables

- `organizations`
- `users`
- `products`
- `reporting_projects`
- `documents`
- `document_pages`
- `document_chunks`
- `extracted_tables`
- `regulations`
- `regulation_fields`
- `field_requirements`
- `field_evidence`
- `field_answers`
- `validation_results`
- `review_actions`
- `exports`
- `audit_logs`


### Example tables

```sql
organizations(
  id uuid pk,
  name text,
  type text,
  created_at timestamp
)

products(
  id uuid pk,
  organization_id uuid fk,
  name text,
  sfdr_article text, -- 6 / 8 / 9
  strategy text,
  benchmark text,
  active boolean
)

reporting_projects(
  id uuid pk,
  organization_id uuid fk,
  product_id uuid fk null,
  disclosure_type text, -- entity_pai / precontractual / periodic / website
  reporting_period_start date,
  reporting_period_end date,
  status text,
  created_by uuid fk
)

documents(
  id uuid pk,
  project_id uuid fk,
  file_name text,
  file_type text,
  source_type text, -- annual_report / sustainability_report / factsheet / website_capture
  storage_url text,
  parsed_status text,
  uploaded_at timestamp
)

document_chunks(
  id uuid pk,
  document_id uuid fk,
  page_no int,
  section_title text,
  chunk_text text,
  embedding vector,
  metadata jsonb
)

regulation_fields(
  id uuid pk,
  framework text, -- SFDR
  disclosure_type text,
  annex_code text,
  field_code text,
  field_label text,
  field_kind text, -- narrative / numeric / boolean / table
  mandatory boolean,
  guidance jsonb
)

field_evidence(
  id uuid pk,
  project_id uuid fk,
  regulation_field_id uuid fk,
  document_chunk_id uuid fk null,
  source_locator jsonb,
  extracted_value jsonb,
  confidence numeric,
  extraction_method text,
  created_at timestamp
)

field_answers(
  id uuid pk,
  project_id uuid fk,
  regulation_field_id uuid fk,
  answer_json jsonb,
  answer_text text,
  status text, -- draft / approved / rejected / missing
  model_name text,
  generated_at timestamp,
  approved_by uuid fk null
)

validation_results(
  id uuid pk,
  project_id uuid fk,
  regulation_field_id uuid fk,
  rule_name text,
  severity text,
  passed boolean,
  details jsonb,
  created_at timestamp
)

audit_logs(
  id uuid pk,
  entity_type text,
  entity_id uuid,
  action text,
  actor_id uuid,
  payload jsonb,
  created_at timestamp
)
```


## API design

Design it as an API-first compliance platform.

### Project APIs

- `POST /projects`
- `GET /projects/{id}`
- `POST /projects/{id}/documents`
- `POST /projects/{id}/classify`
- `POST /projects/{id}/extract-evidence`
- `POST /projects/{id}/generate-drafts`
- `POST /projects/{id}/validate`
- `GET /projects/{id}/fields`
- `POST /projects/{id}/fields/{field_id}/approve`
- `POST /projects/{id}/fields/{field_id}/reject`
- `POST /projects/{id}/export`


### Retrieval APIs

- `GET /projects/{id}/evidence?field_code=...`
- `GET /documents/{id}/pages/{page_no}`
- `POST /search/chunks`


### Admin APIs

- `POST /regulations/import`
- `GET /regulations/fields`
- `POST /regulations/fields`
- `POST /rules/test`


## Folder structure

A clean monorepo in Python could look like this:

```text
sfdr-ai-reporting/
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── schemas/
│   │   ├── deps/
│   │   └── middleware/
│   ├── worker/
│   │   ├── tasks/
│   │   └── main.py
│   └── ui/
│       └── streamlit_app.py
├── core/
│   ├── config.py
│   ├── logging.py
│   ├── security.py
│   └── db.py
├── domain/
│   ├── projects/
│   ├── documents/
│   ├── regulations/
│   ├── evidence/
│   ├── generation/
│   ├── validation/
│   ├── review/
│   └── export/
├── pipelines/
│   ├── ingest_pipeline.py
│   ├── extraction_pipeline.py
│   ├── retrieval_pipeline.py
│   ├── generation_pipeline.py
│   └── validation_pipeline.py
├── adapters/
│   ├── llm/
│   │   ├── openai_client.py
│   │   ├── groq_client.py
│   │   └── schemas.py
│   ├── ocr/
│   ├── storage/
│   ├── vectorstore/
│   └── exporters/
├── prompts/
│   ├── sfdr/
│   │   ├── entity_pai/
│   │   ├── precontractual/
│   │   └── periodic/
├── rules/
│   ├── sfdr/
│   │   ├── completeness.yaml
│   │   ├── consistency.yaml
│   │   └── units.yaml
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evals/
├── scripts/
│   ├── seed_regulations.py
│   └── load_sample_docs.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```


## End-to-end workflow

The app should behave like this:

1. User creates a reporting project.
2. User selects disclosure type, entity PAI, pre-contractual, or periodic.
3. User uploads documents.
4. System parses and classifies document sections.
5. System maps required SFDR fields for that disclosure type.
6. Retrieval engine finds candidate evidence for each field.
7. LLM extracts normalized JSON per field.
8. Validation engine checks completeness and consistency.
9. Draft disclosure text is generated only for valid or partially valid fields.
10. Reviewer approves or edits.
11. Export to template-oriented package.

That workflow is aligned with the SFDR’s emphasis on exact content, methodology, and presentation rather than broad narrative flexibility.

## Prompt design

Use prompt chains per field, not one master prompt.

### Prompt 1: evidence extraction

Input:

- field code
- field description
- allowed answer type
- candidate chunks

Output:

```json
{
  "field_code": "PAI_GHG_001",
  "status": "found|missing|uncertain",
  "evidence": [
    {
      "source_doc_id": "...",
      "page": 14,
      "quote": "...",
      "value": "123.4",
      "unit": "tCO2e"
    }
  ],
  "normalized_value": {
    "value": 123.4,
    "unit": "tCO2e"
  },
  "reasoning_short": "..."
}
```


### Prompt 2: challenge prompt

Ask the model:

- Is the evidence contradictory?
- Is the unit ambiguous?
- Is this field actually answered or only implied?
- What is missing for compliance?


### Prompt 3: draft prompt

Generate final field text only from approved evidence JSON.
Hard constraints:

- no invented numbers
- no invented methodology
- return “insufficient evidence” when uncertain

This design keeps the LLM bounded, which matters because SFDR is intended to reduce greenwashing and improve comparability.

## Validation engine rules

This is where the product becomes enterprise-grade.

### Rule categories

- **Presence rules**: mandatory field missing.
- **Type rules**: numeric field contains prose.
- **Unit rules**: value lacks expected unit or incompatible unit.
- **Consistency rules**: same KPI differs across documents.
- **Temporal rules**: reporting period mismatch.
- **Provenance rules**: answer exists without evidence.
- **Template rules**: annex section not filled in correct order.
- **Policy rules**: sustainability claim lacks methodology support.


### Example rule

```python
def rule_answer_must_have_evidence(field_answer, evidence_list):
    if field_answer.answer_text and not evidence_list:
        return Fail("Generated answer has no supporting evidence")
    return Pass()
```


## UI modules

For MVP, build six screens:

- Dashboard: projects, due periods, completion status.
- Upload center: document ingest and parse status.
- Requirement matrix: all SFDR fields with status.
- Evidence viewer: page excerpt, table cell, confidence.
- Draft editor: AI answer + human edit.
- Export center: report package, checklist, audit file.


### Best UI pattern

Use a matrix like:


| Field | Status | Evidence | Confidence | Validation | Reviewer |
| :-- | :-- | :-- | :-- | :-- | :-- |
| PAI-01 | Drafted | 3 sources | 0.89 | 1 warning | Pending |
| PAI-02 | Missing | 0 sources | 0.00 | Failed | Pending |

That kind of reviewer-centric UX will be more useful than a chatbot pane.

## MVP milestones

### Phase 1: foundations, 2 weeks

- Regulation schema.
- Disclosure type registry.
- Upload and parsing.
- PostgreSQL models.
- Basic FastAPI endpoints.


### Phase 2: evidence extraction, 2-3 weeks

- PDF chunking.
- Table extraction.
- Embedding search.
- Initial field mapping.


### Phase 3: drafting and validation, 2 weeks

- Prompt templates.
- JSON extraction.
- Completeness rules.
- Reviewer screen.


### Phase 4: export and pilot, 2 weeks

- Word/PDF export.
- Audit log export.
- Benchmark against 5-10 real sample disclosures.


## Evaluation strategy

Measure the product on compliance usefulness, not just NLP metrics.

### Metrics

- Field extraction precision and recall.
- Numeric accuracy.
- Unsupported-claim rate.
- Human edit distance.
- Time-to-first-draft.
- Percentage of fields auto-approved after validation.
- Reviewer override rate.


### Gold dataset

Build a benchmark from:

- Public SFDR disclosures.
- Template annex samples from regulators or fund disclosures.[^3][^1]
- Manually annotated fields with evidence links.


## Security and governance

For a compliance product, add these from day one:

- Role-based access, analyst, reviewer, admin.
- Full audit trail for every generated answer.
- Prompt/version logging.
- Model/version logging.
- PII and confidential document tagging.
- Redaction option before sending to external LLM APIs.
- On-prem or VPC deployment path later.


## What I would build first

If I were executing this with your profile, I’d build:

- FastAPI backend.
- Streamlit reviewer UI.
- PostgreSQL + pgvector.
- One disclosure type only: periodic report or entity PAI.
- 20-30 high-value fields first.
- Rule engine before advanced multi-agent logic.

That route is faster, cheaper, and more likely to produce something buyers trust than starting with a large autonomous agent system. Your background in RAG, OCR, structured ML products, and Python-first delivery makes this a very feasible build.

## Practical differentiation

Your best product pitch is:

- “Upload your ESG documents.”
- “We map evidence to SFDR-required fields.”
- “We draft disclosure text with citations.”
- “We flag unsupported claims before sign-off.”

That is much stronger than “GenAI for ESG reporting,” because SFDR is fundamentally a disclosure-control problem under a standardized regime.

Would you like me to do the next step as actual implementation assets — a FastAPI starter codebase design with models, endpoints, prompt schemas, and a 4-week build sprint?
<span style="display:none">[^10][^11][^12][^13][^14][^15][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://www.esma.europa.eu/document/sfdr-templates

[^2]: https://perspectives.se.com/blog-stream/product-level-disclosure-under-sfdr-how-to-disclose

[^3]: https://www.swissfunddata.ch/sfdpub/docs/pd-8062_01_10-20230511-en.pdf

[^4]: https://www.dechert.com/knowledge/onpoint/2025/4/sfdr-1-5--a-new-set-of-rts-.html

[^5]: https://www.greenscope.io/en/sfdr/rts

[^6]: https://connect.earth/use-cases/periodic-report

[^7]: https://www.eiopa.europa.eu/publications/principal-adverse-impact-and-product-templates-sustainable-finance-disclosure-regulation_en

[^8]: https://eba.europa.eu/publications-and-media/press-releases/three-european-supervisory-authorities-publish-final-report

[^9]: https://www.ey.com/en_lu/industries/wealth-asset-management/sfdr-sustainable-finance-disclosure-regulation

[^10]: https://www.msci.com/documents/1296102/23400696/MSCI+SFDR+Adverse+Impact+Metrics+Methodology.pdf/ac60df37-681e-6b18-6f9b-fd5196b3fd78?t=1694625178508

[^11]: https://finance.ec.europa.eu/sustainable-finance/disclosures/sustainability-related-disclosure-financial-services-sector_en

[^12]: https://www.aoshearman.com/en/download/media/project/aoshearman/pdf-downloads/insights/2022/10/great-fund-insights-sfdr-and-taxonomy-rts-checklist-what-fund-managers-need-to-know-october-2022.pdf

[^13]: https://www.esma.europa.eu/sites/default/files/2025-09/JC_2025_26_Report_on_PAI_disclosures_under_Article_18_SFDR.pdf

[^14]: https://www.eba.europa.eu/sites/default/files/2024-07/0259cc55-3884-4c5e-a7e0-ad60d401f5b3/JC 2023 18 - Consolidated JC SFDR QAs.pdf

[^15]: https://www.meridiam.com/wp-content/uploads/2023/07/Meridiam-PAI.pdf


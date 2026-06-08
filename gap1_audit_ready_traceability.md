# Gap 1 Implementation Plan — Audit-Ready Data Traceability (BRSR Core)

## Overview

SEBI mandates BRSR Core reasonable assurance for the top 150 listed companies by market cap, and extends mandatory BRSR filing to the top 1000. Despite this, approximately 500 of 600 top Indian companies still rely on manual spreadsheets for ESG data management. The critical gap is not data collection — it is provability. When an external auditor arrives, no current platform can produce an unbroken, tamper-evident chain from a final reported metric back to its raw source document. This plan closes that gap by adding an Auditor Ledger, immutable document hashing, and a single-click audit export to the existing compliance workspace.

---

## Problem Statement

### The Audit Reality

Existing ESG platforms act as passive data warehouses. A compliance manager enters numbers into fields, and the platform generates a BRSR report. When an auditor performs reasonable assurance under SEBI BRSR Core guidelines, they must manually:

- Locate the original utility bills, fuel receipts, and HR payroll records
- Cross-reference those source documents against the submitted figures
- Verify that no data was altered between ingestion and final submission
- Reconstruct the reviewer approval chain manually

This process takes weeks, introduces human error, and is entirely unsupported by the software the company paid for.

### What SEBI BRSR Core Requires

SEBI's BRSR Core framework requires reasonable assurance — a formal audit standard equivalent to a limited assurance engagement — for nine specific Leadership Indicators including:

- GHG Scope 1 and Scope 2 absolute emissions (tonnes CO₂e)
- Energy consumption intensity
- Water withdrawal and discharge intensity
- Waste generation intensity
- Pay gap between median and mean compensation (gender-disaggregated)
- Turnover rate disaggregated by gender and age

Each of these must be traceable to its raw source with a verifiable evidence chain. No current Indian ESG software platform provides this automatically.

---

## Solution Architecture

### Component 1 — Immutable Document Hashing

**What it does:** When a document is ingested, compute and store a SHA-256 hash of the raw file bytes alongside the `Document` record. On any auditor query, recompute the hash from the stored file and compare. Display a tamper-status badge on every document.

**Changes to existing codebase:**

#### `app/models.py`
Add to the `Document` model:
```python
file_hash = Column(String(64), nullable=True)   # SHA-256 hex digest
hash_algorithm = Column(String(16), default="sha256")
hashed_at = Column(DateTime, nullable=True)
```

#### `app/services/ingestion.py`
After file write, before chunking:
```python
import hashlib

def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

# In ingest_document():
file_hash = compute_file_hash(raw_bytes)
document.file_hash = file_hash
document.hashed_at = datetime.utcnow()
db.commit()
```

**Auditor verification logic:**
```python
def verify_document_integrity(document_id: int, db: Session) -> dict:
    doc = db.query(Document).filter(Document.id == document_id).first()
    current_bytes = open(doc.file_path, "rb").read()
    current_hash = hashlib.sha256(current_bytes).hexdigest()
    is_intact = current_hash == doc.file_hash
    return {
        "document_id": document_id,
        "stored_hash": doc.file_hash,
        "current_hash": current_hash,
        "integrity_status": "INTACT" if is_intact else "TAMPERED",
        "hashed_at": doc.hashed_at
    }
```

---

### Component 2 — Auditor Ledger Data Model

**What it does:** Every BRSR field answer is linked not just to its reviewer, but to a full evidence chain: extracted chunk → source document → file hash → approval action. The Auditor Ledger is a read-only materialized view of this chain, queryable per field or per project.

#### `app/models.py` — New `AuditorLedgerEntry` model
```python
class AuditorLedgerEntry(Base):
    __tablename__ = "auditor_ledger"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    regulation_field_id = Column(Integer, ForeignKey("regulation_fields.id"), nullable=False)
    field_answer_id = Column(Integer, ForeignKey("field_answers.id"), nullable=True)
    evidence_id = Column(Integer, ForeignKey("field_evidence.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    document_hash = Column(String(64), nullable=True)
    source_passage = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)
    extraction_model = Column(String(128), nullable=True)
    extraction_timestamp = Column(DateTime, nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_timestamp = Column(DateTime, nullable=True)
    final_value = Column(Text, nullable=True)
    integrity_verified = Column(Boolean, default=False)
    ledger_created_at = Column(DateTime, default=datetime.utcnow)
```

This table is populated automatically when a `FieldAnswer` transitions to `approved` status.

---

### Component 3 — Auditor Role and Portal API

**What it does:** Adds a new `auditor` user role with read-only access to all ledger data, integrity verification endpoints, and audit export.

#### New API Endpoints in `app/main.py`

```
GET  /api/projects/{project_id}/auditor-ledger
     → Returns full ledger for all BRSR fields in the project
     → Optional: ?field_code=BRSR_GHG_SCOPE1 to filter by field
     → Optional: ?framework=BRSR to filter by framework

GET  /api/projects/{project_id}/auditor-ledger/{field_id}
     → Returns ledger entry + integrity check for a single field

GET  /api/documents/{document_id}/integrity
     → Returns SHA-256 integrity verification result

POST /api/projects/{project_id}/audit-export
     → Generates and returns a ZIP containing:
         - Final BRSR report (Markdown + HTML)
         - All source documents used as evidence
         - evidence_mapping.csv (field → document → page → passage → hash)
         - audit_log.csv (all reviewer actions with timestamps and user IDs)
         - integrity_report.json (hash verification status for every document)
```

---

### Component 4 — Frontend Auditor Portal

**New page: `AuditorPortal.jsx`**

This is a dedicated read-only view accessible under `/auditor` route, protected by the `auditor` role.

**UI sections:**
1. **Project Overview Bar** — shows total fields, verified fields, tampered documents (if any), and last audit date
2. **Field-by-Field Ledger Table** with columns:
   - Field name and BRSR article reference
   - Final reported value
   - Source document name + page
   - Source passage excerpt (truncated, expandable)
   - Document integrity badge (🟢 INTACT / 🔴 TAMPERED)
   - Approved by + timestamp
3. **Document Integrity Panel** — lists all ingested documents with hash status
4. **One-Click Audit Export Button** — triggers `/audit-export` and downloads ZIP

**Integrity badge component:**
```jsx
const IntegrityBadge = ({ status }) => (
  <span className={`badge ${status === 'INTACT' ? 'badge-success' : 'badge-danger'}`}>
    {status === 'INTACT' ? '✓ Untampered' : '⚠ Hash Mismatch'}
  </span>
);
```

---

### Component 5 — Ledger Auto-Population on Approval

When a reviewer approves a `FieldAnswer`, a post-approval hook automatically creates an `AuditorLedgerEntry`:

```python
# In the approval route handler in main.py:
def create_ledger_entry_on_approval(answer: FieldAnswer, db: Session, reviewer_id: int):
    evidence = db.query(FieldEvidence).filter(
        FieldEvidence.regulation_field_id == answer.regulation_field_id,
        FieldEvidence.project_id == answer.project_id
    ).first()

    ledger_entry = AuditorLedgerEntry(
        project_id=answer.project_id,
        regulation_field_id=answer.regulation_field_id,
        field_answer_id=answer.id,
        evidence_id=evidence.id if evidence else None,
        document_id=evidence.document_id if evidence else None,
        document_hash=evidence.document.file_hash if evidence and evidence.document else None,
        source_passage=evidence.extracted_text if evidence else None,
        source_page=evidence.source_page if evidence else None,
        extraction_model=answer.model_parameters,
        extraction_timestamp=answer.created_at,
        approved_by_user_id=reviewer_id,
        approval_timestamp=datetime.utcnow(),
        final_value=answer.answer_text,
        integrity_verified=True
    )
    db.add(ledger_entry)
    db.commit()
```

---

## Database Migration

```python
# alembic/versions/xxxx_add_auditor_ledger.py
def upgrade():
    op.add_column('documents', sa.Column('file_hash', sa.String(64), nullable=True))
    op.add_column('documents', sa.Column('hash_algorithm', sa.String(16), nullable=True))
    op.add_column('documents', sa.Column('hashed_at', sa.DateTime(), nullable=True))
    op.create_table('auditor_ledger', ...)  # full column spec as above
```

---

## Verification Plan

### Automated Tests (add to `tests_verify.py`)
- Ingest a test document and verify `file_hash` is populated
- Modify the file bytes and verify `integrity_status` returns `TAMPERED`
- Approve a `FieldAnswer` and verify an `AuditorLedgerEntry` is created
- Call `/audit-export` and verify the ZIP contains all required files
- Verify the `auditor` role cannot POST/PATCH any data (read-only enforcement)

### Manual Verification
1. Upload a real BRSR sustainability report PDF
2. Run GenAI extraction for BRSR framework fields
3. Approve 3–5 field answers as reviewer
4. Switch to Auditor Portal view
5. Verify each approved field shows source document, page, passage, and INTACT badge
6. Click Audit Export and open the ZIP — verify `evidence_mapping.csv` is populated correctly

---

## Build Effort Estimate

| Component | Estimated effort |
|---|---|
| SHA-256 hashing in ingestion | 0.5 days |
| `AuditorLedgerEntry` model + migration | 1 day |
| Ledger auto-population on approval | 1 day |
| Auditor Portal API endpoints | 1.5 days |
| `AuditorPortal.jsx` frontend | 2 days |
| Audit Export ZIP generation | 1 day |
| Tests and verification | 1 day |
| **Total** | **~8 working days** |

---

## Commercial Positioning

This feature directly addresses the ₹50,000–₹5,00,000 per engagement cost that Indian listed companies currently pay auditors to manually reconstruct evidence trails during BRSR Core reasonable assurance engagements. A platform that eliminates that reconstruction work and reduces audit preparation from weeks to hours is solving an operational pain that compliance teams actively budget for. The Auditor Portal is also a natural upsell lever: the base product serves the compliance team, while the Auditor role is a separately purchasable seat that the company's external assurance provider uses directly.

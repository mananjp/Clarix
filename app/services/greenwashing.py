import re
import uuid
import json
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    GreenwashingAudit, GreenwashingFinding, DocumentChunk, FieldAnswer, FieldEvidence, RegulationField,
    AnswerStatus, Severity, PenaltyTier,
)
from app.services.generation import GenerationService

logger = logging.getLogger(__name__)

# =============================================================================
# Greenwashing legal consequence knowledge base
# =============================================================================

GREENWASHING_LEGAL_MAP = {
    "absolute_claim_vs_measured": {
        "legal_citation": (
            "SFDR Art. 10(2) & 11(1) — marketing claims must be consistent with pre-contractual and "
            "periodic disclosures; ESMA Guidelines on funds' names using ESG or sustainability-related terms "
            "(2024); SEC Rule 17 CFR 229.1500 (Climate Disclosure Rule); SEC anti-fraud Rule 10b-5."
        ),
        "penalty_tier": "Critical",
        "enforcement_body": "ESMA / National Competent Authority / US SEC",
        "remediation": (
            "1. Withdraw or amend the marketing claim to match the audited disclosure figure.\n"
            "2. Issue a corrective investor communication within 30 days.\n"
            "3. Update fund pre-contractual documentation (prospectus, KIID/KID).\n"
            "4. Document the discrepancy, root cause, and corrective action plan in the compliance file."
        ),
    },
    "fossil_exposure": {
        "legal_citation": (
            "SFDR Art. 7(1)(a), RTS Annex I Table 1 Indicator 5 (Fossil fuel exposure); "
            "SEC Climate Disclosure Rule 17 CFR 229.1500 (GHG metrics); "
            "UK FCA SDR Anti-Greenwashing Rule COBS 4.3.8 (PS23/16)."
        ),
        "penalty_tier": "High",
        "enforcement_body": "National Competent Authority / ESMA / FCA / SEC",
        "remediation": (
            "1. Reconcile the marketing claim against the audited PAI fossil-fuel exposure percentage.\n"
            "2. Either reduce portfolio fossil-fuel exposure or soften the marketing language to 'reduced' / 'limited'\n"
            "   instead of 'zero' / 'no exposure'.\n"
            "3. Ensure the periodic SFDR report discloses the true fossil-fuel percentage."
        ),
    },
    "taxonomy_misrepresentation": {
        "legal_citation": (
            "EU Taxonomy Regulation Art. 5-6; SFDR RTS Annex IV (Taxonomy alignment); "
            "SEC Climate Disclosure Rule 17 CFR 229.1500(d)."
        ),
        "penalty_tier": "High",
        "enforcement_body": "National Competent Authority / ESMA / US SEC",
        "remediation": (
            "1. Correct the taxonomy-alignment percentage in marketing materials to match audited EU\n"
            "   Taxonomy alignment disclosures.\n"
            "2. Re-verify taxonomy eligibility and alignment calculations against the EU Taxonomy Technical\n"
            "   Screening Criteria.\n"
            "3. Update any fund naming or SFDR Article classification if material."
        ),
    },
    "net_zero_overstatement": {
        "legal_citation": (
            "ESMA Net-Zero Guidelines; UK FCA SDR principles; SEC anti-fraud Rule 10b-5; "
            "CCC (Climate Corporate Accountability) litigation precedent."
        ),
        "penalty_tier": "Critical",
        "enforcement_body": "ESMA / FCA / US SEC",
        "remediation": (
            "1. Substantiate the net-zero target with a credible, dated transition plan and interim milestones.\n"
            "2. Disclose the baseline year, interim targets, and methodology.\n"
            "3. If emissions have not actually been reduced to zero, rephrase to 'net-zero commitment by 2050'\n"
            "   rather than 'net zero achieved'."
        ),
    },
    "green_bond_improper": {
        "legal_citation": (
            "ICMA Green Bond Principles; EU Green Bond Standard (Regulation (EU) 2023/2631); "
            "SEC Rule 17 CFR 240.10b-5 (anti-fraud)."
        ),
        "penalty_tier": "High",
        "enforcement_body": "ICMA / ESMA / US SEC",
        "remediation": (
            "1. Confirm the funds were applied to eligible green projects and verified under the use-of-proceeds\n"
            "   framework.\n"
            "2. Provide a second-party opinion (SPO) or external reviewer verification.\n"
            "3. Correct any overstatement of 'green' designation in the marketing collateral."
        ),
    },
    "carbon_neutral_claim": {
        "legal_citation": (
            "UK CMA Green Claims Code; FCA Anti-Greenwashing Rule COBS 4.3.8; "
            "SEC Rule 10b-5; European Commission Green Claims Directive (proposed)."
        ),
        "penalty_tier": "High",
        "enforcement_body": "CMA / FCA / SEC",
        "remediation": (
            "1. Verify whether carbon-neutrality claims rely on purchased offsets vs. actual emissions reductions.\n"
            "2. Disclose offsets separately from direct emissions reductions.\n"
            "3. Rephrase claims to specify 'carbon neutral through verified offsets' where applicable."
        ),
    },
}

# Fallback for unknown categories
_DEFAULT_CATEGORY = "absolute_claim_vs_measured"


# =============================================================================
# Claim extraction heuristics — (quantitative + absolute claim patterns)
# =============================================================================

# Each pattern captures: (regex, category, implied_field_codes)
CLAIM_PATTERNS = [
    {
        "name": "zero_fossil",
        "category": "fossil_exposure",
        "field_codes": ["PAI_FOSSIL_FUEL"],
        "regex": re.compile(
            r"(?:zero\s*(?:fossil|oil|gas|coal)|no\s*(?:fossil|oil|gas|coal)|fossil\s*fuel\s*free)",
            re.IGNORECASE,
        ),
        "claimed_constant": 0.0,
        "unit": "%",
    },
    {
        "name": "hundred_percent_green",
        "category": "absolute_claim_vs_measured",
        "field_codes": ["PERIODIC_ASSET_ALLOCATION", "PERIODIC_TAXONOMY_ALIGNMENT"],
        "regex": re.compile(r"(?:100\s*%|fully|entirely|completely|wholly)\s*(?:green|sustainable|impact|aligned)", re.IGNORECASE),
        "claimed_constant": 100.0,
        "unit": "%",
    },
    {
        "name": "net_zero_achieved",
        "category": "net_zero_overstatement",
        "field_codes": ["PAI_GHG_SCOPE1", "PAI_GHG_SCOPE2", "PAI_GHG_SCOPE3", "PAI_CARBON_FOOTPRINT"],
        "regex": re.compile(r"(?:already\s*)?(?:achieved|became|reached)\s*(?:net\s*zero|net-zero|carbon\s*neutral|climate\s*neutral)", re.IGNORECASE),
        "claimed_constant": None,
        "unit": None,
    },
    {
        "name": "net_zero_target",
        "category": "net_zero_overstatement",
        "field_codes": ["PAI_CARBON_FOOTPRINT"],
        "regex": re.compile(r"net\s*[- ]?zero\s*(?:by|commitment)", re.IGNORECASE),
        "claimed_constant": None,
        "unit": None,
    },
    {
        "name": "carbon_neutral",
        "category": "carbon_neutral_claim",
        "field_codes": ["PAI_GHG_SCOPE1", "PAI_GHG_SCOPE2", "PAI_GHG_SCOPE3", "PAI_CARBON_FOOTPRINT"],
        "regex": re.compile(r"(?:carbon\s*neutral|climate\s*neutral)", re.IGNORECASE),
        "claimed_constant": None,
        "unit": None,
    },
    {
        "name": "green_bond",
        "category": "green_bond_improper",
        "field_codes": ["PERIODIC_ASSET_ALLOCATION", "PERIODIC_TAXONOMY_ALIGNMENT"],
        "regex": re.compile(r"(?:100\s*%|all)\s*(?:green\s*bonds?|proceeds)", re.IGNORECASE),
        "claimed_constant": 100.0,
        "unit": "%",
    },
    {
        "name": "taxonomy_aligned",
        "category": "taxonomy_misrepresentation",
        "field_codes": ["PERIODIC_TAXONOMY_ALIGNMENT"],
        "regex": re.compile(
            r"(?:100\s*%|fully|entirely)\s*(?:taxonomy[- ]aligned|EU\s*[Tt]axonomy[- ]aligned)",
            re.IGNORECASE,
        ),
        "claimed_constant": 100.0,
        "unit": "%",
    },
    {
        "name": "percentage_sustainable",
        "category": "absolute_claim_vs_measured",
        "field_codes": ["PERIODIC_ASSET_ALLOCATION", "PERIODIC_TAXONOMY_ALIGNMENT"],
        "regex": re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of\s*(?:the\s*|our\s*)?)?(?:investments?|assets?|portfolio)\s*(?:are|is)?\s*(?:sustainable|green|aligned)", re.IGNORECASE),
        "claimed_constant": "captured",
        "unit": "%",
    },
]


def _category_legal_map(category: str) -> Dict[str, str]:
    """Return legal citation fields for a category with safe fallback."""
    return GREENWASHING_LEGAL_MAP.get(category, GREENWASHING_LEGAL_MAP[_DEFAULT_CATEGORY])


class GreenwashingDetector:
    """Detects contradictions between marketing claims and audited regulatory disclosures."""

    # ------------------------------------------------------------------
    # 1. Claim extraction
    # ------------------------------------------------------------------
    @classmethod
    def extract_marketing_claims(cls, doc_text: str, source: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract quantified / absolute marketing claims from a document text.
        Returns a list of claim dicts:
          {pattern_name, category, quote, sentence, claimed_metric, unit, source}
        """
        claims: List[Dict[str, Any]] = []
        if not doc_text:
            return claims

        sentences = re.split(r'(?<=[.!?])\s+', doc_text)
        for sentence in sentences:
            for pattern in CLAIM_PATTERNS:
                m = pattern["regex"].search(sentence)
                if not m:
                    continue

                claimed_metric = pattern["claimed_constant"]
                if claimed_metric == "captured":
                    try:
                        captured = m.group(1).replace(",", "")
                        claimed_metric = float(captured)
                    except (IndexError, ValueError):
                        claimed_metric = None

                claims.append({
                    "pattern_name": pattern["name"],
                    "category": pattern["category"],
                    "field_codes": pattern["field_codes"],
                    "quote": m.group(0).strip(),
                    "sentence": sentence.strip(),
                    "claimed_metric": claimed_metric,
                    "unit": pattern["unit"],
                    "source": source or {},
                })
        return claims

    # ------------------------------------------------------------------
    # 2. Contradiction detection
    # ------------------------------------------------------------------
    @staticmethod
    def _audited_value_for_field(field_code: str, audited_answers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the audited / approved answer value for a given field_code."""
        for item in audited_answers:
            if item.get("field_code") == field_code and item.get("has_value"):
                return item
        return None

    @classmethod
    def detect_contradictions(
        cls,
        claims: List[Dict[str, Any]],
        audited_answers: List[Dict[str, Any]],
        tolerance: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """
        Compare each marketing claim against the audited disclosure values.
        Returns a list of finding dicts.
        """
        findings: List[Dict[str, Any]] = []

        for claim in claims:
            claimed = claim.get("claimed_metric")
            category = claim.get("category")
            field_codes = claim.get("field_codes", [])
            unit = claim.get("unit")

            legal = _category_legal_map(category)

            for field_code in field_codes:
                audited = cls._audited_value_for_field(field_code, audited_answers)
                if not audited:
                    continue

                audited_val = audited.get("value")
                if audited_val is None:
                    continue

                try:
                    audited_num = float(audited_val)
                except (TypeError, ValueError):
                    continue

                # Determine if there is a contradiction
                contradicted = False
                rationale = None

                if claimed is not None and unit == "%":
                    # Absolute claims: "zero fossil" -> claimed 0 vs. audited 2.4%
                    # Percentage claims: "82% sustainable" vs. audited 78% (within tolerance?)
                    if claimed == 0.0 and audited_num > 0.0:
                        contradicted = True
                        rationale = (
                            f"Marketing claim states {claim['quote']} (0%), but audited disclosure "
                            f"reports {audited_num}{unit or ''} exposure."
                        )
                    elif claimed == 100.0 and audited_num < (100.0 - tolerance):
                        contradicted = True
                        rationale = (
                            f"Marketing claim states '{claim['quote']}', but audited disclosure "
                            f"reports only {audited_num}{unit or ''}."
                        )
                    elif claimed not in (0.0, 100.0) and claimed is not None:
                        # Relative claim; flag only if materially below (higher than 2x tolerance gap)
                        if abs(claimed - audited_num) > tolerance and claimed > audited_num:
                            contradicted = True
                            rationale = (
                                f"Marketing claim states {claimed}{unit or ''}, but audited disclosure "
                                f"reports {audited_num}{unit or ''} — a materially lower figure."
                            )
                elif claimed is None and category in ("net_zero_overstatement", "carbon_neutral_claim"):
                    # Non-numeric absolute claim: check if any GHG field has a non-zero value
                    if audited_num > tolerance:
                        contradicted = True
                        rationale = (
                            f"Marketing claim '{claim['quote']}' implies zero / negligible emissions, "
                            f"but audited disclosure reports {audited_num} in field {field_code}."
                        )

                if contradicted:
                    findings.append({
                        "claim_quote": claim["sentence"],
                        "claim_metric": claim["quote"],
                        "claim_source": claim["source"],
                        "contradicting_field_code": field_code,
                        "contradicting_value": {"value": audited_num, "unit": unit or audited.get("unit")},
                        "discrepancy_category": category,
                        "rationale": rationale,
                        "severity": cls._severity_for_category(category),
                        "legal_citation": legal["legal_citation"],
                        "penalty_tier": legal["penalty_tier"],
                        "enforcement_body": legal["enforcement_body"],
                        "remediation": legal["remediation"],
                    })
                    break  # one finding per claim

        return findings

    @staticmethod
    def _severity_for_category(category: str) -> str:
        if category in ("absolute_claim_vs_measured", "net_zero_overstatement"):
            return Severity.ERROR.value
        if category in ("fossil_exposure", "taxonomy_misrepresentation", "green_bond_improper", "carbon_neutral_claim"):
            return Severity.WARNING.value
        return Severity.INFO.value

    # ------------------------------------------------------------------
    # 3. Risk scoring
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_risk_score(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute a Greenwashing Risk Score (0-100) plus a risk level.
        Scoring: severity weighting * count + penalty-tier uplift, capped at 100.
        """
        severity_weights = {
            Severity.ERROR.value: 34.0,
            Severity.WARNING.value: 20.0,
            Severity.INFO.value: 8.0,
        }
        tier_uplift = {
            PenaltyTier.CRITICAL.value: 6.0,
            PenaltyTier.HIGH.value: 4.0,
            PenaltyTier.MEDIUM.value: 2.0,
            PenaltyTier.LOW.value: 0.0,
        }

        if not findings:
            return {"risk_score": 0.0, "risk_level": "Low", "total_findings": 0}

        raw = 0.0
        for f in findings:
            sev = f.get("severity", Severity.WARNING.value)
            tier = f.get("penalty_tier", PenaltyTier.MEDIUM.value)
            raw += severity_weights.get(sev, 10.0) + tier_uplift.get(tier, 0.0)

        # Slight dampening for very large finding lists so score stays meaningful
        if len(findings) > 3:
            raw = 60.0 + (raw - 60.0) * 0.5

        risk_score = round(min(100.0, raw), 1)
        if risk_score >= 80:
            level = "Critical"
        elif risk_score >= 60:
            level = "High"
        elif risk_score >= 35:
            level = "Moderate"
        else:
            level = "Low"

        return {
            "risk_score": risk_score,
            "risk_level": level,
            "total_findings": len(findings),
        }

    # ------------------------------------------------------------------
    # 4. Optional LLM enhancement (heuristic-first pattern)
    # ------------------------------------------------------------------
    @classmethod
    def _run_llm_evaluation(cls, claims: List[Dict[str, Any]], audited_summary: str) -> Optional[Dict[str, Any]]:
        """
        Optionally enhance detection using the LLM when Groq is configured.
        Returns None (never raises) so heuristic results always remain usable.
        """
        client = GenerationService.get_groq_client()
        if not client:
            return None
        try:
            claims_json = json.dumps(claims, default=str)[:4000]
            system_prompt = (
                "You are an expert ESG regulatory auditor. Based on a list of extracted marketing claims "
                "and an audited disclosure summary, identify any clear greenwashing contradictions (a claim "
                "that conflicts with audited facts). Output ONLY JSON: {\"risk_score\": 0-100, "
                "\"notes\": string, \"contradictions\": [{\"claim\": string, \"finding\": string}]}."
            )
            user_content = f"Marketing claims: {claims_json}\n\nAudited summary: {audited_summary[:4000]}"
            from app.services.generation import DEFAULT_MODEL
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.warning("LLM greenwashing evaluation failed; using heuristic result only: %s", e)
            return None

    # ------------------------------------------------------------------
    # 5. Orchestrator
    # ------------------------------------------------------------------
    @classmethod
    def run_audit(cls, db: Session, project_id: str, document_id: str, actor_id: Optional[str] = None) -> GreenwashingAudit:
        """
        Run a full greenwashing contradiction scan for a project against a
        marketing document, persist the audit + findings, and return the audit.
        """
        audit = GreenwashingAudit(
            id=str(uuid.uuid4()),
            project_id=project_id,
            document_id=document_id,
            audit_status="Running",
            created_by=actor_id,
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)

        try:
            # 1. Pull marketing document text from its chunks
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
            doc_text = " ".join([c.chunk_text for c in chunks])
            source = {"document_id": document_id, "chunks": len(chunks)}

            # 2. Extract claims
            claims = cls.extract_marketing_claims(doc_text, source)

            # 3. Build audited answers from approved FieldAnswers
            audited_answers = cls._build_audited_answers(db, project_id)

            # 4. Detect contradictions
            findings = cls.detect_contradictions(claims, audited_answers)

            # 5. Score
            score = cls.calculate_risk_score(findings)

            # 6. Optional LLM enhancement (does not replace heuristic findings)
            llm_result = cls._run_llm_evaluation(
                claims,
                json.dumps(audited_answers, default=str),
            )
            summary_parts = [
                f"Scanned {len(chunks)} document chunk(s); extracted {len(claims)} marketing claim(s).",
                f"Identified {len(findings)} contradiction(s). {score['risk_level']} risk.",
            ]
            if llm_result and llm_result.get("notes"):
                summary_parts.append(f"LLM note: {llm_result['notes']}")

            # 7. Persist findings
            for f in findings:
                db.add(GreenwashingFinding(
                    id=str(uuid.uuid4()),
                    audit_id=audit.id,
                    claim_quote=f["claim_quote"],
                    claim_source=f["claim_source"],
                    contradicting_field_code=f["contradicting_field_code"],
                    contradicting_value=f["contradicting_value"],
                    discrepancy_category=f["discrepancy_category"],
                    severity=f["severity"],
                    legal_citation=f["legal_citation"],
                    penalty_tier=f["penalty_tier"],
                    enforcement_body=f["enforcement_body"],
                    remediation=f["remediation"],
                ))

            audit.audit_status = "Completed"
            audit.total_claims_extracted = len(claims)
            audit.total_findings = len(findings)
            audit.risk_score = score["risk_score"]
            audit.risk_level = score["risk_level"]
            audit.summary = " ".join(summary_parts)
            db.commit()
        except Exception as e:
            logger.error("Greenwashing audit failed for project %s: %s", project_id, e)
            audit.audit_status = "Failed"
            audit.summary = f"Audit failed: {e}"
            db.commit()
            # Re-raise after recording failure so caller sees the error
            raise

        db.refresh(audit)
        return audit

    @staticmethod
    def _build_audited_answers(db: Session, project_id: str) -> List[Dict[str, Any]]:
        """
        Collect the latest approved FieldAnswers with their numeric values and
        associated regulation field codes, for contradiction comparison.
        """
        answers = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == project_id,
            FieldAnswer.is_latest.is_(True),
        ).all()

        # Map field id -> code
        field_ids = {a.regulation_field_id for a in answers}
        fields = db.query(RegulationField).filter(RegulationField.id.in_(field_ids)).all() if field_ids else []
        code_by_id = {f.id: f.field_code for f in fields}

        # Evidence values (most recent per project/field)
        evidence = db.query(FieldEvidence).filter(FieldEvidence.project_id == project_id).all()
        evidence_by_field = {}
        for ev in evidence:
            evidence_by_field[ev.regulation_field_id] = ev.extracted_value or {}

        result = []
        for a in answers:
            ans_value = None
            ans_unit = None
            if a.answer_json and isinstance(a.answer_json, dict):
                ans_value = a.answer_json.get("value")
                ans_unit = a.answer_json.get("unit")
            if ans_value is None:
                ev = evidence_by_field.get(a.regulation_field_id) or {}
                ans_value = ev.get("value")
                ans_unit = ev.get("unit")

            result.append({
                "field_code": code_by_id.get(a.regulation_field_id),
                "value": ans_value,
                "unit": ans_unit,
                "status": a.status,
                "has_value": ans_value is not None,
            })

        # Prefer approved values, then drafts
        result.sort(key=lambda x: 0 if x.get("status") == AnswerStatus.APPROVED.value else 1)
        return result

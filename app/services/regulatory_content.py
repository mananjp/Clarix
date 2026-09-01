"""
Regulatory content update pipeline.

Maintains the live-ness of `RegulationField` legal metadata (legal basis,
penalty tiers, enforcement bodies, cross-references). The pipeline tracks a
known regulatory-amendment registry (e.g. SFDR Level I revision, updates to
ESRS / RTS) and provides versioned content updates with a full audit trail,
so stale legal metadata never silently persists in a compliance product.

The actual rule-text changes are supplied by a "registry" (seed data or an
operator-provided feed); this service manages application + versioning + audit.
"""

import uuid
import logging
import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    RegulationField, AuditLog, User,
)
import app.seed_regulations as seed_reg

logger = logging.getLogger(__name__)

# Known regulatory instruments and their (monotonic) effective versions.
REGULATORY_INSTRUMENTS = [
    {
        "instrument": "SFDR",
        "regulation": "Regulation (EU) 2019/2088",
        "versions": {
            "2022/1288": "RTS Annex I-IV (PAI tables) — current baseline",
            "SFDR_LEVEL1_REVISION_2025": "Commission 2025 simplification revision — under consultation",
        },
        "baseline_version": "2022/1288",
    },
    {
        "instrument": "CSRD",
        "regulation": "Directive (EU) 2022/2464",
        "versions": {
            "ESRS_2023": "EFRAG ESRS (delegated act Dec 2023)",
            "ESRS_SET1_2024": "First set of ESRS — in force",
        },
        "baseline_version": "ESRS_2023",
    },
]


class RegulatoryContentService:
    """Apply and audit versioned updates to RegulationField legal metadata."""

    @staticmethod
    def list_instruments() -> List[Dict[str, Any]]:
        """Return the known regulatory instrument registry for UI/ops visibility."""
        return REGULATORY_INSTRUMENTS

    @staticmethod
    def current_version_field_counts(db: Session) -> Dict[str, Any]:
        """Summarize which regulation_version each field currently holds."""
        fields = db.query(RegulationField).all()
        summary: Dict[str, Dict[str, int]] = {}
        for f in fields:
            entry = summary.setdefault(f.framework or "Unknown", {})
            v = f.regulation_version or "unversioned"
            entry[v] = entry.get(v, 0) + 1
        return summary

    @staticmethod
    def stale_fields(
        db: Session,
        target_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Identify RegulationFields whose regulation_version is behind the
        target baseline (or the latest known version per instrument).
        """
        baseline_by_instrument = {i["instrument"]: i["baseline_version"] for i in REGULATORY_INSTRUMENTS}
        fields = db.query(RegulationField).all()
        stale = []
        for f in fields:
            baseline = target_version or baseline_by_instrument.get(f.framework)
            if baseline and f.regulation_version != baseline:
                stale.append({
                    "field_id": f.id,
                    "field_code": f.field_code,
                    "framework": f.framework,
                    "current_version": f.regulation_version,
                    "target_version": baseline,
                    "legal_basis": f.legal_basis,
                })
        return stale

    @staticmethod
    def apply_content_update(
        db: Session,
        *,
        actor_id: str,
        framework: str,
        target_regulation_version: str,
        update_payload: Dict[str, Dict[str, Any]],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply a content update to all RegulationFields of a framework:

        update_payload is a dict keyed by field_code -> {"legal_basis",
        "penalty_tier" (optional), "enforcement_body" (optional), and
        "regulation_version" (optional, defaults to target)}.

        Every change is recorded in the AuditLog for full traceability.
        """
        actor = db.query(User).filter(User.id == actor_id).first()
        if not actor:
            raise ValueError("Actor not found.")

        fields = db.query(RegulationField).filter(RegulationField.framework == framework).all()
        updated = []
        skipped = []

        for f in fields:
            change = update_payload.get(f.field_code)
            if change:
                old = {
                    "legal_basis": f.legal_basis,
                    "penalty_tier": f.penalty_tier,
                    "enforcement_body": f.enforcement_body,
                    "regulation_version": f.regulation_version,
                }
                if "legal_basis" in change:
                    f.legal_basis = change["legal_basis"]
                if "penalty_tier" in change:
                    f.penalty_tier = change["penalty_tier"]
                if "enforcement_body" in change:
                    f.enforcement_body = change["enforcement_body"]
                f.regulation_version = change.get("regulation_version", target_regulation_version)
                f.cross_references = change.get("cross_references", f.cross_references)

                write = AuditLog(
                    id=str(uuid.uuid4()),
                    entity_type="regulation_field",
                    entity_id=f.id,
                    action="content_update",
                    actor_id=actor_id,
                    payload={
                        "framework": framework,
                        "target_regulation_version": target_regulation_version,
                        "old": old,
                        "new": {
                            "legal_basis": f.legal_basis,
                            "penalty_tier": f.penalty_tier,
                            "enforcement_body": f.enforcement_body,
                            "regulation_version": f.regulation_version,
                        },
                        "notes": notes,
                    },
                    created_at=datetime.datetime.utcnow(),
                )
                db.add(write)
                updated.append(f.field_code)
            else:
                skipped.append(f.field_code)

        db.commit()
        logger.info("Regulatory content update applied to %d fields (framework=%s)", len(updated), framework)
        return {
            "framework": framework,
            "target_regulation_version": target_regulation_version,
            "fields_updated": len(updated),
            "fields_skipped": len(skipped),
            "updated_field_codes": updated,
            "notes": notes,
        }

    @staticmethod
    def reset_to_seed(db: Session, actor_id: str, framework: str) -> Dict[str, Any]:
        """Restore a framework's fields to the baseline seed values (dangerous, audited)."""
        source_payload = {
            framework: getattr(seed_reg, {
                "SFDR": "SFDR_FIELDS",
                "CSRD": "CSRD_FIELDS",
                "SEC": "SEC_FIELDS",
                "UK SDR": "UK_SDR_FIELDS",
                "ISSB": "ISSB_FIELDS",
            }.get(framework, "SFDR_FIELDS"), [])
        }[framework]

        reset_payload = {}
        for seed_field in source_payload:
            reset_payload[seed_field["field_code"]] = {
                "legal_basis": seed_field.get("legal_basis"),
                "penalty_tier": seed_field.get("penalty_tier", "Medium"),
                "enforcement_body": seed_field.get("enforcement_body"),
                "regulation_version": seed_field.get("regulation_version"),
                "cross_references": seed_field.get("cross_references"),
            }

        return RegulatoryContentService.apply_content_update(
            db,
            actor_id=actor_id,
            framework=framework,
            target_regulation_version="(reset-to-seed)",
            update_payload=reset_payload,
            notes="Operator-initiated reset to baseline seed data.",
        )

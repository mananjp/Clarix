"""
Double Materiality Assessment service.

Implements the CSRD-mandated double-materiality workflow (CSRD Art. 19a,
ESRS 1). Each ESRS topic receives a financial-materiality score (impact of
sustainability matters on the undertaking) and an impact-materiality score
(impact of the undertaking on people and planet). Combined materiality
determines which ESRS topics are in scope for the entity's sustainability
statement.
"""

import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    DoubleMaterialityAssessment, ESRS_TOPICS,
)

logger = logging.getLogger(__name__)

DEFAULT_MATERIALITY_THRESHOLD = 50.0


class DoubleMaterialityService:
    """Scoring, verdict, and reporting for double-materiality assessments."""

    @staticmethod
    def _template(org_id: str, project_id: Optional[str]) -> DoubleMaterialityAssessment:
        """Create an in-memory (uncommitted) template row for an ESRS topic."""
        return DoubleMaterialityAssessment(
            id=f"dm_{uuid.uuid4().hex[:12]}",
            organization_id=org_id,
            project_id=project_id,
            esrs_topic="",
            topic_name="",
            financial_materiality=0.0,
            impact_materiality=0.0,
            material_threshold=DEFAULT_MATERIALITY_THRESHOLD,
            combined_verdict="NotMaterial",
            assessment_status="Draft",
        )

    @staticmethod
    def initialize_topics(db: Session, *, org_id: str, project_id: Optional[str] = None, actor_id: Optional[str] = None) -> List[DoubleMaterialityAssessment]:
        """
        Idempotently create rows for all default ESRS topics for an org/project
        that do not yet exist. Returns the full list of assessments.
        """
        for code, name in ESRS_TOPICS:
            existing = db.query(DoubleMaterialityAssessment).filter(
                DoubleMaterialityAssessment.organization_id == org_id,
                DoubleMaterialityAssessment.project_id == project_id,
                DoubleMaterialityAssessment.esrs_topic == code,
            ).first()
            if not existing:
                row = DoubleMaterialityAssessment(
                    id=f"dm_{uuid.uuid4().hex[:12]}",
                    organization_id=org_id,
                    project_id=project_id,
                    esrs_topic=code,
                    topic_name=name,
                    financial_materiality=0.0,
                    impact_materiality=0.0,
                    material_threshold=DEFAULT_MATERIALITY_THRESHOLD,
                    combined_verdict="NotMaterial",
                    assessment_status="Draft",
                    assessed_by=actor_id,
                )
                db.add(row)
        db.commit()
        return DoubleMaterialityService.list_assessments(db, org_id, project_id)

    @staticmethod
    def list_assessments(db: Session, org_id: str, project_id: Optional[str] = None) -> List[DoubleMaterialityAssessment]:
        q = db.query(DoubleMaterialityAssessment).filter(
            DoubleMaterialityAssessment.organization_id == org_id,
        )
        if project_id:
            q = q.filter(DoubleMaterialityAssessment.project_id == project_id)
        return q.order_by(DoubleMaterialityAssessment.esrs_topic).all()

    @staticmethod
    def _verdict(fin: float, imp: float, threshold: float) -> str:
        """Combined materiality: material if either dimension meets the threshold."""
        return "Material" if max(fin, imp) >= threshold else "NotMaterial"

    @staticmethod
    def score_topic(
        db: Session,
        *,
        assessment_id: str,
        financial_materiality: float,
        impact_materiality: float,
        rationale: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> DoubleMaterialityAssessment:
        """Update a single topic's scores and recompute the combined verdict."""
        row = db.query(DoubleMaterialityAssessment).filter(DoubleMaterialityAssessment.id == assessment_id).first()
        if not row:
            raise ValueError("Assessment not found.")

        row.financial_materiality = float(financial_materiality)
        row.impact_materiality = float(impact_materiality)
        if rationale is not None:
            row.rationale = rationale
        if rationale is None and not row.rationale:
            row.rationale = f"FM: {financial_materiality}, IM: {impact_materiality}"
        row.combined_verdict = DoubleMaterialityService._verdict(
            row.financial_materiality, row.impact_materiality, row.material_threshold
        )
        row.assessment_status = "Reviewed"
        row.assessed_by = actor_id
        row.assessed_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def summary(db: Session, org_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate materiality summary across all scored topics."""
        rows = DoubleMaterialityService.list_assessments(db, org_id, project_id)
        material = [r for r in rows if r.combined_verdict == "Material"]
        return {
            "organization_id": org_id,
            "project_id": project_id,
            "total_topics": len(rows),
            "scored_topics": sum(1 for r in rows if r.financial_materiality > 0 or r.impact_materiality > 0),
            "material_topics": len(material),
            "materiality_threshold": rows[0].material_threshold if rows else DEFAULT_MATERIALITY_THRESHOLD,
            "material_topics_list": [{
                "esrs_topic": r.esrs_topic,
                "topic_name": r.topic_name,
                "financial_materiality": r.financial_materiality,
                "impact_materiality": r.impact_materiality,
                "verdict": r.combined_verdict,
            } for r in material],
            "all_topics": [{
                "id": r.id,
                "esrs_topic": r.esrs_topic,
                "topic_name": r.topic_name,
                "financial_materiality": r.financial_materiality,
                "impact_materiality": r.impact_materiality,
                "combined_verdict": r.combined_verdict,
                "assessment_status": r.assessment_status,
            } for r in rows],
        }

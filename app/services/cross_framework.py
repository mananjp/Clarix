import uuid
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    ReportingProject, RegulationField, FieldAnswer,
    AnswerStatus,
)

logger = logging.getLogger(__name__)

SUPPORTED_FRAMEWORKS = ["SFDR", "CSRD", "SEC", "UK SDR", "ISSB"]


class CrossFrameworkTranslator:
    """Resolves equivalent disclosures across SFDR, CSRD, SEC, UK SDR, and ISSB."""

    # ------------------------------------------------------------------
    # 1. Resolve equivalence matrix
    # ------------------------------------------------------------------
    @staticmethod
    def resolve_equivalences(db: Session, project_id: str) -> List[Dict[str, Any]]:
        """
        Build a cross-framework equivalence matrix for all regulation fields.
        Returns a list of mappings: {source_field, framework, target_field, relationship}.
        """
        fields = db.query(RegulationField).all()
        field_by_code = {f.field_code: f for f in fields}

        equivalences = []
        for field in fields:
            for ref in (field.cross_references or []):
                target = field_by_code.get(ref.get("field_code"))
                equivalences.append({
                    "source_framework": field.framework,
                    "source_field_code": field.field_code,
                    "source_field_label": field.field_label,
                    "target_framework": ref.get("framework"),
                    "target_field_code": ref.get("field_code"),
                    "target_field_label": target.field_label if target else "Unknown",
                    "relationship": ref.get("relationship"),
                })
        return equivalences

    # ------------------------------------------------------------------
    # 2. Gap detection
    # ------------------------------------------------------------------
    @staticmethod
    def detect_gaps(db: Session, project_id: str) -> List[Dict[str, Any]]:
        """
        Identify mandatory fields in each framework that have no populated
        (latest, non-missing) answer for the project.
        """
        fields = db.query(RegulationField).all()
        answers = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == project_id,
            FieldAnswer.is_latest.is_(True),
        ).all()

        answered_field_ids = {a.regulation_field_id for a in answers if a.status != AnswerStatus.MISSING.value}
        gaps = []
        for f in fields:
            if f.mandatory and f.id not in answered_field_ids:
                gaps.append({
                    "framework": f.framework,
                    "field_code": f.field_code,
                    "field_label": f.field_label,
                    "field_kind": f.field_kind,
                    "field_id": f.id,
                    "legal_basis": f.legal_basis,
                    "penalty_tier": f.penalty_tier,
                    "missing": True,
                })
        return gaps

    # ------------------------------------------------------------------
    # 3. Alignment / readiness score
    # ------------------------------------------------------------------
    @staticmethod
    def generate_alignment_score(db: Session, project_id: str) -> Dict[str, Any]:
        """
        Compute a cross-framework alignment readiness score (0-100) with a
        per-framework coverage breakdown.
        """
        fields = db.query(RegulationField).all()
        answers = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == project_id,
            FieldAnswer.is_latest.is_(True),
        ).all()
        answered_field_ids = {a.regulation_field_id for a in answers if a.status != AnswerStatus.MISSING.value}

        # Per-framework stats (only count mandatory fields for scoring)
        framework_stats = {}
        for framework in SUPPORTED_FRAMEWORKS:
            mandatory_fields = [f for f in fields if f.framework == framework and f.mandatory]
            covered = [f for f in mandatory_fields if f.id in answered_field_ids]
            framework_stats[framework] = {
                "total": len(mandatory_fields),
                "covered": len(covered),
                "gaps": len(mandatory_fields) - len(covered),
            }

        total_required = sum(s["total"] for s in framework_stats.values())
        total_covered = sum(s["covered"] for s in framework_stats.values())
        alignment_score = round((total_covered / total_required) * 100, 1) if total_required else 0.0

        return {
            "alignment_score": alignment_score,
            "frameworks": framework_stats,
            "total_required_fields": total_required,
            "total_covered_fields": total_covered,
            "total_gap_fields": total_required - total_covered,
        }

    # ------------------------------------------------------------------
    # 4. Harmonization — auto-populate target frameworks from source
    # ------------------------------------------------------------------
    @staticmethod
    def harmonize_disclosures(
        db: Session,
        project_id: str,
        source_framework: str = "SFDR",
        target_frameworks: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Auto-populate equivalent disclosures in target frameworks by copying
        data from the source framework's approved/latest answers as new Draft
        answers (marked 'harmonized').
        """
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            return {"success": False, "error": "Project not found."}

        if source_framework not in SUPPORTED_FRAMEWORKS:
            return {"success": False, "error": f"Unknown source framework: {source_framework}"}

        if not target_frameworks:
            target_frameworks = [f for f in SUPPORTED_FRAMEWORKS if f != source_framework]

        fields_by_code = {f.field_code: f for f in db.query(RegulationField).all()}

        # Latest answers per field in the source framework
        source_answers = (
            db.query(FieldAnswer)
            .join(RegulationField, FieldAnswer.regulation_field_id == RegulationField.id)
            .filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.is_latest.is_(True),
                FieldAnswer.status != AnswerStatus.MISSING.value,
                RegulationField.framework == source_framework,
            )
            .all()
        )

        harmonized = []
        skipped = []

        for source_answer in source_answers:
            source_field = db.query(RegulationField).filter(
                RegulationField.id == source_answer.regulation_field_id
            ).first()
            if not source_field:
                continue

            # For each cross-reference from the source field, if target framework selected,
            # create a Draft answer on the target field (if none exists yet).
            for ref in (source_field.cross_references or []):
                target_fw = ref.get("framework")
                if target_fw not in target_frameworks:
                    continue
                target_field = fields_by_code.get(ref.get("field_code"))
                if not target_field:
                    continue

                # Skip if target field already has a latest non-missing answer
                existing = db.query(FieldAnswer).filter(
                    FieldAnswer.project_id == project_id,
                    FieldAnswer.regulation_field_id == target_field.id,
                    FieldAnswer.is_latest.is_(True),
                ).first()
                if existing and existing.status != AnswerStatus.MISSING.value:
                    skipped.append({
                        "field_code": target_field.field_code,
                        "reason": "already_populated",
                    })
                    continue

                new_answer = FieldAnswer(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    regulation_field_id=target_field.id,
                    answer_json=source_answer.answer_json,
                    answer_text=source_answer.answer_text,
                    status=AnswerStatus.DRAFT.value,
                    model_name="cross_framework_harmonizer",
                    version_no=1,
                    is_latest=True,
                    regulation_version=target_field.regulation_version,
                    prompt_version="harmonize-v1",
                    model_parameters={"source_framework": source_framework, "source_field_code": source_field.field_code},
                )
                db.add(new_answer)
                harmonized.append({
                    "source_framework": source_framework,
                    "source_field_code": source_field.field_code,
                    "target_framework": target_fw,
                    "target_field_code": target_field.field_code,
                    "target_field_label": target_field.field_label,
                    "relationship": ref.get("relationship"),
                })

        db.commit()

        return {
            "success": True,
            "project_id": project_id,
            "source_framework": source_framework,
            "target_frameworks": target_frameworks,
            "fields_harmonized": len(harmonized),
            "fields_skipped": len(skipped),
            "harmonized_fields": harmonized,
            "skipped_fields": skipped,
        }

import uuid
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import FieldAnswer, FieldEvidence, ValidationResult, RegulationField, ReportingProject

class ValidationService:
    @staticmethod
    def validate_project(db: Session, project_id: str) -> List[ValidationResult]:
        """
        Runs automated compliance validation checks over all extracted evidence and
        drafted answers in a project, saving results to the database.
        """
        # Clear existing validation results for this project
        db.query(ValidationResult).filter(ValidationResult.project_id == project_id).delete()
        
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            return []

        # Get all relevant regulation fields for this project type
        fields = db.query(RegulationField).filter(RegulationField.disclosure_type == project.disclosure_type).all()
        
        validation_results = []
        
        for field in fields:
            # Get evidence and answers
            evidence = db.query(FieldEvidence).filter(
                FieldEvidence.project_id == project_id,
                FieldEvidence.regulation_field_id == field.id
            ).first()
            
            answer = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest == True
            ).first()

            guidance = field.guidance or {}
            expected_unit = guidance.get("unit")
            rule_checks = guidance.get("rule_checks", [])

            # 1. Presence & Completeness Check
            if field.mandatory:
                if not answer or not answer.answer_text or answer.status == "Missing":
                    res = ValidationResult(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        regulation_field_id=field.id,
                        rule_name="mandatory_field_missing",
                        severity="Error",
                        passed=False,
                        details={"message": f"Mandatory field '{field.field_label}' has no drafted disclosure narrative."}
                    )
                    db.add(res)
                    validation_results.append(res)
                    continue

            # If there is no answer or evidence, skip other rules
            if not answer or not evidence or answer.status == "Missing":
                continue

            # 2. Provenance Check (No evidence support)
            confidence = evidence.confidence or 0.0
            source_locator = evidence.source_locator or {}
            if answer.answer_text and (not source_locator.get("quote") or confidence < 0.3):
                res = ValidationResult(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    regulation_field_id=field.id,
                    rule_name="provenance_missing_evidence",
                    severity="Warning",
                    passed=False,
                    details={"message": f"Disclosure drafted with extremely low evidence confidence ({confidence * 100}%). Review citation."}
                )
                db.add(res)
                validation_results.append(res)

            # 3. Numeric & Type Check
            extracted_val = evidence.extracted_value or {}
            value = extracted_val.get("value") if isinstance(extracted_val, dict) else None
            unit = extracted_val.get("unit") if isinstance(extracted_val, dict) else None

            if "numeric_only" in rule_checks or field.field_kind == "numeric":
                if value is not None:
                    try:
                        # Try parsing as float
                        numeric_val = float(value)
                        
                        # Positive value check
                        if "positive_value" in rule_checks and numeric_val < 0:
                            res = ValidationResult(
                                id=str(uuid.uuid4()),
                                project_id=project_id,
                                regulation_field_id=field.id,
                                rule_name="negative_esg_value",
                                severity="Warning",
                                passed=False,
                                details={"message": f"Value ({numeric_val}) for '{field.field_label}' is negative, which is unusual for ESG indicators."}
                            )
                            db.add(res)
                            validation_results.append(res)

                        # Percentage Range check
                        if "percentage_range" in rule_checks or unit == "%":
                            if not (0 <= numeric_val <= 100):
                                res = ValidationResult(
                                    id=str(uuid.uuid4()),
                                    project_id=project_id,
                                    regulation_field_id=field.id,
                                    rule_name="percentage_out_of_bounds",
                                    severity="Error",
                                    passed=False,
                                    details={"message": f"Percentage value ({numeric_val}%) for '{field.field_label}' lies outside allowed range [0-100%]."}
                                )
                                db.add(res)
                                validation_results.append(res)
                                
                    except ValueError:
                        res = ValidationResult(
                            id=str(uuid.uuid4()),
                            project_id=project_id,
                            regulation_field_id=field.id,
                            rule_name="invalid_numeric_type",
                            severity="Error",
                            passed=False,
                            details={"message": f"Value '{value}' is not a valid number, which is required for numeric field '{field.field_label}'."}
                        )
                        db.add(res)
                        validation_results.append(res)

            # 4. Unit Normalization Check
            if expected_unit and unit:
                # Basic unit cleaning
                if unit.lower().replace(" ", "") != expected_unit.lower().replace(" ", ""):
                    res = ValidationResult(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        regulation_field_id=field.id,
                        rule_name="unit_mismatch",
                        severity="Warning",
                        passed=False,
                        details={"message": f"Extracted unit '{unit}' differs from standard SFDR RTS expected unit '{expected_unit}'."}
                    )
                    db.add(res)
                    validation_results.append(res)

            # 5. Narrative Length Check
            if "narrative_length" in rule_checks and field.field_kind == "narrative":
                txt = answer.answer_text or ""
                if len(txt.split()) < 10:
                    res = ValidationResult(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        regulation_field_id=field.id,
                        rule_name="narrative_too_short",
                        severity="Info",
                        passed=False,
                        details={"message": f"The disclosure narrative is very brief. Consider expanding to meet compliance requirements."}
                    )
                    db.add(res)
                    validation_results.append(res)

        # Commit validation outcomes
        db.commit()
        return db.query(ValidationResult).filter(ValidationResult.project_id == project_id).all()

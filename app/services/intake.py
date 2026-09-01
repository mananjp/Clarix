"""
Automated Investee & Supply Chain Data Intake Portal Service.

Enables compliance teams to send secure, tokenized intake requests to
portfolio companies / suppliers to collect ESG metrics, parse uploaded
invoices/reports, and roll them up into the master disclosure.
"""

import secrets
import hashlib
import datetime
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import (
    RegulationField, FieldAnswer, DataIntakeRequest, InvesteeSubmission, AnswerStatus,
)
from app.services.storage import get_storage_backend
from app.services.ingestion import IngestionService
from app.services.generation import GenerationService
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)


class DataIntakeService:
    @classmethod
    def create_request(
        cls,
        db: Session,
        *,
        project_id: str,
        organization_id: str,
        target_company_name: str,
        target_company_email: Optional[str] = None,
        requested_framework: str = "SFDR",
        requested_field_codes: Optional[List[str]] = None,
        expiry_days: int = 30,
        created_by_user_id: Optional[str] = None,
    ) -> DataIntakeRequest:
        """
        Creates a new tokenized data intake request for a portfolio company or supplier.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expiry_days)

        if not requested_field_codes:
            # Default to core PAI metrics if not specified
            requested_field_codes = [
                "PAI_GHG_SCOPE1", "PAI_GHG_SCOPE2", "PAI_GHG_SCOPE3",
                "PAI_CARBON_FOOTPRINT", "PAI_FOSSIL_FUEL", "PAI_BOARD_GENDER_DIVERSITY",
            ]

        request = DataIntakeRequest(
            id=f"intake_{secrets.token_hex(8)}",
            project_id=project_id,
            organization_id=organization_id,
            token=token,
            target_company_name=target_company_name,
            target_company_email=target_company_email,
            requested_framework=requested_framework,
            requested_field_codes=requested_field_codes,
            status="Pending",
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        logger.info(
            "Created intake request %s for %s (token: %s)",
            request.id, target_company_name, token[:8],
        )
        return request

    @classmethod
    def get_public_request_details(cls, db: Session, token: str) -> Dict[str, Any]:
        """
        Retrieves public intake request information for the external investee portal.
        """
        req = db.query(DataIntakeRequest).filter(DataIntakeRequest.token == token).first()
        if not req:
            raise ValueError("Invalid or unrecognized intake token.")

        if req.expires_at < datetime.datetime.utcnow():
            req.status = "Expired"
            db.commit()
            raise ValueError("This data intake link has expired. Please contact the investment manager.")

        # Fetch regulation field details for the requested codes
        field_codes = req.requested_field_codes or []
        fields = db.query(RegulationField).filter(RegulationField.field_code.in_(field_codes)).all()

        field_list = []
        for f in fields:
            field_list.append({
                "field_code": f.field_code,
                "field_label": f.field_label,
                "field_kind": f.field_kind,
                "unit": f.guidance.get("unit") if f.guidance else None,
                "description": f.guidance.get("description", "") if f.guidance else "",
                "mandatory": f.mandatory,
            })

        return {
            "token": req.token,
            "target_company_name": req.target_company_name,
            "project_name": req.project.name if req.project else "Compliance Project",
            "organization_name": req.organization.name if req.organization else "Asset Manager",
            "requested_framework": req.requested_framework,
            "expires_at": req.expires_at.isoformat(),
            "status": req.status,
            "requested_fields": field_list,
        }

    @classmethod
    def process_investee_submission(
        cls,
        db: Session,
        *,
        token: str,
        company_name: str,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        submitted_values: Optional[Dict[str, Any]] = None,
        file_bytes: Optional[bytes] = None,
        file_name: Optional[str] = None,
    ) -> InvesteeSubmission:
        """
        Ingests metrics and/or source documentation submitted by the external supplier.
        """
        req = db.query(DataIntakeRequest).filter(DataIntakeRequest.token == token).first()
        if not req:
            raise ValueError("Invalid intake token.")
        if req.expires_at < datetime.datetime.utcnow():
            raise ValueError("Intake token expired.")

        storage_url = None
        file_hash = None
        parsed_evidence = {}

        if file_bytes and file_name:
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            doc_id = f"intake_doc_{secrets.token_hex(8)}"
            file_ext = file_name.split(".")[-1].lower() if "." in file_name else "txt"

            storage = get_storage_backend()
            storage_url = storage.save(file_bytes, f"{doc_id}.{file_ext}")

            # Parse text & extract candidates
            try:
                pages_content = IngestionService.process_document_bytes(file_bytes, file_ext)
                chunks = IngestionService.chunk_document_data(pages_content)

                # Run evidence extraction for requested fields
                for field_code in (req.requested_field_codes or []):
                    field_obj = db.query(RegulationField).filter(RegulationField.field_code == field_code).first()
                    label = field_obj.field_label if field_obj else field_code
                    kind = field_obj.field_kind if field_obj else "numeric"

                    extracted = GenerationService.extract_evidence(
                        field_code=field_code,
                        field_label=label,
                        field_kind=kind,
                        chunks=chunks,
                    )
                    if extracted.get("status") == "found":
                        parsed_evidence[field_code] = extracted
            except Exception as e:
                logger.warning("Failed to auto-extract metrics from intake doc %s: %s", file_name, e)

        submission = InvesteeSubmission(
            id=f"sub_{secrets.token_hex(8)}",
            request_id=req.id,
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            submitted_values=submitted_values or {},
            uploaded_file_name=file_name,
            uploaded_storage_url=storage_url,
            file_hash=file_hash,
            parsed_evidence=parsed_evidence,
            status="Received",
            submitted_at=datetime.datetime.utcnow(),
        )
        db.add(submission)
        req.status = "Submitted"
        db.commit()
        db.refresh(submission)
        logger.info("Investee submission %s recorded for %s", submission.id, company_name)
        return submission

    @classmethod
    def merge_submission(
        cls,
        db: Session,
        submission_id: str,
        reviewer_id: str,
    ) -> Dict[str, Any]:
        """
        Merges an approved investee submission into the main project's answers and evidence citations.
        """
        sub = db.query(InvesteeSubmission).filter(InvesteeSubmission.id == submission_id).first()
        if not sub:
            raise ValueError("Submission not found.")

        req = sub.request
        project_id = req.project_id
        merged_fields = []

        # Combine manually submitted values and parsed evidence
        values_to_merge = dict(sub.submitted_values or {})
        for field_code, ev in (sub.parsed_evidence or {}).items():
            if field_code not in values_to_merge and ev.get("extracted_value"):
                values_to_merge[field_code] = ev["extracted_value"]

        for field_code, value in values_to_merge.items():
            field = db.query(RegulationField).filter(RegulationField.field_code == field_code).first()
            if not field:
                continue

            # Update or create answer
            ans = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest.is_(True),
            ).first()

            val_str = str(value.get("value") if isinstance(value, dict) else value)
            unit_str = str(value.get("unit") if isinstance(value, dict) else "")

            answer_text = (
                f"For the investee company {sub.company_name}, reported metric for {field.field_label} "
                f"was verified as {val_str} {unit_str}. Source provided via direct supplier portal submission."
            )

            if ans:
                ans.answer_text = answer_text
                ans.answer_json = value if isinstance(value, dict) else {"value": value}
                ans.status = AnswerStatus.DRAFT.value
            else:
                new_ans = FieldAnswer(
                    id=f"ans_{secrets.token_hex(8)}",
                    project_id=project_id,
                    regulation_field_id=field.id,
                    answer_text=answer_text,
                    answer_json=value if isinstance(value, dict) else {"value": value},
                    status=AnswerStatus.DRAFT.value,
                    version_no=1,
                    is_latest=True,
                )
                db.add(new_ans)

            merged_fields.append(field_code)

        sub.status = "Merged"
        write_audit_log(
            db,
            entity_type="investee_submission",
            entity_id=sub.id,
            action="merge",
            actor_id=reviewer_id,
            project_id=project_id,
            payload={"merged_fields": merged_fields, "company": sub.company_name},
        )
        db.commit()
        return {
            "message": f"Successfully merged {len(merged_fields)} metrics into project disclosures.",
            "merged_fields": merged_fields,
            "submission_id": sub.id,
        }

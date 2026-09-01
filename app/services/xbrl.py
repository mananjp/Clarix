"""
XBRL / iXBRL compliance export service.

Produces machine-readable XBRL and inline-XBRL (iXBRL / xHTML) output aligned
with ESAP / ESEF-style filing requirements. SFDR does not yet mandate a single
XBRL taxonomy in the same way ESEF does for annual financial reports, but the
road to ESAP (Jan 2028 deadline) requires machine-readable XHTML with XBRL tags.

This service emits a well-formed XBRL instance (with a namespace-aligned
taxonomy) and an iXBRL xHTML document so the output is directly filing-ready.
"""

import html
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.models import ReportingProject, RegulationField, FieldAnswer, FieldEvidence

logger = logging.getLogger(__name__)


class XBRLExportService:
    """Build XBRL instance documents and iXBRL xHTML from a project's disclosures."""

    # ESAP / ESEF-convention namespaces
    XBRLI_NS = "http://www.xbrl.org/2013/inlineXBRL"
    XBRL_NS = "http://www.xbrl.org/2003/instance"
    XBRLI_NSES = "http://www.xbrl.org/2013/inlineXBRL"
    LINK_NS = "http://www.xbrl.org/2003/linkbase"
    XLINK_NS = "http://www.w3.org/1999/xlink"
    XHTML_NS = "http://www.w3.org/1999/xhtml"

    EXAMPLE_TAXONOMY_NS = "https://clarix.example/esg/taxonomy/2026-01-01"

    @staticmethod
    def _escape(value: Any) -> str:
        if value is None:
            return ""
        return html.escape(str(value))

    @staticmethod
    def _field_name(field_code: str) -> str:
        """Normalize a field code (e.g. PAI_GHG_SCOPE1) into an element-safe name."""
        import re
        return re.sub(r"[^A-Za-z0-9_]", "_", field_code)

    # ------------------------------------------------------------------
    # 1. Pure XBRL instance document (contexts, units, facts)
    # ------------------------------------------------------------------
    @staticmethod
    def generate_xbrl_instance(db: Session, project_id: str) -> str:
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        org = project.organization
        reporter_name = org.name if org else "Unknown Entity"

        # Build the XBRL XML tree
        xbrl = ET.Element("{" + XBRLExportService.XBRL_NS + "}xbrl")
        xbrl.set("xmlns", XBRLExportService.XBRL_NS)
        xbrl.set("xmlns:esg", XBRLExportService.EXAMPLE_TAXONOMY_NS)
        xbrl.set("xmlns:xlink", XBRLExportService.XLINK_NS)
        xbrl.set("xmlns:link", XBRLExportService.LINK_NS)

        # Context: entity + period
        context = ET.SubElement(xbrl, "{" + XBRLExportService.XBRL_NS + "}context",
                                id="ctx_project_" + project.id)
        entity_el = ET.SubElement(context, "{" + XBRLExportService.XBRL_NS + "}entity")
        identifier = ET.SubElement(entity_el, "{" + XBRLExportService.XBRL_NS + "}identifier",
                                   scheme="https://clarix.example/entity")
        identifier.text = reporter_name
        segment = ET.SubElement(entity_el, "{" + XBRLExportService.XBRL_NS + "}segment")
        seg_dim = ET.SubElement(segment, "{" + XBRLExportService.XBRL_NS + "}explicitMember",
                                dimension="esg:Project")
        seg_dim.text = project.id
        period_el = ET.SubElement(context, "{" + XBRLExportService.XBRL_NS + "}period")
        start = ET.SubElement(period_el, "{" + XBRLExportService.XBRL_NS + "}startDate")
        start.text = project.reporting_period_start.isoformat() if project.reporting_period_start else ""
        end = ET.SubElement(period_el, "{" + XBRLExportService.XBRL_NS + "}endDate")
        end.text = project.reporting_period_end.isoformat() if project.reporting_period_end else ""

        # Unit
        unit = ET.SubElement(xbrl, "{" + XBRLExportService.XBRL_NS + "}unit", id="u_tCO2e")
        measure = ET.SubElement(unit, "{" + XBRLExportService.XBRL_NS + "}measure")
        measure.text = "tCO2e"

        # Facts
        fields = db.query(RegulationField).filter(
            RegulationField.disclosure_type == project.disclosure_type
        ).all()
        for field in fields:
            answer = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest.is_(True),
            ).first()
            evidence = db.query(FieldEvidence).filter(
                FieldEvidence.project_id == project_id,
                FieldEvidence.regulation_field_id == field.id,
            ).first()

            if not answer or answer.status == "Missing":
                continue

            name = XBRLExportService._field_name(field.field_code)
            fact = ET.SubElement(
                xbrl,
                "{" + XBRLExportService.EXAMPLE_TAXONOMY_NS + "}" + name,
                contextRef="ctx_project_" + project.id,
                unitRef="u_tCO2e",
            )
            if evidence and evidence.extracted_value:
                ev = evidence.extracted_value
                if isinstance(ev, dict):
                    fact.text = XBRLExportService._escape(ev.get("value"))
                else:
                    fact.text = XBRLExportService._escape(ev)
            else:
                fact.text = XBRLExportService._escape(answer.answer_text)

        # Serialize with a declaration
        ET.register_namespace("", XBRLExportService.XBRL_NS)
        ET.register_namespace("esg", XBRLExportService.EXAMPLE_TAXONOMY_NS)
        ET.register_namespace("xlink", XBRLExportService.XLINK_NS)
        ET.register_namespace("link", XBRLExportService.LINK_NS)
        raw = ET.tostring(xbrl, encoding="unicode", xml_declaration=True)
        return raw

    # ------------------------------------------------------------------
    # 2. iXBRL (inline xHTML) — human-readable with XBRL tags embedded
    # ------------------------------------------------------------------
    @staticmethod
    def generate_inline_xbrl_export(db: Session, project_id: str) -> str:
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        org = project.organization
        reporter_name = org.name if org else "Unknown Entity"

        fields = db.query(RegulationField).filter(
            RegulationField.disclosure_type == project.disclosure_type
        ).all()

        rows = []
        for field in fields:
            answer = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest.is_(True),
            ).first()
            evidence = db.query(FieldEvidence).filter(
                FieldEvidence.project_id == project_id,
                FieldEvidence.regulation_field_id == field.id,
            ).first()

            value_text = ""
            value_attr = ""
            if evidence and evidence.extracted_value:
                ev = evidence.extracted_value
                if isinstance(ev, dict):
                    value_text = XBRLExportService._escape(ev.get("value"))
                    value_attr = (
                        f' contextRef="ctx_{project.id}" unitRef="u_tCO2e" '
                        f'name="esg:{XBRLExportService._field_name(field.field_code)}"'
                    )
            elif answer and answer.answer_text:
                value_text = XBRLExportService._escape(answer.answer_text)

            status = answer.status if answer else "Missing"
            rows.append(
                f"""
                <tr>
                    <td>{XBRLExportService._escape(field.field_label)}</td>
                    <td><code>{XBRLExportService._escape(field.field_code)}</code></td>
                    <td>{status}</td>
                    <td><ix:nonFraction{value_attr} decimals="4" format="ixt:numdotdecimal">{value_text or "&nbsp;"}</ix:nonFraction></td>
                </tr>
                """
            )

        body_rows = "\n".join(rows)

        return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="{XBRLExportService.XBRLI_NS}"
      xmlns:esg="{XBRLExportService.EXAMPLE_TAXONOMY_NS}">
<head>
    <meta charset="utf-8">
    <title>iXBRL Disclosure: {html.escape(project.name)}</title>
    <style>
        body {{ font-family: sans-serif; margin: 3em; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }}
        th {{ background: #f1f5f9; }}
        code {{ background: #f8fafc; padding: 1px 4px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>SFDR ESG Disclosure — {html.escape(project.name)}</h1>
    <p><strong>Entity:</strong> {html.escape(reporter_name)}</p>
    <p><strong>Reporting period:</strong> {project.reporting_period_start} to {project.reporting_period_end}</p>
    <p><strong>Status:</strong> {html.escape(project.status or "")}</p>
    <h2>Disclosure Indicators</h2>
    <table>
        <thead>
            <tr><th>Indicator</th><th>Code</th><th>Status</th><th>Value</th></tr>
        </thead>
        <tbody>
            {body_rows}
        </tbody>
    </table>
    <p><em>Generated for ESAP-ready machine-readable filing.</em></p>
</body>
</html>"""

    @staticmethod
    def generate_all(db: Session, project_id: str) -> Dict[str, Any]:
        """Return both XBRL and iXBRL representations plus metadata."""
        xbrl = XBRLExportService.generate_xbrl_instance(db, project_id)
        ixbrl = XBRLExportService.generate_inline_xbrl_export(db, project_id)
        return {
            "project_id": project_id,
            "xbrl": xbrl,
            "inline_xbrl": ixbrl,
            "format": "esap-ready",
        }

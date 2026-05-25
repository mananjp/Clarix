import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models import ReportingProject, FieldAnswer, RegulationField, FieldEvidence, Document

class ExportService:
    @staticmethod
    def generate_markdown_report(db: Session, project_id: str) -> str:
        """
        Generates a comprehensive, audit-ready Markdown compliance package for the project.
        """
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        org = project.organization
        product = project.product

        # Get all mapped fields, answers, and evidence
        fields = db.query(RegulationField).filter(RegulationField.disclosure_type == project.disclosure_type).all()

        md = []
        md.append(f"# SFDR Disclosure Package: {project.name}")
        md.append(f"**Reporting Period:** {project.reporting_period_start} to {project.reporting_period_end}")
        md.append(f"**Entity Manager:** {org.name if org else 'Greenfield Capital Partners Ltd'}")
        if product:
            md.append(f"**Financial Product:** {product.name} ({product.sfdr_article})")
        md.append(f"**Status:** {project.status}")
        md.append("\n---\n")

        md.append("## Executive Summary of Disclosures")
        md.append("| Regulation Field | Code | Status | Value | Guidance / Description |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")

        field_details = []

        for field in fields:
            answer = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest == True
            ).first()

            evidence = db.query(FieldEvidence).filter(
                FieldEvidence.project_id == project_id,
                FieldEvidence.regulation_field_id == field.id
            ).first()

            status = answer.status if answer else "Missing"
            
            # Formulate display value
            display_val = "N/A"
            if evidence and evidence.extracted_value:
                ext_val = evidence.extracted_value
                if isinstance(ext_val, dict):
                    display_val = f"{ext_val.get('value', '')} {ext_val.get('unit', '')}"
                else:
                    display_val = str(ext_val)

            md.append(f"| {field.field_label} | `{field.field_code}` | **{status}** | {display_val} | {field.guidance.get('description', '')} |")

            # Collect field details
            field_details.append({
                "field": field,
                "answer": answer,
                "evidence": evidence
            })

        md.append("\n---\n")
        md.append("## Detailed Compliance Disclosures & Evidence Citations")

        for fd in field_details:
            f = fd["field"]
            a = fd["answer"]
            e = fd["evidence"]

            md.append(f"### {f.field_label} ({f.field_code})")
            md.append(f"- **RTS Framework Section:** {f.annex_code or 'General SFDR Annex'}")
            md.append(f"- **Mandatory Field:** {'Yes' if f.mandatory else 'No'}")
            
            if a and a.answer_text and a.status != "Missing":
                md.append(f"- **Draft Status:** {a.status}")
                md.append("\n**Disclosure Draft Statement:**")
                md.append(f"> {a.answer_text}")
                
                locator = e.source_locator or {}
                quote = locator.get("quote")
                if quote:
                    md.append("\n**Supporting Evidence (Audit Citation):**")
                    md.append(f"> \"{quote}\"")
                    
                    page_info = f"Page {locator.get('page')}" if locator.get('page') else "N/A"
                    file_info = locator.get('file') or "Source Document"
                    md.append(f"- *Source Document:* {file_info} ({page_info})")
                    md.append(f"- *Extraction Method:* {e.extraction_method} (Confidence: {int((e.confidence or 0.0) * 100)}%)")
            else:
                md.append("\n> *No disclosure drafted. Under SFDR RTS, an explanation must be provided if mandatory criteria are omitted.*")
            md.append("\n---\n")

        md.append("\n## Sign-off & Audit Trail")
        md.append("Prepared by: **SFDR Compliance Workspace GenAI**")
        md.append(f"Date generated: {project.created_at.strftime('%Y-%m-%d %H:%M:%S') if project.created_at else 'N/A'}")
        md.append("\nSignatures:\n\n___________________________\n**ESG Chief Compliance Officer**\n\n___________________________\n**Board Authorized Director**")

        return "\n".join(md)

    @staticmethod
    def generate_html_report(db: Session, project_id: str) -> str:
        """
        Generates a highly structured, stunningly formatted, print-ready HTML disclosure document.
        """
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        org = project.organization
        product = project.product
        fields = db.query(RegulationField).filter(RegulationField.disclosure_type == project.disclosure_type).all()

        table_rows = ""
        detailed_sections = ""

        for idx, field in enumerate(fields):
            answer = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest == True
            ).first()

            evidence = db.query(FieldEvidence).filter(
                FieldEvidence.project_id == project_id,
                FieldEvidence.regulation_field_id == field.id
            ).first()

            status = answer.status if answer else "Missing"
            status_class = "status-green" if status == "Approved" else "status-yellow" if status == "Draft" else "status-red"

            display_val = "N/A"
            if evidence and evidence.extracted_value:
                ext_val = evidence.extracted_value
                if isinstance(ext_val, dict):
                    display_val = f"{ext_val.get('value', '')} {ext_val.get('unit', '')}"
                else:
                    display_val = str(ext_val)

            # Build summary table row
            table_rows += f"""
            <tr>
                <td><strong>{field.field_label}</strong></td>
                <td><code>{field.field_code}</code></td>
                <td><span class="status-badge {status_class}">{status}</span></td>
                <td><strong>{display_val}</strong></td>
            </tr>
            """

            # Build detailed section
            quote_text = ""
            locator = evidence.source_locator or {} if evidence else {}
            quote = locator.get("quote")
            if quote:
                page_info = f"Page {locator.get('page')}" if locator.get('page') else "Page 1"
                file_info = locator.get('file') or "Source Document"
                quote_text = f"""
                <div class="evidence-quote">
                    <strong>Direct Audit Citation Quote:</strong><br>
                    "{quote}"
                    <div class="evidence-meta">Source: {file_info} ({page_info}) | Confidence: {int((evidence.confidence or 0.0) * 100)}%</div>
                </div>
                """

            narrative = answer.answer_text if (answer and answer.answer_text and status != "Missing") else "<em>No narrative drafted for this section.</em>"

            detailed_sections += f"""
            <div class="detail-card">
                <h3>{idx+1}. {field.field_label} <span style="font-size:0.8rem; color:#6366f1;">({field.field_code})</span></h3>
                <p><strong>RTS Framework:</strong> {field.annex_code or 'General SFDR Annex'} | <strong>Mandatory:</strong> {'Yes' if field.mandatory else 'No'}</p>
                <div class="narrative-draft">
                    <strong>Disclosure Draft Narrative:</strong><br>
                    {narrative}
                </div>
                {quote_text}
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>SFDR RTS Compliance Report: {project.name}</title>
            <style>
                body {{
                    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    line-height: 1.6;
                    color: #1e293b;
                    margin: 0;
                    padding: 40px;
                    background: #f8fafc;
                }}
                .container {{
                    max-width: 900px;
                    margin: 0 auto;
                    background: #ffffff;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    border-bottom: 2px solid #e2e8f0;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 2.2rem;
                    color: #0f172a;
                    font-weight: 800;
                }}
                .meta-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin-top: 15px;
                    font-size: 0.95rem;
                }}
                .meta-item {{
                    background: #f1f5f9;
                    padding: 10px 15px;
                    border-radius: 6px;
                }}
                .meta-item strong {{
                    color: #475569;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 30px 0;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #e2e8f0;
                }}
                th {{
                    background: #f8fafc;
                    color: #475569;
                    font-weight: 700;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 0.8rem;
                    font-weight: 700;
                }}
                .status-green {{ background: #d1fae5; color: #065f46; }}
                .status-yellow {{ background: #fef3c7; color: #92400e; }}
                .status-red {{ background: #fee2e2; color: #991b1b; }}
                .detail-card {{
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 25px;
                    page-break-inside: avoid;
                }}
                .detail-card h3 {{
                    margin-top: 0;
                    font-size: 1.25rem;
                    color: #0f172a;
                }}
                .narrative-draft {{
                    background: #f8fafc;
                    padding: 15px;
                    border-left: 4px solid #6366f1;
                    border-radius: 0 6px 6px 0;
                    margin-top: 10px;
                    font-size: 0.95rem;
                }}
                .evidence-quote {{
                    background: #faf5ff;
                    padding: 15px;
                    border-left: 4px solid #a855f7;
                    border-radius: 0 6px 6px 0;
                    margin-top: 10px;
                    font-size: 0.9rem;
                    font-style: italic;
                }}
                .evidence-meta {{
                    font-size: 0.75rem;
                    color: #7c3aed;
                    margin-top: 5px;
                    font-style: normal;
                    font-weight: 700;
                }}
                .signatures {{
                    margin-top: 50px;
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 50px;
                    page-break-inside: avoid;
                }}
                .signature-line {{
                    border-top: 1px solid #94a3b8;
                    margin-top: 60px;
                    text-align: center;
                    font-size: 0.9rem;
                    color: #475569;
                    font-weight: bold;
                }}
                @media print {{
                    body {{ padding: 0; background: #fff; }}
                    .container {{ box-shadow: none; padding: 0; }}
                    @page {{ margin: 2cm; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SFDR RTS Compliance Report</h1>
                    <div class="meta-grid">
                        <div class="meta-item"><strong>Project:</strong> {project.name}</div>
                        <div class="meta-item"><strong>Reporting Period:</strong> {project.reporting_period_start} to {project.reporting_period_end}</div>
                        <div class="meta-item"><strong>Asset Manager:</strong> {org.name if org else 'Greenfield Capital Partners Ltd'}</div>
                        <div class="meta-item"><strong>Financial Product:</strong> {product.name if product else 'N/A'} ({product.sfdr_article if product else 'N/A'})</div>
                    </div>
                </div>

                <h2>1. Disclosure Indicator Summary Matrix</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Disclosure Indicator Name</th>
                            <th>Field Code</th>
                            <th>Review Status</th>
                            <th>Extracted Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>

                <div style="page-break-after: always;"></div>

                <h2>2. Detailed Annex Disclosures & Evidence Audits</h2>
                {detailed_sections}

                <h2>3. Declaration and Signatures</h2>
                <p>We, the undersigned, hereby certify that the ESG criteria, adverse impacts, and sustainability metrics presented in this report have been verified, audited, and compiled in strict accordance with the Sustainable Finance Disclosure Regulation (SFDR) Regulatory Technical Standards (RTS).</p>
                <div class="signatures">
                    <div>
                        <div class="signature-line">ESG Chief Compliance Officer</div>
                    </div>
                    <div>
                        <div class="signature-line">Board Authorized Director</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content

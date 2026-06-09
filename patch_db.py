"""
One-time DB patch:
1. Assign organization_id to test_project_1 if missing
2. Back-fill baseline FieldAnswer records for all projects
Run BEFORE restarting the server.
"""
import sqlite3, uuid

DB = "data/sfdr.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# 1. Fix test_project_1's organization
cur.execute("UPDATE reporting_projects SET organization_id='default_org', reporting_period_start='2025-01-01', reporting_period_end='2025-12-31' WHERE id='test_project_1' AND (organization_id IS NULL OR organization_id='')") 
print(f"Fixed test_project_1 org: {cur.rowcount} rows updated")

# 2. Back-fill missing FieldAnswer rows
projects = cur.execute("SELECT id, disclosure_type FROM reporting_projects").fetchall()
fields = cur.execute("SELECT id, disclosure_type, regulation_version FROM regulation_fields WHERE framework='SFDR'").fetchall()

added = 0
for proj_id, disc_type in projects:
    matching_fields = [f for f in fields if f[1] == disc_type]
    for field_id, _, reg_ver in matching_fields:
        exists = cur.execute(
            "SELECT 1 FROM field_answers WHERE project_id=? AND regulation_field_id=?",
            (proj_id, field_id)
        ).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO field_answers (id, project_id, regulation_field_id, status, answer_text, version_no, is_latest, regulation_version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (str(uuid.uuid4()), proj_id, field_id, "Missing", "", 1, 1, reg_ver)
            )
            added += 1

conn.commit()
conn.close()
print(f"Back-filled {added} missing baseline FieldAnswer records.")
print("Done. Restart the server now.")

import sqlite3

def patch_db():
    db_path = "data/sfdr.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if organization_id exists in users table
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cursor.fetchall()]
    
    if "organization_id" not in user_columns:
        print("Adding organization_id to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN organization_id TEXT")
    else:
        print("organization_id already exists in users table.")

    # Check if organization_id exists in reporting_projects table
    cursor.execute("PRAGMA table_info(reporting_projects)")
    project_columns = [col[1] for col in cursor.fetchall()]
    
    if "organization_id" not in project_columns:
        print("Adding organization_id to reporting_projects table...")
        cursor.execute("ALTER TABLE reporting_projects ADD COLUMN organization_id TEXT")
    else:
        print("organization_id already exists in reporting_projects table.")

    # Ensure default organization exists
    cursor.execute("SELECT id FROM organizations WHERE id = 'default_org'")
    if not cursor.fetchone():
        print("Seeding default organization...")
        cursor.execute("INSERT INTO organizations (id, name, type, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))", 
                       ("default_org", "Clarix Default Organization", "System Root"))
    
    # Backfill missing organization_ids
    cursor.execute("UPDATE users SET organization_id = 'default_org' WHERE organization_id IS NULL OR organization_id = ''")
    cursor.execute("UPDATE reporting_projects SET organization_id = 'default_org' WHERE organization_id IS NULL OR organization_id = ''")

    conn.commit()
    conn.close()
    print("Database schema patched successfully.")

if __name__ == "__main__":
    patch_db()

import sqlite3

def patch_db_ext():
    db_path = "data/sfdr.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tables that need organization_id
    tables = {
        "users": "TEXT",
        "reporting_projects": "TEXT",
        "products": "TEXT"
    }

    for table, col_type in tables.items():
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "organization_id" not in columns:
            print(f"Adding organization_id to {table} table...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN organization_id {col_type}")
        else:
            print(f"organization_id already exists in {table} table.")

    # Seeding
    cursor.execute("UPDATE products SET organization_id = 'default_org' WHERE organization_id IS NULL OR organization_id = ''")
    
    conn.commit()
    conn.close()
    print("Extended database patch complete.")

if __name__ == "__main__":
    patch_db_ext()

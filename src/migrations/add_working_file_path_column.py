"""
Database migration script to add the working_file_path column to the videos table.
"""
from src.utils.postgresql_client import postgres_client


def migrate_add_working_file_path():
    """
    Add the working_file_path column to the videos table if it doesn't exist.
    """
    engine = postgres_client.engine
    with engine.connect() as conn:
        # Check if the column already exists
        result = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='videos' AND column_name='working_file_path'
        """)
        exists = result.fetchone() is not None
        
        if not exists:
            # Add the working_file_path column to the videos table
            conn.execute("""
                ALTER TABLE videos 
                ADD COLUMN working_file_path VARCHAR(255)
            """)
            conn.commit()
            print("Added working_file_path column to videos table successfully!")
        else:
            print("working_file_path column already exists in videos table.")


if __name__ == "__main__":
    migrate_add_working_file_path()
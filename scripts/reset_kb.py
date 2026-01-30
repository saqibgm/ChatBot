
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.conversation_db import _get_connection, _release_connection

def reset_kb():
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        print("Truncating knowledge_base_chunks...")
        cursor.execute("TRUNCATE TABLE knowledge_base_chunks")
        
        print("Truncating knowledge_base (and resetting identity)...")
        # Use DELETE if TRUNCATE fails due to FKs (which chunks was, but we just truncated it)
        # Actually TRUNCATE TABLE knowledge_base might fail if referenced? 
        # But we truncated the child table first.
        cursor.execute("DELETE FROM knowledge_base")
        cursor.execute("DBCC CHECKIDENT ('knowledge_base', RESEED, 0)")
        
        conn.commit()
        print("Knowledge Base reset successfully.")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        _release_connection(conn)

if __name__ == "__main__":
    reset_kb()

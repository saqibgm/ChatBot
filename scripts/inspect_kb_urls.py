
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.conversation_db import _get_connection, _release_connection

def inspect_urls():
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 10 title, url FROM knowledge_base")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} rows.")
        for row in rows:
            print(f"Title: {row.title}")
            print(f"URL: {row.url}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        _release_connection(conn)

if __name__ == "__main__":
    inspect_urls()

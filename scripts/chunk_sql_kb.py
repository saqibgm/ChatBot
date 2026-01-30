
import os
import sys

# Add parent directory to path to import actions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.conversation_db import _get_connection, _fetchall_dict

def chunk_text(text, chunk_size=600, overlap=100):
   if not text:
       return []
   chunks = []
   start = 0
   while start < len(text):
       end = start + chunk_size
       if end < len(text):
           # Try to break at newline or space
           last_newline = text.rfind('\n', start, end)
           if last_newline != -1 and last_newline > start + chunk_size // 2:
               end = last_newline + 1
           else:
               last_space = text.rfind(' ', start, end)
               if last_space != -1 and last_space > start + chunk_size // 2:
                   end = last_space + 1
       
       chunk = text[start:end].strip()
       if chunk:
           chunks.append(chunk)
       
       start = end - overlap
       if start < 0: start = 0
   return chunks

def populate_chunks():
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Clear existing chunks
        print("Clearing old chunks...")
        cursor.execute("TRUNCATE TABLE knowledge_base_chunks")
        conn.commit()
        
        # Get articles
        print("Fetching articles...")
        cursor.execute("SELECT id, title, content FROM knowledge_base")
        articles = _fetchall_dict(cursor)
        print(f"Found {len(articles)} articles.")
        
        total_chunks = 0
        for article in articles:
            if not article['content']:
                continue
                
            chunks = chunk_text(article['content'])
            if not chunks:
                continue
                
            for i, chunk in enumerate(chunks):
                # Save raw chunk (search_kb checks title column separately now)
                
                cursor.execute(
                    "INSERT INTO knowledge_base_chunks (article_id, content, chunk_index) VALUES (?, ?, ?)",
                    (article['id'], chunk, i)
                )
                total_chunks += 1
        
        conn.commit()
        print(f"Successfully created {total_chunks} chunks.")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_chunks()

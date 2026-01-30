
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.conversation_db import search_kb

def test_search():
    query = "how to configure shipping"
    print(f"Searching for: {query}")
    results = search_kb(query)
    print(f"Found {len(results)} results.")
    for res in results:
        print(f"--- {res['title']} ---")
        print(f"Snippet: {res['content'][:100]}...")
        print(f"URL: {res['url']}")

if __name__ == "__main__":
    test_search()


import os
import sys
import shutil
import subprocess
import glob
import re

# Add parent directory to path to import actions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.conversation_db import add_kb_article

REPO_URL = "https://github.com/nopSolutions/nopCommerce-Docs.git"
CLONE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp_docs_repo'))
BASE_DOCS_PATH = os.path.join(CLONE_DIR, "en", "running-your-store")
DOCS_URL_PREFIX = "https://docs.nopcommerce.com/en/running-your-store"

def clean_markdown(text, relative_path):
    """
    Cleans markdown and fixes image/doc links.
    relative_path: relative path from BASE_DOCS_PATH (e.g. 'catalog')
    """
    if not text:
        return ""

    # Remove YAML frontmatter if present
    if text.startswith('---'):
        try:
            _, frontmatter, content = re.split('---', text, 2)
            text = content
        except ValueError:
            pass 

    # Strip images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # regex for [Text](link)
    def fix_link(match):
        label = match.group(1)
        link = match.group(2)
        
        if link.startswith('http') or link.startswith('mailto'):
            return match.group(0)
            
        # Handle DocFX xref links: [Text](xref:doc_id) -> just return Label (since we can't resolve ID easily without map)
        # OR better: [Text](xref:path/to/doc) -> [Text](https://docs.../path/to/doc.html)
        if link.startswith('xref:'):
             # Try to extract path if it looks like a path
             # simple xref often is just ID e.g. xref:en/running-your-store...
             path = link.replace('xref:', '')
             if path.endswith('.md'):
                 path = path[:-3] + '.html'
             elif not path.endswith('.html'):
                 # It might be an ID without extension, hard to map.
                 # Just return label to keep text readable
                 return label
             
             # If it looks like a relative path to "en/running-your-store"
             if 'running-your-store' in path: 
                 # Extract part after running-your-store
                 # This is tricky without knowing the exact structure xref maps to.
                 # Safest: Return label text only to avoid broken links
                 return label
                 
             return label

        # Handle relative links: [Text](other-page.md)
        # We need to resolve this relative to current file's directory
        # This is getting complex for a simple regex. 
        # Strategy: Return just the label text for internal links to prevent 404s in chat.
        # Check if it ends in .md
        if link.endswith('.md'):
            return label
            
        return match.group(0)

    text = re.sub(r'\[(.*?)\]\((.*?)\)', fix_link, text)
    
    # Remove TOC (often lists of links at top or bottom)
    # A simple heuristic: lines that start with - [Text](link)
    # Remove lines causing "4 messages" appearance (unwanted newlines/lists)
    # Actually, the user saw "Running your store" multiple times. That sounds like the Title being repeated in the text?
    
    return text.strip()

def process_files():
    print(f"Cloning {REPO_URL}...")
    if os.path.exists(CLONE_DIR):
        try:
            # Try to pull if exists
            subprocess.run(["git", "-C", CLONE_DIR, "pull"], check=False)
        except:
             # If pull fails (e.g. forced push upstream or corruption), re-clone
            if os.path.exists(CLONE_DIR):
                # Only try to remove if it exists (extra check)
                try:
                    # Windows sometimes locks files, so try-except rmtree
                    # If git pull failed, maybe just proceed? No, corrupted repo.
                    # FORCE REMOVE
                    # We can use shell command for robustness
                    subprocess.run(f'rmdir /s /q "{CLONE_DIR}"', shell=True) 
                except:
                    pass
            subprocess.run(["git", "clone", REPO_URL, CLONE_DIR], check=True)
    else:
        subprocess.run(["git", "clone", REPO_URL, CLONE_DIR], check=True)

    print(f"Scanning {BASE_DOCS_PATH}...")
    
    count = 0
    # Walk through directory
    for root, dirs, files in os.walk(BASE_DOCS_PATH):
        for file in files:
            if file.lower().endswith('.md'):
                full_path = os.path.join(root, file)
                
                # Calculate relative path for URL
                # e.g. root = .../running-your-store/catalog
                # rel_dir = catalog
                rel_dir = os.path.relpath(root, BASE_DOCS_PATH)
                if rel_dir == '.': rel_dir = ''
                
                # URL construction
                # https://docs.nopcommerce.com/en/running-your-store/{rel_dir}/{filename}.html
                filename_no_ext = os.path.splitext(file)[0]
                
                if rel_dir:
                    url_path = f"{rel_dir}/{filename_no_ext}".replace('\\', '/')
                else:
                    url_path = filename_no_ext
                    
                doc_url = f"{DOCS_URL_PREFIX}/{url_path}.html"
                
                # Check for index.html case (usually maps to folder/)
                if filename_no_ext == 'index':
                     if rel_dir:
                        rel_dir_clean = rel_dir.replace('\\', '/')
                        doc_url = f"{DOCS_URL_PREFIX}/{rel_dir_clean}"
                     else:
                        doc_url = f"{DOCS_URL_PREFIX}"
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Extract title
                    match = re.search(r'^#\s+(.*)', content, re.MULTILINE)
                    title = match.group(1).strip() if match else filename_no_ext.replace('-', ' ').title()
                    
                    cleaned_content = clean_markdown(content, rel_dir)
                    
                    if add_kb_article(title, cleaned_content, doc_url):
                        print(f"Saved: {title}")
                        count += 1
                        
                except Exception as e:
                    print(f"Error processing {file}: {e}")
                    
    print(f"Scraping completed. Processed {count} files.")
    
    # Cleanup (optional, keep it for cache)
    # shutil.rmtree(CLONE_DIR)

if __name__ == "__main__":
    process_files()

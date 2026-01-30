"""
Conversation Database Module
SQL Server database for persistent conversation storage and analytics.
"""

import pyodbc
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import time

def _get_db_config():
    """Get database configuration from app.config file."""
    # Rely on config_manager to be present. If faulty, we want it to fail or fix config_manager.
    from actions.config_manager import get_db_config
    return get_db_config()

def _get_connection_string():
    config = _get_db_config()
    driver = config.get('driver', 'ODBC Driver 17 for SQL Server')
    host = str(config.get('host', 'localhost')).strip()
    port = str(config.get('port', 1433)).strip()
    # If host is a named instance (e.g., MACHINE\SQLEXPRESS), do not append port
    if "\\" in host or "," in host:
        server = host
    else:
        server = f"{host},{port}"
    return (f"DRIVER={{{driver}}};SERVER={server};"
            f"DATABASE={config['database']};UID={config['user']};PWD={config['password']}")

def _get_connection():
    """Get connection."""
    # pyodbc handles pooling at the driver manager level usually.
    # We create a new connection object each time but underlying physical connection might be pooled.
    return pyodbc.connect(_get_connection_string())

def _release_connection(conn):
    """Return connection (close it)."""
    conn.close()

def _dict_factory(cursor, row):
    """Helper to convert row to dict."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def _get_cursor(conn):
    """Get cursor."""
    return conn.cursor()

def _fetchall_dict(cursor):
    """Fetch all rows as dicts."""
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def _fetchone_dict(cursor):
    """Fetch one row as dict."""
    row = cursor.fetchone()
    if row:
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))
    return None

def _init_database():
    """Initialize database schema."""
    # Connect to master first to create DB if not exists? 
    # Usually we assume DB exists or we connect to master. 
    # For now assume DB 'ChatBot' exists or is handled by setup.
    # But if we need to create tables, we do it here.
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # SQL Server table creation syntax
        
        # Conversations table
        # Note: IF NOT EXISTS logic
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='conversations' AND xtype='U')
            CREATE TABLE conversations (
                id INT IDENTITY(1,1) PRIMARY KEY,
                sender_id NVARCHAR(255) UNIQUE NOT NULL,
                app_id NVARCHAR(50) DEFAULT 'General',
                started_at DATETIME DEFAULT GETDATE(),
                last_activity DATETIME DEFAULT GETDATE(),
                resolved INT DEFAULT 0
            )
        ''')
        
        # Messages table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='messages' AND xtype='U')
            CREATE TABLE messages (
                id INT IDENTITY(1,1) PRIMARY KEY,
                conversation_id INT NOT NULL,
                sender NVARCHAR(50) NOT NULL,
                text NVARCHAR(MAX),
                intent NVARCHAR(255),
                timestamp DATETIME DEFAULT GETDATE(),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        ''')
        
        # Feedback table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='feedback' AND xtype='U')
            CREATE TABLE feedback (
                id INT IDENTITY(1,1) PRIMARY KEY,
                conversation_id INT NOT NULL,
                type NVARCHAR(50) NOT NULL,
                timestamp DATETIME DEFAULT GETDATE(),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        ''')
        
        # Actions table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='actions' AND xtype='U')
            CREATE TABLE actions (
                id INT IDENTITY(1,1) PRIMARY KEY,
                conversation_id INT NOT NULL,
                action_name NVARCHAR(255) NOT NULL,
                success INT DEFAULT 1,
                timestamp DATETIME DEFAULT GETDATE(),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        ''')
        
        # Config table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='config' AND xtype='U')
            CREATE TABLE config (
                [key] NVARCHAR(255) PRIMARY KEY,
                value NVARCHAR(MAX),
                updated_at DATETIME DEFAULT GETDATE()
            )
        ''')
        
        # Themes table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='themes' AND xtype='U')
            CREATE TABLE themes (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) NOT NULL,
                settings NVARCHAR(MAX),
                is_default INT DEFAULT 0,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        ''')
        
        # Indexes
        # IF NOT EXISTS check for indexes is a bit verbose in T-SQL, skipping for brevity or using try/catch logic
        # Simple workaround:
        try: cursor.execute("CREATE INDEX idx_conv_sender ON conversations(sender_id)")
        except: pass
        try: cursor.execute("CREATE INDEX idx_msg_conv ON messages(conversation_id)")
        except: pass
        try: cursor.execute("CREATE INDEX idx_msg_intent ON messages(intent)")
        except: pass
        
        # Add columns if missing
        alter_statements = [
            "ALTER TABLE conversations ADD user_id NVARCHAR(255)",
            "ALTER TABLE conversations ADD user_name NVARCHAR(255)",
            "ALTER TABLE conversations ADD ticket_id NVARCHAR(255)",
            "ALTER TABLE messages ADD app_id NVARCHAR(50) DEFAULT 'General'",
            "ALTER TABLE messages ADD user_id NVARCHAR(255)",
            "ALTER TABLE messages ADD ticket_id NVARCHAR(255)",
            "ALTER TABLE feedback ADD app_id NVARCHAR(50) DEFAULT 'General'",
            "ALTER TABLE feedback ADD user_id NVARCHAR(255)",
            "ALTER TABLE feedback ADD ticket_id NVARCHAR(255)",
            "ALTER TABLE actions ADD app_id NVARCHAR(50) DEFAULT 'General'",
            "ALTER TABLE actions ADD user_id NVARCHAR(255)",
            "ALTER TABLE actions ADD ticket_id NVARCHAR(255)",
            "ALTER TABLE actions ADD ticket_id NVARCHAR(255)",
            "ALTER TABLE feedback ADD feedback_text NVARCHAR(MAX)",
            "ALTER TABLE messages ADD user_name NVARCHAR(255)" 
        ]
        
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
            except Exception:
                pass # Column exists
        
        try: cursor.execute("CREATE INDEX idx_conv_app ON conversations(app_id)")
        except: pass
        try: cursor.execute("CREATE INDEX idx_msg_app ON messages(app_id)")
        except: pass
        
        # ChatApps table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='chat_apps' AND xtype='U')
            CREATE TABLE chat_apps (
                id INT IDENTITY(1,1) PRIMARY KEY,
                app_id NVARCHAR(50) UNIQUE NOT NULL,
                name NVARCHAR(255) NOT NULL,
                description NVARCHAR(MAX),
                is_active INT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE()
            )
        ''')
        
        # Knowledge Base table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='knowledge_base' AND xtype='U')
            CREATE TABLE knowledge_base (
                id INT IDENTITY(1,1) PRIMARY KEY,
                title NVARCHAR(255) NOT NULL,
                content NVARCHAR(MAX),
                url NVARCHAR(500),
                created_at DATETIME DEFAULT GETDATE()
            )
        ''')

        # Knowledge Base Chunks table
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='knowledge_base_chunks' AND xtype='U')
            CREATE TABLE knowledge_base_chunks (
                id INT IDENTITY(1,1) PRIMARY KEY,
                article_id INT,
                content NVARCHAR(MAX),
                chunk_index INT,
                FOREIGN KEY (article_id) REFERENCES knowledge_base(id)
            )
        ''')

        # Seed default apps
        cursor.execute('SELECT COUNT(*) FROM chat_apps')
        if cursor.fetchone()[0] == 0:
            default_apps = [
                ('IT', 'IT Support', 'Technical support and IT helpdesk'),
                ('Accounting', 'Accounting Support', 'Finance and accounting inquiries'),
                ('HR', 'Human Resources', 'HR and employee support'),
                ('General', 'General Support', 'General inquiries and support')
            ]
            for app in default_apps:
                cursor.execute(
                    'INSERT INTO chat_apps (app_id, name, description) VALUES (?, ?, ?)',
                    app
                )
        
        conn.commit()
    finally:
        _release_connection(conn)

# Knowledge Base Cache
_kb_cache = {
    "articles": [],  # List of KB articles with chunks
    "loaded_at": None,
    "enabled": True
}

def _load_kb_cache():
    """Load all knowledge base articles and chunks into memory cache."""
    global _kb_cache

    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()

            # Load all articles with their chunks
            cursor.execute('''
                SELECT k.id, k.title, k.url, c.content, c.chunk_index
                FROM knowledge_base k
                LEFT JOIN knowledge_base_chunks c ON k.id = c.article_id
                ORDER BY k.id, c.chunk_index
            ''')

            rows = _fetchall_dict(cursor)

            # Group chunks by article
            articles_dict = {}
            for row in rows:
                article_id = row['id']
                if article_id not in articles_dict:
                    articles_dict[article_id] = {
                        'id': article_id,
                        'title': row['title'] or '',
                        'url': row['url'] or '',
                        'chunks': []
                    }

                if row['content']:
                    articles_dict[article_id]['chunks'].append({
                        'content': row['content'],
                        'chunk_index': row['chunk_index'] or 0
                    })

            _kb_cache['articles'] = list(articles_dict.values())
            _kb_cache['loaded_at'] = datetime.now()

            count = len(_kb_cache['articles'])
            chunks_count = sum(len(a['chunks']) for a in _kb_cache['articles'])
            print(f"✓ Knowledge Base cached: {count} articles, {chunks_count} chunks loaded into memory")

            return True

        finally:
            _release_connection(conn)

    except Exception as e:
        print(f"Warning: Could not load KB cache: {e}")
        _kb_cache['enabled'] = False
        return False

def refresh_kb_cache():
    """Manually refresh the knowledge base cache."""
    return _load_kb_cache()

def get_kb_cache_stats() -> Dict:
    """Get knowledge base cache statistics."""
    global _kb_cache

    return {
        'enabled': _kb_cache['enabled'],
        'loaded_at': _kb_cache['loaded_at'].isoformat() if _kb_cache['loaded_at'] else None,
        'articles_count': len(_kb_cache['articles']),
        'chunks_count': sum(len(a['chunks']) for a in _kb_cache['articles']),
        'cache_size_kb': sum(
            len(a['title']) + len(a['url']) +
            sum(len(c['content']) for c in a['chunks'])
            for a in _kb_cache['articles']
        ) / 1024
    }

# Initialize on load
try:
    _init_database()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")

# Load KB cache on startup
try:
    _load_kb_cache()
except Exception as e:
    print(f"Warning: Could not load KB cache on startup: {e}")

def log_conversation_start(sender_id: str, app_id: str = "General", user_id: str = None, user_name: str = None) -> int:
    """Log start of a new conversation. Returns conversation ID."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM conversations WHERE sender_id = ?', (sender_id,))
        row = _fetchone_dict(cursor)
        
        if row:
            if user_id:
                if user_name:
                    cursor.execute(
                        'UPDATE conversations SET last_activity = GETDATE(), user_id = ?, user_name = ? WHERE sender_id = ?',
                        (user_id, user_name, sender_id)
                    )
                else:
                    cursor.execute(
                        'UPDATE conversations SET last_activity = GETDATE(), user_id = ? WHERE sender_id = ?',
                        (user_id, sender_id)
                    )
            elif user_name:
                cursor.execute(
                    'UPDATE conversations SET last_activity = GETDATE(), user_name = ? WHERE sender_id = ?',
                    (user_name, sender_id)
                )
            else:
                cursor.execute(
                    'UPDATE conversations SET last_activity = GETDATE() WHERE sender_id = ?',
                    (sender_id,)
                )
            conn.commit()
            return row['id']
        
        # Create new
        # OUTPUT INSERTED.id
        cursor.execute(
            'INSERT INTO conversations (sender_id, app_id, user_id, user_name, started_at, last_activity) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, GETDATE(), GETDATE())',
            (sender_id, app_id, user_id, user_name)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        _release_connection(conn)

def log_message(sender_id: str, message_type: str, text: str, intent: str = None, app_id: str = "General", user_id: str = None, ticket_id: str = None, user_name: str = None):
    # Filter unwanted messages
    if not text or not text.strip() or text.strip() == "/admin_me":
        return

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        conv_id = log_conversation_start(sender_id, app_id, user_id=user_id, user_name=user_name)
        
        cursor.execute(
            'INSERT INTO messages (conversation_id, sender, text, intent, app_id, user_id, ticket_id, user_name, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE())',
            (conv_id, message_type, text[:500] if text else "", intent, app_id, user_id, ticket_id, user_name)
        )
        
        if ticket_id:
            cursor.execute(
                'UPDATE conversations SET last_activity = GETDATE(), ticket_id = ? WHERE id = ?',
                (ticket_id, conv_id)
            )
        else:
            cursor.execute(
                'UPDATE conversations SET last_activity = GETDATE() WHERE id = ?',
                (conv_id,)
            )
        conn.commit()
    finally:
        _release_connection(conn)

def log_intent(sender_id: str, intent: str, confidence: float = None):
    pass

def log_feedback(sender_id: str, feedback_type: str, app_id: str = "General", user_id: str = None, ticket_id: str = None):
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        if feedback_type in ('up', 'positive'):
            feedback_type = 'positive'
        elif feedback_type in ('down', 'negative'):
            feedback_type = 'negative'
            
        conv_id = log_conversation_start(sender_id, app_id, user_id=user_id)
        
        cursor.execute(
            'INSERT INTO feedback (conversation_id, type, app_id, user_id, ticket_id, timestamp) VALUES (?, ?, ?, ?, ?, GETDATE())',
            (conv_id, feedback_type, app_id, user_id, ticket_id)
        )
        
        if feedback_type == 'positive':
            cursor.execute('UPDATE conversations SET resolved = 1 WHERE id = ?', (conv_id,))
            
        conn.commit()
        print(f"Feedback saved to SQL Server: {feedback_type} for sender {sender_id}")
    except Exception as e:
        print(f"Error saving feedback to SQL Server: {e}")
        conn.rollback()
    finally:
        _release_connection(conn)

def log_action(sender_id: str, action_name: str, success: bool = True, app_id: str = "General", user_id: str = None, ticket_id: str = None):
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        conv_id = log_conversation_start(sender_id, app_id, user_id=user_id)
        
        cursor.execute(
            'INSERT INTO actions (conversation_id, action_name, success, app_id, user_id, ticket_id, timestamp) VALUES (?, ?, ?, ?, ?, ?, GETDATE())',
            (conv_id, action_name, 1 if success else 0, app_id, user_id, ticket_id)
        )
        conn.commit()
        print(f"Action logged to SQL Server: {action_name} for sender {sender_id}")
    except Exception as e:
        print(f"Error logging action to SQL Server: {e}")
        conn.rollback()
    finally:
        _release_connection(conn)



def add_kb_article(title: str, content: str, url: str = None, refresh_cache: bool = True) -> bool:
    """Add an article to the knowledge base.

    Args:
        title: Article title
        content: Article content
        url: Optional URL
        refresh_cache: If True, reload KB cache after adding article (default: True)
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Check if URL exists to avoid duplicates
        if url:
            cursor.execute("SELECT id FROM knowledge_base WHERE url = ?", (url,))
            if cursor.fetchone():
                # Update existing
                cursor.execute(
                    "UPDATE knowledge_base SET title = ?, content = ?, created_at = GETDATE() WHERE url = ?",
                    (title, content, url)
                )
                conn.commit()

                # Refresh cache to reflect updates
                if refresh_cache:
                    _load_kb_cache()

                return True

        cursor.execute(
            "INSERT INTO knowledge_base (title, content, url) VALUES (?, ?, ?)",
            (title, content, url)
        )
        conn.commit()

        # Refresh cache to include new article
        if refresh_cache:
            _load_kb_cache()

        return True
    except Exception as e:
        print(f"Error adding KB article: {e}")
        return False
    finally:
        _release_connection(conn)

def search_kb(query: str) -> List[Dict]:
    """Search knowledge base chunks for query using exact and keyword matching.
    Returns list of dicts with: title, content, url, article_id
    Prioritizes title matches over content-only matches.

    Uses in-memory cache for faster search if available, falls back to database.
    """
    global _kb_cache

    # Use cache if available and enabled
    if _kb_cache['enabled'] and _kb_cache['articles']:
        return _search_kb_cache(query)

    # Fallback to database search
    return _search_kb_database(query)

def _search_kb_cache(query: str) -> List[Dict]:
    """Search KB using in-memory cache (fast)."""
    global _kb_cache

    # Normalize query
    query_lower = query.lower().strip()

    # Extract keywords (filter stop words)
    stop_words = {'how', 'to', 'do', 'i', 'the', 'a', 'an', 'in', 'on', 'at', 'for', 'of',
                  'is', 'are', 'can', 'you', 'help', 'me', 'with', 'about', 'tell', 'show',
                  'find', 'search', 'get', 'what', 'where', 'when', 'why', 'which', 'my',
                  'please', 'need', 'want', 'would', 'could', 'should', 'have', 'has', 'had'}
    words = [w for w in query_lower.split() if w.isalnum() and len(w) > 2 and w not in stop_words]

    if not words:
        # Fallback: try exact phrase in title
        for article in _kb_cache['articles']:
            if query_lower in article['title'].lower():
                best_chunk = max(article['chunks'], key=lambda c: len(c['content'])) if article['chunks'] else None
                if best_chunk:
                    return [{
                        'article_id': article['id'],
                        'title': article['title'],
                        'content': best_chunk['content'],
                        'url': article['url']
                    }]
        return []

    # Main keyword is typically the last content word
    main_keyword = words[-1]

    # STEP 1: Find article with main keyword in TITLE
    for article in _kb_cache['articles']:
        if main_keyword in article['title'].lower():
            # Get longest chunk
            best_chunk = max(article['chunks'], key=lambda c: len(c['content'])) if article['chunks'] else None
            if best_chunk:
                return [{
                    'article_id': article['id'],
                    'title': article['title'],
                    'content': best_chunk['content'],
                    'url': article['url']
                }]

    # STEP 2: Try with all keywords in title (AND logic)
    if len(words) > 1:
        for article in _kb_cache['articles']:
            title_lower = article['title'].lower()
            if all(w in title_lower for w in words):
                best_chunk = max(article['chunks'], key=lambda c: len(c['content'])) if article['chunks'] else None
                if best_chunk:
                    return [{
                        'article_id': article['id'],
                        'title': article['title'],
                        'content': best_chunk['content'],
                        'url': article['url']
                    }]

    # STEP 3: Fall back to content search, prioritize title matches
    best_match = None
    best_score = -1

    for article in _kb_cache['articles']:
        title_lower = article['title'].lower()

        # Check if any keyword matches title
        title_has_main_keyword = main_keyword in title_lower
        title_match_count = sum(1 for w in words if w in title_lower)

        # Search in chunks
        for chunk in article['chunks']:
            content_lower = chunk['content'].lower()
            content_match_count = sum(1 for w in words if w in content_lower)

            if content_match_count > 0 or title_match_count > 0:
                # Calculate score: prioritize title matches, then content length
                score = (title_match_count * 1000) + (content_match_count * 100) + len(chunk['content'])

                if title_has_main_keyword:
                    score += 10000

                if score > best_score:
                    best_score = score
                    best_match = {
                        'article_id': article['id'],
                        'title': article['title'],
                        'content': chunk['content'],
                        'url': article['url']
                    }

    return [best_match] if best_match else []

def _search_kb_database(query: str) -> List[Dict]:
    """Search KB using database queries (fallback)."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Normalize query
        query_lower = query.lower().strip()

        # Extract keywords (filter stop words)
        stop_words = {'how', 'to', 'do', 'i', 'the', 'a', 'an', 'in', 'on', 'at', 'for', 'of',
                      'is', 'are', 'can', 'you', 'help', 'me', 'with', 'about', 'tell', 'show',
                      'find', 'search', 'get', 'what', 'where', 'when', 'why', 'which', 'my',
                      'please', 'need', 'want', 'would', 'could', 'should', 'have', 'has', 'had'}
        words = [w for w in query_lower.split() if w.isalnum() and len(w) > 2 and w not in stop_words]

        if not words:
            # Fallback: try exact phrase
            search_term = f"%{query_lower}%"
            cursor.execute('''
                SELECT TOP 1 k.id as article_id, k.title, c.content, k.url
                FROM knowledge_base_chunks c
                JOIN knowledge_base k ON c.article_id = k.id
                WHERE LOWER(k.title) LIKE ?
            ''', (search_term,))
            results = _fetchall_dict(cursor)
            return results

        # Main keyword is typically the last content word (e.g., "shipping" in "configure shipping")
        main_keyword = words[-1]

        # STEP 1: First try to find article with main keyword in TITLE
        cursor.execute('''
            SELECT TOP 1 k.id as article_id, k.title, c.content, k.url
            FROM knowledge_base_chunks c
            JOIN knowledge_base k ON c.article_id = k.id
            WHERE LOWER(k.title) LIKE ?
            ORDER BY LEN(c.content) DESC
        ''', (f"%{main_keyword}%",))
        results = _fetchall_dict(cursor)

        if results:
            return results

        # STEP 2: Try with all keywords in title (AND logic)
        if len(words) > 1:
            title_conditions = " AND ".join([f"LOWER(k.title) LIKE ?" for _ in words])
            title_params = [f"%{w}%" for w in words]

            cursor.execute(f'''
                SELECT TOP 1 k.id as article_id, k.title, c.content, k.url
                FROM knowledge_base_chunks c
                JOIN knowledge_base k ON c.article_id = k.id
                WHERE {title_conditions}
                ORDER BY LEN(c.content) DESC
            ''', tuple(title_params))
            results = _fetchall_dict(cursor)

            if results:
                return results

        # STEP 3: Fall back to content search with keyword in title preferred
        # Search content but prioritize results where title also contains a keyword
        params = []
        for w in words:
            params.append(f"%{w}%")
            params.append(f"%{w}%")

        where_conditions = " OR ".join([f"(LOWER(c.content) LIKE ? OR LOWER(k.title) LIKE ?)" for _ in words])

        cursor.execute(f'''
            SELECT TOP 1 k.id as article_id, k.title, c.content, k.url
            FROM knowledge_base_chunks c
            JOIN knowledge_base k ON c.article_id = k.id
            WHERE {where_conditions}
            ORDER BY
                CASE WHEN LOWER(k.title) LIKE ? THEN 0 ELSE 1 END,
                LEN(c.content) DESC
        ''', tuple(params) + (f"%{main_keyword}%",))
        results = _fetchall_dict(cursor)

        return results

    finally:
        _release_connection(conn)

def get_analytics_summary(app_id: str = None) -> Dict:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        app_filter = ""
        app_params = ()
        if app_id and app_id != "all":
            app_filter = " WHERE app_id = ?"
            app_params = (app_id,)
            
        cursor.execute(f'SELECT COUNT(*) as count FROM conversations{app_filter}', app_params)
        total_conversations = cursor.fetchone()[0]
        
        if app_id and app_id != "all":
            cursor.execute('SELECT COUNT(*) as count FROM messages WHERE app_id = ?', (app_id,))
        else:
            cursor.execute('SELECT COUNT(*) as count FROM messages')
        total_messages = cursor.fetchone()[0]
        
        if app_id and app_id != "all":
            cursor.execute("SELECT COUNT(*) as count FROM feedback WHERE type = 'positive' AND app_id = ?", (app_id,))
            feedback_positive = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) as count FROM feedback WHERE type = 'negative' AND app_id = ?", (app_id,))
            feedback_negative = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) as count FROM feedback WHERE type = 'positive'")
            feedback_positive = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) as count FROM feedback WHERE type = 'negative'")
            feedback_negative = cursor.fetchone()[0]
            
        total_feedback = feedback_positive + feedback_negative
        resolution_rate = round((feedback_positive / total_feedback) * 100, 1) if total_feedback > 0 else 0
        
        # Top intents (TOP 10)
        # Note: intent != '' check needs care with NULLs in SQL Server
        if app_id and app_id != "all":
            cursor.execute('''
                SELECT TOP 10 intent, COUNT(*) as count 
                FROM messages 
                WHERE intent IS NOT NULL AND intent != '' AND app_id = ?
                GROUP BY intent 
                ORDER BY count DESC
            ''', (app_id,))
        else:
            cursor.execute('''
                SELECT TOP 10 intent, COUNT(*) as count 
                FROM messages 
                WHERE intent IS NOT NULL AND intent != '' 
                GROUP BY intent 
                ORDER BY count DESC
            ''')
        top_intents = [(row[0], row[1]) for row in cursor.fetchall()]
        
        # Conversations today
        # DATE(last_activity) -> CAST(last_activity AS DATE)
        if app_id and app_id != "all":
            cursor.execute(
                "SELECT COUNT(*) as count FROM conversations WHERE CAST(last_activity AS DATE) = CAST(GETDATE() AS DATE) AND app_id = ?",
                (app_id,)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) as count FROM conversations WHERE CAST(last_activity AS DATE) = CAST(GETDATE() AS DATE)"
            )
        conversations_today = cursor.fetchone()[0]
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "feedback_positive": feedback_positive,
            "feedback_negative": feedback_negative,
            "resolution_rate": resolution_rate,
            "top_intents": top_intents,
            "conversations_today": conversations_today,
            "intent_distribution": dict(top_intents),
            "app_id": app_id or "all"
        }
    finally:
        _release_connection(conn)

def get_recent_conversations(limit: int = 20) -> List[Dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # SELECT TOP N
        # Also, subqueries for message_count and feedback need care
        query = f'''
            SELECT TOP {limit}
                c.id,
                c.sender_id,
                c.app_id,
                c.started_at,
                c.last_activity,
                c.resolved,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count,
                (SELECT TOP 1 type FROM feedback WHERE conversation_id = c.id ORDER BY timestamp DESC) as feedback
            FROM conversations c
            ORDER BY c.last_activity DESC
        '''
        cursor.execute(query)
        result = []
        rows = _fetchall_dict(cursor)
        
        for row in rows:
            cursor.execute('''
                SELECT DISTINCT TOP 5 intent FROM messages 
                WHERE conversation_id = ? AND intent IS NOT NULL AND intent != ''
            ''', (row['id'],))
            intents = [r[0] for r in cursor.fetchall()]
            
            result.append({
                "sender_id": row['sender_id'][:8] + "..." if row['sender_id'] else "",
                "app_id": row['app_id'] or "General",
                "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                "message_count": row['message_count'],
                "intents": intents,
                "feedback": row['feedback'],
                "resolved": bool(row['resolved'])
            })
            
        return result
    finally:
        _release_connection(conn)

def get_app_list() -> List[Dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, app_id, name, description, is_active FROM chat_apps WHERE is_active = 1 ORDER BY name')
        return _fetchall_dict(cursor)
    finally:
        _release_connection(conn)

def get_chat_app(app_id: str) -> Dict:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, app_id, name, description, is_active FROM chat_apps WHERE app_id = ?', (app_id,))
        return _fetchone_dict(cursor)
    finally:
        _release_connection(conn)

def create_chat_app(app_id: str, name: str, description: str = None) -> int:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO chat_apps (app_id, name, description) OUTPUT INSERTED.id VALUES (?, ?, ?)',
            (app_id, name, description)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        _release_connection(conn)

def update_chat_app(app_id: str, name: str = None, description: str = None, is_active: int = None) -> bool:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        
        if not updates:
            return False
        
        params.append(app_id)
        cursor.execute(f"UPDATE chat_apps SET {', '.join(updates)} WHERE app_id = ?", params)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        _release_connection(conn)

def delete_chat_app(app_id: str) -> bool:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE chat_apps SET is_active = 0 WHERE app_id = ?', (app_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        _release_connection(conn)

def get_conversation_transcript(sender_id: str) -> List[Dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM conversations WHERE sender_id = ?', (sender_id,))
        row = cursor.fetchone()
        
        if not row:
            return []
        
        cursor.execute('''
            SELECT sender, text, intent, timestamp 
            FROM messages 
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (row[0],))
        
        return _fetchall_dict(cursor)
    finally:
        _release_connection(conn)

# Admin Config
def get_config(key: str = None) -> Dict:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        if key:
            cursor.execute('SELECT [key], value FROM config WHERE [key] = ?', (key,))
            row = cursor.fetchone()
            if row:
                return {row[0]: row[1]}
            return {}
        
        cursor.execute('SELECT [key], value FROM config')
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        _release_connection(conn)

def set_config(key: str, value: str):
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # MERGE for UPSERT in SQL Server
        cursor.execute('''
            MERGE config AS target
            USING (SELECT ? AS [key], ? AS value) AS source
            ON (target.[key] = source.[key])
            WHEN MATCHED THEN
                UPDATE SET value = source.value, updated_at = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT ([key], value, updated_at) VALUES (source.[key], source.value, GETDATE());
        ''', (key, value))
        conn.commit()
    finally:
        _release_connection(conn)

def set_config_bulk(config_dict: Dict):
    for key, value in config_dict.items():
        set_config(key, str(value) if value is not None else '')

def get_themes() -> List[Dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM themes ORDER BY created_at DESC')
        themes = []
        for row in _fetchall_dict(cursor):
            theme = row
            if theme.get('created_at'):
                theme['created_at'] = theme['created_at'].isoformat()
            if theme.get('updated_at'):
                theme['updated_at'] = theme['updated_at'].isoformat()
            themes.append(theme)
        return themes
    finally:
        _release_connection(conn)

def get_theme(theme_id: int) -> Optional[Dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM themes WHERE id = ?', (theme_id,))
        row = _fetchone_dict(cursor)
        if row:
            theme = row
            if theme.get('created_at'):
                theme['created_at'] = theme['created_at'].isoformat()
            if theme.get('updated_at'):
                theme['updated_at'] = theme['updated_at'].isoformat()
            return theme
        return None
    finally:
        _release_connection(conn)

def create_theme(name: str, settings: str, is_default: bool = False) -> int:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        if is_default:
            cursor.execute('UPDATE themes SET is_default = 0')
            
        cursor.execute('''
            INSERT INTO themes (name, settings, is_default, created_at, updated_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, GETDATE(), GETDATE())
        ''', (name, settings, 1 if is_default else 0))
        new_id = cursor.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        _release_connection(conn)

def update_theme(theme_id: int, name: str = None, settings: str = None, is_default: bool = None):
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if settings is not None:
            updates.append('settings = ?')
            params.append(settings)
        if is_default is not None:
            if is_default:
                cursor.execute('UPDATE themes SET is_default = 0')
            updates.append('is_default = ?')
            params.append(1 if is_default else 0)
            
        if updates:
            updates.append('updated_at = GETDATE()')
            # SQL Server UPDATE syntax: UPDATE table SET ... WHERE ...
            params.append(theme_id)
            cursor.execute(f'UPDATE themes SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()
    finally:
        _release_connection(conn)

def delete_theme(theme_id: int):
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM themes WHERE id = ?', (theme_id,))
        conn.commit()
    finally:
        _release_connection(conn)

def get_default_theme() -> Optional[Dict]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # LIMIT 1 -> TOP 1
        cursor.execute('SELECT TOP 1 * FROM themes WHERE is_default = 1')
        row = _fetchone_dict(cursor)
        if row:
            theme = row
            if theme.get('created_at'):
                theme['created_at'] = theme['created_at'].isoformat()
            if theme.get('updated_at'):
                theme['updated_at'] = theme['updated_at'].isoformat()
            return theme
        return None
    finally:
        _release_connection(conn)


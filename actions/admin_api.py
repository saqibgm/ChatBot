"""
Admin API Module
Flask API for admin dashboard operations, analytics, and static file serving.
Consolidated server running on port 8181.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from actions.conversation_db import (
    get_themes, get_theme, create_theme, update_theme, delete_theme,
    get_default_theme, get_app_list, get_chat_app, create_chat_app, update_chat_app, delete_chat_app,
    _get_connection, _release_connection
)
# conversation_db functions handle their own DB interactions, but inspector/analytics here do raw queries.
from actions.analytics_store import get_analytics_summary, get_recent_conversations
from actions.config_manager import get_all_config as get_file_config, set_all_config as save_file_config

# Static files directory
# Static files directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client ui', 'dist-widget')
INVOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'invoices')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
CORS(app)

@app.route('/invoices/<path:filename>')
def serve_invoice(filename):
    return send_from_directory(INVOICES_DIR, filename)
CORS(app)


# Helpers for pyodbc dict rows
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


# Serve static files - Flask handles /static/* automatically via static_folder
@app.route('/')
def serve_index():
    return send_from_directory(STATIC_DIR, 'admin.html')

@app.route('/admin.html')
def serve_admin():
    return send_from_directory(STATIC_DIR, 'admin.html')

@app.route('/inspector.html')
def serve_inspector():
    return send_from_directory(STATIC_DIR, 'inspector.html')

@app.route('/analytics.html')
def serve_analytics():
    return send_from_directory(STATIC_DIR, 'analytics.html')

@app.route('/createl-chat-widget.js')
def serve_widget_js():
    return send_from_directory(STATIC_DIR, 'createl-chat-widget.js')

# Default configuration keys
DEFAULT_CONFIG_KEYS = [
    'RASA_API_URL',
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
    'DB_DRIVER',
    'WIDGET_TITLE',
    'WIDGET_SUBTITLE',
    'NOP_API_URL',
    'NOP_SECRET_KEY',
    'NOP_ADMIN_USERNAME',
    'NOP_ADMIN_PASSWORD',
    'NOP_VERIFY_SSL'
]


@app.route('/admin/config', methods=['GET'])
def get_all_config():
    """Get all configuration values from app.config file."""
    try:
        config = get_file_config()
        # Ensure all default keys exist
        for key in DEFAULT_CONFIG_KEYS:
            if key not in config:
                config[key] = ''
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/config', methods=['POST'])
def save_config():
    """Save configuration values to app.config file."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        save_file_config(data)
        return jsonify({"success": True, "message": "Configuration saved to app.config"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/config/<key>', methods=['GET'])
def get_config_key(key):
    """Get a specific configuration value from app.config file."""
    try:
        config = get_file_config()
        return jsonify({"success": True, "value": config.get(key, '')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/config/<key>', methods=['POST'])
def set_config_key(key):
    """Set a specific configuration value in app.config file."""
    try:
        data = request.get_json()
        value = data.get('value', '')
        save_file_config({key: value})
        return jsonify({"success": True, "message": f"{key} saved to app.config"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================
# THEMES ENDPOINTS
# =====================

@app.route('/admin/themes', methods=['GET'])
def list_themes():
    """Get all themes."""
    try:
        themes = get_themes()
        # Parse settings JSON for each theme
        for theme in themes:
            if theme.get('settings'):
                try:
                    theme['settings'] = json.loads(theme['settings'])
                except:
                    pass
        return jsonify({"success": True, "themes": themes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/themes', methods=['POST'])
def add_theme():
    """Create a new theme."""
    try:
        data = request.get_json()
        name = data.get('name', 'Untitled Theme')
        settings = data.get('settings', {})
        is_default = data.get('is_default', False)
        
        # Convert settings to JSON string
        settings_json = json.dumps(settings) if isinstance(settings, dict) else settings
        
        theme_id = create_theme(name, settings_json, is_default)
        return jsonify({"success": True, "theme_id": theme_id, "message": "Theme created"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/themes/<int:theme_id>', methods=['GET'])
def get_theme_by_id(theme_id):
    """Get a specific theme."""
    try:
        theme = get_theme(theme_id)
        if not theme:
            return jsonify({"success": False, "error": "Theme not found"}), 404
        
        # Parse settings JSON
        if theme.get('settings'):
            try:
                theme['settings'] = json.loads(theme['settings'])
            except:
                pass
        
        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/themes/<int:theme_id>', methods=['PUT'])
def modify_theme(theme_id):
    """Update a theme."""
    try:
        data = request.get_json()
        name = data.get('name')
        settings = data.get('settings')
        is_default = data.get('is_default')
        
        # Convert settings to JSON string if provided
        settings_json = None
        if settings is not None:
            settings_json = json.dumps(settings) if isinstance(settings, dict) else settings
        
        update_theme(theme_id, name, settings_json, is_default)
        return jsonify({"success": True, "message": "Theme updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/themes/<int:theme_id>', methods=['DELETE'])
def remove_theme(theme_id):
    """Delete a theme."""
    try:
        delete_theme(theme_id)
        return jsonify({"success": True, "message": "Theme deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/themes/default', methods=['GET'])
def get_default():
    """Get the default theme."""
    try:
        theme = get_default_theme()
        if theme and theme.get('settings'):
            try:
                theme['settings'] = json.loads(theme['settings'])
            except:
                pass
        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================
# ANALYTICS ENDPOINTS
# =====================

@app.route('/admin/analytics/apps', methods=['GET'])
def list_apps():
    """Get list of distinct app IDs for filtering."""
    try:
        apps = get_app_list()
        return jsonify({
            "success": True,
            "apps": apps
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/admin/analytics/summary', methods=['GET'])
def analytics_summary():
    """Get overall analytics summary. Supports ?app_id= filter."""
    try:
        app_id = request.args.get('app_id', None)
        print(f"[DEBUG] analytics_summary called with app_id={app_id}")
        summary = get_analytics_summary(app_id=app_id)
        print(f"[DEBUG] Summary returned: {summary.get('total_conversations')} conversations, {summary.get('total_messages')} messages")
        return jsonify({
            "success": True,
            "data": summary
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/admin/analytics/conversations', methods=['GET'])
def recent_conversations():
    """Get recent conversations. Supports ?app_id= filter."""
    try:
        app_id = request.args.get('app_id', None)
        conversations = get_recent_conversations(limit=20)
        # Filter by app_id if provided
        if app_id and app_id != 'all':
            conversations = [c for c in conversations if c.get('app_id') == app_id]
        return jsonify({
            "success": True,
            "data": conversations
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/admin/analytics/intents', methods=['GET'])
def intent_distribution():
    """Get intent distribution data. Supports ?app_id= filter."""
    try:
        app_id = request.args.get('app_id', None)
        summary = get_analytics_summary(app_id=app_id)
        return jsonify({
            "success": True,
            "data": {
                "intents": summary.get("intent_distribution", {}),
                "top_intents": summary.get("top_intents", [])
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/admin/analytics/feedback', methods=['GET'])
def feedback_metrics():
    """Get feedback metrics. Supports ?app_id= filter."""
    try:
        app_id = request.args.get('app_id', None)
        summary = get_analytics_summary(app_id=app_id)
        return jsonify({
            "success": True,
            "data": {
                "positive": summary.get("feedback_positive", 0),
                "negative": summary.get("feedback_negative", 0),
                "resolution_rate": summary.get("resolution_rate", 0)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =====================
# SATISFACTION RATINGS
# =====================

@app.route('/analytics/satisfaction', methods=['GET'])
@app.route('/admin/analytics/satisfaction', methods=['GET'])
def satisfaction_ratings():
    """Get satisfaction ratings distribution with optional date filter."""
    try:
        days = request.args.get('days', '30')
        
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Build date filter
        date_filter = ""
        if days != 'all':
            try:
                days_int = int(days)
                # T-SQL DATEADD
                date_filter = f"AND timestamp >= DATEADD(day, -{days_int}, GETDATE())"
            except ValueError:
                pass
        
        # Query ratings from feedback
        cursor.execute(f"""
            SELECT 
                CASE 
                    WHEN feedback_text LIKE '%5 stars%' THEN 5
                    WHEN feedback_text LIKE '%4 stars%' THEN 4
                    WHEN feedback_text LIKE '%3 stars%' THEN 3
                    WHEN feedback_text LIKE '%2 stars%' THEN 2
                    WHEN feedback_text LIKE '%1 star%' THEN 1
                    ELSE 0
                END as rating,
                COUNT(*) as count
            FROM feedback 
            WHERE feedback_text LIKE '%Satisfaction%' {date_filter}
            GROUP BY 
                CASE 
                    WHEN feedback_text LIKE '%5 stars%' THEN 5
                    WHEN feedback_text LIKE '%4 stars%' THEN 4
                    WHEN feedback_text LIKE '%3 stars%' THEN 3
                    WHEN feedback_text LIKE '%2 stars%' THEN 2
                    WHEN feedback_text LIKE '%1 star%' THEN 1
                    ELSE 0
                END
            ORDER BY rating DESC
        """)
        
        results = cursor.fetchall()
        
        ratings = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total = 0
        weighted_sum = 0
        
        # results are list of tuples because we don't use dict factory on raw fetchall unless we convert
        # T-SQL GROUP BY logic is standard
        for row in results:
            rating, count = row[0], row[1]
            if rating > 0:
                ratings[rating] = count
                total += count
                weighted_sum += rating * count
        
        average = weighted_sum / total if total > 0 else 0
        
        _release_connection(conn)
        
        return jsonify({
            "success": True,
            "data": {
                "ratings": ratings,
                "total": total,
                "average": round(average, 2)
            }
        })
    except Exception as e:
        print(f"Error in satisfaction_ratings: {e}")
        return jsonify({
            "success": True,
            "data": {
                "ratings": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "total": 0,
                "average": 0
            }
        })


# =====================
# HEALTH CHECK
# =====================

@app.route('/health', methods=['GET'])
@app.route('/admin/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "admin-api"})


# =====================
# INSPECTOR ENDPOINTS
# =====================

import yaml
from datetime import datetime
from actions.conversation_db import _get_connection, _release_connection, get_conversation_transcript


def get_stories_and_rules():
    """Parse stories.yml and rules.yml to extract flow definitions."""
    flows = {"stories": [], "rules": []}
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    stories_path = os.path.join(base_path, "data", "stories.yml")
    if os.path.exists(stories_path):
        with open(stories_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
                flows["stories"] = data.get("stories", [])
            except Exception as e:
                print(f"Error parsing stories.yml: {e}")
    
    rules_path = os.path.join(base_path, "data", "rules.yml")
    if os.path.exists(rules_path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
                flows["rules"] = data.get("rules", [])
            except Exception as e:
                print(f"Error parsing rules.yml: {e}")
    
    return flows


def get_domain_info():
    """Parse domain.yml to extract intents, entities, actions, and slots."""
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    domain_path = os.path.join(base_path, "domain.yml")
    
    domain = {"intents": [], "entities": [], "actions": [], "slots": {}, "responses": []}
    
    if os.path.exists(domain_path):
        with open(domain_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
                domain["intents"] = data.get("intents", [])
                domain["entities"] = data.get("entities", [])
                domain["actions"] = data.get("actions", [])
                domain["slots"] = data.get("slots", {})
                domain["responses"] = list(data.get("responses", {}).keys())
            except Exception as e:
                print(f"Error parsing domain.yml: {e}")
    
    return domain


@app.route('/inspector/conversations', methods=['GET'])
def inspector_list_conversations():
    """Get list of conversations with detailed info for inspector."""
    try:
        limit = request.args.get('limit', 100, type=int)
        app_id_filter = request.args.get('app_id', None)
        
        conn = _get_connection()
        cursor = conn.cursor()
        
        # T-SQL TOP
        query = f'''
            SELECT TOP {limit}
                c.id, c.sender_id, c.app_id, c.user_id,
                c.started_at, c.last_activity, c.resolved,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id AND sender = 'user') as user_message_count,
                (SELECT COUNT(*) FROM actions WHERE conversation_id = c.id) as action_count,
                (SELECT TOP 1 type FROM feedback WHERE conversation_id = c.id ORDER BY timestamp DESC) as feedback
            FROM conversations c
        '''
        
        params = []
        if app_id_filter:
            query += " WHERE c.app_id = ?"
            params.append(app_id_filter)
        
        query += " ORDER BY c.last_activity DESC"
        
        cursor.execute(query, tuple(params))
        conversations = []
        
        for row in _fetchall_dict(cursor):
            conversations.append({
                "id": row['id'],
                "sender_id": row['sender_id'],
                "sender_id_short": row['sender_id'][:12] + "..." if row['sender_id'] and len(row['sender_id']) > 12 else row['sender_id'],
                "app_id": row['app_id'] or "General",
                "user_id": row['user_id'],
                "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                "last_activity": row['last_activity'].isoformat() if row['last_activity'] else None,
                "resolved": bool(row['resolved']),
                "message_count": row['message_count'],
                "user_message_count": row['user_message_count'],
                "action_count": row['action_count'],
                "feedback": row['feedback']
            })
        
        _release_connection(conn)
        return jsonify({"success": True, "data": conversations, "count": len(conversations)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/inspector/conversation/<sender_id>', methods=['GET'])
def inspector_get_conversation_detail(sender_id):
    """Get detailed conversation data including messages, intents, actions."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM conversations WHERE sender_id = ?', (sender_id,))
        conv = _fetchone_dict(cursor)
        
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found"}), 404
        
        conv_id = conv['id']
        
        # Get messages
        cursor.execute('''
            SELECT id, sender, text, intent, timestamp
            FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC
        ''', (conv_id,))
        messages = []
        intent_history = []
        
        for row in _fetchall_dict(cursor):
            msg = {
                "id": row['id'], "sender": row['sender'], "text": row['text'],
                "intent": row['intent'],
                "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None
            }
            messages.append(msg)
            if row['intent']:
                intent_history.append({
                    "intent": row['intent'],
                    "message": row['text'][:50] + "..." if row['text'] and len(row['text']) > 50 else row['text'],
                    "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None
                })
        
        # Get actions
        cursor.execute('''
            SELECT action_name, success, timestamp
            FROM actions WHERE conversation_id = ? ORDER BY timestamp ASC
        ''', (conv_id,))
        actions = [{"action": row['action_name'], "success": bool(row['success']),
                    "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None} 
                   for row in _fetchall_dict(cursor)]
        
        # Get feedback
        cursor.execute('SELECT type, timestamp FROM feedback WHERE conversation_id = ? ORDER BY timestamp ASC', (conv_id,))
        feedback = [{"type": row['type'], "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None} 
                    for row in _fetchall_dict(cursor)]
        
        _release_connection(conn)
        
        return jsonify({
            "success": True,
            "data": {
                "conversation": {
                    "id": conv['id'], "sender_id": conv['sender_id'], "app_id": conv['app_id'],
                    "user_id": conv['user_id'],
                    "started_at": conv['started_at'].isoformat() if conv['started_at'] else None,
                    "last_activity": conv['last_activity'].isoformat() if conv['last_activity'] else None,
                    "resolved": bool(conv['resolved'])
                },
                "messages": messages, "intent_history": intent_history, "actions": actions, "feedback": feedback,
                "stats": {
                    "total_messages": len(messages),
                    "user_messages": len([m for m in messages if m['sender'] == 'user']),
                    "bot_messages": len([m for m in messages if m['sender'] == 'bot']),
                    "actions_executed": len(actions),
                    "unique_intents": len(set(m['intent'] for m in messages if m['intent']))
                }
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/inspector/flows', methods=['GET'])
def inspector_get_flows():
    """Get all defined conversation flows from stories and rules."""
    try:
        flows = get_stories_and_rules()
        flow_diagrams = []
        
        for story in flows.get("stories", []):
            if isinstance(story, dict) and "story" in story:
                flow_diagrams.append({
                    "name": story.get("story", "Unknown"), "type": "story",
                    "steps": story.get("steps", [])
                })
        
        for rule in flows.get("rules", []):
            if isinstance(rule, dict) and "rule" in rule:
                flow_diagrams.append({
                    "name": rule.get("rule", "Unknown"), "type": "rule",
                    "steps": rule.get("steps", [])
                })
        
        return jsonify({"success": True, "data": flow_diagrams, "count": len(flow_diagrams)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/inspector/intents', methods=['GET'])
def inspector_get_intent_stats():
    """Get intent statistics."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT intent, COUNT(*) as count FROM messages 
            WHERE intent IS NOT NULL AND intent != '' GROUP BY intent ORDER BY count DESC
        ''')
        intent_distribution = {row['intent']: row['count'] for row in _fetchall_dict(cursor)}
        
        # T-SQL DATEPART(hour, timestamp)
        cursor.execute('''
            SELECT DATEPART(hour, timestamp) as hour, COUNT(*) as count
            FROM messages WHERE intent IS NOT NULL AND timestamp > DATEADD(hour, -24, GETDATE())
            GROUP BY DATEPART(hour, timestamp) ORDER BY hour
        ''')
        hourly_activity = {int(row['hour']): row['count'] for row in _fetchall_dict(cursor)}
        
        domain = get_domain_info()
        _release_connection(conn)
        
        return jsonify({
            "success": True,
            "data": {
                "distribution": intent_distribution, "hourly_activity": hourly_activity,
                "known_intents": domain["intents"],
                "total_intent_messages": sum(intent_distribution.values())
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/inspector/actions', methods=['GET'])
def inspector_get_action_stats():
    """Get action execution statistics."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT action_name, COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failure_count
            FROM actions GROUP BY action_name ORDER BY total DESC
        ''')
        
        action_stats = []
        for row in _fetchall_dict(cursor):
            total = row['total']
            success = row['success_count'] or 0
            action_stats.append({
                "action": row['action_name'], "total": total, "success": success,
                "failure": row['failure_count'] or 0,
                "success_rate": round((success / total) * 100, 1) if total > 0 else 0
            })
        
        _release_connection(conn)
        return jsonify({"success": True, "data": action_stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/inspector/domain', methods=['GET'])
def inspector_get_domain():
    """Get domain configuration (intents, entities, actions, slots)."""
    try:
        domain = get_domain_info()
        return jsonify({"success": True, "data": domain})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/inspector/health', methods=['GET'])
def inspector_health():
    """Inspector health check."""
    return jsonify({"status": "healthy", "service": "inspector-api", "timestamp": datetime.now().isoformat()})


if __name__ == '__main__':
    print("Starting Unified Server on port 8181...")
    print(f"Serving static files from: {STATIC_DIR}")
    print("  Admin Dashboard:        http://localhost:8181/admin.html")
    app.run(host='0.0.0.0', port=8181, debug=False)

# Project Change Log & Integration Summary

**Date:** 2026-02-03
**Objective:** Integrate Python/Rasa Chatbot into NopCommerce (IIS) with secure routing, visibility, and performance optimization.

---

## 1. Infrastructure & Networking

### A. Windows `hosts` File
*   **File:** `C:\Windows\System32\drivers\etc\hosts`
*   **Change:** Mapped `createl.shop` and `www.createl.shop` to `127.0.0.1`.
*   **Reason:** Fixes "NAT Loopback" latency issues. Allows the server to talk to itself via its public domain name instantly without going out to the internet firewall.

### B. IIS Reverse Proxy (`web.config`)
*   **File:** `C:\inetpub\wwwroot\Createl-V2\web.config`
*   **Change:** Added URL Rewrite rules.

```xml
<rewrite>
  <rules>
    <!-- Rule to Forward Webhooks traffic to Rasa Core (Port 5105) -->
    <rule name="ChatBotWebhookProxy" stopProcessing="true">
      <match url="^chatbot/webhooks/(.*)" />
      <action type="Rewrite" url="http://localhost:5105/webhooks/{R:1}" />
    </rule>
    <!-- Rule to Forward Socket.IO traffic to Rasa Core (Port 5105) -->
    <rule name="ChatBotSocketProxy" stopProcessing="true">
      <match url="^chatbot/socket.io/(.*)" />
      <action type="Rewrite" url="http://localhost:5105/socket.io/{R:1}" />
    </rule>

    <!-- Rule to Forward ROOT Socket.IO traffic to Rasa Core (Port 5105) - For clients dropping the path -->
    <rule name="ChatBotRootSocketProxy" stopProcessing="true">
      <match url="^socket.io/(.*)" />
      <action type="Rewrite" url="http://localhost:5105/socket.io/{R:1}" />
    </rule>

    <!-- Rule to Forward rest of /chatbot/* requests to the Python Server (Port 8181) -->
    <rule name="ChatBotProxy" stopProcessing="true">
      <match url="^chatbot/(.*)" />
      <conditions>
         <!-- Prevent loops -->
        <add input="{CACHE_URL}" pattern="^(https?)://" />
      </conditions>
      <!-- Changed to use http explicitly to avoid SSL mismatch -->
      <action type="Rewrite" url="http://localhost:8181/{R:1}" />
    </rule>
  </rules>
</rewrite>
```

---

## 2. Frontend Integration (NopCommerce Theme)

### A. View Modification (`_Root.cshtml`)
*   **File:** `C:\inetpub\wwwroot\Createl-V2\Themes\Pavilion\Views\Shared\_Root.cshtml`
*   **Major Upgrade:** Implemented **Shadow DOM Isolation**.

```html
<!-- Createl Chatbot -->

@if (showChatbot)
{
	<div id="chat-host" style="position: fixed; bottom: 20px; right: 20px; z-index: 2147483647; width: 0; height: 0; overflow: visible;"></div>
	<script>
	  // Chatbot Widget Loader (Shadow DOM Isolation)
	  (function() {
		const host = document.getElementById('chat-host');
		if (!host) return; // Safety check
		if (!host.shadowRoot) {
			const shadow = host.attachShadow({mode: 'open'});
			
			// Inject CSS and Widget into Shadow DOM
			const cssLink = document.createElement('link');
			cssLink.rel = 'stylesheet';
			cssLink.href = '/css/modern-web-interface.css?v=1.1';
			
			const widget = document.createElement('createl-chat-widget');
			widget.setAttribute('title', 'Createl Bot');
			widget.setAttribute('app-id', 'IT');
			widget.setAttribute('theme-id', '6');
			// Widget styles must be valid inside shadow too
			widget.style.cssText = "display: block; width: auto; height: auto;";
			
			shadow.appendChild(cssLink);
			shadow.appendChild(widget);
		}

		// Load the Component Logic (Global Registry)
		fetch('/js/createl-chat-widget.js?v=' + Date.now())
			.then(r => r.text())
			.then(code => {
				const s = document.createElement('script');
				s.textContent = code;
				document.body.appendChild(s);
			})
			.catch(e => console.error("WIDGET LOAD ERROR: " + e.message));
	  })();
	</script>
}
```

### B. Static Assets
*   **File:** `C:\inetpub\wwwroot\Createl-V2\wwwroot\css\modern-web-interface.css`
*   **Change:** Clean, standard CSS file (No Hacks).
*   **Usage:** Injected *inside* the Shadow Root via JS.

### C. Chatbot Client (`createl-chat-widget.js`)
*   **File:** `C:\inetpub\wwwroot\Createl-V2\wwwroot\js\createl-chat-widget.js`
*   **Change:** Patched URLs (`/chatbot`) & Removed Debug Alerts.

---

## 3. Backend Configuration (Rasa/Python)

### A. Database Connection (`endpoints.yml`)
*   **File:** `C:\inetpub\wwwroot\Chatbot\endpoints.yml`
*   **Change:** Updated `tracker_store` URL to use `localhost`.

```yaml
tracker_store:
  type: SQL
  dialect: "mssql+pyodbc"
  url: "mssql+pyodbc://createlsa:ABC123bedm@localhost/ChatBot?driver=ODBC+Driver+17+for+SQL+Server"
```

### B. App Configuration (`app.config`)
*   **Change:** Verified `NOP_API_URL` uses the public domain and `NOP_VERIFY_SSL` is managed correctly.


---

## 4. Automation Scripts

### A. Deployment Script (`deploy_chatbot.py`)
*   **Location:** `C:\inetpub\wwwroot\Chatbot\deploy_chatbot.py`
*   **Function:** Automated deployment that Patches URLs and removes Debug Alerts.

```python
import os
import shutil
import re

# -- CONFIGURATION --
# Source: Where your "fresh build" lands
SRC_DIR = r'C:\inetpub\wwwroot\Chatbot\client ui\dist-widget'
JS_FILENAME = 'createl-chat-widget.js'
CSS_FILENAME = 'modern-web-interface.css'

# Destination: Where IIS serves them statically
DEST_JS_DIR = r'C:\inetpub\wwwroot\Createl-V2\wwwroot\js'
DEST_CSS_DIR = r'C:\inetpub\wwwroot\Createl-V2\wwwroot\css'

def deploy():
    print("--- STARTING CHATBOT DEPLOYMENT ---")
    
    # 1. Verify Source Files Exist
    src_js = os.path.join(SRC_DIR, JS_FILENAME)
    src_css = os.path.join(SRC_DIR, CSS_FILENAME)
    
    if not os.path.exists(src_js):
        print(f"ERROR: Source JS not found at {src_js}")
        return
    if not os.path.exists(src_css):
        print(f"ERROR: Source CSS not found at {src_css}")
        return

    # 2. Patch Javascript File
    print(f"Reading {src_js}...")
    with open(src_js, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_len = len(content)
    print(f"Original Size: {original_len} bytes")

    # -- AUTO-PATCHING --
    # Replace Admin API (Port 8181) -> /chatbot
    content = re.sub(r'http://(localhost|127\.0\.0\.1):8181', '/chatbot', content)
    
    # Replace Rasa Core (Port 5105) -> /chatbot
    content = re.sub(r'http://(localhost|127\.0\.0\.1):5105', '/chatbot', content)

    # -- REMOVE DEBUG ALERTS --
    # Ensure production builds don't show popups
    if "alert('TOP OF FILE CHECK');" in content:
        print("Removing 'TOP OF FILE CHECK' alert...")
        content = content.replace("alert('TOP OF FILE CHECK');", "")
        
    if "alert('Widget JS Executed!');" in content:
        print("Removing 'Widget JS Executed!' alert...")
        content = content.replace("alert('Widget JS Executed!');", "")

    # -- UI OVERLAY FIX (Z-Index Patch) --
    if "z-index: 2147483647" in content:
        print("Patching Z-Index Container to be non-blocking...")
        content = content.replace("z-index: 2147483647", "z-index: 2147483647; pointer-events: none")

    # Safety Check: Verify Patch
    if '/chatbot' not in content:
        print("WARNING: The patch string '/chatbot' was not found in the output. Maybe the source file URLs changed?")
    else:
        print("Patches applied successfully.")

    # 3. Write to Destination
    dest_js = os.path.join(DEST_JS_DIR, JS_FILENAME)
    print(f"Deploying JS to {dest_js}...")
    with open(dest_js, 'w', encoding='utf-8') as f:
        f.write(content)
        
    # 4. Copy CSS (No patching needed usually, but good to move)
    dest_css = os.path.join(DEST_CSS_DIR, CSS_FILENAME)
    print(f"Deploying CSS to {dest_css}...")
    shutil.copy(src_css, dest_css)

    print("--- DEPLOYMENT COMPLETE ---")
    print("1. JS Patched & Copied.")
    print("2. CSS Copied.")
    print("3. Please refresh your browser to see changes.")

if __name__ == '__main__':
    deploy()
```

### B. Wrapper Script (`deploy_updates.bat`)
*   **Location:** `C:\inetpub\wwwroot\Chatbot\deploy_updates.bat`
*   **Function:** One-click execution of the Python deployment script using the correct Python environment.

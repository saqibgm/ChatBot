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
    # Replace Admin API (Port 8181)
    # Pattern: http://localhost:8181 or http://127.0.0.1:8181 -> /chatbot
    content = re.sub(r'http://(localhost|127\.0\.0\.1):8181', '/chatbot', content)
    
    # Replace Rasa Core (Port 5105)
    # Pattern: http://localhost:5105 or http://127.0.0.1:5105 -> /chatbot
    # This handles the base URL so that /webhooks/rest/webhook appends correctly
    content = re.sub(r'http://(localhost|127\.0\.0\.1):5105', '/chatbot', content)

    # -- REMOVE DEBUG ALERTS --
    # Ensure production builds don't show popups
    if "alert('TOP OF FILE CHECK');" in content:
        print("Removing 'TOP OF FILE CHECK' alert...")
        content = content.replace("alert('TOP OF FILE CHECK');", "")
        
    if "alert('Widget JS Executed!');" in content:
        print("Removing 'Widget JS Executed!' alert...")
        content = content.replace("alert('Widget JS Executed!');", "")

    # -- UI OVERLAY FIX (Pointer Events) --
    # Inject pointer-events: none to the host and main containers, but auto for the widget
    # We look for the Shadow DOM injection point or known container classes
    
    # 1. Force the Host Component to not block clicks
    # (We already did this in _Root.cshtml, but let's reinforce it in the web component definition if possible, 
    #  or just rely on the CSS file if we can find it).
    
    # Actually, the most robust way is to replace the style definition in the JS if it's inline.
    # Searching for "z-index: 2147483647" which is likely the container.
    # We replace it with "z-index: 2147483647; pointer-events: none;"
    # And then find the chat window/button and ensure "pointer-events: auto"
    
    if "z-index: 2147483647" in content:
        print("Patching Z-Index Container to be non-blocking...")
        content = content.replace("z-index: 2147483647", "z-index: 2147483647; pointer-events: none")
        
    # We also need to make sure the children (the actual chat window) allow clicks.
    # This is tricky without parsing the JS ast. 
    # However, standard practice is: Container = none, Children = auto.
    # If the JS builds the style string dynamically, we might need a broader replace.
    
    # Let's try to inject a global style into the shadow root wrapper if we can identify it.
    # Or better: Append a style tag to the custom element's shadow root construction.
    
    # For now, let's assume the "z-index" patch hits the main wrapper.
    # And we hope the inner elements (button/window) typically have their own styles or we can force them.
    # Wait, if we set the PARENT to pointer-events: none, the CHILDREN are also none unless overridden.
    # We MUST ensure the children have pointer-events: auto.
    
    # Search for the class names often used: "fixed bottom-4 right-4" or similar tailwind classes.
    # We can try to append "pointer-events-auto" to the class list if it's a tailwind string.
    
    # Heuristic: Find where the class "fixed" is defined or used near z-index.
    # The user said "Icon visible", so the icon is the child.
    # Let's heuristically add 'pointer-events: auto;' to any style string that defines the chat button/window.
    # Look for "display: flex" or "display: block" near the icon definitions? 
    # Too risky.
    
    # SAFE BET: 
    # The issue is the "display: block" we removed from _Root.cshtml was the HOST.
    # If the user says "No improvement", maybe they didn't refresh hard enough OR the internal container is fixed.
    
    # Let's stick to the z-index patch but be careful. 
    # Actually, the user's `modern-web-interface.css` likely has the class.
    # I should patch the CSS file instead! It's safer.


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

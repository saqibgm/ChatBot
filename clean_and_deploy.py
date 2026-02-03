import re

src = r'C:\inetpub\wwwroot\Chatbot\client ui\dist-widget\createl-chat-widget.js'
dst = r'C:\inetpub\wwwroot\Createl-V2\wwwroot\js\createl-chat-widget.js'

print(f"Reading from {src}...")
with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove specific alerts I added
content = content.replace("alert('TOP OF FILE CHECK');", "")
content = content.replace("alert('Widget JS Executed!');", "")

# Verify Patches
p1 = '/chatbot/webhooks' in content
p2 = '/chatbot/admin/themes' in content
p3 = 'const ADMIN_API_URL = "/chatbot"' in content

print(f"Patch 1 (Webhooks): {p1}")
print(f"Patch 2 (Themes):   {p2}")
print(f"Patch 3 (Base URL): {p3}")

if p1 and p2 and p3:
    print(f"Writing clean patched file to {dst}...")
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS")
else:
    print("ABORT: Missing patches!")

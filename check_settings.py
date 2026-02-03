import pyodbc
try:
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=Createl-V3.1;UID=createlsa;PWD=ABC123bedm;TrustServerCertificate=yes')
    cursor = conn.cursor()
    print("Checking Misc.WebApi settings:")
    cursor.execute("SELECT Name, Value FROM Setting WHERE Name LIKE 'misc.webapi%' OR Name LIKE 'adminapi%'")
    rows = cursor.fetchall()
    for r in rows:
        print(f"{r.Name}: {r.Value}")
    
    print("Checking security settings:")
    cursor.execute("SELECT Name, Value FROM Setting WHERE Name LIKE '%jwt%' OR Name LIKE '%key%' OR Name LIKE '%secret%' OR Value LIKE '%6800436ac8a8f13a5dea08c66ad6e2e14a6d3042d8287e877b54e1a9b09532e8%'")
    rows = cursor.fetchall()
    for r in rows:
        print(f"{r.Name}: {r.Value}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")

import json
import psycopg2

# Connect to your DB
conn = psycopg2.connect(
    host="localhost",
    database="earthquake_db",
    user="aryanraopippal",
    password=""
)
cur = conn.cursor()

print("\n=== LOADING company_data.json ===")

# Load raw dictionary
raw = json.load(open("company_data.json"))

# Convert dictionary → list
company_list = []
for ticker, data in raw.items():
    company_list.append({
        "ticker": ticker,
        "name": data["name"],
        "country": data["country"],
        "industry": data["industry"],
        "lat": data["lat"],
        "lon": data["lon"]
    })

print(f"Converted {len(company_list)} companies.")

# Insert into database
count = 0
for c in company_list:
    cur.execute("""
        INSERT INTO companies (ticker, name, country, industry, lat, lon, geo)
        VALUES (%s, %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        )
    """, (c["ticker"], c["name"], c["country"], c["industry"],
          c["lat"], c["lon"], c["lon"], c["lat"]))
    count += 1

conn.commit()
print(f"Inserted {count} companies into PostgreSQL!")

cur.close()
conn.close()

print("=== DONE ===")
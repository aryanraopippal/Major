import psycopg2

print("[SYSTEM] Initializing Global Supply Chain Injection...")

# Connect to your database
conn = psycopg2.connect(host="localhost", port=5432, database="earthquake_db", user="aryanraopippal", password="")
cur = conn.cursor()

# 1. Wipe the old, tiny company list
cur.execute("TRUNCATE TABLE companies RESTART IDENTITY;")

# 2. The Mega-List (Indian Heavy + Global Partners)
global_companies = [
    # --- INDIA (The Core) ---
    ("RELI.NS", "Reliance Industries", "India", "Energy/Conglomerate", 19.07, 72.87),
    ("TCS.NS", "Tata Consultancy Services", "India", "Tech", 18.97, 72.82),
    ("HDFCBANK.NS", "HDFC Bank", "India", "Finance", 19.01, 72.84),
    ("INFY.NS", "Infosys", "India", "Tech", 12.84, 77.66),
    ("ICICIBANK.NS", "ICICI Bank", "India", "Finance", 19.05, 72.87),
    ("SBIN.NS", "State Bank of India", "India", "Finance", 18.92, 72.80),
    ("BHARTIARTL.NS", "Bharti Airtel", "India", "Telecom", 28.61, 77.20),
    ("ITC.NS", "ITC Limited", "India", "Conglomerate", 22.57, 88.36),
    ("LT.NS", "Larsen & Toubro", "India", "Infrastructure", 19.11, 72.88),
    ("BAJFINANCE.NS", "Bajaj Finance", "India", "Finance", 18.55, 73.89),
    ("TAMO.NS", "Tata Motors", "India", "Automotive", 18.62, 73.81),
    ("MARUTI.NS", "Maruti Suzuki", "India", "Automotive", 28.40, 77.31),
    ("SUNPHARMA.NS", "Sun Pharma", "India", "Healthcare", 19.10, 72.86),
    ("M&M.NS", "Mahindra & Mahindra", "India", "Automotive", 18.92, 72.83),
    ("WIPRO.NS", "Wipro", "India", "Tech", 12.87, 77.68),
    ("HCLTECH.NS", "HCL Technologies", "India", "Tech", 28.53, 77.39),
    ("ADANIENT.NS", "Adani Enterprises", "India", "Conglomerate", 23.02, 72.57),
    ("ADANIPORTS.NS", "Adani Ports", "India", "Logistics", 22.82, 69.65),
    ("ONGC.NS", "ONGC", "India", "Energy", 30.32, 78.00),
    ("NTPC.NS", "NTPC Limited", "India", "Energy", 28.59, 77.23),
    ("JSWSTEEL.NS", "JSW Steel", "India", "Infrastructure", 15.17, 76.64),
    ("TATASTEEL.NS", "Tata Steel", "India", "Infrastructure", 22.80, 86.20),
    ("HINDALCO.NS", "Hindalco", "India", "Infrastructure", 19.02, 72.84),
    ("POWERGRID.NS", "Power Grid Corp", "India", "Energy", 28.46, 77.02),
    ("TECHM.NS", "Tech Mahindra", "India", "Tech", 18.61, 73.87),

    # --- ASIA PACIFIC (The Supply Chain) ---
    ("TSM", "TSMC", "Taiwan", "Tech Hardware", 24.77, 120.98),
    ("2317.TW", "Foxconn", "Taiwan", "Manufacturing", 25.04, 121.53),
    ("005930.KS", "Samsung Electronics", "South Korea", "Tech", 37.26, 127.02),
    ("005380.KS", "Hyundai Motor", "South Korea", "Automotive", 37.46, 126.88),
    ("7203.T", "Toyota Motor", "Japan", "Automotive", 35.08, 137.15),
    ("6758.T", "Sony Group", "Japan", "Tech", 35.62, 139.74),
    ("6861.T", "Keyence", "Japan", "Tech Hardware", 34.75, 135.50),
    ("BABA", "Alibaba Group", "China", "E-commerce", 30.27, 120.15),
    ("TCEHY", "Tencent", "China", "Tech", 22.54, 114.05),
    ("BYDDF", "BYD Co.", "China", "Automotive", 22.68, 114.36),
    ("DBS", "DBS Group", "Singapore", "Finance", 1.28, 103.85),
    ("SIA", "Singapore Airlines", "Singapore", "Logistics", 1.33, 103.95),
    ("BHP", "BHP Group", "Australia", "Mining", -37.81, 144.96),

    # --- NORTH AMERICA & EUROPE (The Buyers) ---
    ("AAPL", "Apple Inc.", "USA", "Tech", 37.33, -122.00),
    ("MSFT", "Microsoft", "USA", "Tech", 47.63, -122.12),
    ("NVDA", "NVIDIA", "USA", "Tech Hardware", 37.37, -121.96),
    ("AMZN", "Amazon", "USA", "E-commerce/Cloud", 47.60, -122.33),
    ("TSLA", "Tesla", "USA", "Automotive", 30.22, -97.87),
    ("ASML", "ASML Holding", "Netherlands", "Tech Hardware", 51.40, 5.46),
    ("VOW3.DE", "Volkswagen", "Germany", "Automotive", 52.42, 10.78),
    ("MC.PA", "LVMH", "France", "Retail", 48.87, 2.30),
    ("NESN.SW", "Nestle", "Switzerland", "Consumer", 46.46, 6.84),
    ("SHEL", "Shell plc", "UK", "Energy", 51.50, -0.12),
]

for ticker, name, country, ind, lat, lon in global_companies:
    try:
        cur.execute(f"""
            INSERT INTO companies (ticker, name, country, industry, lat, lon, geo)
            VALUES ('{ticker}', '{name}', '{country}', '{ind}', {lat}, {lon}, ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326))
            ON CONFLICT DO NOTHING;
        """)
    except Exception as e:
        print(f"Skipping {name}: {e}")
        conn.rollback()

conn.commit()
cur.close()
conn.close()
print("[SUCCESS] 48 Global Mega-Corps injected. Supply Web Ready.")
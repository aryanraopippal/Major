import joblib
import random
import math

try:
    rf_model = joblib.load('rf_impact_model.joblib')
    xgb_model = joblib.load('xgb_recovery_model.joblib')
    ai_active = True
except:
    ai_active = False

def run_earthquake(params, db_conn, financial_model=None):
    lat, lon, mag, depth = params["lat"], params["lon"], params["mag"], params["depth"]
    cur = db_conn.cursor()
    affected = {"cities": [], "transportation": [], "infrastructure": [], "companies": []}
    
    max_physical_distance_km = 0 
    total_impact = 0
    total_assets_hit = 0

    warnings = []
    if mag >= 9.0: warnings.append("⚠️ [CRITICAL] GROUND RUPTURE LIKELY: MASSIVE LITHOSPHERIC CRACKS")
    if mag > 7.0: warnings.append("🌊 [WARNING] TSUNAMI THREAT EVALUATION INITIATED")

    try:
        epicenter_geom = f'SRID=4326;POINT({lon} {lat})'
        query_radius_m = max(50000, (mag ** 3) * 1500) 
        global_trade_radius = 12000000 

        tables = [("cities", "cities", query_radius_m, 7.0), ("transportation", "transportation", query_radius_m, 6.0), ("infrastructure", "infrastructure", query_radius_m, 8.0), ("companies", "companies", global_trade_radius, 5.0)]
        
        for table, key, radius, default_vuln in tables:
            cur.execute(f"SELECT name, ST_Y(geo::geometry), ST_X(geo::geometry), ST_Distance(geo, '{epicenter_geom}') / 1000 FROM {table} WHERE ST_DWithin(geo, '{epicenter_geom}', {radius})")
            for name, t_lat, t_lon, dist in cur.fetchall():
                
                # SCIENTIFIC DECAY FALLBACK
                if ai_active:
                    impact = rf_model.predict([[mag, dist, default_vuln]])[0]
                else:
                    impact = mag - (2.1 * math.log10(dist + 1)) + (10 / max(1, depth))
                
                impact = max(0, min(10, impact + random.uniform(-0.04, 0.04))) # Cap at 10
                
                if impact > 0.2: 
                    item = {"name": name, "lat": t_lat, "lon": t_lon, "distance": round(dist, 1), "impact_score": round(impact, 2), "type": "Seismic Asset"}
                    
                    if key == "companies":
                        item["predicted_drop_percent"] = round(impact * 1.5, 2)
                        item["industry"] = "Global Market"
                        item["type"] = "Company"
                    else:
                        max_physical_distance_km = max(max_physical_distance_km, dist)
                    
                    affected[key].append(item)
                    total_impact += impact
                    total_assets_hit += 1

    except Exception as e: return {"error": str(e)}
    finally: cur.close()

    if max_physical_distance_km == 0: max_physical_distance_km = query_radius_m / 1000.0
    macro_recovery_years = xgb_model.predict([[mag, max_physical_distance_km, 8.0]])[0] if ai_active else mag / 2

    # REALISTIC PROJECTIONS TIED TO TOTAL IMPACT
    base_price_drop = min(65.0, (total_impact / 1000.0) * 1.8) # Huge impact = Huge Drop
    base_arch_loss = int(total_impact * 25)

    affected["type"] = "earthquake"
    affected["max_distance_km"] = round(max_physical_distance_km, 1) 
    affected["warnings"] = warnings 
    affected["predictions"] = { 
        "price_fluctuation": f"-{round(base_price_drop + random.uniform(-0.5, 0.5), 2)}%", 
        "homelessness_rate": f"{round((total_impact / max(1, total_assets_hit)) * 2.5, 2)}%", 
        "architecture_loss": f"{base_arch_loss:,} critical structures", 
        "recovery_rate": f"{round(macro_recovery_years, 1)} years", 
        "city_impact_score": round(total_impact / max(1, len(affected["cities"])), 2) 
    }
    return affected
import joblib
import random
import math

try:
    rf_model = joblib.load('rf_impact_model.joblib')
    xgb_model = joblib.load('xgb_recovery_model.joblib')
    kmeans_model = joblib.load('kmeans_zone_model.joblib')
    ai_active = True
except:
    ai_active = False

def run_flood(params, db_conn, financial_model=None):
    rainfall_mm = params["mag"] 
    cur = db_conn.cursor()
    affected = {"cities": [], "transportation": [], "infrastructure": [], "companies": []}
    
    max_physical_distance_km = 0 
    total_impact = 0
    total_assets_hit = 0

    try:
        epicenter_geom = f'SRID=4326;POINT({params["lon"]} {params["lat"]})'
        query_radius_m = max(20000, 1000 * rainfall_mm) 
        global_trade_radius = 5000000 

        tables = [("cities", "cities", query_radius_m, 6.0), ("transportation", "transportation", query_radius_m, 9.0), ("infrastructure", "infrastructure", query_radius_m, 7.0), ("companies", "companies", global_trade_radius, 3.0)]
        
        for table, key, radius, default_vuln in tables:
            cur.execute(f"SELECT name, ST_Y(geo::geometry), ST_X(geo::geometry), ST_Distance(geo, '{epicenter_geom}') / 1000 FROM {table} WHERE ST_DWithin(geo, '{epicenter_geom}', {radius})")
            for name, t_lat, t_lon, dist in cur.fetchall():
                
                if ai_active:
                    ai_intensity = rainfall_mm / 15.0 
                    impact = rf_model.predict([[ai_intensity, dist, default_vuln]])[0]
                else:
                    impact = (rainfall_mm/10) - (2.0 * math.log10(dist + 1))
                
                impact = max(0, min(10, impact + random.uniform(-0.02, 0.05))) 
                
                if impact > 0.5: 
                    item = {"name": name, "lat": t_lat, "lon": t_lon, "distance": round(dist, 1), "impact_score": round(impact, 2), "type": "Submerged Asset"}
                    
                    if key == "companies":
                        item["predicted_drop_percent"] = round(impact * 0.9, 2)
                        item["industry"] = "Supply Chain"
                        item["type"] = "Company"
                    else:
                        max_physical_distance_km = max(max_physical_distance_km, dist)
                    
                    affected[key].append(item)
                    total_impact += impact
                    total_assets_hit += 1

    except Exception as e: return {"error": str(e)}
    finally: cur.close()

    if max_physical_distance_km == 0: max_physical_distance_km = query_radius_m / 1000.0
    ai_intensity = rainfall_mm / 15.0
    macro_recovery_years = xgb_model.predict([[ai_intensity, max_physical_distance_km, 8.0]])[0] if ai_active else rainfall_mm / 50

    base_price_drop = min(50.0, (total_impact / 1000.0) * 1.1) 
    base_arch_loss = int(total_impact * 15)

    affected["type"] = "flood"
    affected["max_distance_km"] = round(max_physical_distance_km, 1)
    affected["predictions"] = { 
        "price_fluctuation": f"-{round(base_price_drop + random.uniform(-0.1, 0.1), 2)}%", 
        "homelessness_rate": f"{round((total_impact / max(1, total_assets_hit)) * 1.5, 2)}%", 
        "architecture_loss": f"{base_arch_loss:,} submerged units", 
        "recovery_rate": f"{round(macro_recovery_years, 1)} years", 
        "city_impact_score": round(total_impact / max(1, len(affected["cities"])), 2) 
    }
    return affected
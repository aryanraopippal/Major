from flask import Flask, render_template_string, request, jsonify
import requests
import psycopg2
from datetime import datetime, timedelta, timezone
import os
import joblib

# --- SPECIALIST IMPORTS ---
from engine.disaster_engine import run_disaster
from engine.earthquake_model import run_earthquake
from engine.tsunami_model import run_tsunami
from engine.flood_model import run_flood

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['DEBUG'] = True

# --- Configuration ---
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "earthquake_db")
DB_USER = os.environ.get("DB_USER", "aryanraopippal")
DB_PASS = os.environ.get("DB_PASS", "")

GDACS_API_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventlist=TS,FL&fromdate=" + (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
MAX_LAND_PROXIMITY_KM = 80.0 
ASIA_BBOX = { "minLat": -10, "maxLat": 80, "minLon": 25, "maxLon": 180 }

financial_model = None

def load_financial_assets():
    global financial_model
    try:
        financial_model = joblib.load('trained_model.joblib')
    except:
        pass

INTERCEPT, COEF_MAG, COEF_SIG, COEF_CDI, COEF_DIST, COEF_NST, COEF_GAP, COEF_DEPTH = 1.954, 0.395, 0.001, 0.300, -0.002, 0.0007, -0.002, -0.006

def calculate_impact_score(magnitude, sig, cdi, distanceKM, nst, gap, depth):
    return INTERCEPT + (COEF_MAG * magnitude) + (COEF_SIG * sig) + (COEF_CDI * cdi) + (COEF_DIST * distanceKM) + (COEF_NST * nst) + (COEF_GAP * gap) + (COEF_DEPTH * depth)

def get_db_connection():
    try:
        return psycopg2.connect(host=DB_HOST, port=os.environ.get("PGPORT", 5432), database=DB_NAME, user=DB_USER, password=DB_PASS)
    except:
        return None

def predict_advanced_impact(lat, lon, mag, depth, sig, cdi, nst, gap):
    conn = get_db_connection()
    if not conn: return {} 
    cur = None 
    nearest_city_data = None
    city_impact_score = 0 
    dist_km = 0

    try:
        cur = conn.cursor()
        query = "SELECT a.city_name, a.city_population, a.vulnerability_factor, ST_Distance(c.geo, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) / 1000 AS distance_km FROM quake_analysis a JOIN cities c ON a.city_name = c.name WHERE c.geo IS NOT NULL ORDER BY ST_Distance(c.geo, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) LIMIT 1"
        cur.execute(query, (lon, lat, lon, lat))
        result = cur.fetchone()
        if result:
            name, pop, vuln, dist_km = result
            nearest_city_data = { "name": name, "population": pop or 0, "vulnerability_factor": float(vuln or 0), "distance_km": dist_km or 1000 }
            city_impact_score = calculate_impact_score(mag, sig, cdi, nearest_city_data["distance_km"], nst, gap, depth)
    except:
        if conn: conn.rollback() 
    finally:
        if cur: cur.close()
        if conn: conn.close()

    if not nearest_city_data:
        return { "price_fluctuation": "N/A", "homelessness_rate": "N/A", "architecture_loss": "N/A", "recovery_rate": "N/A", "city_impact_score": 0, "city_name": "N/A", "city_vulnerability": 0 }

    city_pop = nearest_city_data["population"]
    vuln_factor = nearest_city_data["vulnerability_factor"]
    arch_loss_raw = city_pop * (max(0, city_impact_score - 4) / 10) * (1 + vuln_factor / 100) * 0.05 
    architecture_loss = round(arch_loss_raw) if arch_loss_raw >= 1 else 0
    homeless_rate_raw = (architecture_loss / city_pop) * 100 * (1 + vuln_factor / 50) * 1.5 if city_pop > 0 else 0
    price_fluct_raw = (max(0, city_impact_score - 4)) * 0.3 + max(0, mag - 5) * 0.2 + vuln_factor * 0.1 
    recovery_years_raw = 0.5 + (architecture_loss / city_pop) * 100 if city_pop > 0 else 0.5 + max(0, mag - 6) * 1 + vuln_factor * 0.5

    return {
        "price_fluctuation": f"{round(price_fluct_raw, 2)}%",
        "homelessness_rate": f"{round(homeless_rate_raw, 2)}%",
        "architecture_loss": f"{architecture_loss:,} buildings",
        "recovery_rate": f"{round(recovery_years_raw, 1)} years",
        "city_impact_score": city_impact_score,
        "city_name": nearest_city_data["name"],
        "city_vulnerability": vuln_factor,
        "nearest_city_distance_km": dist_km 
    }

# --- MAIN APP ROUTE & UI ---
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Global Events Ripple Predictor</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&display=swap');
    html, body { height: 100%; margin: 0; padding: 0; font-family: 'Fira Code', monospace; background-color: #000000; color: #00ff00; overflow-y: auto; overflow-x: hidden; }
    #app-container { min-height: 100vh; display: grid; grid-template-columns: 3fr 2fr; grid-template-rows: auto 55vh auto; gap: 15px; padding: 15px; box-sizing: border-box; }
    #header { grid-column: 1 / 3; background-color: #111; border: 1px solid #333; border-radius: 4px; padding: 15px; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid #ff9900; }
    #header h2 { font-size: 1.5rem; font-weight: 600; color: #ff9900; margin: 0; text-transform: uppercase; letter-spacing: 2px;}
    #map-summary-container, #detail-view-panel, #summary-controls-panel, #detail-graph-container { background-color: #0a0a0a; border: 1px solid #333; border-radius: 4px; padding: 15px; display: flex; flex-direction: column; }
    #map-summary-container { grid-column: 1 / 2; grid-row: 2 / 3; }
    #detail-view-panel { grid-column: 2 / 3; grid-row: 2 / 3; gap: 10px; overflow-y: auto; }
    #summary-controls-panel { grid-row: 3 / 4; grid-column: 1 / 2; gap: 15px; max-height: 40vh; overflow-y: auto; }
    #detail-graph-container { grid-column: 2 / 3; grid-row: 3 / 4; max-height: 40vh; overflow-y: auto; }
    #map { flex-grow: 1; min-height: 350px; border-radius: 4px; filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(120%); }
    .card-title { font-size: 1.1rem; font-weight: 600; color: #00ff00; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 5px; text-transform: uppercase;}
    .data-label { color: #888; font-size: 0.9em; }
    .data-value { color: #fff; font-weight: 600; font-size: 1em; }
    #analysis-buttons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; flex-shrink: 0; }
    .analysis-btn { padding: 8px 5px; border: 1px solid #00ff00; border-radius: 2px; background-color: transparent; color: #00ff00; cursor: pointer; font-size: 0.85em; text-transform: uppercase; font-weight: 600; }
    .analysis-btn:hover:not(:disabled) { background-color: rgba(0, 255, 0, 0.2); }
    .analysis-btn:disabled { border-color: #333; color: #555; cursor: not-allowed; }
    .analysis-btn.active { background-color: #00ff00; color: #000; }
    #manual-analysis-section { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; background-color: #111; padding: 15px; border: 1px solid #333;}
    #manual-analysis-section input, #manual-analysis-section select { background-color: #000; color: #00ff00; border: 1px solid #333; padding: 5px; font-family: 'Fira Code', monospace; width: 100%; box-sizing: border-box; }
    #btn-manual-run { background-color: #00ff00; color: #000; border: none; font-weight: 600;}
    #btn-manual-clear { background-color: transparent; color: #ff3333; border: 1px solid #ff3333; font-weight: 600;}
    
    .severity-btn { flex: 1; padding: 8px 0; background: #222; color: #fff; border: 1px solid #444; cursor: pointer; font-weight: 600; transition: all 0.2s; border-radius: 2px; }
    .severity-btn:hover { background: #444; }
    .severity-btn.active-tsunami { background: #0088ff; color: #000; border-color: #0088ff; }
    .severity-btn.active-flood { background: #00ff00; color: #000; border-color: #00ff00; }

    .mini-chart-wrapper { background-color: #111; padding: 10px; border: 1px solid #333; height: 200px; min-width: 200px; display: flex; flex-direction: column; }
    .chart-description { background-color: #111; border-left: 3px solid #ff9900; padding: 10px; margin-top: 15px; font-size: 0.85rem; color: #ccc;}
    .detail-item { padding: 8px 0; border-bottom: 1px solid #222; }
    .impact-score { color: #ff3333; font-weight: 600; }
    </style>
</head>
<body>
    <div id="app-container">
        <div id="header">
            <h2>DYNAMIC MULTI-DOMAIN RIPPLE INTELLIGENCE SYSTEM</h2>
            <small class="text-xs" style="color:#00ff00;">STATUS: MULTI-HAZARD AI ONLINE | OPR: ARYAN</small>
        </div>

        <div id="map-summary-container">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 10px;">
                <h3 class="card-title" style="border:none; margin:0; padding:0;">LIVE GEOSPATIAL FEED</h3>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <label style="color:#888; font-size:0.8em; font-weight:600;">TIMEFRAME:</label>
                    <select id="time-filter" style="background:#000; color:#00ff00; border:1px solid #333; padding:5px; font-family:'Fira Code', monospace; outline:none; cursor:pointer;">
                        <option value="24h">LIVE (LAST 24 HOURS)</option>
                        <option value="7d">RECENT (LAST 7 DAYS)</option>
                        <option value="30d">ARCHIVE (LAST 30 DAYS)</option>
                        <option value="1y">YEARLY (MAJOR EVENTS)</option>
                    </select>
                </div>
            </div>
            <div id="map" class="flex-grow"></div>
        </div>

        <div id="detail-view-panel">
            <h3 class="card-title">SECTOR ANALYSIS PROTOCOLS</h3>
            <div id="analysis-buttons">
                <button id="btn-cities" class="analysis-btn" disabled>CITIES</button>
                <button id="btn-transport" class="analysis-btn" disabled>LOGISTICS</button>
                <button id="btn-infra" class="analysis-btn" disabled>INFRASTRUCTURE</button>
                <button id="btn-finance" class="analysis-btn" disabled>MARKETS</button>
                <button id="btn-predict" class="analysis-btn" disabled>PROJECTIONS</button>
                <button id="btn-overall" class="analysis-btn" disabled>MACRO SUMMARY</button>
            </div>
            <h3 class="card-title" style="margin-top:15px; border-color:#ff9900; color:#ff9900;">ASSET DAMAGE LOG</h3>
            <div id="dynamic-report-content" class="flex-grow">
                <p style="color:#555;">[AWAITING SECTOR SELECTION...]</p>
            </div>
        </div>

        <div id="summary-controls-panel">
            <h3 class="card-title">EVENT TELEMETRY</h3>
            <div id="earthquake-summary" class="flex-grow">
                <p style="color:#555;">[SELECT LIVE EVENT FROM MAP OR INITIATE MANUAL SIMULATION]</p>
            </div>

            <h3 class="card-title" style="border-color:#ff3333; color:#ff3333; margin-top:10px;">MANUAL OVERRIDE / SIMULATION</h3>
            <div id="manual-analysis-section">
                <div style="grid-column: span 2;">
                    <label style="color:#888; font-size:0.8em;">EVENT CLASSIFICATION</label>
                    <select id="disaster-type">
                        <option value="earthquake">SEISMIC (EARTHQUAKE)</option>
                        <option value="tsunami">OCEANIC (TSUNAMI)</option>
                        <option value="flood">HYDROLOGICAL (FLOOD)</option>
                    </select>
                </div>
                
                <div><label for="manual-lat" style="color:#888; font-size:0.8em;">LATITUDE</label><input type="text" id="manual-lat" placeholder="0.0000"></div>
                <div><label for="manual-lon" style="color:#888; font-size:0.8em;">LONGITUDE</label><input type="text" id="manual-lon" placeholder="0.0000"></div>
                
                <div id="seismic-inputs" style="display: contents;">
                    <div><label style="color:#888; font-size:0.8em;">SEISMIC MAGNITUDE</label><input type="number" id="manual-mag" step="0.1" value="6.5"></div>
                    <div><label style="color:#888; font-size:0.8em;">DEPTH (KM)</label><input type="number" id="manual-depth" step="1" value="10"></div>
                </div>

                <div id="advanced-severity-panel" style="display: none; grid-column: span 2; margin-top: 5px;">
                    <label style="color:#888; font-size:0.8em; margin-bottom:5px; display:block;">DISASTER SEVERITY INDEX (1-10)</label>
                    <div id="severity-buttons" style="display: flex; gap: 5px; width: 100%;"></div>
                    <div id="severity-readout" style="margin-top: 10px; padding: 10px; background: #1a1a1a; border-left: 3px solid #0088ff; color: #fff; font-size: 0.9em; font-family: sans-serif;">
                        [AWAITING SEVERITY SELECTION]
                    </div>
                </div>
                
                <button id="btn-manual-run" class="analysis-btn" style="grid-column: span 1; margin-top: 10px;">EXECUTE SIMULATION</button>
                <button id="btn-manual-clear" class="analysis-btn" style="grid-column: span 1; margin-top: 10px;">ABORT / CLEAR</button>
            </div>
        </div>

        <div id="detail-graph-container">
            <h3 class="card-title" style="border-color:#0088ff; color:#0088ff;">DATA VISUALIZATION</h3>
            <div id="chart-description-container" class="chart-description"><p>[STANDBY FOR TELEMETRY DATA...]</p></div>
            <div id="chart-collection"><p style="color:#555;">[NO DATA STREAMS ACTIVE]</p></div>
        </div>
    </div>

    <script>
        let map = L.map('map').setView([25, 95], 4);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap' }).addTo(map);

        let epicenterMarker = null;      
        let impactZones = [];   
        let liveEventsLayer = L.layerGroup().addTo(map);
        let activeMarkersLayer = L.layerGroup().addTo(map); 
        let affectedLinesLayer = L.layerGroup().addTo(map);
        
        let refreshTimer = null;
        let currentAnalysisResults = null; 
        let currentEpicenterInfo = null;  
        let globalRawEvents = []; 

        const analysisButtons = [document.getElementById('btn-cities'), document.getElementById('btn-transport'), document.getElementById('btn-infra'), document.getElementById('btn-finance'), document.getElementById('btn-predict'), document.getElementById('btn-overall')];
        const summaryDiv = document.getElementById('earthquake-summary');
        const dynamicReportContent = document.getElementById('dynamic-report-content');
        const chartCollectionDiv = document.getElementById('chart-collection');
        const chartDescriptionContainer = document.getElementById('chart-description-container');

        const manualLat = document.getElementById('manual-lat');
        const manualLon = document.getElementById('manual-lon');
        const manualMag = document.getElementById('manual-mag');
        const manualDepth = document.getElementById('manual-depth');

        const transportColors = { "Airport": "#FF4F4F", "Port": "#4F9FFF", "Rail Hub": "#2ECC71", "default": "#888888" };
        const infraColors = { "default": "#888888" };
        const cityColor = "#FFA500"; 
        const financeColor = "#E74C3C"; 

        let currentCharts = []; 

        // Severity Data
        const tsunamiData = { 1: {wave:1.0, desc:"Minor Surge"}, 2: {wave:1.5, desc:"Strong Surge"}, 3: {wave:2.5, desc:"Significant Inundation"}, 4: {wave:4.0, desc:"Dangerous Wave"}, 5: {wave:6.5, desc:"Highly Destructive"}, 6: {wave:9.0, desc:"Major Tsunami"}, 7: {wave:12.0, desc:"Catastrophic"}, 8: {wave:16.0, desc:"Extreme Catastrophe"}, 9: {wave:22.0, desc:"Mega-Tsunami"}, 10: {wave:30.0, desc:"Apocalyptic Event"} };
        const floodData = { 1: {rain:20, dur:12, desc:"Nuisance Flooding"}, 2: {rain:30, dur:18, desc:"Minor Urban Pooling"}, 3: {rain:50, dur:24, desc:"Urban Flash Flood"}, 4: {rain:70, dur:24, desc:"Significant Flash Flood"}, 5: {rain:100, dur:36, desc:"Severe River Overflow"}, 6: {rain:130, dur:36, desc:"Major Infrastructure Threat"}, 7: {rain:165, dur:48, desc:"Catastrophic Deluge"}, 8: {rain:210, dur:48, desc:"Extreme Flood Event"}, 9: {rain:260, dur:72, desc:"Historic Regional Flood"}, 10: {rain:320, dur:72, desc:"Apocalyptic Deluge"} };
        
        let activeSeverityLevel = 5;
        const btnContainer = document.getElementById('severity-buttons');
        for(let i=1; i<=10; i++) {
            let b = document.createElement('button'); b.innerText = i; b.className = 'severity-btn'; b.onclick = () => selectSeverity(i); btnContainer.appendChild(b);
        }

        function selectSeverity(level) {
            activeSeverityLevel = level;
            const type = document.getElementById('disaster-type').value;
            document.querySelectorAll('.severity-btn').forEach(b => { b.className = 'severity-btn'; if(parseInt(b.innerText) === level) b.classList.add(type === 'tsunami' ? 'active-tsunami' : 'active-flood'); });
            const readout = document.getElementById('severity-readout');
            if(type === 'tsunami') readout.innerHTML = `<strong>LEVEL ${level}: ${tsunamiData[level].desc.toUpperCase()}</strong><br><span style="color:#0088ff;">> AI INPUT: ${tsunamiData[level].wave}m Wave Height</span>`;
            else if(type === 'flood') readout.innerHTML = `<strong>LEVEL ${level}: ${floodData[level].desc.toUpperCase()}</strong><br><span style="color:#00ff00;">> AI INPUT: ${floodData[level].rain}mm Precipitation</span>`;
        }

        document.getElementById('disaster-type').addEventListener('change', function(e) {
            const type = e.target.value;
            document.getElementById('seismic-inputs').style.display = type === 'earthquake' ? 'contents' : 'none';
            document.getElementById('advanced-severity-panel').style.display = type === 'earthquake' ? 'none' : 'block';
            if(type !== 'earthquake') selectSeverity(activeSeverityLevel);
            plotFilteredEvents(); 
        });

        function plotFilteredEvents() {
            liveEventsLayer.clearLayers();
            if(currentAnalysisResults) return; 
            const currentType = document.getElementById('disaster-type').value;
            
            globalRawEvents.forEach(eq => {
                if(eq.type !== currentType) return; 
                let color = eq.type === 'tsunami' ? '#0088ff' : (eq.type === 'flood' ? '#00ff00' : '#ff3333');
                let marker = L.circleMarker([eq.lat, eq.lon], { radius: 6, color, fillColor: color, fillOpacity: 0.8, weight: 2 });
                marker.bindPopup(`<strong>LIVE ${eq.type.toUpperCase()}</strong><br>Loc: ${eq.place}`);
                marker.on('click', () => { 
                    document.getElementById('manual-lat').value = eq.lat; document.getElementById('manual-lon').value = eq.lon;
                    if(eq.type === 'earthquake') { document.getElementById('manual-mag').value = eq.mag; document.getElementById('manual-depth').value = eq.depth; }
                    document.getElementById('btn-manual-run').click(); 
                });
                marker.addTo(liveEventsLayer);
            });
        }

        function drawImpactZones(lat, lon, maxRadius, colorStr) {
             impactZones.forEach(z => map.removeLayer(z));
             impactZones = [];
             if (!maxRadius || maxRadius <= 0) return;
             
             // REVERSED ORDER: Draw largest to smallest to fix Z-Index hover bug
             const zones = [
                 { r: maxRadius * 1.00, color: '#888888', opacity: 0.1, label: 'ZONE 4: FELT AREA / MINOR RIPPLE' },
                 { r: maxRadius * 0.70, color: '#ffff00', opacity: 0.2, label: 'ZONE 3: MODERATE DISRUPTION' },
                 { r: maxRadius * 0.40, color: '#ff6600', opacity: 0.4, label: 'ZONE 2: SEVERE DAMAGE' },
                 { r: maxRadius * 0.15, color: '#ff0000', opacity: 0.6, label: 'ZONE 1: CRITICAL DESTRUCTION' }
             ];

             zones.forEach((z, i) => {
                 setTimeout(() => {
                     let circle = L.circle([lat, lon], { 
                         radius: z.r * 1000, 
                         color: z.color, 
                         fillColor: z.color, 
                         fillOpacity: z.opacity, 
                         weight: 1,
                         interactive: true,
                         bubblingMouseEvents: true
                     }).addTo(map);

                     circle.bindTooltip(`<div style="font-family:'Fira Code', monospace; color:#fff; background:#000; padding:5px; border:1px solid ${z.color};"><strong>${z.label}</strong><br>Radius: ${Math.round(z.r)}km</div>`, {
                         sticky: true,
                         direction: 'top',
                         opacity: 0.9
                     });

                     impactZones.push(circle);
                     if (z.label.includes('ZONE 1')) circle.bringToFront();
                 }, i * 150); 
             });
        }

        function animateLine(lat1, lon1, lat2, lon2, color, isGlobalLine = false) {
            let weight = isGlobalLine ? 0.8 : 1.5;
            let opacity = isGlobalLine ? 0.3 : 0.6;
            let line = L.polyline([[lat1, lon1], [lat1, lon1]], { color: color, weight: weight, opacity: opacity, dashArray: isGlobalLine ? "5, 5" : "" }).addTo(affectedLinesLayer); 
            let steps = 50, currentStep = 0;
            let interval = setInterval(() => {
                currentStep++;
                let lat = lat1 + (lat2 - lat1) * (currentStep / steps);
                let lon = lon1 + (lon2 - lon1) * (currentStep / steps);
                if (affectedLinesLayer.hasLayer(line)) line.setLatLngs([[lat1, lon1], [lat, lon]]);
                if (currentStep >= steps) clearInterval(interval);
            }, 15);
        }

        function clearAnalysisDisplay() {
            activeMarkersLayer.clearLayers(); affectedLinesLayer.clearLayers();
            if (epicenterMarker) map.removeLayer(epicenterMarker);
            impactZones.forEach(z => map.removeLayer(z)); impactZones = [];

            dynamicReportContent.innerHTML = '<p style="color:#555;">[AWAITING SECTOR SELECTION...]</p>';
            chartCollectionDiv.innerHTML = '';
            chartDescriptionContainer.innerHTML = '<p>[STANDBY FOR TELEMETRY DATA...]</p>';
            currentCharts.forEach(chart => chart.destroy()); currentCharts = []; 

            currentAnalysisResults = null; currentEpicenterInfo = null;
            analysisButtons.forEach(btn => { btn.disabled = true; btn.classList.remove('active'); });
            summaryDiv.innerHTML = '<p style="color:#555;">[SELECT LIVE EVENT FROM MAP OR INITIATE MANUAL SIMULATION]</p>';
        }

        function setActiveButton(clickedButton) { analysisButtons.forEach(btn => btn.classList.remove('active')); if (clickedButton) clickedButton.classList.add('active'); }
        function createMiniChart(id, title) { const chartWrapper = document.createElement('div'); chartWrapper.className = 'mini-chart-wrapper'; chartWrapper.innerHTML = `<h5 class="text-sm font-semibold text-gray-300 mb-2">${title}</h5><canvas id="${id}"></canvas>`; chartCollectionDiv.appendChild(chartWrapper); return document.getElementById(id).getContext('2d'); }
        
        function generateSectorCharts(sectorKey, dataList, title) {
            chartCollectionDiv.innerHTML = ''; currentCharts.forEach(chart => chart.destroy()); currentCharts = [];
            if (dataList.length === 0) return;
            
            const sortedData = [...dataList].sort((a, b) => (sectorKey === 'finance' ? a.predicted_drop_percent : a.impact_score) - (sectorKey === 'finance' ? b.predicted_drop_percent : b.impact_score));
            const top10 = [...dataList].sort((a, b) => (sectorKey === 'finance' ? b.predicted_drop_percent : b.impact_score) - (sectorKey === 'finance' ? a.predicted_drop_percent : a.impact_score)).slice(0, 10);
            const primaryColor = (sectorKey === 'finance' ? financeColor : (sectorKey === 'cities' ? cityColor : '#4f88ff'));

            let categoryData = {}; let categoryKey = sectorKey === 'finance' ? 'industry' : 'type';
            if (sectorKey !== 'cities') dataList.forEach(item => { categoryData[item[categoryKey]] = (categoryData[item[categoryKey]] || 0) + 1; });
            
            const ctx1 = createMiniChart('chart1', `Asset Distribution`);
            if (sectorKey !== 'cities') {
                 currentCharts.push(new Chart(ctx1, { type: 'doughnut', data: { labels: Object.keys(categoryData), datasets: [{ data: Object.values(categoryData), backgroundColor: ['#4f88ff', '#FFA500', '#2ECC71', '#E74C3C', '#FF00FF'] }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } } }));
            }
            const ctx2 = createMiniChart('chart2', `Top 10 Impacted Assets`);
            currentCharts.push(new Chart(ctx2, { type: 'bar', data: { labels: top10.map(i => i.name.split(' ')[0]), datasets: [{ data: top10.map(i => sectorKey === 'finance' ? i.predicted_drop_percent : i.impact_score), backgroundColor: primaryColor }] }, options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y' } }));
        }

        function populateDetailPanel(sectorKey, dataList, title) {
            setActiveButton(document.getElementById(`btn-${sectorKey}`));
            activeMarkersLayer.clearLayers(); affectedLinesLayer.clearLayers();
            generateSectorCharts(sectorKey, dataList, title);
            
            const sortKey = sectorKey === 'finance' ? 'predicted_drop_percent' : 'impact_score';
            const unit = sectorKey === 'finance' ? '%' : 'Score';
            let html = `<h4 class="text-xl text-blue-400 mb-4">${title} Log (${dataList.length} items)</h4>`;
            
            const sortedList = [...dataList].sort((a, b) => b[sortKey] - a[sortKey]);
            let drawnLines = 0;
            
            const globalHubs = [[37.33,-122.00], [51.50,-0.12], [35.68,139.76], [19.07,72.87], [22.30,114.17]];

            html += sortedList.map(item => {
                let color = sectorKey === 'finance' ? financeColor : cityColor;
                activeMarkersLayer.addLayer(L.circleMarker([item.lat, item.lon], { radius: 5, color: color, fillColor: color }).bindPopup(`<strong>${item.name}</strong>`));
                
                if (drawnLines < 60) {
                    animateLine(currentEpicenterInfo.lat, currentEpicenterInfo.lon, item.lat, item.lon, color); 
                    if (sectorKey === 'finance' && item.predicted_drop_percent > 2.0) {
                        let randomHub = globalHubs[Math.floor(Math.random() * globalHubs.length)];
                        animateLine(item.lat, item.lon, randomHub[0], randomHub[1], '#ff9900', true); 
                    }
                    drawnLines++;
                }

                return `<div class="detail-item" style="border-left: 3px solid ${color}; padding-left: 10px;">
                        <h5 class="data-value">${item.name}</h5><p class="data-label">Impact: <span style="color:#ff3333;">${item[sortKey]}${unit}</span></p></div>`;
            }).join('');
            dynamicReportContent.innerHTML = html;
        }

        function generateOverallReport() {
            setActiveButton(document.getElementById('btn-overall'));
            if (!currentAnalysisResults) return;
            const r = currentAnalysisResults;
            const totAss = (r.cities?.length||0) + (r.transportation?.length||0) + (r.infrastructure?.length||0) + (r.companies?.length||0);
            dynamicReportContent.innerHTML = `
                <h4 class="text-xl text-yellow-400 mb-4" style="color:#ff9900;">MACRO SUMMARY</h4>
                <div class="p-3 bg-gray-800 rounded mb-4" style="border:1px solid #333; background:#111;">
                    <p class="data-label">TOTAL ASSETS: <span class="data-value">${totAss}</span></p>
                    <p class="data-label">MAX REACH: <span class="data-value">${r.max_distance_km} KM</span></p>
                </div>
            `;
            chartCollectionDiv.innerHTML = '<p style="color:#555;">[MACRO VISUALIZATIONS LOADED]</p>';
        }

        function generatePredictionReport() {
            setActiveButton(document.getElementById('btn-predict'));
            if (!currentAnalysisResults || !currentAnalysisResults.predictions) return;
            const p = currentAnalysisResults.predictions;
            dynamicReportContent.innerHTML = `
                <h4 class="card-title" style="color:#0088ff;">PROJECTIONS</h4>
                <div class="detail-item"><p class="data-label">Price Fluctuation:</p> <span class="data-value" style="color:#ff3333;">${p.price_fluctuation}</span></div>
                <div class="detail-item"><p class="data-label">Architecture Loss:</p> <span class="data-value" style="color:#ff3333;">${p.architecture_loss}</span></div>
                <div class="detail-item"><p class="data-label">Recovery Rate:</p> <span class="data-value" style="color:#00ff00;">${p.recovery_rate}</span></div>
            `;
        }

        async function fetchAndPlotEvents() {
             try {
                 const response = await fetch(`/api/live_events?timeframe=${document.getElementById('time-filter').value}`);
                 globalRawEvents = await response.json();
                 plotFilteredEvents();
                 summaryDiv.innerHTML = `<p style="color:#00ff00;">[TELEMETRY SYNCED]</p><p style="color:#555;">Select event to analyze.</p>`;
             } catch (err) { console.error(err); }
        }

        document.getElementById('time-filter').addEventListener('change', fetchAndPlotEvents);

        document.getElementById('btn-cities').addEventListener('click', () => { if (currentAnalysisResults) populateDetailPanel('cities', currentAnalysisResults.cities || [], "Cities"); });
        document.getElementById('btn-transport').addEventListener('click', () => { if (currentAnalysisResults) populateDetailPanel('transport', currentAnalysisResults.transportation || [], "Logistics"); });
        document.getElementById('btn-infra').addEventListener('click', () => { if (currentAnalysisResults) populateDetailPanel('infra', currentAnalysisResults.infrastructure || [], "Infrastructure"); });
        document.getElementById('btn-finance').addEventListener('click', () => { if (currentAnalysisResults) populateDetailPanel('finance', currentAnalysisResults.companies || [], "Markets & Supply Chain"); }); 
        document.getElementById('btn-predict').addEventListener('click', generatePredictionReport);
        document.getElementById('btn-overall').addEventListener('click', generateOverallReport);

        // --- MAP CLICK LISTENER ---
        map.on('click', function(e){
             const targetClasses = e.originalEvent.target.classList;
             if (targetClasses.contains('leaflet-marker-icon') || 
                 targetClasses.contains('leaflet-interactive') ||
                 e.originalEvent.target.closest('.leaflet-control')) {
                 return; 
             }
             if (manualLat && manualLon) { 
                 manualLat.value = e.latlng.lat.toFixed(4); 
                 manualLon.value = e.latlng.lng.toFixed(4); 
             }
        });

        // --- MAIN SIMULATION EXECUTION ---
        document.getElementById('btn-manual-run').addEventListener('click', async () => {
            const lat = parseFloat(manualLat.value); const lon = parseFloat(manualLon.value);
            const type = document.getElementById('disaster-type').value;
            let simMag, simDepth;

            if (type === 'earthquake') { simMag = parseFloat(manualMag.value); simDepth = parseFloat(manualDepth.value); } 
            else if (type === 'tsunami') { simMag = tsunamiData[activeSeverityLevel].wave; simDepth = 4000; } 
            else { simMag = floodData[activeSeverityLevel].rain; simDepth = 48; }

            if (isNaN(lat) || isNaN(lon)) return alert('VALIDATION ERROR: Please click the map to select coordinates.');

            activeMarkersLayer.clearLayers(); affectedLinesLayer.clearLayers(); liveEventsLayer.clearLayers();
            summaryDiv.innerHTML = `<h4 class="card-title" style="color:#ff9900;">[SYSTEM WORKING...]</h4>`;

            try {
                let apiUrl = type === "earthquake" 
                    ? `/api/calculate_impact?lat=${lat}&lon=${lon}&mag=${simMag}&depth=${simDepth}`
                    : `/api/simulate_event?type=${type}&lat=${lat}&lon=${lon}&mag=${simMag}&depth=${simDepth}`;

                const response = await fetch(apiUrl);
                const data = await response.json();

                let disasterColor = type === 'tsunami' ? '#0088ff' : (type === 'flood' ? '#00ff00' : '#ff3333');
                epicenterMarker = L.circleMarker([lat, lon], { radius: 10, color: '#fff', weight: 4, fill: true, fillColor: disasterColor, fillOpacity: 1 }).addTo(map).bindPopup(`<strong>ORIGIN</strong>`).openPopup();
                
                currentEpicenterInfo = { lat, lon, mag: simMag, depth: simDepth };
                
                currentAnalysisResults = {
                    cities: data.cities || data.affected_cities || [],
                    transportation: data.transportation || data.affected_transportation || [],
                    infrastructure: data.infrastructure || data.affected_infrastructure || [],
                    companies: data.companies || data.affected_companies || [],
                    predictions: data.predictions || {},
                    warnings: data.warnings || [],
                    max_distance_km: data.max_distance_km || 500
                };
                
                // TRIGGER NUCLEAR BLAST ZONES
                drawImpactZones(lat, lon, currentAnalysisResults.max_distance_km, disasterColor);

                let totalHit = currentAnalysisResults.cities.length + currentAnalysisResults.transportation.length + currentAnalysisResults.infrastructure.length + currentAnalysisResults.companies.length;
                
                // GENERATE HAZARD BANNERS
                let warningsHtml = '';
                if (currentAnalysisResults.warnings && currentAnalysisResults.warnings.length > 0) {
                    currentAnalysisResults.warnings.forEach(w => {
                        let warnColor = w.includes('RUPTURE') ? '#ff00ff' : '#0088ff';
                        warningsHtml += `<div style="background:#220000; border-left:4px solid ${warnColor}; padding:8px; margin-top:8px; font-size:0.85em; color:${warnColor}; font-weight:bold; text-transform:uppercase; box-shadow: 0 0 10px ${warnColor}44;">${w}</div>`;
                    });
                }

                summaryDiv.innerHTML = `<h4 class="card-title" style="color:${disasterColor};">[PROTOCOL COMPLETE]</h4>
                                        <p class="data-label">Total Assets Hit: <span style="color:#fff; font-weight:bold; font-size:1.2em;">${totalHit}</span></p>
                                        ${warningsHtml}
                                        <p class="text-xs mt-3" style="color:#00ff00;">> Select sector to map lasers...</p>`;
                
                analysisButtons.forEach(btn => btn.disabled = false);
            } catch (err) { summaryDiv.innerHTML = `<p style="color:#ff3333;">ERROR: ${err.message}</p>`; }
        });

        document.getElementById('btn-manual-clear').addEventListener('click', () => {
            currentAnalysisResults = null; activeMarkersLayer.clearLayers(); affectedLinesLayer.clearLayers(); 
            if(epicenterMarker) map.removeLayer(epicenterMarker); 
            impactZones.forEach(z => map.removeLayer(z)); impactZones = [];
            plotFilteredEvents(); 
            summaryDiv.innerHTML = '<p style="color:#555;">[STANDBY]</p>';
            analysisButtons.forEach(btn => { btn.disabled = true; btn.classList.remove('active'); });
            chartCollectionDiv.innerHTML = '';
            dynamicReportContent.innerHTML = '<p style="color:#555;">[AWAITING SECTOR SELECTION...]</p>';
        });

        fetchAndPlotEvents();
    </script>
</body>
</html>
""")

# --- API ROUTES ---
@app.route("/api/live_events")
def get_live_events():
    timeframe = request.args.get("timeframe", "24h")
    events = []
    usgs_urls = { "24h": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson", "7d": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson", "30d": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_month.geojson" }

    try:
        url = usgs_urls.get(timeframe, usgs_urls["24h"]) if timeframe != "1y" else f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={(datetime.now(timezone.utc) - timedelta(days=365)).strftime('%Y-%m-%d')}&minmagnitude=6.0"
        for f in requests.get(url, timeout=5).json().get("features", []):
            c = f["geometry"]["coordinates"]
            if ASIA_BBOX["minLat"] <= c[1] <= ASIA_BBOX["maxLat"] and ASIA_BBOX["minLon"] <= c[0] <= ASIA_BBOX["maxLon"]:
                events.append({ "id": f["id"], "type": "earthquake", "place": f["properties"]["place"], "mag": f["properties"]["mag"], "lat": c[1], "lon": c[0] })
    except: pass

    try:
        for f in requests.get(GDACS_API_URL, timeout=5).json().get("features", []):
            p = f["properties"]; c = f["geometry"]["coordinates"]
            events.append({ "id": p.get("eventid"), "type": "tsunami" if p.get("eventtype") == "TS" else "flood", "place": p.get("country", "Alert"), "mag": p.get("severitydata", {}).get("severity", 5), "lat": c[1], "lon": c[0] })
    except: pass

    return jsonify(events)

@app.route("/api/simulate_event")
def simulate_event():
    try:
        t = request.args.get("type", "earthquake")
        p = { "lat": float(request.args.get("lat")), "lon": float(request.args.get("lon")), "mag": float(request.args.get("mag")), "depth": float(request.args.get("depth")) }
        conn = psycopg2.connect(host=DB_HOST, port=os.environ.get("PGPORT", 5432), database=DB_NAME, user=DB_USER, password=DB_PASS)
        res = run_disaster(t, p, conn, financial_model)
        conn.close()
        return jsonify(res)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/calculate_impact")
def calculate_impact_api():
    try:
        lat, lon, mag, depth = float(request.args.get("lat")), float(request.args.get("lon")), float(request.args.get("mag")), float(request.args.get("depth"))
        sig, cdi, nst, gap = float(request.args.get("sig", 0)), float(request.args.get("cdi", 0)), float(request.args.get("nst", 0)), float(request.args.get("gap", 0))
    except: return jsonify({"error": "Invalid params"}), 400

    prelims = predict_advanced_impact(lat, lon, mag, depth, sig, cdi, nst, gap)
    is_oceanic = prelims.get("nearest_city_distance_km", 100) > MAX_LAND_PROXIMITY_KM
    params = { "lat": lat, "lon": lon, "mag": mag, "depth": depth, "sig": 0 if is_oceanic else sig, "cdi": 0 if is_oceanic else cdi, "nst": 0 if is_oceanic else nst, "gap": 0 if is_oceanic else gap }

    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB Offline"}), 500
    try:
        result = run_earthquake(params, conn, financial_model)
        result["predictions"] = prelims
        return jsonify(result)
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: conn.close()

if __name__ == "__main__":
    load_financial_assets()
    app.run(host='0.0.0.0', port=5050, debug=True)
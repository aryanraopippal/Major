import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.cluster import KMeans
import xgboost as xgb
import joblib

print("[SYSTEM] Booting Advanced AI Data Factory (Logarithmic Calibration)...")

# 1. GENERATE SYNTHETIC DATA (Logarithmic Attenuation)
np.random.seed(42)
n_samples = 15000

print("[SYSTEM] Synthesizing 15,000 historical disaster data points...")
intensity = np.random.uniform(1.0, 15.0, n_samples)
distance = np.random.uniform(0.0, 5000.0, n_samples)
vulnerability = np.random.uniform(1.0, 10.0, n_samples)

# THE SCIENTIFIC FIX: Joyner-Boore Logarithmic Decay Formula
# Damage drops off exponentially the further you get from the epicenter.
impact_scores = intensity - (2.1 * np.log10(distance + 1)) + (vulnerability / 5)
impact_scores = np.clip(impact_scores, 0, 10) # Strictly cap between 0 and 10

recovery_years = (impact_scores ** 1.5) * 0.12 + (vulnerability * 0.15)
recovery_years = np.clip(recovery_years, 0.1, 15.0)

X_impact = np.column_stack((intensity, distance, vulnerability))
y_impact = impact_scores
y_recovery = recovery_years
X_cluster = np.column_stack((intensity, distance))

# 2. TRAIN RANDOM FOREST
print("[AI] Training Random Forest Regressor...")
rf_model = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42)
rf_model.fit(X_impact, y_impact)
joblib.dump(rf_model, 'rf_impact_model.joblib')

# 3. TRAIN XGBOOST
print("[AI] Training XGBoost Regressor...")
xgb_model = xgb.XGBRegressor(n_estimators=150, learning_rate=0.1, max_depth=5, random_state=42)
xgb_model.fit(X_impact, y_recovery)
joblib.dump(xgb_model, 'xgb_recovery_model.joblib')

# 4. TRAIN K-MEANS
print("[AI] Training K-Means Classifier...")
kmeans_model = KMeans(n_clusters=3, random_state=42, n_init=10)
kmeans_model.fit(X_cluster)
joblib.dump(kmeans_model, 'kmeans_zone_model.joblib')

print("\n[SUCCESS] AI Models Retrained with Scientific Decay. Ready for Terminal Integration!")
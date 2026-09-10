import os
import json
import sqlite3
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, IsolationForest
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

FEATURE_COLS = [
    'orig_cost',
    'rev_cost',
    'expenditure',
    'progress',
    'financial_progress_pct',
    'progress_gap',
    'time_elapsed_months',
    'planned_duration_months',
    'time_utilization_pct',
    'progress_velocity',
    'expenditure_velocity',
    'delay_slippage'
]

LABEL_MAPPING = {0: "HIGH", 1: "LOW", 2: "MEDIUM"}
REVERSE_MAPPING = {"HIGH": 0, "LOW": 1, "MEDIUM": 2}

class MLEngine:
    def __init__(self):
        self.risk_model = None
        self.delay_model = None
        self.cost_model = None
        self.anomaly_model = None
        self.scaler = None
        self.benchmarks = {}
        self.feature_names = FEATURE_COLS

    def load_data(self):
        csv_path = os.path.join(DATA_DIR, "projects_master.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"{csv_path} not found. Run data_pipeline.py first.")
        df = pd.read_csv(csv_path)
        return df

    def train_all_models(self):
        os.makedirs(MODELS_DIR, exist_ok=True)
        df = self.load_data()
        
        # Features and target
        X = df[FEATURE_COLS].copy().fillna(0)
        
        # 1. RISK CLASSIFICATION BENCHMARK & MODEL
        y_risk = df['risk_level'].map(REVERSE_MAPPING)
        X_train_c, X_test_c, y_train_c, y_test_c = train_test_split(
            X, y_risk, test_size=0.2, random_state=42, stratify=y_risk
        )
        
        # Scaling for Logistic Regression
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_c)
        X_test_scaled = scaler.transform(X_test_c)
        self.scaler = scaler
        
        # Logistic Regression
        lr = LogisticRegression(max_iter=1000, random_state=42)
        lr.fit(X_train_scaled, y_train_c)
        y_pred_lr = lr.predict(X_test_scaled)
        acc_lr = accuracy_score(y_test_c, y_pred_lr)
        p_lr, r_lr, f1_lr, _ = precision_recall_fscore_support(y_test_c, y_pred_lr, average='weighted', zero_division=0)
        
        # Random Forest Classifier
        rf_clf = RandomForestClassifier(n_estimators=150, max_depth=12, random_state=42)
        rf_clf.fit(X_train_c, y_train_c)
        y_pred_rf = rf_clf.predict(X_test_c)
        acc_rf = accuracy_score(y_test_c, y_pred_rf)
        p_rf, r_rf, f1_rf, _ = precision_recall_fscore_support(y_test_c, y_pred_rf, average='weighted', zero_division=0)
        
        # XGBoost Classifier
        xgb_clf = xgb.XGBClassifier(
            n_estimators=180,
            max_depth=6,
            learning_rate=0.08,
            random_state=42,
            eval_metric='mlogloss'
        )
        xgb_clf.fit(X_train_c, y_train_c)
        y_pred_xgb = xgb_clf.predict(X_test_c)
        acc_xgb = accuracy_score(y_test_c, y_pred_xgb)
        p_xgb, r_xgb, f1_xgb, _ = precision_recall_fscore_support(y_test_c, y_pred_xgb, average='weighted', zero_division=0)
        
        self.risk_model = xgb_clf
        
        # 2. DELAY REGRESSION BENCHMARK & MODEL
        y_delay = df['delay_months'].fillna(0)
        X_train_d, X_test_d, y_train_d, y_test_d = train_test_split(
            X, y_delay, test_size=0.2, random_state=42
        )
        
        # Linear Regression
        lin_reg = LinearRegression()
        lin_reg.fit(X_train_d, y_train_d)
        y_pred_lin = lin_reg.predict(X_test_d)
        mae_lin = mean_absolute_error(y_test_d, y_pred_lin)
        r2_lin = r2_score(y_test_d, y_pred_lin)
        
        # Random Forest Regressor
        rf_reg_delay = RandomForestRegressor(n_estimators=120, max_depth=10, random_state=42)
        rf_reg_delay.fit(X_train_d, y_train_d)
        y_pred_rf_d = rf_reg_delay.predict(X_test_d)
        mae_rf_d = mean_absolute_error(y_test_d, y_pred_rf_d)
        r2_rf_d = r2_score(y_test_d, y_pred_rf_d)
        
        # XGBoost Regressor
        xgb_reg_delay = xgb.XGBRegressor(n_estimators=150, max_depth=5, learning_rate=0.06, random_state=42)
        xgb_reg_delay.fit(X_train_d, y_train_d)
        y_pred_xgb_d = xgb_reg_delay.predict(X_test_d)
        mae_xgb_d = mean_absolute_error(y_test_d, y_pred_xgb_d)
        r2_xgb_d = r2_score(y_test_d, y_pred_xgb_d)
        
        self.delay_model = xgb_reg_delay
        
        # 3. COST OVERRUN REGRESSION BENCHMARK & MODEL
        y_cost = df['cost_overrun_pct'].fillna(0)
        X_train_co, X_test_co, y_train_co, y_test_co = train_test_split(
            X, y_cost, test_size=0.2, random_state=42
        )
        
        xgb_reg_cost = xgb.XGBRegressor(n_estimators=150, max_depth=5, learning_rate=0.07, random_state=42)
        xgb_reg_cost.fit(X_train_co, y_train_co)
        y_pred_co = xgb_reg_cost.predict(X_test_co)
        mae_co = mean_absolute_error(y_test_co, y_pred_co)
        r2_co = r2_score(y_test_co, y_pred_co)
        
        self.cost_model = xgb_reg_cost
        
        # 4. ANOMALY DETECTION (ISOLATION FOREST)
        # Features with strong discrepancy signals
        anomaly_features = ['progress_gap', 'expenditure_velocity', 'progress_velocity', 'time_utilization_pct', 'cost_overrun_pct']
        iso = IsolationForest(contamination=0.05, random_state=42)
        iso.fit(df[anomaly_features].fillna(0))
        self.anomaly_model = iso
        
        # Calculate anomaly labels & scores on full dataset
        anomaly_preds = iso.predict(df[anomaly_features].fillna(0))
        anomaly_scores = iso.decision_function(df[anomaly_features].fillna(0))
        df['is_anomaly'] = [int(p == -1) for p in anomaly_preds]
        df['anomaly_score'] = [round(float(s), 4) for s in anomaly_scores]
        
        # Update SQLite and CSV with anomaly flags
        csv_path = os.path.join(DATA_DIR, "projects_master.csv")
        df.to_csv(csv_path, index=False)
        db_path = os.path.join(DATA_DIR, "projects.sqlite")
        conn = sqlite3.connect(db_path)
        df.to_sql("projects", conn, if_exists="replace", index=False)
        cursor = conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON projects (project_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk ON projects (risk_level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anom ON projects (is_anomaly)")
        conn.commit()
        conn.close()
        
        # Save benchmarks
        self.benchmarks = {
            "classification": [
                {"model": "Logistic Regression", "accuracy": round(acc_lr, 4), "precision": round(p_lr, 4), "recall": round(r_lr, 4), "f1": round(f1_lr, 4)},
                {"model": "Random Forest Classifier", "accuracy": round(acc_rf, 4), "precision": round(p_rf, 4), "recall": round(r_rf, 4), "f1": round(f1_rf, 4)},
                {"model": "XGBoost Classifier (Selected)", "accuracy": round(acc_xgb, 4), "precision": round(p_xgb, 4), "recall": round(r_xgb, 4), "f1": round(f1_xgb, 4)}
            ],
            "delay_regression": [
                {"model": "Linear Regression", "mae": round(mae_lin, 2), "r2": round(r2_lin, 4)},
                {"model": "Random Forest Regressor", "mae": round(mae_rf_d, 2), "r2": round(r2_rf_d, 4)},
                {"model": "XGBoost Regressor (Selected)", "mae": round(mae_xgb_d, 2), "r2": round(r2_xgb_d, 4)}
            ],
            "cost_regression": [
                {"model": "XGBoost Regressor (Selected)", "mae": round(mae_co, 2), "r2": round(r2_co, 4)}
            ],
            "anomalies_detected": int((anomaly_preds == -1).sum()),
            "total_projects": len(df)
        }
        
        bench_path = os.path.join(MODELS_DIR, "benchmarks.json")
        with open(bench_path, "w", encoding="utf-8") as f:
            json.dump(self.benchmarks, f, indent=2)
            
        # Serialize models
        joblib.dump(self.risk_model, os.path.join(MODELS_DIR, "risk_model.joblib"))
        joblib.dump(self.delay_model, os.path.join(MODELS_DIR, "delay_model.joblib"))
        joblib.dump(self.cost_model, os.path.join(MODELS_DIR, "cost_model.joblib"))
        joblib.dump(self.anomaly_model, os.path.join(MODELS_DIR, "anomaly_model.joblib"))
        joblib.dump(self.scaler, os.path.join(MODELS_DIR, "scaler.joblib"))
        
        # Save feature importances
        risk_importances = dict(zip(FEATURE_COLS, [round(float(v), 4) for v in self.risk_model.feature_importances_]))
        with open(os.path.join(MODELS_DIR, "feature_importances.json"), "w", encoding="utf-8") as f:
            json.dump(risk_importances, f, indent=2)
            
        print(f"Models successfully trained and saved to {MODELS_DIR}")
        print(f"Classification Performance: XGBoost Accuracy={acc_xgb:.4f}, F1={f1_xgb:.4f}")
        print(f"Delay MAE: {mae_xgb_d:.2f} months | Cost Overrun MAE: {mae_co:.2f}%")
        print(f"Anomalies Flagged: {self.benchmarks['anomalies_detected']} of {len(df)}")
        return self.benchmarks

    def load_saved_models(self):
        try:
            self.risk_model = joblib.load(os.path.join(MODELS_DIR, "risk_model.joblib"))
            self.delay_model = joblib.load(os.path.join(MODELS_DIR, "delay_model.joblib"))
            self.cost_model = joblib.load(os.path.join(MODELS_DIR, "cost_model.joblib"))
            self.anomaly_model = joblib.load(os.path.join(MODELS_DIR, "anomaly_model.joblib"))
            self.scaler = joblib.load(os.path.join(MODELS_DIR, "scaler.joblib"))
            
            bench_path = os.path.join(MODELS_DIR, "benchmarks.json")
            if os.path.exists(bench_path):
                with open(bench_path, "r", encoding="utf-8") as f:
                    self.benchmarks = json.load(f)
            return True
        except Exception as e:
            print(f"Could not load pre-trained models: {e}. Training fresh models...")
            self.train_all_models()
            return True

    def predict_project(self, project_dict):
        """
        Takes raw project dict and returns comprehensive AI risk profile:
        - risk_level (HIGH, MEDIUM, LOW)
        - risk_score (0-100)
        - predicted_delay_months
        - predicted_delay_days
        - predicted_cost_overrun_pct
        - predicted_final_cost
        - is_anomaly
        - risk_factors (SHAP-style relative contribution)
        - recommendations
        """
        if self.risk_model is None:
            self.load_saved_models()
            
        # Build feature vector
        orig_cost = float(project_dict.get('orig_cost', 0) or 0)
        rev_cost = float(project_dict.get('rev_cost', orig_cost) or orig_cost)
        expenditure = float(project_dict.get('expenditure', 0) or 0)
        progress = float(project_dict.get('progress', 0) or 0)
        
        fin_prog = (expenditure / rev_cost * 100.0) if rev_cost > 0 else 0.0
        gap = fin_prog - progress
        elapsed = float(project_dict.get('time_elapsed_months', 24) or 24)
        duration = float(project_dict.get('planned_duration_months', 36) or 36)
        time_util = (elapsed / duration * 100.0) if duration > 0 else 100.0
        pv = float(project_dict.get('progress_velocity', 1.0) or 1.0)
        ev = float(project_dict.get('expenditure_velocity', 5.0) or 5.0)
        slip = float(project_dict.get('delay_slippage', 0) or 0)
        
        feat_vals = [
            orig_cost, rev_cost, expenditure, progress,
            fin_prog, gap, elapsed, duration, time_util,
            pv, ev, slip
        ]
        X_vec = pd.DataFrame([feat_vals], columns=FEATURE_COLS)
        
        # 1. Risk Classification & Probability
        probs = self.risk_model.predict_proba(X_vec)[0]
        # Class 0: HIGH, Class 1: LOW, Class 2: MEDIUM
        prob_high = probs[0]
        prob_low = probs[1]
        prob_med = probs[2]
        pred_class_idx = int(np.argmax(probs))
        risk_level = LABEL_MAPPING[pred_class_idx]
        
        # Risk Score (0 - 100): Weighted formula emphasizing High risk probability
        risk_score = int(round((prob_high * 1.0 + prob_med * 0.45 + prob_low * 0.05) * 100))
        risk_score = max(5, min(99, risk_score))
        
        # 2. Delay Prediction
        pred_delay_m = float(self.delay_model.predict(X_vec)[0])
        pred_delay_m = max(0.0, round(pred_delay_m, 1))
        pred_delay_days = int(round(pred_delay_m * 30.4))
        
        # 3. Cost Overrun Prediction
        pred_overrun_pct = float(self.cost_model.predict(X_vec)[0])
        pred_overrun_pct = max(0.0, round(pred_overrun_pct, 1))
        pred_final_cost = round(orig_cost * (1.0 + pred_overrun_pct / 100.0), 2)
        
        # 4. Anomaly Detection
        anom_vec = pd.DataFrame([[gap, ev, pv, time_util, pred_overrun_pct]], 
                                columns=['progress_gap', 'expenditure_velocity', 'progress_velocity', 'time_utilization_pct', 'cost_overrun_pct'])
        is_anom = int(self.anomaly_model.predict(anom_vec)[0] == -1)
        
        # 5. Explainable AI Feature Drivers (SHAP approximation via tree weights)
        importances = [float(imp) for imp in self.risk_model.feature_importances_]
        # Normalize local influence based on feature deviations
        local_weights = {
            "Progress Gap (Spend vs Physical)": max(0.0, float(gap * importances[5] * 0.1)),
            "Time Utilization Overrun": max(0.0, float((time_util - 100.0) * importances[8] * 0.05)) if time_util > 100 else 0.0,
            "Delay Slippage Pattern": max(0.0, float(slip * importances[11] * 0.25)),
            "Pace Stalling (Low Progress Rate)": max(0.0, float((2.0 - pv) * importances[9] * 0.2)) if pv < 2.0 else 0.0,
            "High Expenditure Burn Velocity": max(0.0, float(ev * importances[10] * 0.02)),
            "Uncompleted Physical Work Scope": max(0.0, float((100.0 - progress) * importances[3] * 0.01))
        }
        total_w = sum(local_weights.values()) or 1.0
        risk_factors = [
            {"factor": k, "contribution_pct": round(float((v / total_w) * 100.0), 1)}
            for k, v in sorted(local_weights.items(), key=lambda x: x[1], reverse=True)
            if v > 0.01
        ][:4]
        
        if not risk_factors:
            risk_factors = [
                {"factor": "Balanced Physical Execution", "contribution_pct": 50.0},
                {"factor": "Expenditure Within Budget", "contribution_pct": 50.0}
            ]
            
        # 6. Recommendation Engine (Rule-based + ML Explanation)
        recommendations = self.generate_recommendations(
            risk_level=risk_level,
            gap=gap,
            slip=slip,
            pv=pv,
            overrun_pct=pred_overrun_pct,
            delay_months=pred_delay_m,
            is_anomaly=is_anom,
            progress=progress
        )
        
        return {
            "risk_level": risk_level,
            "risk_score": int(risk_score),
            "probability_breakdown": {
                "high": round(float(prob_high), 3),
                "medium": round(float(prob_med), 3),
                "low": round(float(prob_low), 3)
            },
            "predicted_delay_months": float(pred_delay_m),
            "predicted_delay_days": int(pred_delay_days),
            "predicted_cost_overrun_pct": float(pred_overrun_pct),
            "predicted_final_cost": float(pred_final_cost),
            "is_anomaly": bool(is_anom),
            "risk_factors": risk_factors,
            "recommendations": recommendations
        }

    def generate_recommendations(self, risk_level, gap, slip, pv, overrun_pct, delay_months, is_anomaly, progress):
        actions = []
        
        if is_anomaly:
            actions.append({
                "severity": "CRITICAL",
                "title": "Investigate Statistical Anomaly",
                "action": "Unusual divergence detected between financial release and ground physical progress. Mandate on-site third-party technical inspection by Central Technical Examiner."
            })
            
        if gap > 25:
            actions.append({
                "severity": "HIGH",
                "title": "Resolve Progress-Spend Disparity",
                "action": f"Expenditure exceeds physical progress by {gap:.1f}%. Halt subsequent advance mobilization funds until physical milestones are validated."
            })
            
        if slip >= 2:
            actions.append({
                "severity": "HIGH",
                "title": "Convene Joint State Coordination Meeting",
                "action": f"Completion deadline slipped by {slip} months in recent cycle. Escalate Right-of-Way (RoW), utility shifting, and state statutory clearances to Cabinet Secretariat (e-SamikSha / Pragati)."
            })
            
        if pv < 0.8 and progress < 85:
            actions.append({
                "severity": "MEDIUM",
                "title": "Remobilize Contractor Machinery & Manpower",
                "action": f"Current progress velocity is sluggish ({pv:.2f}%/month). Enforce milestone liquidated damages clause and demand revised catch-up schedule from EPC contractor."
            })
            
        if overrun_pct > 15:
            actions.append({
                "severity": "HIGH",
                "title": "Submit Revised Cost Estimates (RCE)",
                "action": f"Projected cost escalation is {overrun_pct:.1f}%. Direct Implementing Agency to submit comprehensive Revised Cost Estimates to Public Investment Board (PIB)."
            })
            
        if delay_months > 12:
            actions.append({
                "severity": "HIGH",
                "title": "Establish High-Frequency Monitoring",
                "action": f"Estimated delay is {delay_months:.1f} months. Shift review cadence from quarterly to fortnightly dashboard reporting with drone-assisted spatial tracking."
            })
            
        if not actions or risk_level == "LOW":
            actions.append({
                "severity": "LOW",
                "title": "Maintain Target Execution Cadence",
                "action": "Project is operating within approved financial and temporal tolerances. Continue regular monthly milestone logging on IPM portal."
            })
            
        return actions

engine = MLEngine()

if __name__ == "__main__":
    engine.train_all_models()

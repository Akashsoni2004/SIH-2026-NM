import os
import sys
import uvicorn

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DB_PATH = os.path.join(DATA_DIR, "projects.sqlite")
MODEL_PATH = os.path.join(MODELS_DIR, "risk_model.joblib")

def initialize_system():
    print("\n")
    print("  AI-POWERED INTEGRATED PROJECT MONITORING & RISK PREDICTION PLATFORM")
    print("  MoSPI / IPMD Infrastructure Early Warning & ML Intelligence Engine")
    print("\n")
    
    #Check Data Pipeline
    if not os.path.exists(DB_PATH):
        print("\n[Step 1/2] Master database not detected. Building longitudinal panel dataset...")
        from src.data_pipeline import build_longitudinal_dataset
        build_longitudinal_dataset()
    else:
        print("\n[Step 1/2] Master SQLite database verified at data/projects.sqlite.")

    #Check ML Models
    if not os.path.exists(MODEL_PATH):
        print("\n[Step 2/2] ML models not detected. Training multi-model architecture...")
        from src.ml_engine import MLEngine
        engine = MLEngine()
        engine.train_all_models()
    else:
        print("[Step 2/2] Serialized ML models verified at models/risk_model.joblib.")

    print("\n")
    print("  STARTING FASTAPI PRODUCTION BACKEND & EXECUTIVE DASHBOARD")
    print("  Dashboard UI:   http://127.0.0.1:8000")
    print("  Swagger Docs:   http://127.0.0.1:8000/docs")
    print("  ReDoc:          http://127.0.0.1:8000/redoc")

if __name__ == "__main__":
    initialize_system()
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

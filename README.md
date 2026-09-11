# 🇮🇳 PAIMANA AI — Integrated Project Monitoring & Risk Prediction Platform

> **Smart India Hackathon (SIH)** • Infrastructure and Project Monitoring Division (IPMD) • Ministry of Statistics & Programme Implementation (MoSPI)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![XGBoost](https://img.shields.io/badge/XGBoost-90.52%25_Accuracy-orange.svg)](https://xgboost.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end AI-powered infrastructure project monitoring, risk classification, delay prediction, cost-overrun forecasting, and early warning system built on longitudinal MoSPI Flash Reports (April–July 2026) spanning over **2,052 central infrastructure projects**.

---

## 📌 Architecture Overview

```
                          4 SIH FLASH REPORT DATASETS
                          (Apr, May, Jun, Jul 2026)
                                     │
                                     ▼
                        LONGITUDINAL INTEGRATION
                (1,391 projects tracked across 4 months)
                                     │
                                     ▼
                           FEATURE ENGINEERING
          ┌──────────────────────────┼──────────────────────────┐
          ▼                          ▼                          ▼
    Progress Velocity        Expenditure Velocity         Delay Slippage
       (% / month)              (₹ Cr / month)               (months)
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     ▼
                    MULTI-MODEL MACHINE LEARNING ENGINE
   ┌────────────────────┬────────────────────┬────────────────────┐
   ▼                    ▼                    ▼                    ▼
Risk Classifier    Delay Regressor      Cost Regressor     Anomaly Detector
   XGBoost              XGBoost              XGBoost        Isolation Forest
 (90.52% Acc)       (MAE: 4.28 mo)         (MAE: 18%)        (87 Flagged)
   │                    │                    │                    │
   └────────────────────┼────────────────────┴────────────────────┘
                        ▼
                EXPLAINABLE AI (XAI)
               SHAP Feature Attribution
                        │
                        ▼
            EARLY WARNING & RECOMMENDATIONS
            Rule-Based + AI Mitigations
                        │
                        ▼
            FASTAPI REST API & EXECUTIVE UI
         (Interactive Glassmorphic Dashboard)
```

---

## 🏆 Machine Learning Benchmark Results

Evaluated across **1,737 infrastructure projects** with stratified train/test validation:

### 1. Risk Classification (High / Medium / Low Risk)
| Model | Accuracy | Precision | Recall | F1-Score | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **XGBoost Classifier** | **90.52%** | **90.15%** | **90.52%** | **90.26%** | **Selected Best** |
| Random Forest Classifier | 89.37% | 88.89% | 89.37% | 88.47% | Baseline |
| Logistic Regression | 84.20% | 81.41% | 84.20% | 80.85% | Baseline |

### 2. Schedule Delay Regressor (Target: Delay in Months)
| Model | Mean Absolute Error (MAE) | $R^2$ Score | Status |
| :--- | :---: | :---: | :---: |
| **XGBoost Regressor** | **4.28 months** | **0.6912** | **Selected Best** |
| Random Forest Regressor | 4.47 months | 0.6672 | Baseline |
| Linear Regression | 9.25 months | 0.5119 | Baseline |

---

## 🚀 Key Features

1. **Longitudinal Velocity Tracking**: Measures true ground execution progress rates ($\Delta\text{Progress}/3$) and fund burn velocity ($\Delta\text{Expenditure}/3$) across 4 consecutive monthly cycles.
2. **AI Risk Classification**: Predicts whether an infrastructure project will enter `HIGH`, `MEDIUM`, or `LOW` risk with 90.52% accuracy.
3. **Delay & Cost Overrun Regressors**: Forecasts delay in days/months and projected final escalated cost.
4. **Isolation Forest Anomaly Detection**: Flags projects with critical discrepancies (e.g. 85% budget spent with only 30% physical ground progress).
5. **Explainable AI (XAI)**: Displays top risk drivers for each project (Progress Gap %, Time Elapsed %, Slippage Pattern %, etc.).
6. **Prescriptive Recommendations**: Automated decision support engine suggesting targeted administrative actions.
7. **Interactive "What-If" Simulation Lab**: Real-time sliders allowing project directors to simulate budget or timeline changes and see live predictions in < 25ms.
8. **Executive Web Dashboard**: Obsidian glassmorphic dark theme, KPI cards, sector charts, risk doughnut, and project deep-dive drawer.

---

## 💻 Installation & Quickstart

### Prerequisites
- Python 3.10 or higher
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/Akashsoni2004/SIH-2026-NM.git
cd SIH-2026-NM
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Platform Locally
```bash
python main.py
```

### 4. Run with Docker (Containerized)
```bash
# Build the optimized production Docker image
docker build -t paimana-ai:latest .

# Run container on port 8000 with auto health checks
docker run -d -p 8000:8000 --name paimana-ai-app paimana-ai:latest
```

### 5. Access the Application
- **Local Application**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Web Dashboard**: [https://sih-2026-nm.onrender.com](https://sih-2026-nm.onrender.com)
- **Demo Video**: [PAIMANA AI](https://youtu.be/2nibS6o8aNM?si=LvPRF2nRxw-nn1dc)

---

## 🌐 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/dashboard/stats` | Global portfolio metrics (Projects, Value, High Risk count, Delays) |
| `GET` | `/api/projects` | Search & filterable pagination (by Ministry, Sector, State, Risk) |
| `GET` | `/api/projects/{code}` | Detailed project dossier with 4-month history, ML risk & XAI drivers |
| `POST` | `/api/predict` | Real-time "What-If" scenario simulation |
| `GET` | `/api/analytics/sectors` | Sector-wise capital value vs schedule delays |
| `GET` | `/api/analytics/ministries` | Ministry performance scorecard |
| `GET` | `/api/analytics/states` | State-wise infrastructure health |
| `GET` | `/api/anomalies` | List of 87 AI-detected progress/financial outliers |
| `GET` | `/api/model/benchmarks` | Algorithm comparison benchmark metrics |

---

## 🛠️ Tech Stack
- **Data Engineering**: Pandas, NumPy, SQLite3, OpenPyXL
- **Machine Learning**: XGBoost, Scikit-Learn, Joblib
- **Backend**: FastAPI, Uvicorn, Pydantic
- **Frontend**: HTML5, Vanilla CSS3 (Glassmorphism), JavaScript (ES6+), Chart.js, Lucide Icons

---

## 📄 License
This project is developed for the Smart India Hackathon (SIH 2026). Licensed under the MIT License.

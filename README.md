# F1Strategist

F1Strategist is an automated pit-stop strategy optimization engine for Formula 1. It leverages historical race data to fit tire degradation models and estimate pit-loss times, providing mathematically optimal strategy recommendations for any given race scenario.

## 🚀 Features

- **Data Ingestion:** Automatically fetches and cleans historical F1 lap data using [FastF1](https://theoehrly-fast-f1.mintlify.app/api/).
- **Tire Degradation Modeling:** Fits non-linear models (Exponential, Quadratic, Linear) to historical lap times per circuit and compound.
- **Pit-Loss Estimation:** Calculates robust median pit-stop time loss with bootstrap confidence intervals.
- **Strategy Optimizer:** Uses dynamic programming and heuristics to find the fastest sequence of pit stops and tire compounds.
- **FastAPI Service:** RESTful API for real-time strategy requests and circuit model exploration.
- **Persistence:** PostgreSQL-based caching for fitted models and computed strategies.

## 🛠 Tech Stack

- **Language:** Python 3.12
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Data Science:** [NumPy](https://numpy.org/), [Pandas](https://pandas.pydata.org/), [SciPy](https://scipy.org/), [FastF1](https://github.com/theoehrly/FastF1)
- **Database:** PostgreSQL (with SQLAlchemy ORM)
- **DevOps:** Docker, Docker Compose, GitHub Actions (CI)

## 📥 Installation

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (optional, for DB and containerized run)

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ecmoser/F1Strategist.git
   cd F1Strategist
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration:**
   Copy the example environment file and adjust as needed:
   ```bash
   cp .env.example .env
   ```

5. **Start PostgreSQL:**
   ```bash
   docker-compose up -d db adminer
   ```

## 🏎 Usage

### 1. Ingest Data
Load and clean historical data for a specific race:
```bash
python scripts/load_and_clean.py --season 2023 --round 1 --session R --out data/cleaned_2023_1.csv
```

### 2. Fit and Save Models
Train degradation models on the cleaned data and persist them to the database:
```bash
python scripts/fit_and_save.py --input data/cleaned_2023_1.csv
```

### 3. Run the API
Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`. You can explore the interactive docs at `http://localhost:8000/docs`.

## 📡 API Examples

### Get Optimal Strategy
Request an optimal strategy for a race in progress:

```bash
curl -X POST "http://localhost:8000/strategy" \
     -H "Content-Type: application/json" \
     -d '{
           "season": 2024,
           "round": 5,
           "current_lap": 15,
           "starting_compound": "MEDIUM",
           "current_tire_age": 15,
           "allowed_compounds": ["HARD", "MEDIUM", "SOFT"]
         }'
```

### Health Check
```bash
curl http://localhost:8000/health
```

## 🧪 Testing

Run the test suite using `pytest`:
```bash
pytest
```

## 🐳 Docker Deployment

To run the entire stack (API + DB) using Docker Compose:
```bash
docker-compose up --build
```

---
*Disclaimer: This project is for educational and entertainment purposes only and is not affiliated with Formula 1 or any of its teams.*

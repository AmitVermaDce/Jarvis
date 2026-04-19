"""
Demand Forecasting Model
Short-term demand prediction (1-14 days) using Facebook Prophet.
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import Prophet, fallback to simple model if not available
try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    HAS_PROPHET = False
    logger.warning("Prophet not available, using simple fallback model")

# Config import using absolute path (works when app is loaded)
try:
    import app.config as app_config
    Config = app_config.Config
except ImportError:
    Config = None

# Base directory for demand sensing data
DEMAND_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../uploads/demand_sensing")
Path(DEMAND_DATA_DIR).mkdir(parents=True, exist_ok=True)


@dataclass
class ForecastResult:
    """Result of a demand forecast."""
    sku: str
    location: str
    date: str  # ISO format
    predicted_demand: float
    confidence: float  # 0-1
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    model_version: str = "prophet-v1"
    components: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingDataPoint:
    """A single training data point for the model."""
    sku: str
    location: str
    date: str
    demand: float
    day_of_week: int
    is_weekend: bool
    is_holiday: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DemandForecastModel:
    """
    Short-term demand forecasting model using Facebook Prophet.
    Prophet is excellent for demand forecasting with built-in:
    - Weekly seasonality (day-of-week patterns)
    - Yearly seasonality (holiday effects)
    - Holiday effects
    - Trend changes
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.model = None
        self.model_path = os.path.join(DEMAND_DATA_DIR, f"{project_id}_model.json")
        self.sku = None
        self.location = None
        self.is_trained = False

    def _get_db_path(self) -> str:
        return os.path.join(DEMAND_DATA_DIR, f"{self.project_id}_demand.db")

    def _init_db(self):
        """Initialize demand sensing database tables."""
        db_path = self._get_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS demand_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL,
                    location TEXT NOT NULL,
                    date TEXT NOT NULL,
                    demand REAL NOT NULL,
                    source TEXT DEFAULT 'manual',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sku, location, date)
                );

                CREATE TABLE IF NOT EXISTS demand_forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL,
                    location TEXT NOT NULL,
                    date TEXT NOT NULL,
                    predicted_demand REAL NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    lower_bound REAL DEFAULT 0,
                    upper_bound REAL DEFAULT 0,
                    model_version TEXT DEFAULT 'prophet-v1',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sku, location, date)
                );

                CREATE INDEX IF NOT EXISTS idx_demand_history_sku_loc_date
                    ON demand_history(sku, location, date);
                CREATE INDEX IF NOT EXISTS idx_demand_forecasts_sku_loc_date
                    ON demand_forecasts(sku, location, date);
            """)

    def add_demand_observation(self, sku: str, location: str, date: str, demand: float, source: str = "manual"):
        """Add an actual demand observation."""
        self._init_db()
        db_path = self._get_db_path()

        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO demand_history (sku, location, date, demand, source)
                VALUES (?, ?, ?, ?, ?)
            """, (sku, location, date, demand, source))

    def get_training_data(self, sku: str = None, location: str = None, limit: int = 1000) -> List[TrainingDataPoint]:
        """Get training data from history."""
        self._init_db()
        db_path = self._get_db_path()

        query = "SELECT sku, location, date, demand FROM demand_history h"
        params = []
        conditions = []

        if sku:
            conditions.append("h.sku = ?")
            params.append(sku)
        if location:
            conditions.append("h.location = ?")
            params.append(location)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY h.date ASC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        data_points = []
        for row in rows:
            dt = datetime.fromisoformat(row["date"])
            data_points.append(TrainingDataPoint(
                sku=row["sku"],
                location=row["location"],
                date=row["date"],
                demand=row["demand"],
                day_of_week=dt.weekday(),
                is_weekend=dt.weekday() >= 5,
            ))

        return data_points

    def train(self, sku: str = None, location: str = None) -> bool:
        """Train the Prophet forecasting model."""
        self.sku = sku
        self.location = location
        training_data = self.get_training_data(sku, location)

        if len(training_data) < 7:
            logger.warning(f"Insufficient training data: {len(training_data)} points (need at least 7)")
            return False

        if HAS_PROPHET:
            return self._train_prophet(training_data)
        else:
            return self._train_fallback(training_data)

    def _train_prophet(self, training_data: List[TrainingDataPoint]) -> bool:
        """Train using Facebook Prophet."""
        import pandas as pd

        # Convert to Prophet format (ds=date, y=value)
        df = pd.DataFrame([
            {"ds": datetime.fromisoformat(dp.date), "y": dp.demand}
            for dp in training_data
        ])

        # Create Prophet model with demand-appropriate settings
        self.model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=len(training_data) > 365,
            seasonality_mode="multiplicative",
            changepoint_prior_scale=0.05,
        )

        # Add US holidays if we have enough data
        if len(training_data) > 30:
            self.model.add_country_holidays(country_name='US')

        self.model.fit(df)
        self.is_trained = True
        logger.info(f"Prophet model trained with {len(training_data)} data points for {self.sku}/{self.location}")
        return True

    def _train_fallback(self, training_data: List[TrainingDataPoint]) -> bool:
        """Fallback: simple weighted moving average by day of week."""
        dow_totals = {}
        dow_counts = {}
        for dp in training_data:
            dow = dp.day_of_week
            if dow not in dow_totals:
                dow_totals[dow] = 0
                dow_counts[dow] = 0
            dow_totals[dow] += dp.demand
            dow_counts[dow] += 1

        self.model = {
            dow: dow_totals[dow] / dow_counts[dow]
            for dow in dow_totals
        }
        self.is_trained = True
        logger.info(f"Fallback model trained with {len(training_data)} data points")
        return True

    def forecast(self, sku: str, location: str, start_date: str, days: int = 14) -> List[ForecastResult]:
        """Generate forecast for next N days."""
        if not self.is_trained:
            self.train(sku, location)

        results = []
        current_date = datetime.fromisoformat(start_date)
        self.sku = sku
        self.location = location

        if HAS_PROPHET and self.model and hasattr(self.model, 'predict'):
            import pandas as pd

            future_dates = pd.date_range(start=current_date, periods=days, freq='D')
            future = pd.DataFrame({'ds': future_dates})
            forecast = self.model.predict(future)

            for _, row in forecast.iterrows():
                ds = row['ds']
                if hasattr(ds, 'date'):
                    date_str = ds.date().isoformat()
                else:
                    date_str = str(ds)[:10]

                yhat = row['yhat']
                lower = row['yhat_lower']
                upper = row['yhat_upper']

                interval = upper - lower if upper > lower else abs(yhat) * 0.1
                confidence = max(0.3, min(0.95, 1 - (interval / (abs(yhat) + 1))))

                results.append(ForecastResult(
                    sku=sku,
                    location=location,
                    date=date_str,
                    predicted_demand=round(max(0, yhat), 2),
                    confidence=round(confidence, 2),
                    lower_bound=round(max(0, lower), 2),
                    upper_bound=round(upper, 2),
                    components={"trend": row.get('trend', yhat)}
                ))
        else:
            # Fallback: simple day-of-week average
            for i in range(days):
                dt = current_date + timedelta(days=i)
                date_str = dt.date().isoformat()
                dow = dt.weekday()

                predicted = self.model.get(dow, 100.0) if self.model else 100.0

                results.append(ForecastResult(
                    sku=sku,
                    location=location,
                    date=date_str,
                    predicted_demand=round(predicted, 2),
                    confidence=0.5,
                    lower_bound=round(predicted * 0.8, 2),
                    upper_bound=round(predicted * 1.2, 2),
                ))

        self._save_forecasts(results)
        return results

    def _save_forecasts(self, forecasts: List[ForecastResult]):
        """Save forecasts to database."""
        self._init_db()
        db_path = self._get_db_path()

        with sqlite3.connect(db_path) as conn:
            for f in forecasts:
                conn.execute("""
                    INSERT OR REPLACE INTO demand_forecasts
                    (sku, location, date, predicted_demand, confidence, lower_bound, upper_bound, model_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (f.sku, f.location, f.date, f.predicted_demand, f.confidence,
                      f.lower_bound, f.upper_bound, f.model_version))

    def get_latest_forecasts(self, sku: str = None, location: str = None, limit: int = 100) -> List[ForecastResult]:
        """Get latest forecasts from database."""
        self._init_db()
        db_path = self._get_db_path()

        query = "SELECT * FROM demand_forecasts"
        params = []

        if sku:
            query += " WHERE sku = ?"
            params.append(sku)
            if location:
                query += " AND location = ?"
                params.append(location)
        elif location:
            query += " WHERE location = ?"
            params.append(location)

        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [ForecastResult(
            sku=row["sku"],
            location=row["location"],
            date=row["date"],
            predicted_demand=row["predicted_demand"],
            confidence=row["confidence"],
            lower_bound=row["lower_bound"],
            upper_bound=row["upper_bound"],
            model_version=row["model_version"],
        ) for row in rows]

    def retrain_on_new_data(self) -> bool:
        """Retrain model when new POS data arrives."""
        return self.train(self.sku, self.location)


def create_forecast_model(project_id: str) -> DemandForecastModel:
    """Factory function to create forecast model."""
    return DemandForecastModel(project_id)
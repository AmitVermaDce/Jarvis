"""
Demand Sensing Adjuster
Compares forecasts against actuals and triggers adjustments/alerts.
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

from .forecast_model import DemandForecastModel, ForecastResult
try:
    import app.config as app_config
    Config = app_config.Config
except ImportError:
    Config = None

# Directory for demand sensing data
DEMAND_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../uploads/demand_sensing")


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Adjustment:
    """A forecast adjustment caused by signals."""
    id: str
    sku: str
    location: str
    date: str
    previous_forecast: float
    new_forecast: float
    deviation_percent: float
    reason: str
    signal_sources: List[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Alert:
    """An exception alert triggered by demand sensing."""
    id: str
    sku: str
    location: str
    alert_type: str  # demand_spike, demand_drop, promotion_underperforming, etc.
    severity: AlertSeverity
    message: str
    current_value: float = 0.0
    expected_value: float = 0.0
    deviation_percent: float = 0.0
    related_adjustments: List[str] = field(default_factory=list)
    acknowledged: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["severity"] = self.severity.value
        return result


class DemandAdjuster:
    """
    Compares forecasts against actual demand signals and triggers adjustments.
    Runs after each LiveDataPipeline tick.
    """

    # Default threshold for triggering adjustments (percentage)
    DEFAULT_DEVIATION_THRESHOLD = 15.0  # 15%
    # Threshold for critical alerts
    CRITICAL_THRESHOLD = 30.0  # 30%

    def __init__(self, project_id: str, deviation_threshold: float = None):
        self.project_id = project_id
        self.deviation_threshold = deviation_threshold or self.DEFAULT_DEVIATION_THRESHOLD
        self.forecast_model = DemandForecastModel(project_id)
        self._db_path = os.path.join(DEMAND_DATA_DIR, f"{project_id}_demand.db")

    def _ensure_db(self):
        """Ensure database is initialized."""
        os.makedirs(DEMAND_DATA_DIR, exist_ok=True)

        # Create tables if they don't exist
        import sqlite3
        conn = sqlite3.connect(self._db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS forecast_adjustments (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                location TEXT NOT NULL,
                date TEXT NOT NULL,
                previous_forecast REAL NOT NULL,
                new_forecast REAL NOT NULL,
                deviation_percent REAL NOT NULL,
                reason TEXT,
                signal_sources TEXT,
                confidence REAL,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                location TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT,
                current_value REAL DEFAULT 0,
                expected_value REAL DEFAULT 0,
                deviation_percent REAL DEFAULT 0,
                related_adjustments TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT,
                acknowledged_at TEXT
            );
        """)
        conn.close()

    def check_and_adjust(
        self,
        sku: str,
        location: str,
        actual_demand: float,
        date: str,
        signals: Dict[str, Any] = None
    ) -> Optional[Adjustment]:
        """
        Check if actual demand deviates from forecast and create adjustment if needed.

        Args:
            sku: SKU identifier
            location: Location identifier
            actual_demand: Actual observed demand
            date: Date of the demand
            signals: Signal data that might explain the deviation

        Returns:
            Adjustment if threshold exceeded, None otherwise
        """
        self._ensure_db()

        # Get the most recent forecast for this SKU/location/date
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT predicted_demand, confidence
                FROM demand_forecasts
                WHERE sku = ? AND location = ? AND date = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (sku, location, date))
            row = cursor.fetchone()

        if not row:
            logger.debug(f"No forecast found for {sku}/{location}/{date}")
            return None

        predicted_demand = row["predicted_demand"]
        confidence = row["confidence"]

        # Calculate deviation
        if predicted_demand > 0:
            deviation_percent = abs(actual_demand - predicted_demand) / predicted_demand * 100
        else:
            deviation_percent = 100 if actual_demand > 0 else 0

        # Check if adjustment needed
        if deviation_percent < self.deviation_threshold:
            return None

        # Create adjustment
        import uuid
        adjustment_id = f"adj_{uuid.uuid4().hex[:12]}"

        # Determine new forecast (weighted average of actual and predicted)
        # Weight actual more when deviation is high
        weight_actual = min(0.7, deviation_percent / 100)
        new_forecast = predicted_demand * (1 - weight_actual) + actual_demand * weight_actual

        # Build reason from signals
        reason = self._build_reason(signals, deviation_percent, actual_demand, predicted_demand)
        signal_sources = list(signals.keys()) if signals else []

        adjustment = Adjustment(
            id=adjustment_id,
            sku=sku,
            location=location,
            date=date,
            previous_forecast=predicted_demand,
            new_forecast=round(new_forecast, 2),
            deviation_percent=round(deviation_percent, 2),
            reason=reason,
            signal_sources=signal_sources,
            confidence=confidence,
        )

        # Save adjustment
        self._save_adjustment(adjustment)

        # Check if alert should be triggered
        if deviation_percent >= self.CRITICAL_THRESHOLD:
            self._create_alert(sku, location, date, actual_demand, predicted_demand, deviation_percent, adjustment_id)
        elif deviation_percent >= self.deviation_threshold:
            self._create_alert(sku, location, date, actual_demand, predicted_demand, deviation_percent, adjustment_id, severity=AlertSeverity.WARNING)

        return adjustment

    def _build_reason(
        self,
        signals: Dict[str, Any],
        deviation_percent: float,
        actual: float,
        predicted: float
    ) -> str:
        """Build human-readable reason for adjustment."""
        if not signals:
            return f"Deviation of {deviation_percent:.1f}% from forecast (actual: {actual}, predicted: {predicted})"

        reasons = []
        if signals.get("weather"):
            weather = signals["weather"]
            if "rain" in weather.lower() or "storm" in weather.lower():
                reasons.append("rainy weather")
            elif "heat" in weather.lower() or "hot" in weather.lower():
                reasons.append("hot weather")
            elif "snow" in weather.lower():
                reasons.append("snow weather")

        if signals.get("promotion"):
            reasons.append(f"promotion: {signals['promotion']}")

        if signals.get("event"):
            reasons.append(f"event: {signals['event']}")

        if signals.get("inventory"):
            inv = signals["inventory"]
            reasons.append(f"inventory level: {inv}")

        if signals.get("price_change"):
            reasons.append(f"price change: {signals['price_change']}")

        if not reasons:
            return f"Deviation of {deviation_percent:.1f}% from forecast"

        return f"Deviation of {deviation_percent:.1f}% due to: {', '.join(reasons)}"

    def _save_adjustment(self, adjustment: Adjustment):
        """Save adjustment to database."""
        self._ensure_db()

        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO forecast_adjustments
                (id, sku, location, date, previous_forecast, new_forecast,
                 deviation_percent, reason, signal_sources, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                adjustment.id,
                adjustment.sku,
                adjustment.location,
                adjustment.date,
                adjustment.previous_forecast,
                adjustment.new_forecast,
                adjustment.deviation_percent,
                adjustment.reason,
                json.dumps(adjustment.signal_sources),
                adjustment.confidence,
                adjustment.created_at,
            ))

        # Also update the forecast
        conn.execute("""
            UPDATE demand_forecasts
            SET predicted_demand = ?, confidence = ?
            WHERE sku = ? AND location = ? AND date = ?
        """, (
            adjustment.new_forecast,
            max(0.3, adjustment.confidence - 0.1),
            adjustment.sku,
            adjustment.location,
            adjustment.date,
        ))

    def _create_alert(
        self,
        sku: str,
        location: str,
        date: str,
        actual: float,
        predicted: float,
        deviation: float,
        adjustment_id: str,
        severity: AlertSeverity = AlertSeverity.INFO
    ):
        """Create an alert."""
        import uuid

        # Determine alert type
        if actual > predicted * 1.2:
            alert_type = "demand_spike"
        elif actual < predicted * 0.8:
            alert_type = "demand_drop"
        else:
            alert_type = "forecast_deviation"

        alert_id = f"alert_{uuid.uuid4().hex[:12]}"

        message = f"{alert_type.replace('_', ' ').title()}: {sku} at {location} on {date} - " \
                  f"Actual: {actual:.0f}, Expected: {predicted:.0f}, Deviation: {deviation:.1f}%"

        alert = Alert(
            id=alert_id,
            sku=sku,
            location=location,
            alert_type=alert_type,
            severity=severity,
            message=message,
            current_value=actual,
            expected_value=predicted,
            deviation_percent=deviation,
            related_adjustments=[adjustment_id],
        )

        self._save_alert(alert)

    def _save_alert(self, alert: Alert):
        """Save alert to database."""
        self._ensure_db()

        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO alerts
                (id, sku, location, alert_type, severity, message,
                 current_value, expected_value, deviation_percent,
                 related_adjustments, acknowledged, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.id,
                alert.sku,
                alert.location,
                alert.alert_type,
                alert.severity.value,
                alert.message,
                alert.current_value,
                alert.expected_value,
                alert.deviation_percent,
                json.dumps(alert.related_adjustments),
                int(alert.acknowledged),
                alert.created_at,
            ))

    def get_alerts(
        self,
        sku: str = None,
        location: str = None,
        severity: AlertSeverity = None,
        acknowledged: bool = None,
        limit: int = 100
    ) -> List[Alert]:
        """Get alerts with optional filters."""
        self._ensure_db()

        query = "SELECT * FROM alerts WHERE 1=1"
        params = []

        if sku:
            query += " AND sku = ?"
            params.append(sku)
        if location:
            query += " AND location = ?"
            params.append(location)
        if severity:
            query += " AND severity = ?"
            params.append(severity.value)
        if acknowledged is not None:
            query += " AND acknowledged = ?"
            params.append(int(acknowledged))

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        alerts = []
        for row in rows:
            alerts.append(Alert(
                id=row["id"],
                sku=row["sku"],
                location=row["location"],
                alert_type=row["alert_type"],
                severity=AlertSeverity(row["severity"]),
                message=row["message"],
                current_value=row["current_value"],
                expected_value=row["expected_value"],
                deviation_percent=row["deviation_percent"],
                related_adjustments=json.loads(row["related_adjustments"]),
                acknowledged=bool(row["acknowledged"]),
                created_at=row["created_at"],
                acknowledged_at=row.get("acknowledged_at"),
            ))

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        self._ensure_db()

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("""
                UPDATE alerts
                SET acknowledged = 1, acknowledged_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), alert_id))
            return cursor.rowcount > 0

    def get_adjustments(
        self,
        sku: str = None,
        location: str = None,
        date: str = None,
        limit: int = 100
    ) -> List[Adjustment]:
        """Get forecast adjustments."""
        self._ensure_db()

        query = "SELECT * FROM forecast_adjustments WHERE 1=1"
        params = []

        if sku:
            query += " AND sku = ?"
            params.append(sku)
        if location:
            query += " AND location = ?"
            params.append(location)
        if date:
            query += " AND date = ?"
            params.append(date)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        adjustments = []
        for row in rows:
            adjustments.append(Adjustment(
                id=row["id"],
                sku=row["sku"],
                location=row["location"],
                date=row["date"],
                previous_forecast=row["previous_forecast"],
                new_forecast=row["new_forecast"],
                deviation_percent=row["deviation_percent"],
                reason=row["reason"],
                signal_sources=json.loads(row["signal_sources"]),
                confidence=row["confidence"],
                created_at=row["created_at"],
            ))

        return adjustments


def create_adjuster(project_id: str, deviation_threshold: float = None) -> DemandAdjuster:
    """Factory function to create adjuster."""
    return DemandAdjuster(project_id, deviation_threshold)
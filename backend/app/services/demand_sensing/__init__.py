"""
Demand Sensing Module for Jarvis
Short-term demand forecasting (1-14 days) at SKU × location × day granularity.

Modules:
- forecast_model: Facebook Prophet model for demand prediction
- adjuster: Exception-based forecast adjustments
- signal_handlers: Handlers for various demand signals (POS, weather, etc.)
- graphify: Convert demand data to knowledge graph facts
- exceptions: Custom exceptions
"""

from .forecast_model import DemandForecastModel, ForecastResult
from .adjuster import DemandAdjuster, Adjustment, Alert, AlertSeverity
from .signal_handlers import SignalHandlerRegistry
from .graphify import DemandGraphifier, DemandGraphReporter, GraphFact, create_graphifier, create_graph_reporter

__all__ = [
    "DemandForecastModel",
    "ForecastResult",
    "DemandAdjuster",
    "Adjustment",
    "Alert",
    "AlertSeverity",
    "SignalHandlerRegistry",
    "DemandGraphifier",
    "DemandGraphReporter",
    "GraphFact",
    "create_graphifier",
    "create_graph_reporter",
]
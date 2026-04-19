"""
Graphify Skills for Demand Sensing
Converts demand data, forecasts, and signals into knowledge graph facts.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependency
GraphManager = None
GraphBuilderService = None

def _ensure_graph_imports():
    global GraphManager, GraphBuilderService
    if GraphManager is None:
        try:
            from ..services.local_graph_store import GraphManager
            from ..services.graph_builder import GraphBuilderService
        except ImportError as e:
            logger.warning(f"Could not import graph services: {e}")

# Import demand sensing components (optional)
try:
    from .forecast_model import DemandForecastModel, ForecastResult
    from .adjuster import DemandAdjuster, Adjustment, Alert
    from .signal_handlers import SignalHandlerRegistry
except ImportError:
    ForecastResult = None
    Adjustment = None
    Alert = None


@dataclass
class GraphFact:
    """A single fact to add to the knowledge graph."""
    source_node: str
    source_labels: List[str]
    target_node: str
    target_labels: List[str]
    edge_name: str
    fact: str
    attributes: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DemandGraphifier:
    """
    Graphify Skills: Convert demand data to knowledge graph facts.

    This enables:
    1. Demand forecasts → Graph nodes
    2. Forecast adjustments → Graph edges
    3. Alerts → Graph events
    4. Signals → Graph relationships
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.graph_id = None

    def set_graph_id(self, graph_id: str):
        """Set the knowledge graph ID for this project."""
        self.graph_id = graph_id

    def graphify_forecast(self, forecast: ForecastResult) -> List[GraphFact]:
        """Convert a forecast to graph facts."""
        facts = []

        # Create SKU node
        facts.append(GraphFact(
            source_node=f"SKU:{forecast.sku}",
            source_labels=["SKU", "DemandEntity"],
            target_node=f"Location:{forecast.location}",
            target_labels=["Location", "DemandEntity"],
            edge_name="forecasted_demand",
            fact=f"Forecasted demand for {forecast.sku} at {forecast.location} on {forecast.date}: "
                 f"{forecast.predicted_demand} units (confidence: {forecast.confidence:.0%})",
            attributes={
                "date": forecast.date,
                "predicted_demand": forecast.predicted_demand,
                "confidence": forecast.confidence,
                "lower_bound": forecast.lower_bound,
                "upper_bound": forecast.upper_bound,
                "model_version": forecast.model_version,
                "source": "demand_sensing"
            }
        ))

        # Add confidence indicator
        if forecast.confidence >= 0.8:
            facts.append(GraphFact(
                source_node=f"Forecast:{forecast.sku}:{forecast.date}",
                source_labels=["Forecast", "HighConfidence"],
                target_node=f"Location:{forecast.location}",
                target_labels=["Location"],
                edge_name="has_high_confidence",
                fact=f"High confidence forecast for {forecast.date}",
                attributes={"confidence": forecast.confidence}
            ))

        return facts

    def graphify_adjustment(self, adjustment: Adjustment) -> List[GraphFact]:
        """Convert a forecast adjustment to graph facts."""
        facts = []

        # Main adjustment fact
        facts.append(GraphFact(
            source_node=f"Adjustment:{adjustment.id}",
            source_labels=["Adjustment", "DemandEvent"],
            target_node=f"SKU:{adjustment.sku}",
            target_labels=["SKU", "DemandEntity"],
            edge_name="adjusts_forecast",
            fact=f"Forecast adjusted for {adjustment.sku} at {adjustment.location} on {adjustment.date}: "
                 f"{adjustment.previous_forecast} → {adjustment.new_forecast} "
                 f"({adjustment.deviation_percent:.1f}% deviation). Reason: {adjustment.reason}",
            attributes={
                "date": adjustment.date,
                "location": adjustment.location,
                "previous_forecast": adjustment.previous_forecast,
                "new_forecast": adjustment.new_forecast,
                "deviation_percent": adjustment.deviation_percent,
                "reason": adjustment.reason,
                "signal_sources": adjustment.signal_sources,
                "confidence": adjustment.confidence,
                "source": "demand_sensing"
            }
        ))

        # Add signal source relationships
        for signal in adjustment.signal_sources:
            facts.append(GraphFact(
                source_node=f"Signal:{signal}",
                source_labels=["Signal", "DemandSignal"],
                target_node=f"Adjustment:{adjustment.id}",
                target_labels=["Adjustment"],
                edge_name="caused_adjustment",
                fact=f"Signal '{signal}' caused forecast adjustment",
                attributes={"signal": signal}
            ))

        return facts

    def graphify_alert(self, alert: Alert) -> List[GraphFact]:
        """Convert an alert to graph facts."""
        facts = []

        severity_label = f"{alert.severity.value.title()}Alert"

        facts.append(GraphFact(
            source_node=f"Alert:{alert.id}",
            source_labels=["Alert", severity_label, "DemandEvent"],
            target_node=f"SKU:{alert.sku}",
            target_labels=["SKU", "DemandEntity"],
            edge_name="triggers_alert",
            fact=f"Alert for {alert.sku} at {alert.location}: {alert.message}",
            attributes={
                "alert_type": alert.alert_type,
                "severity": alert.severity.value,
                "message": alert.message,
                "current_value": alert.current_value,
                "expected_value": alert.expected_value,
                "deviation_percent": alert.deviation_percent,
                "acknowledged": alert.acknowledged,
                "created_at": alert.created_at,
                "source": "demand_sensing"
            }
        ))

        return facts

    def graphify_signal(self, signal_type: str, signal_data: Dict[str, Any]) -> List[GraphFact]:
        """Convert an external signal to graph facts."""
        facts = []

        if signal_type == "weather":
            facts.append(GraphFact(
                source_node=f"Weather:{signal_data.get('condition', 'unknown')}",
                source_labels=["WeatherCondition", "ExternalSignal"],
                target_node=f"Location:{signal_data.get('location', 'unknown')}",
                target_labels=["Location", "DemandEntity"],
                edge_name="affects_demand",
                fact=f"Weather on {signal_data.get('date')}: {signal_data.get('condition')} "
                     f"at {signal_data.get('temperature')}°C - affects demand patterns",
                attributes=signal_data
            ))

        elif signal_type == "pos":
            facts.append(GraphFact(
                source_node=f"SKU:{signal_data.get('sku')}",
                source_labels=["SKU", "DemandEntity"],
                target_node=f"Location:{signal_data.get('location')}",
                target_labels=["Location", "DemandEntity"],
                edge_name="sold",
                fact=f"Sold {signal_data.get('quantity', 0)} units on {signal_data.get('date')}",
                attributes={
                    "date": signal_data.get("date"),
                    "quantity": signal_data.get("quantity"),
                    "source": "pos"
                }
            ))

        elif signal_type == "inventory":
            facts.append(GraphFact(
                source_node=f"SKU:{signal_data.get('sku')}",
                source_labels=["SKU", "InventoryEntity"],
                target_node=f"Location:{signal_data.get('location')}",
                target_labels=["Location", "InventoryEntity"],
                edge_name="has_inventory_level",
                fact=f"Inventory level: {signal_data.get('level', 0)} units",
                attributes={
                    "level": signal_data.get("level"),
                    "reorder_point": signal_data.get("reorder_point"),
                    "source": "inventory"
                }
            ))

        elif signal_type == "promotion":
            facts.append(GraphFact(
                source_node=f"Promotion:{signal_data.get('name', 'unknown')}",
                source_labels=["Promotion", "DemandDriver"],
                target_node=f"SKU:{signal_data.get('sku')}",
                target_labels=["SKU", "DemandEntity"],
                edge_name="boosts_demand",
                fact=f"Promotion '{signal_data.get('name')}' - "
                     f"{signal_data.get('discount_percent')} discount from "
                     f"{signal_data.get('start_date')} to {signal_data.get('end_date')}",
                attributes={
                    "discount_percent": signal_data.get("discount_percent"),
                    "start_date": signal_data.get("start_date"),
                    "end_date": signal_data.get("end_date"),
                    "source": "promotion"
                }
            ))

        return facts

    def add_facts_to_graph(self, facts: List[GraphFact]) -> int:
        """Add graph facts to the knowledge graph."""
        if not self.graph_id:
            logger.warning("No graph_id set, cannot add facts")
            return 0

        try:
            _ensure_graph_imports()
            if GraphManager is None:
                logger.error("GraphManager not available")
                return 0

            store = GraphManager.get_store(self.graph_id)
            facts_added = 0

            for fact in facts:
                try:
                    # Upsert source node
                    src_uuid = store.upsert_node(
                        name=fact.source_node,
                        labels=fact.source_labels,
                    )

                    # Upsert target node
                    tgt_uuid = store.upsert_node(
                        name=fact.target_node,
                        labels=fact.target_labels,
                    )

                    # Add edge
                    store.add_edge(
                        name=fact.edge_name,
                        fact=fact.fact,
                        source_node_uuid=src_uuid,
                        target_node_uuid=tgt_uuid,
                        attributes=fact.attributes or {},
                    )
                    facts_added += 1

                except Exception as e:
                    logger.warning(f"Failed to add fact: {e}")

            logger.info(f"Added {facts_added} graph facts")
            return facts_added

        except Exception as e:
            logger.error(f"Failed to add facts to graph: {e}")
            return 0


class DemandGraphReporter:
    """
    Generate graph-based reports from demand sensing data.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id

    def generate_demand_summary_graph(self) -> Dict[str, Any]:
        """Generate a summary graph of demand sensing data."""
        from .forecast_model import DemandForecastModel
        from .adjuster import DemandAdjuster

        model = DemandForecastModel(self.project_id)
        adjuster = DemandAdjuster(self.project_id)

        # Get latest data
        forecasts = model.get_latest_forecasts(limit=10)
        alerts = adjuster.get_alerts(acknowledged=False, limit=5)
        adjustments = adjuster.get_adjustments(limit=5)

        # Build graph summary
        nodes = []
        edges = []

        # Add forecast nodes
        for f in forecasts:
            nodes.append({
                "id": f"forecast-{f.sku}-{f.date}",
                "label": f"{f.sku}: {f.predicted_demand:.0f}",
                "type": "forecast",
                "data": f.to_dict()
            })

        # Add alert nodes
        for a in alerts:
            nodes.append({
                "id": f"alert-{a.id}",
                "label": f"Alert: {a.alert_type}",
                "type": "alert",
                "severity": a.severity.value,
                "data": a.to_dict()
            })

        # Add adjustment edges
        for adj in adjustments:
            edges.append({
                "source": f"adjustment-{adj.id}",
                "target": f"forecast-{adj.sku}-{adj.date}",
                "label": f"Deviation: {adj.deviation_percent:.1f}%",
                "type": "adjustment"
            })

        return {
            "project_id": self.project_id,
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "total_forecasts": len(forecasts),
                "active_alerts": len(alerts),
                "recent_adjustments": len(adjustments)
            }
        }


def create_graphifier(project_id: str) -> DemandGraphifier:
    """Factory function to create a graphifier."""
    return DemandGraphifier(project_id)


def create_graph_reporter(project_id: str) -> DemandGraphReporter:
    """Factory function to create a graph reporter."""
    return DemandGraphReporter(project_id)
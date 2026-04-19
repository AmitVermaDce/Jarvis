"""
Demand Sensing API Endpoints
API for forecasts, alerts, graphify, and demand signal management.
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import demand sensing components
try:
    from ..services.demand_sensing.forecast_model import DemandForecastModel
    from ..services.demand_sensing.adjuster import DemandAdjuster, AlertSeverity
    from ..services.demand_sensing.signal_handlers import SignalHandlerRegistry
    from ..services.demand_sensing.graphify import create_graphifier, create_graph_reporter
    from ..services.live_data_pipeline import live_data_pipeline
    DEMAND_SENSING_AVAILABLE = True
except ImportError as e:
    DEMAND_SENSING_AVAILABLE = False
    logger.warning(f"Demand sensing not available: {e}")


def create_demand_sensing_blueprint():
    """Create the demand sensing API blueprint."""
    if not DEMAND_SENSING_AVAILABLE:
        logger.warning("Demand sensing module not available")

    bp = Blueprint('demand_sensing', __name__, url_prefix='/api/demand-sensing')

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Check if demand sensing is available."""
        return jsonify({
            "available": DEMAND_SENSING_AVAILABLE,
            "message": "Demand sensing module is ready" if DEMAND_SENSING_AVAILABLE else "Module not available"
        })

    # ── Forecast Endpoints ─────────────────────────────────────────────

    @bp.route('/forecast', methods=['POST'])
    def create_forecast():
        """Generate a new forecast."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        data = request.get_json() or {}
        project_id = data.get("project_id")
        sku = data.get("sku")
        location = data.get("location")
        start_date = data.get("start_date")
        days = data.get("days", 14)

        if not all([project_id, sku, location, start_date]):
            return jsonify({"error": "Missing required fields: project_id, sku, location, start_date"}), 400

        try:
            model = DemandForecastModel(project_id)
            forecasts = model.forecast(sku, location, start_date, days)

            return jsonify({
                "success": True,
                "forecasts": [f.to_dict() for f in forecasts]
            })
        except Exception as e:
            logger.error(f"Error creating forecast: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/forecast/<project_id>', methods=['GET'])
    def get_forecasts(project_id):
        """Get latest forecasts for a project."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        sku = request.args.get("sku")
        location = request.args.get("location")
        limit = int(request.args.get("limit", 100))

        try:
            model = DemandForecastModel(project_id)
            forecasts = model.get_latest_forecasts(sku, location, limit)

            return jsonify({
                "success": True,
                "forecasts": [f.to_dict() for f in forecasts]
            })
        except Exception as e:
            logger.error(f"Error getting forecasts: {e}")
            return jsonify({"error": str(e)}), 500

    # ── Alert Endpoints ─────────────────────────────────────────────────

    @bp.route('/alerts', methods=['GET'])
    def get_alerts():
        """Get alerts for a project."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        project_id = request.args.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        sku = request.args.get("sku")
        location = request.args.get("location")
        severity = request.args.get("severity")
        acknowledged = request.args.get("acknowledged")

        if acknowledged is not None:
            acknowledged = acknowledged.lower() == "true"

        try:
            adjuster = DemandAdjuster(project_id)
            alerts = adjuster.get_alerts(
                sku=sku,
                location=location,
                severity=AlertSeverity(severity) if severity else None,
                acknowledged=acknowledged
            )

            return jsonify({
                "success": True,
                "count": len(alerts),
                "alerts": [a.to_dict() for a in alerts]
            })
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
    def acknowledge_alert(alert_id):
        """Acknowledge an alert."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        project_id = request.args.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        try:
            adjuster = DemandAdjuster(project_id)
            success = adjuster.acknowledge_alert(alert_id)

            if success:
                return jsonify({"success": True, "message": "Alert acknowledged"})
            else:
                return jsonify({"error": "Alert not found"}), 404
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/alerts/<alert_id>', methods=['GET'])
    def get_alert(alert_id):
        """Get a specific alert."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        project_id = request.args.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        try:
            adjuster = DemandAdjuster(project_id)
            alerts = adjuster.get_alerts(limit=1000)

            alert = next((a for a in alerts if a.id == alert_id), None)
            if alert:
                return jsonify({"success": True, "alert": alert.to_dict()})
            else:
                return jsonify({"error": "Alert not found"}), 404
        except Exception as e:
            logger.error(f"Error getting alert: {e}")
            return jsonify({"error": str(e)}), 500

    # ── Adjustment Endpoints ───────────────────────────────────────────

    @bp.route('/adjustments', methods=['GET'])
    def get_adjustments():
        """Get forecast adjustments for a project."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        project_id = request.args.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        sku = request.args.get("sku")
        location = request.args.get("location")
        date = request.args.get("date")
        limit = int(request.args.get("limit", 100))

        try:
            adjuster = DemandAdjuster(project_id)
            adjustments = adjuster.get_adjustments(sku, location, date, limit)

            return jsonify({
                "success": True,
                "count": len(adjustments),
                "adjustments": [a.to_dict() for a in adjustments]
            })
        except Exception as e:
            logger.error(f"Error getting adjustments: {e}")
            return jsonify({"error": str(e)}), 500

    # ── Signal Endpoints ───────────────────────────────────────────────

    @bp.route('/signals/fetch', methods=['POST'])
    def fetch_signals():
        """Manually trigger signal fetch for a project."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        data = request.get_json() or {}
        project_id = data.get("project_id")
        sku = data.get("sku")
        location = data.get("location")
        sources = data.get("sources")  # list of sources to fetch

        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        try:
            signals = SignalHandlerRegistry.fetch_all_signals(
                sku=sku,
                location=location,
                sources=sources
            )

            return jsonify({
                "success": True,
                "sources": {k: len(v) for k, v in signals.items()},
                "signals": signals
            })
        except Exception as e:
            logger.error(f"Error fetching signals: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/signals/ingest', methods=['POST'])
    def ingest_signals():
        """Ingest signals into knowledge graph and process for forecasting."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        data = request.get_json() or {}
        project_id = data.get("project_id")
        signals = data.get("signals", {})

        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        if not signals:
            return jsonify({"error": "signals required"}), 400

        try:
            # Ingest to graph
            facts_added = live_data_pipeline.ingest_demand_signals_to_graph(project_id, signals)

            # Process for forecasting
            processing_results = live_data_pipeline.process_demand_signals_for_forecasting(project_id, signals)

            return jsonify({
                "success": True,
                "facts_added": facts_added,
                "processing": processing_results
            })
        except Exception as e:
            logger.error(f"Error ingesting signals: {e}")
            return jsonify({"error": str(e)}), 500

    # ── Demand Observation Endpoints ───────────────────────────────────

    @bp.route('/observations', methods=['POST'])
    def add_observation():
        """Add a demand observation (actual sales data)."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        data = request.get_json() or {}
        project_id = data.get("project_id")
        sku = data.get("sku")
        location = data.get("location")
        date = data.get("date")
        demand = data.get("demand")

        if not all([project_id, sku, location, date, demand]):
            return jsonify({"error": "Missing required fields"}), 400

        try:
            model = DemandForecastModel(project_id)
            model.add_demand_observation(sku, location, date, demand)

            # Check for adjustments
            adjuster = DemandAdjuster(project_id)
            adjustment = adjuster.check_and_adjust(sku, location, demand, date)

            return jsonify({
                "success": True,
                "observation_added": True,
                "adjustment": adjustment.to_dict() if adjustment else None
            })
        except Exception as e:
            logger.error(f"Error adding observation: {e}")
            return jsonify({"error": str(e)}), 500

    # ── Summary Endpoint ───────────────────────────────────────────────

    @bp.route('/summary/<project_id>', methods=['GET'])
    def get_summary(project_id):
        """Get demand sensing summary for a project."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        try:
            model = DemandForecastModel(project_id)
            adjuster = DemandAdjuster(project_id)

            # Get latest forecasts
            forecasts = model.get_latest_forecasts(limit=10)

            # Get unacknowledged alerts
            alerts = adjuster.get_alerts(acknowledged=False, limit=10)

            # Get recent adjustments
            adjustments = adjuster.get_adjustments(limit=5)

            return jsonify({
                "success": True,
                "project_id": project_id,
                "forecasts_count": len(forecasts),
                "unacknowledged_alerts": len(alerts),
                "recent_adjustments": len(adjustments),
                "latest_alerts": [a.to_dict() for a in alerts[:5]],
                "recent_adjustments_list": [a.to_dict() for a in adjustments[:5]]
            })
        except Exception as e:
            logger.error(f"Error getting summary: {e}")
            return jsonify({"error": str(e)}), 500

    # ── Graphify Endpoints ───────────────────────────────────────────────

    @bp.route('/graphify/forecast', methods=['POST'])
    def graphify_forecast():
        """Convert forecasts to graph facts and add to knowledge graph."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        data = request.get_json() or {}
        project_id = data.get("project_id")
        graph_id = data.get("graph_id")
        sku = data.get("sku")
        location = data.get("location")

        if not project_id or not graph_id:
            return jsonify({"error": "project_id and graph_id required"}), 400

        try:
            # Get forecasts
            model = DemandForecastModel(project_id)
            forecasts = model.get_latest_forecasts(sku, location, limit=10)

            # Convert to graph facts
            graphifier = create_graphifier(project_id)
            graphifier.set_graph_id(graph_id)

            all_facts = []
            for f in forecasts:
                facts = graphifier.graphify_forecast(f)
                all_facts.extend(facts)

            # Add to graph
            facts_added = graphifier.add_facts_to_graph(all_facts)

            return jsonify({
                "success": True,
                "forecasts_processed": len(forecasts),
                "facts_added": facts_added
            })
        except Exception as e:
            logger.error(f"Error in graphify forecast: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/graphify/signals', methods=['POST'])
    def graphify_signals():
        """Convert signals to graph facts."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        data = request.get_json() or {}
        project_id = data.get("project_id")
        graph_id = data.get("graph_id")
        signals = data.get("signals", {})

        if not project_id or not graph_id:
            return jsonify({"error": "project_id and graph_id required"}), 400

        try:
            graphifier = create_graphifier(project_id)
            graphifier.set_graph_id(graph_id)

            all_facts = []
            for signal_type, signal_list in signals.items():
                for sig in signal_list:
                    facts = graphifier.graphify_signal(signal_type, sig)
                    all_facts.extend(facts)

            facts_added = graphifier.add_facts_to_graph(all_facts)

            return jsonify({
                "success": True,
                "signals_processed": sum(len(v) for v in signals.values()),
                "facts_added": facts_added
            })
        except Exception as e:
            logger.error(f"Error in graphify signals: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/graphify/summary', methods=['GET'])
    def get_graph_summary():
        """Get demand sensing summary as graph data."""
        if not DEMAND_SENSING_AVAILABLE:
            return jsonify({"error": "Demand sensing not available"}), 500

        project_id = request.args.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id required"}), 400

        try:
            reporter = create_graph_reporter(project_id)
            summary = reporter.generate_demand_summary_graph()

            return jsonify({
                "success": True,
                "graph": summary
            })
        except Exception as e:
            logger.error(f"Error getting graph summary: {e}")
            return jsonify({"error": str(e)}), 500

    return bp
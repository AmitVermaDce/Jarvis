#!/usr/bin/env python3
"""
Demand Sensing Runner
Run demand sensing for a project from the command line.

Usage:
    python run_demand_sensing.py --project PROJECT_ID --sku SKU123 --location StoreA
    python run_demand_sensing.py --project PROJECT_ID --fetch-signals
    python run_demand_sensing.py --project PROJECT_ID --forecast
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Run demand sensing for Jarvis')

    parser.add_argument('--project', type=str, required=True,
                        help='Project ID')
    parser.add_argument('--sku', type=str,
                        help='SKU to forecast (optional)')
    parser.add_argument('--location', type=str,
                        help='Location to forecast (optional)')
    parser.add_argument('--start-date', type=str,
                        help='Start date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--days', type=int, default=14,
                        help='Number of days to forecast (default: 14)')

    # Action flags
    parser.add_argument('--fetch-signals', action='store_true',
                        help='Fetch demand signals from all sources')
    parser.add_argument('--forecast', action='store_true',
                        help='Generate demand forecast')
    parser.add_argument('--add-observation', nargs=4, metavar=('SKU', 'LOCATION', 'DATE', 'DEMAND'),
                        help='Add demand observation: SKU LOCATION DATE YYYY-MM-DD DEMAND')
    parser.add_argument('--list-alerts', action='store_true',
                        help='List unacknowledged alerts')
    parser.add_argument('--acknowledge-alert', type=str,
                        help='Alert ID to acknowledge')
    parser.add_argument('--summary', action='store_true',
                        help='Get demand sensing summary')

    args = parser.parse_args()

    # Import after path setup
    try:
        from app.services.demand_sensing.forecast_model import DemandForecastModel
        from app.services.demand_sensing.adjuster import DemandAdjuster, AlertSeverity
        from app.services.demand_sensing.signal_handlers import SignalHandlerRegistry
        from app.services.live_data_pipeline import live_data_pipeline
    except ImportError as e:
        logger.error(f"Failed to import demand sensing modules: {e}")
        logger.error("Make sure demand_sensing module is installed")
        sys.exit(1)

    project_id = args.project
    logger.info(f"Starting demand sensing for project: {project_id}")

    # ─────────────────────────────────────────────────────────────────
    # Fetch Signals
    # ─────────────────────────────────────────────────────────────────
    if args.fetch_signals:
        logger.info("Fetching demand signals...")
        signals = live_data_pipeline.fetch_demand_signals(
            project_id=project_id,
            sku=args.sku,
            location=args.location
        )

        print(f"\n=== Signals Fetched ===")
        for source, sig_list in signals.items():
            print(f"{source}: {len(sig_list)} signals")
            for sig in sig_list[:3]:  # Show first 3
                print(f"  - {sig}")

        # Ingest into graph
        facts_added = live_data_pipeline.ingest_demand_signals_to_graph(project_id, signals)
        print(f"\nAdded {facts_added} facts to knowledge graph")

        # Process for forecasting
        results = live_data_pipeline.process_demand_signals_for_forecasting(project_id, signals)
        print(f"\nProcessing results: {results}")

    # ─────────────────────────────────────────────────────────────────
    # Generate Forecast
    # ─────────────────────────────────────────────────────────────────
    if args.forecast:
        if not args.sku or not args.location:
            logger.error("--forecast requires --sku and --location")
            sys.exit(1)

        start_date = args.start_date or datetime.now().date().isoformat()

        logger.info(f"Generating forecast for {args.sku} at {args.location}")
        model = DemandForecastModel(project_id)
        forecasts = model.forecast(args.sku, args.location, start_date, args.days)

        print(f"\n=== Forecast for {args.sku} at {args.location} ===")
        print(f"Start: {start_date}, Days: {args.days}")
        print("-" * 60)
        for f in forecasts:
            print(f"{f.date}: {f.predicted_demand:.0f} units (confidence: {f.confidence:.0%})")

    # ─────────────────────────────────────────────────────────────────
    # Add Observation
    # ─────────────────────────────────────────────────────────────────
    if args.add_observation:
        sku, location, date, demand = args.add_observation
        demand = float(demand)

        logger.info(f"Adding observation: {sku} at {location} on {date} = {demand}")

        model = DemandForecastModel(project_id)
        model.add_demand_observation(sku, location, date, demand)

        # Check for adjustment
        adjuster = DemandAdjuster(project_id)
        adjustment = adjuster.check_and_adjust(sku, location, demand, date)

        if adjustment:
            print(f"\nAdjustment made: {adjustment.reason}")
            print(f"  Previous: {adjustment.previous_forecast:.0f} -> New: {adjustment.new_forecast:.0f}")
            print(f"  Deviation: {adjustment.deviation_percent:.1f}%")
        else:
            print("\nNo adjustment needed - within threshold")

    # ─────────────────────────────────────────────────────────────────
    # List Alerts
    # ─────────────────────────────────────────────────────────────────
    if args.list_alerts:
        adjuster = DemandAdjuster(project_id)
        alerts = adjuster.get_alerts(acknowledged=False)

        print(f"\n=== Unacknowledged Alerts ({len(alerts)}) ===")
        for alert in alerts:
            print(f"\n[{alert.severity.value.upper()}] {alert.id}")
            print(f"  {alert.message}")
            print(f"  Created: {alert.created_at}")

    # ─────────────────────────────────────────────────────────────────
    # Acknowledge Alert
    # ─────────────────────────────────────────────────────────────────
    if args.acknowledge_alert:
        adjuster = DemandAdjuster(project_id)
        success = adjuster.acknowledge_alert(args.acknowledge_alert)

        if success:
            print(f"Alert {args.acknowledge_alert} acknowledged")
        else:
            print(f"Alert {args.acknowledge_alert} not found")

    # ─────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────
    if args.summary:
        model = DemandForecastModel(project_id)
        adjuster = DemandAdjuster(project_id)

        forecasts = model.get_latest_forecasts(limit=10)
        alerts = adjuster.get_alerts(acknowledged=False, limit=10)
        adjustments = adjuster.get_adjustments(limit=5)

        print(f"\n=== Demand Sensing Summary for {project_id} ===")
        print(f"Latest forecasts: {len(forecasts)}")
        print(f"Unacknowledged alerts: {len(alerts)}")
        print(f"Recent adjustments: {len(adjustments)}")

        if alerts:
            print("\n--- Top Alerts ---")
            for a in alerts[:5]:
                print(f"  [{a.severity.value}] {a.message}")

        if adjustments:
            print("\n--- Recent Adjustments ---")
            for adj in adjustments[:5]:
                print(f"  {adj.sku} @ {adj.location} on {adj.date}: "
                      f"{adj.previous_forecast:.0f} -> {adj.new_forecast:.0f} ({adj.deviation_percent:.1f}%)")

    # If no specific action, show help
    if not any([args.fetch_signals, args.forecast, args.add_observation,
                args.list_alerts, args.acknowledge_alert, args.summary]):
        parser.print_help()


if __name__ == "__main__":
    main()
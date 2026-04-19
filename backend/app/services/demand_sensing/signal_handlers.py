"""
Signal Handlers for Demand Sensing
Handlers for various demand signal sources (POS, weather, inventory, etc.)
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
from datetime import datetime, date
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

try:
    import app.config as app_config
    Config = app_config.Config
except ImportError:
    Config = None

# Directory for demand sensing data
DEMAND_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../uploads/demand_sensing")


class BaseSignalHandler(ABC):
    """Base class for signal handlers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the signal source."""
        pass

    @abstractmethod
    def fetch_signals(self, sku: str = None, location: str = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch signals from this source.

        Args:
            sku: Optional SKU filter
            location: Optional location filter
            **kwargs: Additional source-specific parameters

        Returns:
            List of signal dictionaries
        """
        pass

    def transform_to_graph_facts(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform signals into graph facts for knowledge graph.

        Returns list of facts in format:
        {
            "source_node": {"name": "...", "labels": [...]},
            "target_node": {"name": "...", "labels": [...]},
            "edge": {"name": "...", "fact": "..."}
        }
        """
        facts = []
        for sig in signals:
            fact = self._transform_single_signal(sig)
            if fact:
                facts.append(fact)
        return facts

    @abstractmethod
    def _transform_single_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a single signal to graph fact format."""
        pass


class POSSignalHandler(BaseSignalHandler):
    """Handler for Point-of-Sale (POS) data from ERP."""

    @property
    def source_name(self) -> str:
        return "pos"

    def fetch_signals(self, sku: str = None, location: str = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch POS data from ERP API.

        Requires ERP_API_KEY and ERP_API_URL in config.
        """
        api_url = os.environ.get("ERP_API_URL")
        api_key = os.environ.get("ERP_API_KEY")

        if not api_url or not api_key:
            logger.debug("ERP API not configured, skipping POS fetch")
            return []

        try:
            params = {"api_key": api_key}
            if sku:
                params["sku"] = sku
            if location:
                params["location"] = location

            # Get date range (last 7 days)
            params["start_date"] = kwargs.get("start_date", (datetime.now() - __import__('datetime').timedelta(days=7)).date().isoformat())
            params["end_date"] = kwargs.get("end_date", datetime.now().date().isoformat())

            response = requests.get(f"{api_url}/pos/sales", params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get("sales", [])

        except Exception as e:
            logger.error(f"Failed to fetch POS data: {e}")
            return []

    def _transform_single_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform POS signal to graph fact."""
        return {
            "source_node": {
                "name": f"SKU:{signal.get('sku', 'unknown')}",
                "labels": ["SKU"]
            },
            "target_node": {
                "name": f"Store:{signal.get('location', 'unknown')}",
                "labels": ["Location"]
            },
            "edge": {
                "name": "sold_at",
                "fact": f"Sold {signal.get('quantity', 0)} units on {signal.get('date', 'unknown')}"
            }
        }


class WeatherSignalHandler(BaseSignalHandler):
    """Handler for weather data."""

    @property
    def source_name(self) -> str:
        return "weather"

    def fetch_signals(self, sku: str = None, location: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Fetch weather forecast data."""
        api_key = os.environ.get("WEATHER_API_KEY")

        if not api_key:
            logger.debug("Weather API not configured, skipping weather fetch")
            return []

        # Default to US if no location provided
        if not location:
            location = "New York,US"

        try:
            # Get 14-day forecast
            url = f"https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "q": location,
                "appid": api_key,
                "units": "metric"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            signals = []

            # Process forecasts (comes in 3-hour blocks)
            for item in data.get("list", []):
                dt = datetime.fromtimestamp(item["dt"])
                signals.append({
                    "date": dt.date().isoformat(),
                    "location": location,
                    "temperature": item["main"]["temp"],
                    "condition": item["weather"][0]["main"],
                    "description": item["weather"][0]["description"],
                    "humidity": item["main"]["humidity"],
                    "source": "openweathermap",
                })

            return signals

        except Exception as e:
            logger.error(f"Failed to fetch weather data: {e}")
            return []

    def _transform_single_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform weather signal to graph fact."""
        condition = signal.get("condition", "unknown")
        location = signal.get("location", "unknown")

        # Map weather conditions to demand impact
        impact_map = {
            "Rain": "increases demand for umbrellas, raincoats",
            "Snow": "increases demand for winter items, reduces foot traffic",
            "Clear": "normal demand",
            "Clouds": "normal demand",
            "Thunderstorm": "reduces foot traffic",
            "Heat": "increases demand for cold drinks, AC units",
        }

        impact = impact_map.get(condition, "normal demand")

        return {
            "source_node": {
                "name": f"Weather:{condition}",
                "labels": ["WeatherCondition"]
            },
            "target_node": {
                "name": f"Location:{location}",
                "labels": ["Location"]
            },
            "edge": {
                "name": "affects_demand_for",
                "fact": f"Weather forecast for {signal.get('date')}: {condition}, {signal.get('description')} at {signal.get('temperature')}°C - {impact}"
            }
        }


class InventorySignalHandler(BaseSignalHandler):
    """Handler for inventory level data."""

    @property
    def source_name(self) -> str:
        return "inventory"

    def fetch_signals(self, sku: str = None, location: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Fetch inventory data from ERP."""
        api_url = os.environ.get("ERP_API_URL")
        api_key = os.environ.get("ERP_API_KEY")

        if not api_url or not api_key:
            logger.debug("ERP API not configured, skipping inventory fetch")
            return []

        try:
            params = {"api_key": api_key}
            if sku:
                params["sku"] = sku
            if location:
                params["location"] = location

            response = requests.get(f"{api_url}/inventory/levels", params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get("inventory", [])

        except Exception as e:
            logger.error(f"Failed to fetch inventory data: {e}")
            return []

    def _transform_single_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform inventory signal to graph fact."""
        level = signal.get("level", 0)
        reorder_point = signal.get("reorder_point", 0)

        status = "OK"
        if level <= 0:
            status = "OUT_OF_STOCK"
        elif level < reorder_point:
            status = "BELOW_REORDER_POINT"

        return {
            "source_node": {
                "name": f"SKU:{signal.get('sku', 'unknown')}",
                "labels": ["SKU"]
            },
            "target_node": {
                "name": f"Store:{signal.get('location', 'unknown')}",
                "labels": ["Location"]
            },
            "edge": {
                "name": "has_inventory",
                "fact": f"Inventory: {level} units (reorder point: {reorder_point}) - Status: {status}"
            }
        }


class PromotionSignalHandler(BaseSignalHandler):
    """Handler for promotion data."""

    @property
    def source_name(self) -> str:
        return "promotion"

    def fetch_signals(self, sku: str = None, location: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Fetch promotion data from ERP/calendar."""
        api_url = os.environ.get("ERP_API_URL")
        api_key = os.environ.get("ERP_API_KEY")

        if not api_url or not api_key:
            logger.debug("ERP API not configured, skipping promotion fetch")
            return []

        try:
            params = {"api_key": api_key}
            if sku:
                params["sku"] = sku

            # Get upcoming promotions
            response = requests.get(f"{api_url}/promotions/active", params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get("promotions", [])

        except Exception as e:
            logger.error(f"Failed to fetch promotion data: {e}")
            return []

    def _transform_single_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform promotion signal to graph fact."""
        return {
            "source_node": {
                "name": f"Promotion:{signal.get('name', 'unknown')}",
                "labels": ["Promotion"]
            },
            "target_node": {
                "name": f"SKU:{signal.get('sku', 'unknown')}",
                "labels": ["SKU"]
            },
            "edge": {
                "name": "applies_to",
                "fact": f"Promotion: {signal.get('name')} - {signal.get('discount_percent')}% off from {signal.get('start_date')} to {signal.get('end_date')}"
            }
        }


class EventSignalHandler(BaseSignalHandler):
    """Handler for local events (sports, concerts, holidays)."""

    @property
    def source_name(self) -> str:
        return "event"

    def fetch_signals(self, sku: str = None, location: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Fetch local events (placeholder - would need Ticketmaster API or similar)."""
        # This would require a proper events API (Ticketmaster, Eventbrite, etc.)
        # For now, return empty list - can be extended
        logger.debug("Event handler: no API configured")
        return []

    def _transform_single_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform event signal to graph fact."""
        return {
            "source_node": {
                "name": f"Event:{signal.get('name', 'unknown')}",
                "labels": ["Event"]
            },
            "target_node": {
                "name": f"Location:{signal.get('location', 'unknown')}",
                "labels": ["Location"]
            },
            "edge": {
                "name": "affects_demand_at",
                "fact": f"Event: {signal.get('name')} on {signal.get('date')} - Expected attendance: {signal.get('attendance', 'unknown')}"
            }
        }


class SignalHandlerRegistry:
    """Registry for all signal handlers."""

    _handlers: Dict[str, BaseSignalHandler] = {}

    @classmethod
    def register(cls, handler: BaseSignalHandler):
        """Register a signal handler."""
        cls._handlers[handler.source_name] = handler
        logger.info(f"Registered signal handler: {handler.source_name}")

    @classmethod
    def get_handler(cls, source_name: str) -> Optional[BaseSignalHandler]:
        """Get a handler by name."""
        return cls._handlers.get(source_name)

    @classmethod
    def get_all_handlers(cls) -> Dict[str, BaseSignalHandler]:
        """Get all registered handlers."""
        return cls._handlers.copy()

    @classmethod
    def fetch_all_signals(
        cls,
        sku: str = None,
        location: str = None,
        sources: List[str] = None,
        **kwargs
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch signals from all or specified sources."""
        results = {}

        handlers_to_use = cls._handlers
        if sources:
            handlers_to_use = {k: v for k, v in cls._handlers.items() if k in sources}

        for name, handler in handlers_to_use.items():
            try:
                signals = handler.fetch_signals(sku=sku, location=location, **kwargs)
                if signals:
                    results[name] = signals
            except Exception as e:
                logger.error(f"Error fetching signals from {name}: {e}")

        return results

    @classmethod
    def transform_to_graph_facts(cls, signals: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Transform all signals to graph facts."""
        facts = []

        for source_name, source_signals in signals.items():
            handler = cls.get_handler(source_name)
            if handler:
                facts.extend(handler.transform_to_graph_facts(source_signals))

        return facts


# Register default handlers
SignalHandlerRegistry.register(POSSignalHandler())
SignalHandlerRegistry.register(WeatherSignalHandler())
SignalHandlerRegistry.register(InventorySignalHandler())
SignalHandlerRegistry.register(PromotionSignalHandler())
SignalHandlerRegistry.register(EventSignalHandler())
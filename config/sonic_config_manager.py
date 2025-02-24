#!/usr/bin/env python
import json
import os
import logging
from typing import Any, Dict
from contextlib import contextmanager

logger = logging.getLogger("SonicConfigManager")

def deep_merge(source: Dict[Any, Any], updates: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Recursively merge updates into the source dictionary.
    """
    for key, value in updates.items():
        if key in source and isinstance(source[key], dict) and isinstance(value, dict):
            logger.debug("Deep merging key: %s", key)
            source[key] = deep_merge(source[key], value)
        else:
            logger.debug("Updating key: %s with value: %s", key, value)
            source[key] = value
    return source

@contextmanager
def file_lock(lock_path: str):
    """
    A simple file lock context manager.
    """
    while os.path.exists(lock_path):
        pass  # Wait until lock is released
    try:
        # Create a lock file
        with open(lock_path, "w") as lock_file:
            lock_file.write("lock")
        yield
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)

class SonicConfigManager:
    def __init__(self, config_path: str, lock_path: str = "sonic_config.lock"):
        self.config_path = config_path
        self.lock_path = lock_path

    def load_config(self) -> Dict[str, Any]:
        """
        Load the JSON configuration from file.
        """
        if not os.path.exists(self.config_path):
            logger.error("Configuration file not found: %s", self.config_path)
            raise FileNotFoundError("Configuration file not found")
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.debug("Loaded config from %s: %s", self.config_path, config)
            return config
        except json.JSONDecodeError as e:
            logger.error("Error decoding JSON from %s: %s", self.config_path, e)
            raise e

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save the JSON configuration to file with flush and fsync for safety.
        """
        try:
            with file_lock(self.lock_path):
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
            logger.info("Configuration saved to %s", self.config_path)
            # Verify by reloading the file immediately
            with open(self.config_path, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            logger.debug("Verified saved config: %s", saved_config)
        except Exception as e:
            logger.error("Error saving configuration to %s: %s", self.config_path, e)
            raise e

    def get_alert_config(self) -> Dict[str, Any]:
        """
        Retrieve the 'alert_ranges' section from the configuration.
        """
        config = self.load_config()
        return config.get("alert_ranges", {})

    def update_alert_config(self, new_alerts: Dict[str, Any]) -> None:
        """
        Merge new alert settings into the existing 'alert_ranges' configuration
        and save the updated configuration.
        """
        config = self.load_config()
        existing_alerts = config.get("alert_ranges", {})
        logger.debug("Existing alert config: %s", existing_alerts)
        merged_alerts = deep_merge(existing_alerts, new_alerts)
        logger.debug("Merged alert config: %s", merged_alerts)
        config["alert_ranges"] = merged_alerts
        self.save_config(config)
        logger.info("Alert configuration updated successfully.")

    def validate_alert_config(self, alerts: Dict[str, Any]) -> bool:
        """
        Basic validation to ensure each metric contains required keys.
        Extend this function with your custom validation rules as needed.
        """
        required_keys = ["low", "medium", "high"]
        for metric, settings in alerts.items():
            for key in required_keys:
                if key not in settings:
                    logger.error("Missing key '%s' in metric '%s'", key, metric)
                    return False
        return True

    def format_alert_config(self) -> str:
        """
        Returns a formatted HTML table representing the alert_ranges configuration.
        """
        config = self.load_config()
        alert_ranges = config.get("alert_ranges", {})
        # Build a simple HTML table
        html = "<table border='1' style='border-collapse: collapse; width:100%;'>"
        html += "<tr><th>Metric</th><th>Enabled</th><th>Low</th><th>Medium</th><th>High</th></tr>"
        for metric, settings in alert_ranges.items():
            enabled = settings.get("enabled", False)
            low = settings.get("low", "")
            medium = settings.get("medium", "")
            high = settings.get("high", "")
            html += f"<tr><td>{metric}</td><td>{enabled}</td><td>{low}</td><td>{medium}</td><td>{high}</td></tr>"
        html += "</table>"
        return html

# Example usage:
if __name__ == "__main__":
    CONFIG_PATH = "/mnt/data/sonic_config.json"  # Confirm this is the file you're checking
    config_mgr = SonicConfigManager(CONFIG_PATH)

    # Print current alert configuration
    alerts_config = config_mgr.get_alert_config()
    print("Current alert config:", alerts_config)

    # Example update: merge new values into 'heat_index_ranges'
    new_alerts = {
        "heat_index_ranges": {
            "enabled": True,
            "low": 400.0,
            "medium": 500.0,
            "high": 600.0,
            "low_notifications": {"call": True, "sms": False, "email": True},
            "medium_notifications": {"call": False, "sms": True, "email": True},
            "high_notifications": {"call": True, "sms": True, "email": True}
        }
    }

    if config_mgr.validate_alert_config(new_alerts.get("heat_index_ranges", {})):
        config_mgr.update_alert_config(new_alerts)
        print("Alert configuration merged and updated successfully!")
        formatted = config_mgr.format_alert_config()
        print("Formatted Alert Config:")
        print(formatted)
    else:
        print("Validation failed. Please check your new alert configuration.")

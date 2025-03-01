import json
import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger("UnifiedConfigManager")

def deep_merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge overrides into base.
    If both base[key] and overrides[key] are dicts, merge them.
    Otherwise, overrides[key] takes precedence.
    """
    merged = dict(base)
    for key, val in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = deep_merge_dicts(merged[key], val)
        else:
            merged[key] = val
    return merged

@contextmanager
def file_lock(lock_path: str):
    """
    A simple file lock context manager.
    Waits until the lock file is absent, then creates it.
    """
    while os.path.exists(lock_path):
        pass  # Busy-wait (for production, consider a more robust solution)
    try:
        with open(lock_path, "w") as f:
            f.write("lock")
        yield
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)

class UnifiedConfigManager:
    def __init__(self, config_path: str, lock_path: str = "sonic_config.lock", db_conn: Optional[Any] = None):
        """
        Initialize with the path to the JSON configuration file,
        an optional lock file path, and an optional database connection.
        """
        self.config_path = config_path
        self.lock_path = lock_path
        self.db_conn = db_conn

    def load_json_config(self) -> Dict[str, Any]:
        """Loads the base configuration from a JSON file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.debug("Loaded config from %s: %s", self.config_path, config)
            return config
        except FileNotFoundError:
            logger.warning("Config file not found: %s. Returning empty dict.", self.config_path)
            return {}
        except json.JSONDecodeError as e:
            logger.error("Error decoding JSON in %s: %s", self.config_path, e)
            return {}

    def load_overrides_from_db(self) -> Dict[str, Any]:
        """Loads configuration overrides from the database, if available."""
        if not self.db_conn:
            return {}
        try:
            # Ensure the overrides table exists.
            self.db_conn.execute("""
                CREATE TABLE IF NOT EXISTS config_overrides (
                    id INTEGER PRIMARY KEY,
                    overrides TEXT
                )
            """)
            self.db_conn.execute("""
                INSERT OR IGNORE INTO config_overrides (id, overrides) VALUES (1, '{}')
            """)
            self.db_conn.commit()
            row = self.db_conn.execute("SELECT overrides FROM config_overrides WHERE id=1").fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return {}
        except Exception as e:
            logger.error("Error loading overrides from DB: %s", e)
            return {}

    def load_config(self) -> Dict[str, Any]:
        """
        Loads the configuration by merging the base JSON config with any DB overrides.
        DB values take precedence.
        """
        base_config = self.load_json_config()
        db_overrides = self.load_overrides_from_db() if self.db_conn else {}
        merged_config = deep_merge_dicts(base_config, db_overrides)
        return merged_config

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Saves the configuration dictionary to the JSON file using a file lock.
        """
        try:
            with file_lock(self.lock_path):
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
            logger.info("Configuration saved to %s", self.config_path)
        except Exception as e:
            logger.error("Error saving config to %s: %s", self.config_path, e)
            raise

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the configuration by deep merging new values into the current configuration,
        then saves and returns the updated configuration.
        """
        current_config = self.load_config()
        updated_config = deep_merge_dicts(current_config, new_config)
        self.save_config(updated_config)
        logger.debug("Configuration updated and saved to %s", self.config_path)
        return updated_config

    def get_alert_config(self) -> Dict[str, Any]:
        """Returns the 'alert_ranges' section of the configuration."""
        config = self.load_config()
        return config.get("alert_ranges", {})

    def update_alert_config(self, new_alerts: Dict[str, Any]) -> None:
        """
        Merges new alert configuration values into the existing 'alert_ranges' section and saves it.
        """
        config = self.load_config()
        existing_alerts = config.get("alert_ranges", {})
        merged_alerts = deep_merge_dicts(existing_alerts, new_alerts)
        config["alert_ranges"] = merged_alerts
        self.save_config(config)
        logger.info("Alert configuration updated successfully.")

    def validate_alert_config(self, alerts: Dict[str, Any]) -> bool:
        """
        Validates that each alert metric includes required keys.
        Extend this method as needed.
        """
        required_keys = ["low", "medium", "high"]
        for metric, settings in alerts.items():
            for key in required_keys:
                if key not in settings:
                    logger.error("Missing key '%s' in metric '%s'", key, metric)
                    return False
        return True

# Example usage:
if __name__ == "__main__":
    CONFIG_PATH = "sonic_config.json"  # Adjust as necessary
    config_manager = UnifiedConfigManager(CONFIG_PATH)
    
    # Load and print the merged configuration
    config = config_manager.load_config()
    logger.info("Unified config: %s", config)
    
    # Example: Update alert configuration
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
    
    if config_manager.validate_alert_config(new_alerts.get("heat_index_ranges", {})):
        config_manager.update_alert_config(new_alerts)
        logger.info("Alert configuration updated successfully!")
    else:
        logger.error("Alert configuration validation failed.")
import json
import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger("UnifiedConfigManager")

def deep_merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge overrides into base.
    If both base[key] and overrides[key] are dicts, merge them.
    Otherwise, overrides[key] takes precedence.
    """
    merged = dict(base)
    for key, val in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = deep_merge_dicts(merged[key], val)
        else:
            merged[key] = val
    return merged

@contextmanager
def file_lock(lock_path: str):
    """
    A simple file lock context manager.
    Waits until the lock file is absent, then creates it.
    """
    while os.path.exists(lock_path):
        pass  # Busy-wait (for production, consider a more robust solution)
    try:
        with open(lock_path, "w") as f:
            f.write("lock")
        yield
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)

class UnifiedConfigManager:
    def __init__(self, config_path: str, lock_path: str = "sonic_config.lock", db_conn: Optional[Any] = None):
        """
        Initialize with the path to the JSON configuration file,
        an optional lock file path, and an optional database connection.
        """
        self.config_path = config_path
        self.lock_path = lock_path
        self.db_conn = db_conn

    def load_json_config(self) -> Dict[str, Any]:
        """Loads the base configuration from a JSON file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.debug("Loaded config from %s: %s", self.config_path, config)
            return config
        except FileNotFoundError:
            logger.warning("Config file not found: %s. Returning empty dict.", self.config_path)
            return {}
        except json.JSONDecodeError as e:
            logger.error("Error decoding JSON in %s: %s", self.config_path, e)
            return {}

    def load_overrides_from_db(self) -> Dict[str, Any]:
        """Loads configuration overrides from the database, if available."""
        if not self.db_conn:
            return {}
        try:
            # Ensure the overrides table exists.
            self.db_conn.execute("""
                CREATE TABLE IF NOT EXISTS config_overrides (
                    id INTEGER PRIMARY KEY,
                    overrides TEXT
                )
            """)
            self.db_conn.execute("""
                INSERT OR IGNORE INTO config_overrides (id, overrides) VALUES (1, '{}')
            """)
            self.db_conn.commit()
            row = self.db_conn.execute("SELECT overrides FROM config_overrides WHERE id=1").fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return {}
        except Exception as e:
            logger.error("Error loading overrides from DB: %s", e)
            return {}

    def load_config(self) -> Dict[str, Any]:
        """
        Loads the configuration by merging the base JSON config with any DB overrides.
        DB values take precedence.
        """
        base_config = self.load_json_config()
        db_overrides = self.load_overrides_from_db() if self.db_conn else {}
        merged_config = deep_merge_dicts(base_config, db_overrides)
        return merged_config

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Saves the configuration dictionary to the JSON file using a file lock.
        """
        try:
            with file_lock(self.lock_path):
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
            logger.info("Configuration saved to %s", self.config_path)
        except Exception as e:
            logger.error("Error saving config to %s: %s", self.config_path, e)
            raise

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the configuration by deep merging new values into the current configuration,
        then saves and returns the updated configuration.
        """
        current_config = self.load_config()
        updated_config = deep_merge_dicts(current_config, new_config)
        self.save_config(updated_config)
        logger.debug("Configuration updated and saved to %s", self.config_path)
        return updated_config

    def get_alert_config(self) -> Dict[str, Any]:
        """Returns the 'alert_ranges' section of the configuration."""
        config = self.load_config()
        return config.get("alert_ranges", {})

    def update_alert_config(self, new_alerts: Dict[str, Any]) -> None:
        """
        Merges new alert configuration values into the existing 'alert_ranges' section and saves it.
        """
        config = self.load_config()
        existing_alerts = config.get("alert_ranges", {})
        merged_alerts = deep_merge_dicts(existing_alerts, new_alerts)
        config["alert_ranges"] = merged_alerts
        self.save_config(config)
        logger.info("Alert configuration updated successfully.")

    def validate_alert_config(self, alerts: Dict[str, Any]) -> bool:
        """
        Validates that each alert metric includes required keys.
        Extend this method as needed.
        """
        required_keys = ["low", "medium", "high"]
        for metric, settings in alerts.items():
            for key in required_keys:
                if key not in settings:
                    logger.error("Missing key '%s' in metric '%s'", key, metric)
                    return False
        return True

# Example usage:
if __name__ == "__main__":
    CONFIG_PATH = "sonic_config.json"  # Adjust as necessary
    config_manager = UnifiedConfigManager(CONFIG_PATH)
    
    # Load and print the merged configuration
    config = config_manager.load_config()
    logger.info("Unified config: %s", config)
    
    # Example: Update alert configuration
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
    
    if config_manager.validate_alert_config(new_alerts.get("heat_index_ranges", {})):
        config_manager.update_alert_config(new_alerts)
        logger.info("Alert configuration updated successfully!")
    else:
        logger.error("Alert configuration validation failed.")

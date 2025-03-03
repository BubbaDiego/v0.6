#!/usr/bin/env python
import os
import time
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from twilio.rest import Client
from config.unified_config_manager import UnifiedConfigManager
from config.config_constants import DB_PATH, CONFIG_PATH
from pathlib import Path
from utils.operations_manager import OperationsLogger

# Minimal Logging Configuration
logger = logging.getLogger("AlertManagerLogger")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler("alert_manager_log.txt")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


def trigger_twilio_flow(custom_message: str, twilio_config: dict) -> str:
    account_sid = twilio_config.get("account_sid")
    auth_token = twilio_config.get("auth_token")
    flow_sid = twilio_config.get("flow_sid")
    to_phone = twilio_config.get("to_phone")
    from_phone = twilio_config.get("from_phone")
    if not all([account_sid, auth_token, flow_sid, to_phone, from_phone]):
        raise ValueError("Missing Twilio configuration variables.")

    client = Client(account_sid, auth_token)
    execution = client.studio.v2.flows(flow_sid).executions.create(
        to=to_phone,
        from_=from_phone,
        parameters={"custom_message": custom_message}
    )
    logger.info("Twilio alert sent.")
    return execution.sid


METRIC_DIRECTIONS = {
    "size": "increasing_bad",
}


def get_alert_class(value: float, low_thresh: float, med_thresh: float, high_thresh: float, metric: str) -> str:
    direction = METRIC_DIRECTIONS.get(metric, "increasing_bad")
    if direction == "increasing_bad":
        if value < low_thresh:
            return "alert-low"
        elif value < med_thresh:
            return "alert-medium"
        else:
            return "alert-high"
    elif direction == "decreasing_bad":
        if value > low_thresh:
            return "alert-low"
        elif value > med_thresh:
            return "alert-medium"
        else:
            return "alert-high"
    else:
        return "alert-low"


class AlertManager:
    ASSET_FULL_NAMES = {
        "BTC": "Bitcoin",
        "ETH": "Ethereum",
        "SOL": "Solana"
    }

    def __init__(self, db_path: str = str(DB_PATH), poll_interval: int = 60, config_path: str = str(CONFIG_PATH)):
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.config_path = config_path
        self.last_profit: Dict[str, str] = {}
        self.last_triggered: Dict[str, float] = {}
        self.last_call_triggered: Dict[str, float] = {}

        from data.data_locker import DataLocker
        from utils.calc_services import CalcServices

        self.data_locker = DataLocker(self.db_path)
        self.calc_services = CalcServices()

        db_conn = self.data_locker.get_db_connection()
        config_manager = UnifiedConfigManager(self.config_path, db_conn=db_conn)
        self.config = config_manager.load_config()

        self.twilio_config = self.config.get("twilio_config", {})
        self.cooldown = self.config.get("alert_cooldown_seconds", 900)
        self.call_refractory_period = self.config.get("call_refractory_period", 3600)
        self.monitor_enabled = self.config.get("system_config", {}).get("alert_monitor_enabled", True)

        logger.info("AlertManager initialized.")

    def reload_config(self):
        from config.config_manager import load_config
        db_conn = self.data_locker.get_db_connection()
        try:
            self.config = load_config(self.config_path, db_conn)
            self.cooldown = self.config.get("alert_cooldown_seconds", 900)
            self.call_refractory_period = self.config.get("call_refractory_period", 3600)
            logger.info("Alert configuration reloaded.")
            op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))
            op_logger.log("Alerts configuration reloaded successfully", source="AlertManager", operation_type="Alerts Configuration Successful")
        except Exception as e:
            logger.error("Failed to reload alert configuration: %s", e)
            op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))
            op_logger.log("Alert configuration reload failed", source="AlertManager", operation_type="Alert Configuration Failed")

    def run(self):
        logger.info("Starting alert monitoring loop.")
        while True:
            self.check_alerts()
            time.sleep(self.poll_interval)

    def check_alerts(self, source: Optional[str] = None):
        if not self.monitor_enabled:
            logger.info("Alert monitoring disabled.")
            return

        aggregated_alerts: List[str] = []
        positions = self.data_locker.read_positions()
        logger.info("Checking %d positions for alerts.", len(positions))

        for pos in positions:
            profit_alert = self.check_profit(pos)
            if profit_alert:
                aggregated_alerts.append(profit_alert)
            travel_alert = self.check_travel_percent_liquid(pos)
            if travel_alert:
                aggregated_alerts.append(travel_alert)
            swing_alert = self.check_swing_alert(pos)
            if swing_alert:
                aggregated_alerts.append(swing_alert)
            blast_alert = self.check_blast_alert(pos)
            if blast_alert:
                aggregated_alerts.append(blast_alert)
        price_alerts = self.check_price_alerts()
        aggregated_alerts.extend(price_alerts)

        from utils.operations_manager import OperationsLogger
        op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))

        if aggregated_alerts:
            op_message = f"{len(aggregated_alerts)} alerts triggered"
            op_logger.log(op_message, source=source, operation_type="Alert Triggered")
        else:
            op_message = "✅ No alerts found"
            op_logger.log(op_message, source=source, operation_type="No Alerts Found")

    def check_travel_percent_liquid(self, pos: Dict[str, Any]) -> str:
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"

        try:
            current_val = float(pos.get("current_travel_percent", 0.0))
        except Exception as e:
            logger.error("%s %s (ID: %s): Error converting travel percent.", asset_full, position_type, position_id)
            print(f"[ERROR] {asset_full} {position_type} (ID: {position_id}): Error converting travel percent: {e}")
            return ""

        logger.debug("Checking travel percent for %s %s (ID: %s): current_travel_percent = %s",
                     asset_full, position_type, position_id, current_val)
        print(f"[DEBUG] Checking travel percent for {asset_full} {position_type} (ID: {position_id}): current_travel_percent = {current_val}")

        if current_val >= 0:
            logger.debug("%s %s (ID: %s): Travel percent is non-negative (%s), no alert needed.",
                         asset_full, position_type, position_id, current_val)
            print(f"[DEBUG] {asset_full} {position_type} (ID: {position_id}): Travel percent is non-negative ({current_val}), no alert needed.")
            return ""

        tpli_config = self.config.get("alert_ranges", {}).get("travel_percent_liquid_ranges", {})
        print(f"[DEBUG] Loaded travel_percent_liquid_ranges config: {tpli_config}")

        if not tpli_config.get("enabled", True):
            logger.debug("Travel percent alert not enabled in config for %s %s (ID: %s).",
                         asset_full, position_type, position_id)
            print(f"[DEBUG] Travel percent alert not enabled in config for {asset_full} {position_type} (ID: {position_id}).")
            return ""

        def parse_threshold(value, default):
            return float(value) if value not in (None, "") else default

        try:
            low = parse_threshold(tpli_config.get("low"), -25.0)
            medium = parse_threshold(tpli_config.get("medium"), -50.0)
            high = parse_threshold(tpli_config.get("high"), -75.0)
        except Exception as e:
            logger.error("%s %s (ID: %s): Error parsing travel percent thresholds.", asset_full, position_type, position_id)
            print(f"[ERROR] {asset_full} {position_type} (ID: {position_id}): Error parsing travel percent thresholds: {e}")
            return ""

        logger.debug(
            "[Travel Percent Alert Debug] %s %s (ID: %s): Actual Travel%% = %.2f, Thresholds - Low: %.2f, Medium: %.2f, High: %.2f",
            asset_full, position_type, position_id, current_val, low, medium, high
        )
        print(f"[DEBUG] [Travel Percent Alert Debug] {asset_full} {position_type} (ID: {position_id}): Actual Travel% = {current_val:.2f}, Thresholds - Low: {low:.2f}, Medium: {medium:.2f}, High: {high:.2f}")

        alert_level = ""
        if current_val <= high:
            alert_level = "HIGH"
        elif current_val <= medium:
            alert_level = "MEDIUM"
        elif current_val <= low:
            alert_level = "LOW"
        else:
            logger.debug("%s %s (ID: %s): No travel percent alert level triggered.", asset_full, position_type, position_id)
            print(f"[DEBUG] {asset_full} {position_type} (ID: {position_id}): No travel percent alert level triggered.")
            return ""

        key = f"{asset_full}-{position_type}-{position_id}-travel-{alert_level}"
        now = time.time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            logger.debug("%s %s (ID: %s): Alert for key '%s' suppressed due to cooldown.", asset_full, position_type, position_id, key)
            print(f"[DEBUG] {asset_full} {position_type} (ID: {position_id}): Alert for key '{key}' suppressed due to cooldown.")
            return ""
        self.last_triggered[key] = now
        wallet_name = pos.get("wallet_name", "Unknown")
        msg = f"Travel Percent Liquid ALERT: {asset_full} {position_type} (Wallet: {wallet_name}) - Travel% = {current_val:.2f}%, Level = {alert_level}"
        logger.debug("Triggered travel percent alert: %s", msg)
        print(f"[DEBUG] Triggered travel percent alert: {msg}")
        return msg

    def check_swing_alert(self, pos: Dict[str, Any]) -> str:
        asset = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset, asset)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            current_value = float(pos.get("liquidation_distance", 0.0))
        except Exception:
            logger.error("%s %s (ID: %s): Error converting liquidation distance.", asset_full, position_type, position_id)
            return ""
        hardcoded_swing_thresholds = {"BTC": 6.24, "ETH": 8.0, "SOL": 13.0}
        swing_threshold = hardcoded_swing_thresholds.get(asset, 0)
        logger.debug(
            f"[Swing Alert Debug] {asset_full} {position_type} (ID: {position_id}): Actual Value = {current_value:.2f} vs Hardcoded Swing Threshold = {swing_threshold:.2f}"
        )
        if current_value >= swing_threshold:
            key = f"swing-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (f"Average Daily Swing ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                        f"Actual Value = {current_value:.2f} exceeds Hardcoded Swing Threshold of {swing_threshold:.2f}")
        return ""

    def check_blast_alert(self, pos: Dict[str, Any]) -> str:
        asset = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset, asset)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        try:
            current_value = float(pos.get("liquidation_distance", 0.0))
        except Exception:
            logger.error("%s %s (ID: %s): Error converting liquidation distance.", asset_full, position_type, position_id)
            return ""
        try:
            blast_threshold = 11.2
        except Exception as e:
            logger.error("Error parsing blast threshold for %s: %s", asset_full, e)
            return ""
        logger.debug(
            f"[Blast Alert Debug] {asset_full} {position_type} (ID: {position_id}): Actual Value = {current_value:.2f} vs Blast Threshold = {blast_threshold:.2f}"
        )
        if current_value >= blast_threshold:
            key = f"blast-{asset_full}-{position_type}-{position_id}"
            now = time.time()
            last_time = self.last_triggered.get(key, 0)
            if now - last_time >= self.cooldown:
                self.last_triggered[key] = now
                return (f"One Day Blast Radius ALERT: {asset_full} {position_type} (ID: {position_id}) - "
                        f"Actual Value = {current_value:.2f} exceeds Blast Threshold of {blast_threshold:.2f}")
        return ""

    def check_profit(self, pos: Dict[str, Any]) -> str:
        asset_code = pos.get("asset_type", "???").upper()
        asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
        position_type = pos.get("position_type", "").capitalize()
        position_id = pos.get("position_id") or pos.get("id") or "unknown"
        raw_profit = pos.get("profit")
        try:
            profit_val = float(raw_profit) if raw_profit is not None else 0.0
        except Exception:
            logger.error("%s %s (ID: %s): Error converting profit.", asset_full, position_type, position_id)
            return ""
        if profit_val <= 0:
            return ""
        profit_config = self.config.get("alert_ranges", {}).get("profit_ranges", {})
        if not profit_config.get("enabled", False):
            return ""
        try:
            low_thresh = float(profit_config.get("low", 25))
            med_thresh = float(profit_config.get("medium", 50))
            high_thresh = float(profit_config.get("high", 75))
        except Exception:
            logger.error("%s %s (ID: %s): Error parsing profit thresholds.", asset_full, position_type, position_id)
            return ""
        logger.debug(
            f"[Profit Alert Debug] {asset_full} {position_type} (ID: {position_id}): Profit = {profit_val:.2f}, Thresholds: Low = {low_thresh:.2f}, Medium = {med_thresh:.2f}, High = {high_thresh:.2f}"
        )
        if profit_val < low_thresh:
            return ""
        elif profit_val < med_thresh:
            current_level = "low"
        elif profit_val < high_thresh:
            current_level = "medium"
        else:
            current_level = "high"
        profit_key = f"profit-{asset_full}-{position_type}-{position_id}"
        last_level = self.last_profit.get(profit_key, "none")
        level_order = {"none": 0, "low": 1, "medium": 2, "high": 3}
        if level_order[current_level] <= level_order.get(last_level, 0):
            self.last_profit[profit_key] = current_level
            return ""
        now = time.time()
        last_time = self.last_triggered.get(profit_key, 0)
        if now - last_time < self.cooldown:
            self.last_profit[profit_key] = current_level
            return ""
        self.last_triggered[profit_key] = now
        msg = f"Profit ALERT: {asset_full} {position_type} profit of {profit_val:.2f} (Level: {current_level.upper()})"
        self.last_profit[profit_key] = current_level
        return msg

    def check_price_alerts(self) -> List[str]:
        alerts = self.data_locker.get_alerts()
        messages: List[str] = []
        price_alerts = [a for a in alerts if a.get("alert_type") == "PRICE_THRESHOLD" and a.get("status", "").lower() == "active"]
        logger.info("Found %d active price alerts.", len(price_alerts))
        for alert in price_alerts:
            asset_code = alert.get("asset_type", "BTC").upper()
            asset_full = self.ASSET_FULL_NAMES.get(asset_code, asset_code)
            position_id = alert.get("position_id") or alert.get("id") or "unknown"
            try:
                trigger_val = float(alert.get("trigger_value", 0.0))
            except Exception:
                trigger_val = 0.0
            condition = alert.get("condition", "ABOVE").upper()
            price_info = self.data_locker.get_latest_price(asset_code)
            if not price_info:
                continue
            current_price = float(price_info.get("current_price", 0.0))
            logger.debug(
                f"[Price Alert Debug] {asset_full}: Condition = {condition}, Trigger Value = {trigger_val:.2f}, Current Price = {current_price:.2f}"
            )
            if (condition == "ABOVE" and current_price >= trigger_val) or (condition != "ABOVE" and current_price <= trigger_val):
                msg = self.handle_price_alert_trigger(alert, current_price, asset_full)
                if msg:
                    messages.append(msg)
        return messages

    def handle_price_alert_trigger(self, alert: dict, current_price: float, asset_full: str) -> str:
        position_id = alert.get("position_id") or alert.get("id") or "unknown"
        key = f"price-alert-{asset_full}-{position_id}"
        now = time.time()
        last_time = self.last_triggered.get(key, 0)
        if now - last_time < self.cooldown:
            logger.info("%s: Price alert suppressed.", asset_full)
            return ""
        self.last_triggered[key] = now
        cond = alert.get("condition", "ABOVE").upper()
        try:
            trig_val = float(alert.get("trigger_value", 0.0))
        except Exception:
            trig_val = 0.0
        position_type = alert.get("position_type", "").capitalize()
        wallet_name = alert.get("wallet_name", "Unknown")
        msg = f"Price ALERT: {asset_full} {position_type}"
        if wallet_name != "Unknown":
            msg += f", Wallet: {wallet_name}"
        msg += f" - Condition: {cond}, Trigger: {trig_val}, Current: {current_price}"
        return msg

    def send_call(self, body: str, key: str):
        from utils.operations_manager import OperationsLogger
        op_logger = OperationsLogger(log_filename=os.path.join(os.getcwd(), "operations_log.txt"))
        now = time.time()
        last_call_time = self.last_call_triggered.get(key, 0)
        if now - last_call_time < self.call_refractory_period:
            logger.info("Call alert '%s' suppressed.", key)
            op_logger.log(f"Alert Silenced: {key}", source="AlertManager", operation_type="Alert Silenced")
            return
        try:
            trigger_twilio_flow(body, self.twilio_config)
            self.last_call_triggered[key] = now
            op_logger.log(f"Notification Sent: {key}", source="AlertManager", operation_type="Notification Sent")
        except Exception as e:
            op_logger.log(f"Notification Failed: {key}", source="AlertManager", operation_type="Notification Failed")
            logger.error("Error sending call for '%s'.", key, exc_info=True)

    def load_json_config(self, json_path: str) -> dict:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self, config: dict, json_path: str):
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

# Create a global AlertManager instance for use in other modules.
manager = AlertManager(
    db_path=str(DB_PATH),
    poll_interval=60,
    config_path=str(CONFIG_PATH)
)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    manager.run()

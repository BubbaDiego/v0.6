#!/usr/bin/env python
import os
import sys
import json
import logging
import pytz
from datetime import datetime
import re
from fuzzywuzzy import fuzz

###############################################################################
# OPERATION CONFIG: Operation type -> icon & color (used by the viewer only)
###############################################################################
OPERATION_CONFIG = {
    "Launch pad started": {
        "icon": "🚀",
        "color": "blue"
    },
    "Update Jupiter": {
        "icon": "🔄",
        "color": "green"
    },
    "Alert Triggered": {
        "icon": "🚨",
        "color": "red"
    },
    "Alert Silenced": {
        "icon": "🔕",
        "color": "yellow"
    },
    "Notification Sent": {
        "icon": "📱",
        "color": "blue"
    },
    "Notification Fail": {
        "icon": "💀",
        "color": "blue"
    }

    # Add more operation types here if you like
}

def fuzzy_find_op_type(op_type: str, config_keys) -> str:
    """
    Fuzzy find the best matching operation_type key from config_keys
    Returns the best match if it's above a certain threshold, else returns None.
    """
    # Normalize: remove non-alphanumeric, lowercase
    def normalize(s):
        return re.sub(r'[^a-z0-9]+', '', s.lower())

    op_norm = normalize(op_type)
    best_key = None
    best_score = 0
    for k in config_keys:
        k_norm = normalize(k)
        score = fuzz.ratio(op_norm, k_norm)  # fuzzy ratio
        if score > best_score:
            best_score = score
            best_key = k
    # Use a threshold (e.g., 60 or 70) to ensure we only match if it's decently close
    if best_score >= 60:
        return best_key
    return None


###############################################################################
# OPERATIONS LOGGER
###############################################################################
class OperationsLogger:
    def __init__(self, log_filename: str = None):
        if log_filename is None:
            log_filename = os.path.join(os.getcwd(), "operations_log.txt")
        self.log_filename = log_filename
        print("Reading log file from:", os.path.abspath(log_filename))

        # Create a logger with a fixed name.
        self.logger = logging.getLogger("OperationsLogger")
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers.
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)

        # FileHandler with UTF-8 encoding; we output only the message (which is our JSON string).
        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(file_handler)

        # Set timezone for PST.
        self.pst = pytz.timezone("US/Pacific")

    def log(self, message: str, source: str = None, operation_type: str = None):
        now = datetime.now(self.pst)
        if sys.platform.startswith('win'):
            time_str = now.strftime("%#m-%#d-%y : %#I:%M:%S %p")
        else:
            time_str = now.strftime("%-m-%-d-%y : %-I:%M:%S %p")
        record = {
            "message": message,
            "source": source or "",
            "operation_type": operation_type or "",
            "timestamp": time_str
        }
        self.logger.info(json.dumps(record, ensure_ascii=False))


###############################################################################
# OPERATIONS VIEWER
###############################################################################
class OperationsViewer:
    """
    Reads each JSON line from operations_log.txt, then injects icons and colors
    at display time. The 'operation_type' field tells us which icon and color to use.
    """
    def __init__(self, log_filename: str):
        self.log_filename = log_filename
        self.entries = []
        with open(log_filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self.entries.append(record)
                except json.JSONDecodeError:
                    # Skip any malformed lines.
                    pass

    def fuzzy_find_op_type(op_type: str, config_keys) -> str:
        """
        Fuzzy find the best matching operation_type key from config_keys
        Returns the best match if it's above a certain threshold, else returns None.
        """

        # Normalize: remove non-alphanumeric, lowercase
        def normalize(s):
            return re.sub(r'[^a-z0-9]+', '', s.lower())

        op_norm = normalize(op_type)
        best_key = None
        best_score = 0
        for k in config_keys:
            k_norm = normalize(k)
            score = fuzz.ratio(op_norm, k_norm)  # fuzzy ratio
            if score > best_score:
                best_score = score
                best_key = k
        # Use a threshold (e.g., 60 or 70) to ensure we only match if it's decently close
        if best_score >= 60:
            return best_key
        return None

    def get_display_string(self, record: dict) -> str:
        from fuzzywuzzy import fuzz  # or put this import at the top
        op_type = record.get("operation_type", "")
        # Attempt a fuzzy match in OPERATION_CONFIG keys
        best_key = fuzzy_find_op_type(op_type, OPERATION_CONFIG.keys())
        if best_key:
            config = OPERATION_CONFIG[best_key]
        else:
            config = {}

        icon = config.get("icon", "")
        color = config.get("color", "")

        # Map color to a Bootstrap alert class
        alert_class = "alert-secondary"
        if color.lower() == "red":
            alert_class = "alert-danger"
        elif color.lower() == "blue":
            alert_class = "alert-primary"
        elif color.lower() == "green":
            alert_class = "alert-success"
        elif color.lower() == "yellow":
            alert_class = "alert-warning"

        # Build the line content
        message = record.get("message", "")
        source = record.get("source", "")
        timestamp = record.get("timestamp", "")
        line = f"{icon} {message}"
        if source:
            line += f" | Source: {source} - <b>{timestamp}</b>"
        else:
            line += f" | <b>{timestamp}</b>"

        # Minimal internal padding, no bottom margin
        return f'<div class="alert {alert_class} p-1 mb-0" role="alert">{line}</div>'

    def get_all_display_strings(self) -> str:
        display_list = [self.get_display_string(e) for e in self.entries]
        # Reverse the list so that the most recent entries appear first
        return "<br>".join(display_list[::-1])


###############################################################################
# Example Usage (Run this file directly to test logging and viewing)
###############################################################################
if __name__ == "__main__":
    # Create logger and log some events (plain JSON lines, no icons/colors stored).
    op_logger = OperationsLogger()
    op_logger.log("Launch Pad - Started", source="System Start-up", operation_type="Launch pad started")
    op_logger.log("Jupiter Positions Updated", source="Monitor", operation_type="Update Jupiter")
    op_logger.log("Plain message with no operation type", source="NoIcon")

    # Now read them back with the viewer, which injects icons and color at display time.
    viewer = OperationsViewer(op_logger.log_filename)
    html_output = viewer.get_all_display_strings()
    print("----- HTML OUTPUT -----")
    print(html_output)
    print("-----------------------")

#!/usr/bin/env python
import os
import sys
import json
import logging
import pytz
from datetime import datetime
import re
#from fuzzywuzzy import fuzz

###############################################################################
# OPERATION CONFIG: Operation type -> icon & color (used by the viewer only)
###############################################################################
OPERATION_CONFIG = {
    "Launch pad started": {
        "icon": "🚀",
        "color": "blue"
    },
    "Jupiter Updated": {
        "icon": "🪐",
        "color": "blue"
    },
    "Alerts Configuration Successful": {
        "icon": "⚙✅",
        "color": "green"
    },
    "Alert Configuration Failed": {
        "icon": "⚙❌",
        "color": "red"
    },
    "Alert Triggered": {
        "icon": "🚨",
        "color": "red"
    },
    "Alert Silenced": {
        "icon": "🔕",
        "color": "yellow"
    },
    "Monitor Loop": {
        "icon": "🔁",
        "color": "blue"
    },
    "No Alerts Found": {
        "icon": "✅",
        "color": "green"
    },
    "Notification Sent": {
        "icon": "📱",
        "color": "blue"
    },
    "Notification Failed": {
        "icon": "💀",
        "color": "red"
    }
    # Add more operation types here if you like
}

###############################################################################
# SOURCE ICONS: Mapping of source names to Unicode icons.
###############################################################################
SOURCE_ICONS = {
    "user": "👤",
    "system": "💻",
    "system test": "⚙️✅",
    "sonic": "🦔",
    "monitor": "📺"
}
# Fallback if no source is provided:
DEFAULT_SOURCE_ICON = "❓"

def fuzzy_find_op_type(op_type: str, config_keys) -> str:
    """
    Fuzzy find the best matching operation_type key from config_keys.
    Returns the best match if it's above a certain threshold, else returns None.
    """
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

        # FileHandler with UTF-8 encoding; we output only the message (our JSON string).
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
    Reads each JSON line from operations_log.txt and renders log entries with:
      - An outer container with a white background.
      - Each log entry as a three-column flex row:
           • Left: A larger icon and bold primary message.
           • Center: A source icon (center-aligned).
           • Right: The date (regular) and time (bold), all aligned to the right.
      - The text color for the log entry is determined by its operation type.
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

    def get_line_color_class(self, color_name: str) -> str:
        color_map = {
            "red": "alert-danger",
            "blue": "alert-primary",
            "green": "alert-success",
            "yellow": "alert-warning"
        }
        return color_map.get(color_name.lower(), "alert-secondary")

    def get_display_string(self, record: dict) -> str:
        # Determine the operation type and use fuzzy matching to get the best key.
        op_type = record.get("operation_type", "")
        best_key = fuzzy_find_op_type(op_type, OPERATION_CONFIG.keys())
        config = OPERATION_CONFIG.get(best_key, {}) if best_key else {}
        icon = config.get("icon", "")
        # Make the icon a little smaller by wrapping it in a span with decreased font-size.
        icon_html = f'<span style="font-size: 1rem;">{icon}</span>'
        color_name = config.get("color", "secondary")
        line_color_class = self.get_line_color_class(color_name)

        # Get the primary message and make it bold.
        msg_text = record.get("message", "")
        msg_html = f"<strong>{msg_text}</strong>"

        # Determine the source icon.
        source_text = record.get("source", "")
        source_icon = SOURCE_ICONS.get(source_text.lower(), DEFAULT_SOURCE_ICON) if source_text else DEFAULT_SOURCE_ICON

        # Split timestamp into date and time parts.
        timestamp_str = record.get("timestamp", "")
        date_part, time_part = ("", "")
        if " : " in timestamp_str:
            date_part, time_part = timestamp_str.split(" : ", 1)
        else:
            date_part = timestamp_str

        # Build the HTML using a flex container with three columns.
        # Updated the margin and padding values to reduce the container height.
        line_html = f"""
    <div class="alert {line_color_class} d-flex align-items-center justify-content-between mb-1" 
         style="margin: 2px 0; padding: 3px; white-space: nowrap;">
      <!-- Left Column: Icon and Bold Message -->
      <div style="flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis;">
        {icon_html} {msg_html}
      </div>
      <!-- Center Column: Source Icon (center aligned) -->
      <div style="flex: 0 0 auto; margin: 0 16px; text-align: center; min-width: 30px;">
        <span style="font-size: 1rem;">{source_icon}</span>
      </div>
      <!-- Right Column: Date (regular) and Time (bold) -->
      <div style="flex: 0 0 auto; text-align: right; min-width: 120px;">
        <span style="font-weight: normal;">{date_part}</span>
        &nbsp;
        <span style="font-weight: bold;">{time_part}</span>
      </div>
    </div>
    """.strip()
        return line_html

    def get_all_display_strings(self) -> str:
        # Reverse the list so that the most recent entries appear first.
        display_list = [self.get_display_string(e) for e in self.entries[::-1]]
        # Wrap the entries in an outer container with a white background and a small padding.
        final_html = f"""
<div style="background-color: white; padding: 8px;">
  {''.join(display_list)}
</div>
""".strip()
        return final_html

###############################################################################
# Example Usage (Run this file directly to test logging and viewing)
###############################################################################
if __name__ == "__main__":
    # Create logger and log some events (plain JSON lines, no icons/colors stored).
    op_logger = OperationsLogger()
    op_logger.log("Launch Pad - Started", source="System Start-up", operation_type="Launch pad started")
    op_logger.log("Jupiter Positions Updated", source="Monitor", operation_type="Jupiter Updated")
    op_logger.log("No alerts found", source="Monitor")
    op_logger.log("Plain message with no operation type", source="NoIcon")

    # Now read them back with the viewer, which injects icons and colors at display time.
    viewer = OperationsViewer(op_logger.log_filename)
    html_output = viewer.get_all_display_strings()
    print("----- HTML OUTPUT -----")
    print(html_output)
    print("-----------------------")

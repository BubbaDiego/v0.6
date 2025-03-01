#!/usr/bin/env python
import os
import sys
import json
import logging
import pytz
from datetime import datetime

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
    # Add more operation types here if you like
}

###############################################################################
# OPERATIONS LOGGER
###############################################################################
class OperationsLogger:
    """
    Writes exactly ONE JSON line per log event:
      {
        "message": "Launch Pad - Started",
        "source": "System Start-up",
        "operation_type": "Launch pad started",
        "timestamp": "3-1-25 : 5:39:20 AM"
      }

    No icons, no color codes, no multiple lines are stored in the log file.
    """
    def __init__(self, filename: str = None):
        if filename is None:
            filename = os.path.join(os.getcwd(), "operations_log.txt")
        self.log_filename = filename

        # Create a logger with a fixed name.
        self.logger = logging.getLogger("OperationsLogger")
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers.
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)

        # FileHandler with UTF-8 encoding; we output only the message (which is our JSON string).
        file_handler = logging.FileHandler(filename, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(file_handler)

        # Use PST timezone.
        self.pst = pytz.timezone("US/Pacific")

    def log(self, message: str, source: str = None, operation_type: str = None):
        """
        Logs a single JSON line:
          { "message": "...", "source": "...", "operation_type": "...", "timestamp": "..." }
        Icons or color codes are not stored here.
        """
        now = datetime.now(self.pst)
        # Use appropriate formatting for Windows vs. Linux.
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
        # Dump as JSON (one line per event).
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

    def get_display_string(self, record: dict) -> str:
        """
        Converts a single record into a 2-line HTML snippet:
          1) Possibly colored icon + message
          2) "Source: <source> - <b><timestamp></b>"

        The icon and color are injected based on OPERATION_CONFIG using record["operation_type"].
        """
        op_type = record.get("operation_type", "")
        config = OPERATION_CONFIG.get(op_type, {})
        icon = config.get("icon", "")
        color = config.get("color", "")

        # Build the first line: if a color is specified, wrap the line in a span.
        if color:
            line1 = f'<span style="color:{color};">{icon} {record["message"]}</span>'
        else:
            line1 = f"{icon} {record['message']}"
        line1 = line1.strip()

        # Build the second line: "Source: <source> - <b><timestamp></b>"
        if record["source"]:
            line2 = f"Source: {record['source']} - <b>{record['timestamp']}</b>"
        else:
            line2 = f"<b>{record['timestamp']}</b>"

        return f"{line1}<br>{line2}"

    def get_all_display_strings(self) -> str:
        """
        Returns all log entries as a single HTML string,
        each entry separated by <br><br>.
        """
        display_list = [self.get_display_string(e) for e in self.entries]
        return "<br><br>".join(display_list)


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

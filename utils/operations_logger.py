#!/usr/bin/env python
import os
import sys
import logging
import pytz
from datetime import datetime

# ANSI escape codes for bold cyan and reset.
BOLD_CYAN = "\033[1;36m"
RESET = "\033[0m"


class OperationsLogger:
    def __init__(self, filename: str = None, use_color: bool = None):
        # Determine whether to use color. Defaults to True if running in a tty.
        if use_color is None:
            use_color = sys.stdout.isatty()
        self.use_color = use_color

        # Place the log file in the project root.
        if filename is None:
            project_root = os.getcwd()
            filename = os.path.join(project_root, "operations_log.txt")
        self.log_filename = filename

        # Create a logger with a fixed name.
        self.logger = logging.getLogger("OperationsLogger")
        self.logger.setLevel(logging.INFO)
        # Remove any existing handlers.
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        # Add a new FileHandler.
        file_handler = logging.FileHandler(filename)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(file_handler)

        self.pst = pytz.timezone("US/Pacific")

    def log(self, message: str, source: str = None):
        """Logs the given message with the current PST timestamp and an optional source.
           Timestamp format: M-D-YY : h:mm:ss AM/PM."""
        now = datetime.now(self.pst)
        # Use platform-specific formatting for removing zero-padding.
        if sys.platform.startswith('win'):
            formatted_time = now.strftime("%#m-%#d-%y : %#I:%M:%S %p")
        else:
            formatted_time = now.strftime("%-m-%-d-%y : %-I:%M:%S %p")
        if source:
            full_message = f"{message} [Source: {source}] - {formatted_time}"
        else:
            full_message = f"{message} - {formatted_time}"
        # Wrap the message in bold cyan if color is enabled.
        if self.use_color:
            colored_message = f"{BOLD_CYAN}{full_message}{RESET}"
        else:
            colored_message = full_message
        self.logger.info(colored_message)
        # Flush the handlers to ensure the log is written immediately.
        for handler in self.logger.handlers:
            handler.flush()


# Example usage:
if __name__ == "__main__":
    op_logger = OperationsLogger(use_color=False)  # Set use_color=False to avoid ANSI codes in file.
    op_logger.log("Update Jupiter - Called Successfully", source="Scheduler")

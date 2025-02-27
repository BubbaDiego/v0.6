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
        """
        Initialize the operations logger.
        - filename: The log file will be placed in the project root if not provided.
        - use_color: If True, wrap messages in bold cyan ANSI codes. If None,
          it defaults to True if sys.stdout is a tty; otherwise False.
        """
        # Determine whether to use color.
        if use_color is None:
            use_color = sys.stdout.isatty()
        self.use_color = use_color

        # Place log file in project root.
        if filename is None:
            project_root = os.getcwd()
            filename = os.path.join(project_root, "operations_log.txt")
        self.log_filename = filename

        self.logger = logging.getLogger("OperationsLogger")
        self.logger.setLevel(logging.INFO)
        # Prevent adding multiple handlers.
        if not self.logger.handlers:
            handler = logging.FileHandler(filename)
            # Use a simple formatter.
            handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.logger.addHandler(handler)
        self.pst = pytz.timezone("US/Pacific")

    def log(self, message: str, source: str = None):
        """
        Logs the given message with the current PST timestamp and an optional source.
        The timestamp format is: M-D-YY : h:mm:ss AM/PM.
        """
        now = datetime.now(self.pst)
        # Format timestamp without leading zeros (e.g., "2-27-25 : 1:34:02 PM")
        formatted_time = now.strftime("%-m-%-d-%y : %-I:%M:%S %p")
        if source:
            full_message = f"{message} [Source: {source}] - {formatted_time}"
        else:
            full_message = f"{message} - {formatted_time}"
        if self.use_color:
            colored_message = f"{BOLD_CYAN}{full_message}{RESET}"
        else:
            colored_message = full_message
        self.logger.info(colored_message)

# Example usage:
if __name__ == "__main__":
    # Set use_color=False if you want to avoid ANSI codes in the log file.
    op_logger = OperationsLogger(use_color=False)
    op_logger.log("Update Jupiter - Called Successfully", source="Scheduler")

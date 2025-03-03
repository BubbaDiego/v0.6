#!/usr/bin/env python3
import time
import requests
import logging
import urllib3
from utils.operations_manager import OperationsLogger  # Import from external module

# Disable InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging to print to the console.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

#URL = "http://www.deadlypanda.com/update_jupiter"
URL = "http://127.0.0.1:5001/positions/update_jupiter"
SLEEP_INTERVAL = 120  # 2 minutes in seconds

def call_update_jupiter():
    try:
        response = requests.get(URL, timeout=30, verify=False)
        response.raise_for_status()  # Raise an exception for HTTP errors.
        logging.info("Called update_jupiter successfully at URL %s. Status code: %s", URL, response.status_code)
    except Exception as e:
        logging.error("Error calling update_jupiter at URL %s: %s", URL, e)

def main():
    loop_counter = 0
    op_logger = OperationsLogger()
    logging.info("Starting always‑on task for update_jupiter. URL: %s", URL)
    while True:
        loop_counter += 1
        logging.info("Loop count: %d. Calling URL: %s", loop_counter, URL)
        call_update_jupiter()

        # Log the operation with the loop count, source set to "monitor", and operation type "Jupiter Updated"
        op_logger.log(f"Monitor Loop # {loop_counter}", source="system", operation_type="Monitor Loop")

        time.sleep(SLEEP_INTERVAL)

if __name__ == '__main__':
    main()

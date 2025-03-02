import os
import json
from twilio.rest import Client

# Use an absolute path so that the config file is found regardless of the working directory.

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "sonic_config.json")


def load_config():
    """Load configuration from the JSON config file."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error loading config file '{CONFIG_FILE}': {e}")

def trigger_twilio_flow(custom_message):
    """
    Trigger a Twilio Studio Flow execution with a custom message using configuration from the JSON file.
    """
    config = load_config()
    twilio_config = config.get("twilio_config")
    if not twilio_config:
        raise ValueError("Twilio configuration is missing from config file.")
    
    account_sid = twilio_config.get('account_sid')
    auth_token = twilio_config.get('auth_token')
    flow_sid = twilio_config.get('flow_sid')
    to_phone = twilio_config.get('to_phone')
    from_phone = twilio_config.get('from_phone')
    
    if not all([account_sid, auth_token, flow_sid, to_phone, from_phone]):
        raise ValueError("One or more Twilio configuration variables are missing from config file.")
    
    # Initialize the Twilio client
    client = Client(account_sid, auth_token)
    
    # Trigger the Studio Flow with the custom message
    execution = client.studio.v2.flows(flow_sid).executions.create(
        to=to_phone,
        from_=from_phone,
        parameters={"custom_message": custom_message}
    )
    
    return execution.sid

if __name__ == '__main__':
    try:
        custom_msg = "Bananas and cream!"
        execution_sid = trigger_twilio_flow(custom_msg)
        print(f"Execution started successfully, SID: {execution_sid}")
    except Exception as e:
        print(f"Error triggering Twilio flow: {e}")

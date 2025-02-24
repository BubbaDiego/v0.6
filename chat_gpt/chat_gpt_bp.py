from flask import Blueprint, render_template, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create the blueprint for ChatGPT
chat_gpt_bp = Blueprint('chat_gpt_bp', __name__, template_folder='templates')

@chat_gpt_bp.route('/chat', methods=['GET'])
def chat():
    """
    Render the ChatGPT interface.
    Ensure your 'chat_gpt.html' file is placed in the templates folder.
    """
    return render_template('chat_gpt.html')

@chat_gpt_bp.route('/chat', methods=['POST'])
def chat_post():
    """
    Handle chat requests by sending the user's message to the OpenAI API
    using the new client interface, and return the assistant's response.
    """
    data = request.get_json()
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({"reply": "Please provide a valid message."}), 400

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_message}
    ]

    try:
        # Use the modern synchronous API call via the instantiated client
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        # The response is now a Pydantic model; access its properties directly
        reply = response.choices[0].message.content.strip()
        return jsonify({"reply": reply})
    except Exception as e:
        import traceback
        print("DEBUG: OpenAI error:", e)
        print(traceback.format_exc())
        return jsonify({"reply": f"An error occurred: {e}"}), 500

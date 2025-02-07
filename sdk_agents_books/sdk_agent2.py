from flask import Flask, request, jsonify
from flask_cors import CORS
from fetchai.crypto import Identity
from fetchai.registration import register_with_agentverse
from fetchai.communication import send_message_to_agent
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

# Initialising client identity
client_identity = None

def init_client():
    """Initialize and register the client agent."""
    global client_identity
    try:
        client_identity = Identity.from_seed(os.getenv("AGENT_SECRET_KEY_2"), 0)
        logger.info(f"Client agent started with address: {client_identity.address}")

        readme = """
            ![domain:innovation-lab](https://img.shields.io/badge/innovation--lab-3D8BD3)
            domain:book-requests

            <description>This Agent sends book names to the recommendation agent.</description>
            <use_cases>
                <use_case>To send book names and receive recommendations.</use_case>
            </use_cases>
            <payload_requirements>
            <description>This agent sends book names in text format.</description>
            <payload>
                <requirement>
                    <parameter>book_name</parameter>
                    <description>The name of the book to get recommendations for.</description>
                </requirement>
            </payload>
            </payload_requirements>
        """

        register_with_agentverse(
            identity=client_identity,
            url="http://localhost:5005/api/webhook",
            agentverse_token=os.getenv("AGENTVERSE_KEY"),
            agent_title="Book Request Agent",
            readme=readme
        )

        logger.info("Book request agent registration complete!")

    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise

@app.route('/api/request-recommendations', methods=['POST'])
def request_recommendations():
    """Send book name to the recommendation agent"""
    try:
        data = request.get_json()
        book_name = data.get('payload').get('book_name')
        agent_address = data.get('agent_address')

        if not book_name or not agent_address:
            return jsonify({"error": "Missing book name or agent address"}), 400

        logger.info(f"Requesting recommendations for book: {book_name}")

        payload = {
            'book_name': book_name
        }

        send_message_to_agent(
            client_identity,
            agent_address,
            payload
        )

        return jsonify({
            "status": "request_sent",
            "book_name": book_name
        })

    except Exception as e:
        logger.error("Error requesting recommendations", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    load_dotenv()
    init_client()
    app.run(host="0.0.0.0", port=5005)
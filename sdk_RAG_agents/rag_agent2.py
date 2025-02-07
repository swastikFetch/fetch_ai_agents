from flask import Flask, request, jsonify
from flask_cors import CORS
from fetchai.crypto import Identity
from fetchai.registration import register_with_agentverse
from fetchai.communication import send_message_to_agent, parse_message_from_agent
import logging
import os
from dotenv import load_dotenv
import threading
from queue import Queue
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

# Initialising client identity and response queue
client_identity = None
response_queues = {}

def init_client():
    """Initialize and register the client agent."""
    global client_identity
    try:
        client_identity = Identity.from_seed(os.getenv("AGENT_SECRET_KEY_2"), 0)
        logger.info(f"Client agent started with address: {client_identity.address}")

        readme = """
            ![domain:innovation-lab](https://img.shields.io/badge/innovation--lab-3D8BD3)
            domain:query-handling

            <description>This Agent sends queries to the RAG processing agent and returns responses.</description>
            <use_cases>
                <use_case>To send user queries and receive RAG-based responses.</use_case>
            </use_cases>
            <payload_requirements>
            <description>This agent sends queries in text format.</description>
            <payload>
                <requirement>
                    <parameter>query</parameter>
                    <description>The question to be processed by RAG.</description>
                </requirement>
            </payload>
            </payload_requirements>
        """

        register_with_agentverse(
            identity=client_identity,
            url="http://localhost:5005/api/webhook",
            agentverse_token=os.getenv("AGENTVERSE_KEY"),
            agent_title="Query Agent",
            readme=readme
        )

        logger.info("Query agent registration complete!")

    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """Handle response from RAG agent"""
    try:
        data = request.get_data().decode("utf-8")
        logger.info("Received response from RAG agent")

        message = parse_message_from_agent(data)
        response = message.payload.get('response')
        query_id = message.payload.get('query_id')

        if query_id in response_queues:
            response_queues[query_id].put(response)
            logger.info(f"Stored response for query_id: {query_id}")

        return jsonify({"status": "success"})

    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/send-query', methods=['POST'])
def send_query():
    """Send query to the RAG processing agent and wait for response"""
    try:
        data = request.json
        query = data.get('query')
        rag_agent_address = data.get('rag_agent_address')

        if not query or not rag_agent_address:
            return jsonify({"error": "Missing query or agent address"}), 400

        # Generate unique query ID
        query_id = str(time.time())
        response_queues[query_id] = Queue()

        logger.info(f"Sending query: {query}")

        payload = {
            'query': query,
            'query_id': query_id
        }

        # Send query to RAG agent
        send_message_to_agent(
            client_identity,
            rag_agent_address,
            payload
        )

        # Wait for response with timeout
        try:
            response = response_queues[query_id].get(timeout=30)  # 30 second timeout
            del response_queues[query_id]  # Cleanup
            
            return jsonify({
                "status": "success",
                "query": query,
                "response": response
            })
        except:
            del response_queues[query_id]  # Cleanup
            return jsonify({
                "status": "error",
                "message": "Timeout waiting for response"
            }), 408

    except Exception as e:
        logger.error(f"Error sending query: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    load_dotenv()
    init_client()
    app.run(host="0.0.0.0", port=5005)
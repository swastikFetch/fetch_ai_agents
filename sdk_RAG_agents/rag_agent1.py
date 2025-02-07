from flask import Flask, request, jsonify
from flask_cors import CORS
from fetchai.crypto import Identity
from fetchai.registration import register_with_agentverse
from fetchai.communication import parse_message_from_agent, send_message_to_agent
from langchain_openai import OpenAIEmbeddings, OpenAI
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.document_loaders import PyPDFLoader
import logging
import os
from dotenv import load_dotenv
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialising client identity
client_identity = None

class RAGProcessor:
    def __init__(self, pdf_path):
        """Initialize RAG processor with PDF path"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("Missing OpenAI API Key")
        
        logger.info(f"Loading PDF from {pdf_path}")
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = Chroma(
            collection_name="rag_store",
            embedding_function=self.embeddings
        )
        
        # Store PDF content in vector store
        texts = [page.page_content for page in pages]
        self.vector_store.add_texts(texts)
        logger.info("PDF processed and stored in vector store")
        
        self.llm = OpenAI()
        
    def process_query(self, query):
        """Process a query using RAG"""
        try:
            retriever = self.vector_store.as_retriever()
            qa_chain = RetrievalQA.from_chain_type(
                self.llm,
                retriever=retriever
            )
            response = qa_chain.run(query)
            return response
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return f"Error processing query: {str(e)}"

# Global RAG processor instance
rag_processor = None

def init_client(pdf_path):
    """Initialize and register the client agent."""
    global client_identity, rag_processor
    try:
        # Initialize RAG processor
        rag_processor = RAGProcessor(pdf_path)
        
        # Initialize agent identity
        client_identity = Identity.from_seed(os.getenv("AGENT_SECRET_KEY_1_RAG"), 0)
        logger.info(f"Client agent started with address: {client_identity.address}")

        readme = """
            ![domain:innovation-lab](https://img.shields.io/badge/innovation--lab-3D8BD3)
            domain:rag-processing

            <description>This Agent processes queries using RAG on a specified PDF.</description>
            <use_cases>
                <use_case>To answer questions about the content of the loaded PDF.</use_case>
            </use_cases>
            <payload_requirements>
            <description>This agent requires a query in text format.</description>
            <payload>
                <requirement>
                    <parameter>query</parameter>
                    <description>The question to be answered using RAG.</description>
                </requirement>
            </payload>
            </payload_requirements>
        """

        register_with_agentverse(
            identity=client_identity,
            url="http://localhost:5002/api/webhook",
            agentverse_token=os.getenv("AGENTVERSE_KEY"),
            agent_title="RAG Processing Agent",
            readme=readme
        )

        logger.info("RAG processing agent registration complete!")
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """Handle incoming queries"""
    try:
        data = request.get_data().decode("utf-8")
        logger.info("Received query request")

        message = parse_message_from_agent(data)
        query = message.payload.get('query')
        query_id = message.payload.get('query_id')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400

        # Process query using RAG
        response = rag_processor.process_query(query)
        logger.info(f"Generated response for query: {query}")
        
        # Send response back to Agent 2
        send_message_to_agent(
            client_identity,
            message.sender,  # Send back to the agent that sent the query
            {
                'response': response,
                'query_id': query_id
            }
        )
        
        return jsonify({
            "status": "success"
        })

    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    load_dotenv()
    
    # Get PDF path from command line argument
    if len(sys.argv) != 2:
        print("Usage: python rag_agent.py <path_to_pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    init_client(pdf_path)
    app.run(host="0.0.0.0", port=5002)
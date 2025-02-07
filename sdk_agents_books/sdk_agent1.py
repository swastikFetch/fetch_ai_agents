from flask import Flask, request, jsonify
from flask_cors import CORS
from fetchai.crypto import Identity
from fetchai.registration import register_with_agentverse
from fetchai.communication import parse_message_from_agent
import logging
import os
from dotenv import load_dotenv
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n')
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app)

# Initialising client identity
client_identity = None

class BookRecommender:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        
    def get_book_details(self, book_name):
        """Fetch detailed book information from OpenLibrary API"""
        # Search for the book
        search_url = f"http://openlibrary.org/search.json?title={book_name}&fields=key,title,author_name,subject,first_publish_year,isbn,edition_key&limit=10"
        response = requests.get(search_url)
        if response.status_code != 200:
            logger.info("Book not found in open library api")
            return None
            
        search_data = response.json()
        if not search_data.get('docs'):
            logger.info("Relevant info not found in open library api")
            return None
            
        # Get the first match
        book = search_data['docs'][0]
        
        # Get additional book details including description
        if book.get('key'):
            works_url = f"https://openlibrary.org{book['key']}.json"
            works_response = requests.get(works_url)
            if works_response.status_code == 200:
                works_data = works_response.json()
                book['description'] = works_data.get('description', '')
        # logger.info(book)
        return book

    def create_book_feature_vector(self, book):
        """Create a feature vector from book metadata"""
        features = []
        
        subjects = book.get('subject', [])
        features.extend(subjects)
    
        authors = book.get('author_name', [])
        features.extend(authors)
        
        if isinstance(book.get('description'), dict):
            features.append(book['description'].get('value', ''))
        elif isinstance(book.get('description'), str):
            features.append(book['description'])
            
        return ' '.join(str(f) for f in features) #concatinating all features into a single string

    def get_similar_books(self, book_name):
        """Get book recommendations using similarity matching"""
        try:
            # Get main book details
            main_book: dict = self.get_book_details(book_name)
            if not main_book:
                logger.error(f"Could not find book: {book_name}")
                return []
                
            # Get the subjects and make multiple queries to ensure we get enough books
            subjects = main_book.get('subject', ['fiction'])[:23]  # Take fewer subjects to avoid over-specificity
            similar_books = []
            
            # Query each subject individually to get more diverse results
            for subject in subjects:
                logger.info(f'Querying subject: {subject}')
                # Use OR operator (|) instead of AND (,) for broader results
                search_url = f"http://openlibrary.org/search.json?subject={subject}&fields=key,title,author_name,subject,first_publish_year,description&limit=10"
                similar_response = requests.get(search_url)
                
                if similar_response.status_code == 200:
                    books = similar_response.json().get('docs', [])
                    similar_books.extend(books)
            
            # Remove duplicates based on title
            seen_titles = set()
            unique_similar_books = []
            for book in similar_books:
                if book.get('title') not in seen_titles:
                    seen_titles.add(book.get('title'))
                    unique_similar_books.append(book)

            logger.info(f"similar_books: {unique_similar_books}")
            # Create feature vectors for similarity comparison
            books_features = [self.create_book_feature_vector(main_book)]
            books_features.extend([self.create_book_feature_vector(book) for book in unique_similar_books])
            
            # Calculate similarity scores
            tfidf_matrix = self.vectorizer.fit_transform(books_features)
            cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
            
            # Sort books by similarity
            unique_similar_books_with_scores = list(zip(unique_similar_books, cosine_similarities))
            unique_similar_books_with_scores.sort(key=lambda x: x[1], reverse=True)

            
            # Format recommendations
            recommendations = []
            for book, score in unique_similar_books_with_scores[:5]:
                logger.info(f"this runs {book}, {score}")
                if book.get('title') != main_book.get('title'):
                    
                    recommendation = {
                        'title': book.get('title'),
                        'author': book.get('author_name', ['Unknown'])[0],
                        'first_publish_year': book.get('first_publish_year', 'Unknown'),
                        'subject': book.get('subject', [])[:3],
                        'similarity_score': round(float(score), 3)
                    }
                    recommendations.append(recommendation)
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting similar books: {str(e)}")
            return []

recommender = BookRecommender()

def init_client():
    """Initialize and register the client agent."""
    global client_identity
    try:
        client_identity = Identity.from_seed(os.getenv("AGENT_SECRET_KEY_1"), 0)
        logger.info(f"Client agent started with address: {client_identity.address}")

        readme = """
            ![domain:innovation-lab](https://img.shields.io/badge/innovation--lab-3D8BD3)
            domain:book-recommendations

            <description>This Agent receives book names and returns similar book recommendations.</description>
            <use_cases>
                <use_case>To receive book names and provide recommendations.</use_case>
            </use_cases>
            <payload_requirements>
            <description>This agent requires a book name in text format.</description>
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
            url="http://localhost:5002/api/webhook",
            agentverse_token=os.getenv("AGENTVERSE_KEY"),
            agent_title="Book Recommendation Agent",
            readme=readme
        )

        logger.info("Book recommendation agent registration complete!")
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """Handle incoming book requests"""
    try:
        data = request.get_data().decode("utf-8")
        logger.info("Received book request")

        message = parse_message_from_agent(data)
        book_name = message.payload.get('book_name')
        logger.info(f"book is : {book_name}")
        if not book_name:
            return jsonify({"error": "No book name provided"}), 400

        recommendations = recommender.get_similar_books(book_name)
        logger.info(f"Generated recommendations for: {book_name}")
        logger.info(f"Book recommendations: {recommendations}")
        
        return jsonify({
            "status": "success",
            "recommendations": recommendations
        })

    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    load_dotenv()
    init_client()
    app.run(host="0.0.0.0", port=5002, debug=True)
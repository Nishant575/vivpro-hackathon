from flask import Flask
from flask_cors import CORS
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os

load_dotenv()

# Global Elasticsearch client
es_client = None

def get_es_client():
    """Get Elasticsearch client singleton."""
    global es_client
    if es_client is None:
        es_host = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
        es_client = Elasticsearch(es_host)
    return es_client

def create_app():
    app = Flask(__name__)

    # Enable CORS for React frontend
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"]
        }
    })

    # Initialize Elasticsearch
    try:
        es = get_es_client()
        es.info()
        print("Connected to Elasticsearch")
    except Exception as e:
        print(f"Elasticsearch connection failed: {e}")

    # Initialize embedding service (pre-load cached embeddings)
    try:
        from services.embedding_service import init_embedding_service
        init_embedding_service()
        print("Embedding service initialized")
    except Exception as e:
        print(f"Embedding service initialization failed: {e}")

    # Initialize MeSH synonym service
    try:
        from services.mesh_service import init_mesh_service
        init_mesh_service()
    except FileNotFoundError as e:
        print(f"MeSH service not available: {e}")
    except Exception as e:
        print(f"MeSH service initialization failed: {e}")

    # Register routes
    from app.routes.health import health_bp
    from app.routes.search import search_bp

    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(search_bp, url_prefix='/api')

    return app

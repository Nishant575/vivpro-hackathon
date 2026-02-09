from flask import Blueprint, jsonify
from datetime import datetime
import os

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Check API and service health."""
    es_status = "disconnected"
    try:
        from app import get_es_client
        es = get_es_client()
        es.info()
        es_status = "connected"
    except:
        pass

    openai_status = "configured" if os.getenv("OPENAI_API_KEY") else "missing"

    return jsonify({
        "status": "healthy" if es_status == "connected" else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {
            "elasticsearch": es_status,
            "openai": openai_status
        }
    }), 200

@health_bp.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Clinical Trials Search API",
        "endpoints": {
            "health": "/api/health",
            "search": "/api/search/<query>"
        }
    }), 200

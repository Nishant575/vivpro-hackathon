import json
import os
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

#Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
SIMILARITY_THRESHOLD = 0.70
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TERMS_FILE = os.path.join(BASE_DIR, "data", "unique_terms.json")
CACHE_FILE = os.path.join(BASE_DIR, "data", "embeddings_cache.json")

#Global state
client = OpenAI()
_embeddings_cache = {}  # {"conditions": {"term": [vector]}, "interventions": {"term": [vector]}}


def load_unique_terms():
    """Load unique terms from extracted JSON."""
    with open(TERMS_FILE, "r") as f:
        return json.load(f)


def get_embedding(text):
    """Get embedding vector for a single text string."""
    response = client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding


def compute_all_embeddings(terms):
    """
    Compute embeddings for a list of terms in batches.
    OpenAI allows up to 2048 inputs per request for text-embedding-3-small.
    """
    embeddings = {}
    batch_size = 500

    for i in range(0, len(terms), batch_size):
        batch = terms[i:i + batch_size]
        response = client.embeddings.create(
            input=batch,
            model=EMBEDDING_MODEL
        )
        for j, item in enumerate(response.data):
            embeddings[batch[j]] = item.embedding
        print(f"  Computed embeddings: {min(i + batch_size, len(terms))}/{len(terms)}")

    return embeddings


def save_embeddings_cache(cache):
    """Save pre-computed embeddings to disk."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)
    print(f"Saved embeddings cache to {CACHE_FILE}")


def load_embeddings_cache():
    """Load cached embeddings from disk if they exist."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return None


def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def find_closest_match(query, category):
    """
    Find the closest matching term from our database.

    Args:
        query: User's input (e.g., "heart attack")
        category: "conditions" or "interventions"

    Returns:
        (matched_term, confidence_score) or (None, 0.0) if no match
    """
    if category not in _embeddings_cache:
        return None, 0.0

    query_embedding = get_embedding(query)
    category_embeddings = _embeddings_cache[category]

    best_match = None
    best_score = 0.0

    for term, term_embedding in category_embeddings.items():
        score = cosine_similarity(query_embedding, term_embedding)
        if score > best_score:
            best_score = score
            best_match = term

    return best_match, best_score


def init_embedding_service():
    """
    Initialize the embedding service.
    Loads from cache if available, otherwise computes and caches.
    """
    global _embeddings_cache

    cached = load_embeddings_cache()
    if cached:
        _embeddings_cache = cached
        conditions_count = len(cached.get("conditions", {}))
        interventions_count = len(cached.get("interventions", {}))
        print(f"Loaded embeddings cache: {conditions_count} conditions, {interventions_count} interventions")
        return

    print("No embeddings cache found. Computing embeddings...")
    terms = load_unique_terms()

    print("Computing condition embeddings...")
    condition_embeddings = compute_all_embeddings(terms["conditions"])

    print("Computing intervention embeddings...")
    intervention_embeddings = compute_all_embeddings(terms["interventions"])

    _embeddings_cache = {
        "conditions": condition_embeddings,
        "interventions": intervention_embeddings
    }

    save_embeddings_cache(_embeddings_cache)
    print("Embedding service initialized")
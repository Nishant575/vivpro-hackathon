import difflib
import json
import os
from typing import Optional

# Global cache
_synonym_cache: dict = None
_mesh_keys: list = None

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SYNONYMS_FILE = os.path.join(DATA_DIR, "mesh_synonyms.json")

# Thresholds
FUZZY_CUTOFF = 0.85
EMBEDDING_THRESHOLD = 0.60


def init_mesh_service() -> None:
    """Loads MeSH synonym dictionary into memory. Called on app startup."""
    global _synonym_cache, _mesh_keys

    if not os.path.exists(SYNONYMS_FILE):
        raise FileNotFoundError(
            f"MeSH cache not found: {SYNONYMS_FILE}\n"
            "Run 'python scripts/build_mesh_cache.py' first"
        )

    with open(SYNONYMS_FILE, "r") as f:
        _synonym_cache = json.load(f)

    _mesh_keys = list(_synonym_cache.keys())
    print(f"Loaded {len(_synonym_cache)} MeSH synonym mappings")


def mesh_lookup(term: str) -> Optional[list]:

    if _synonym_cache is None:
        init_mesh_service()

    return _synonym_cache.get(term.lower())


def fuzzy_mesh_lookup(term: str) -> Optional[list]:

    if _mesh_keys is None:
        init_mesh_service()

    matches = difflib.get_close_matches(
        term.lower(), _mesh_keys, n=1, cutoff=FUZZY_CUTOFF
    )

    if matches:
        return _synonym_cache.get(matches[0])

    return None


def get_synonyms(term: str) -> list[str]:
    if not term or not term.strip():
        return []

    term = term.strip()

    # Layer 1: Direct MeSH lookup
    synonyms = mesh_lookup(term)
    if synonyms:
        return synonyms

    # Layer 1.5: Fuzzy string match against MeSH keys
    synonyms = fuzzy_mesh_lookup(term)
    if synonyms:
        return synonyms

    # Layer 2: Embedding fallback — match against existing condition embeddings
    try:
        from services.embedding_service import find_closest_match

        matched_term, confidence = find_closest_match(term, "conditions")

        if matched_term and confidence >= EMBEDDING_THRESHOLD:
            synonyms = mesh_lookup(matched_term)
            if synonyms:
                return synonyms
    except Exception as e:
        print(f"Embedding fallback failed: {e}")

    # Layer 3: No match — return original term
    return [term]


def get_synonyms_with_info(term: str) -> dict:
    """
    Get synonyms with match metadata (useful for debugging / UI display).

    Returns dict with: original, matched_term, match_type, confidence, synonyms
    """
    if not term or not term.strip():
        return {
            "original": term,
            "matched_term": None,
            "match_type": "none",
            "confidence": 0.0,
            "synonyms": [],
        }

    term = term.strip()

    # Layer 1: Direct MeSH lookup
    synonyms = mesh_lookup(term)
    if synonyms:
        return {
            "original": term,
            "matched_term": term,
            "match_type": "exact",
            "confidence": 1.0,
            "synonyms": synonyms,
        }

    # Fuzzy string match
    if _mesh_keys is None:
        init_mesh_service()

    matches = difflib.get_close_matches(
        term.lower(), _mesh_keys, n=1, cutoff=FUZZY_CUTOFF
    )
    if matches:
        synonyms = _synonym_cache.get(matches[0])
        if synonyms:
            return {
                "original": term,
                "matched_term": matches[0],
                "match_type": "fuzzy",
                "confidence": difflib.SequenceMatcher(
                    None, term.lower(), matches[0]
                ).ratio(),
                "synonyms": synonyms,
            }

    # Layer 2: Embedding fallback
    try:
        from services.embedding_service import find_closest_match

        matched_term, confidence = find_closest_match(term, "conditions")

        if matched_term and confidence >= EMBEDDING_THRESHOLD:
            synonyms = mesh_lookup(matched_term)
            if synonyms:
                return {
                    "original": term,
                    "matched_term": matched_term,
                    "match_type": "embedding",
                    "confidence": confidence,
                    "synonyms": synonyms,
                }
    except Exception as e:
        print(f"Embedding fallback failed: {e}")

    # No match
    return {
        "original": term,
        "matched_term": None,
        "match_type": "none",
        "confidence": 0.0,
        "synonyms": [term],
    }
"""
Elasticsearch Query Builder for Clinical Trials Search.
Builds targeted queries based on extracted entities.
"""

# --- Configuration ---
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


# --- Helper Functions for Nested Queries ---

def build_condition_query(condition):
    """Build nested query for conditions.name using MeSH synonyms."""
    from services.mesh_service import get_synonyms

    synonyms = get_synonyms(condition)

    if len(synonyms) == 1:
        # Single term — simple match with fuzziness as safety net
        return {
            "nested": {
                "path": "conditions",
                "query": {
                    "match": {
                        "conditions.name": {
                            "query": synonyms[0],
                            "fuzziness": "AUTO"
                        }
                    }
                }
            }
        }

    # Multiple synonyms — OR them together
    should_clauses = []
    for synonym in synonyms:
        should_clauses.append({
            "match": {
                "conditions.name": {
                    "query": synonym,
                    "fuzziness": "AUTO"
                }
            }
        })

    return {
        "nested": {
            "path": "conditions",
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            }
        }
    }


def build_location_query(location):
    """Build nested query for facilities (searches city, state, country)."""
    return {
        "nested": {
            "path": "facilities",
            "query": {
                "multi_match": {
                    "query": location,
                    "fields": [
                        "facilities.city^3",
                        "facilities.state^2",
                        "facilities.country"
                    ],
                    "fuzziness": "AUTO"
                }
            }
        }
    }


def build_sponsor_query(sponsor):
    """Build nested query for sponsors.name"""
    return {
        "nested": {
            "path": "sponsors",
            "query": {
                "match": {
                    "sponsors.name": {
                        "query": sponsor,
                        "fuzziness": "AUTO"
                    }
                }
            }
        }
    }


def build_intervention_query(intervention):
    """Build nested query for interventions.name"""
    return {
        "nested": {
            "path": "interventions",
            "query": {
                "match": {
                    "interventions.name": {
                        "query": intervention,
                        "fuzziness": "AUTO"
                    }
                }
            }
        }
    }


def build_age_query(age_group):
    """Build nested term query for age.age_category"""
    return {
        "nested": {
            "path": "age",
            "query": {
                "term": {
                    "age.age_category": age_group
                }
            }
        }
    }


def build_keyword_query(keyword):
    """Build multi-match query across text fields and nested keywords."""
    return {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": keyword,
                        "fields": [
                            "brief_title^2",
                            "official_title",
                            "brief_summaries_description"
                        ],
                        "fuzziness": "AUTO"
                    }
                },
                {
                    "nested": {
                        "path": "keywords",
                        "query": {
                            "match": {
                                "keywords.name": {
                                    "query": keyword,
                                    "fuzziness": "AUTO"
                                }
                            }
                        }
                    }
                }
            ],
            "minimum_should_match": 1
        }
    }

def build_date_query(date_info):
    """Build range query for start_date based on extracted date entity."""
    if not isinstance(date_info, dict):
        return None

    range_filter = {}
    if "start" in date_info:
        range_filter["gte"] = date_info["start"]
    if "end" in date_info:
        range_filter["lte"] = date_info["end"]

    if not range_filter:
        return None

    return {"range": {"start_date": range_filter}}


def build_highlight_config():
    """Build highlight configuration for search results."""
    return {
        "fields": {
            "brief_title": {},
            "conditions.name": {},
            "brief_summaries_description": {
                "fragment_size": 150,
                "number_of_fragments": 2
            }
        },
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"]
    }


# --- Main Query Builder ---

def build_query(entities, page=1, size=10):
    """
    Build Elasticsearch DSL query from extracted entities.
    All entity values are arrays (normalized by NLP service).
    Multiple values for the same entity are OR'd together.
    """
    # Validate pagination
    page = max(1, page)
    size = min(max(1, size), MAX_PAGE_SIZE)
    offset = (page - 1) * size

    # Handle empty entities — return all results
    if not entities:
        return {
            "query": {"match_all": {}},
            "from": offset,
            "size": size,
            "sort": [{"enrollment": "desc"}]
        }

    must_clauses = []
    filter_clauses = []
    should_clauses = []

    # --- Exact Filters (keyword fields) — use terms for arrays ---

    if "phase" in entities:
        phases = entities["phase"]
        if len(phases) == 1:
            filter_clauses.append({"term": {"phase": phases[0]}})
        else:
            filter_clauses.append({"terms": {"phase": phases}})

    if "status" in entities:
        statuses = entities["status"]
        if len(statuses) == 1:
            filter_clauses.append({"term": {"overall_status": statuses[0]}})
        else:
            filter_clauses.append({"terms": {"overall_status": statuses}})

    # --- Nested Queries (array fields) — OR multiple values ---

    if "condition" in entities:
        conditions = entities["condition"]
        op = entities.get("condition_op", "OR")
        if len(conditions) == 1:
            must_clauses.append(build_condition_query(conditions[0]))
        elif op == "AND":
            for c in conditions:
                must_clauses.append(build_condition_query(c))
        else:
            cond_should = [build_condition_query(c) for c in conditions]
            must_clauses.append({
                "bool": {"should": cond_should, "minimum_should_match": 1}
            })

    if "location" in entities:
        locations = entities["location"]
        op = entities.get("location_op", "OR")
        if len(locations) == 1:
            must_clauses.append(build_location_query(locations[0]))
        elif op == "AND":
            for loc in locations:
                must_clauses.append(build_location_query(loc))
        else:
            loc_should = [build_location_query(loc) for loc in locations]
            must_clauses.append({
                "bool": {"should": loc_should, "minimum_should_match": 1}
            })

    if "sponsor" in entities:
        sponsors = entities["sponsor"]
        op = entities.get("sponsor_op", "OR")
        if len(sponsors) == 1:
            must_clauses.append(build_sponsor_query(sponsors[0]))
        elif op == "AND":
            for s in sponsors:
                must_clauses.append(build_sponsor_query(s))
        else:
            spon_should = [build_sponsor_query(s) for s in sponsors]
            must_clauses.append({
                "bool": {"should": spon_should, "minimum_should_match": 1}
            })

    if "intervention" in entities:
        interventions = entities["intervention"]
        op = entities.get("intervention_op", "OR")
        if len(interventions) == 1:
            must_clauses.append(build_intervention_query(interventions[0]))
        elif op == "AND":
            for i in interventions:
                must_clauses.append(build_intervention_query(i))
        else:
            intv_should = [build_intervention_query(i) for i in interventions]
            must_clauses.append({
                "bool": {"should": intv_should, "minimum_should_match": 1}
            })

    if "age_group" in entities:
        age_groups = entities["age_group"]
        if len(age_groups) == 1:
            must_clauses.append(build_age_query(age_groups[0]))
        else:
            age_should = [build_age_query(a) for a in age_groups]
            must_clauses.append({
                "bool": {"should": age_should, "minimum_should_match": 1}
            })

    # --- Text Search (keyword/biomarker entity) ---

    if "keyword" in entities:
        keywords = entities["keyword"]
        if len(keywords) == 1:
            must_clauses.append(build_keyword_query(keywords[0]))
        else:
            kw_should = [build_keyword_query(k) for k in keywords]
            must_clauses.append({
                "bool": {"should": kw_should, "minimum_should_match": 1}
            })

    # --- Date Range Filter ---

    if "date" in entities:
        date_clause = build_date_query(entities["date"])
        if date_clause:
            filter_clauses.append(date_clause)

    # --- Relevance Boosting on brief_title ---

    boost_terms = []
    for key in ("condition", "intervention", "keyword"):
        if key in entities:
            boost_terms.extend(entities[key])

    if boost_terms:
        should_clauses.append({
            "match": {
                "brief_title": {
                    "query": " ".join(boost_terms),
                    "boost": 2
                }
            }
        })

    # --- Construct Final Query ---

    bool_query = {}

    if must_clauses:
        bool_query["must"] = must_clauses
    if filter_clauses:
        bool_query["filter"] = filter_clauses
    if should_clauses:
        bool_query["should"] = should_clauses
        bool_query["minimum_should_match"] = 0

    # If only filters and no must, we still need something to match on
    if not must_clauses and filter_clauses:
        bool_query["must"] = [{"match_all": {}}]

    query = {
        "query": {"bool": bool_query},
        "from": offset,
        "size": size,
        "sort": [
            {"_score": "desc"},
            {"enrollment": "desc"}
        ],
        "highlight": build_highlight_config()
    }

    return query



from flask import Blueprint, jsonify, request
from app import get_es_client
from services.nlp_service import extract_entities
from services.query_builder import build_query
import math

search_bp = Blueprint('search', __name__)

INDEX_NAME = "clinical_trials"


def format_result(hit):
    """Transform a single ES hit into a clean API response object."""
    source = hit.get("_source", {})

    # Extract condition names
    conditions = [
        c.get("name") for c in source.get("conditions", [])
        if c.get("name")
    ]

    # Extract primary sponsor
    sponsors = source.get("sponsors", [])
    primary_sponsor = None
    for s in sponsors:
        if s.get("lead_or_collaborator") == "lead":
            primary_sponsor = s.get("name")
            break
    if not primary_sponsor and sponsors:
        primary_sponsor = sponsors[0].get("name")

    # Extract ALL unique countries (for filters)
    all_countries = list(dict.fromkeys(
        f.get("country")
        for f in source.get("facilities", [])
        if f.get("country")
    ))

    # Extract locations (limit to 3)
    locations = []
    for f in source.get("facilities", [])[:3]:
        loc_parts = [f.get("city"), f.get("state"), f.get("country")]
        loc_str = ", ".join([p for p in loc_parts if p])
        if loc_str:
            locations.append(loc_str)

    return {
        "nct_id": source.get("nct_id"),
        "brief_title": source.get("brief_title"),
        "overall_status": source.get("overall_status"),
        "phase": source.get("phase"),
        "conditions": conditions,
        "sponsor": primary_sponsor,
        "enrollment": source.get("enrollment"),
        "locations": locations,
        "countries": all_countries,
        "start_date": source.get("start_date"),
        "score": hit.get("_score"),
        "highlights": hit.get("highlight", {})
    }


@search_bp.route('/search/<path:query>', methods=['GET'])
def search(query):
    """
    Main search endpoint.

    GET /api/search/<natural language query>?page=1&size=10
    """
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 10, type=int)
    page = max(1, page)
    size = min(max(1, size), 100)

    try:
        # Step 1: Extract entities using NLP service
        nlp_result = extract_entities(query)
        entities = nlp_result.get("entities", {})
        interpretation = nlp_result.get("interpretation", "")

        # Step 2: Build Elasticsearch query
        es_query = build_query(entities, page=page, size=size)

        # Step 3: Execute search
        es = get_es_client()
        response = es.search(index=INDEX_NAME, body=es_query)

        # Step 4: Format results
        hits = response.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        total_pages = math.ceil(total / size) if total > 0 else 0

        results = [format_result(hit) for hit in hits.get("hits", [])]

        return jsonify({
            "success": True,
            "query": query,
            "interpretation": interpretation,
            "entities": entities,
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "results": results
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "query": query,
            "interpretation": "",
            "entities": {},
            "total": 0,
            "page": page,
            "size": size,
            "total_pages": 0,
            "results": []
        }), 500
    
@search_bp.route('/summarize', methods=['POST'])
def summarize():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "summary": ""}), 400

    query = data.get("query", "")
    total = data.get("total", 0)
    entities = data.get("entities", {})
    results = data.get("results", [])

    condensed = []
    for r in results[:20]:
        condensed.append({
            "title": r.get("brief_title", ""),
            "status": r.get("overall_status", ""),
            "phase": r.get("phase", ""),
            "conditions": r.get("conditions", []),
            "sponsor": r.get("sponsor", ""),
            "enrollment": r.get("enrollment"),
            "locations": r.get("locations", []),
        })

    # Count stats for context
    status_counts = {}
    phase_counts = {}
    sponsor_counts = {}
    countries = {}
    for r in results:
        s = r.get("overall_status")
        if s:
            status_counts[s] = status_counts.get(s, 0) + 1
        p = r.get("phase")
        if p:
            phase_counts[p] = phase_counts.get(p, 0) + 1
        sp = r.get("sponsor")
        if sp:
            sponsor_counts[sp] = sponsor_counts.get(sp, 0) + 1
        for loc in r.get("locations", []):
            parts = loc.split(", ")
            c = parts[-1] if parts else None
            if c:
                countries[c] = countries.get(c, 0) + 1

    top_sponsors = sorted(sponsor_counts.items(), key=lambda x: -x[1])[:5]
    top_countries = sorted(countries.items(), key=lambda x: -x[1])[:5]

    query_type = entities.get("query_type", "search")

    if query_type == "question":
        prompt = f"""You are a clinical trials research assistant. The user asked a QUESTION about clinical trials data. Answer it directly and specifically.

User's question: "{query}"
Entities extracted: {entities}
Total matching trials: {total}

Status breakdown: {status_counts}
Phase breakdown: {phase_counts}
Top sponsors: {top_sponsors}
Top locations: {top_countries}

Sample trials:
{condensed[:5]}

Answer the user's question directly in 2-4 sentences. Be specific with numbers and percentages. If the question asks "how many", give the exact count. If it asks "which countries", list them. Do NOT just summarize — answer the question."""

    else:
        prompt = f"""You are a clinical trials research assistant. Summarize these search results in 2-3 concise sentences.

User searched: "{query}"
Entities extracted: {entities}
Total matching trials: {total}
Results returned: {len(results)}

Status breakdown: {status_counts}
Phase breakdown: {phase_counts}
Top sponsors: {top_sponsors}
Top locations: {top_countries}

Sample trials:
{condensed[:5]}

Write a brief, informative summary. Mention the most notable patterns — recruitment status, phase distribution, key sponsors, geographic spread. Be specific with numbers. Do NOT use bullet points or markdown."""
   
    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        load_dotenv()

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You summarize clinical trial search results concisely. 2-3 sentences max. Be specific and data-driven."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200,
        )

        summary = response.choices[0].message.content.strip()
        return jsonify({"success": True, "summary": summary})

    except Exception as e:
        print(f"Summary generation failed: {e}")
        return jsonify({"success": False, "summary": ""}), 500

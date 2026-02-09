import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

#Configuration
LLM_MODEL = "gpt-4o-mini"
client = OpenAI()

SYSTEM_PROMPT = """You are a clinical trials search assistant. Extract search filters from natural language queries.

IMPORTANT: If the user mentions MULTIPLE values for any entity, return them as a JSON array.
For example: "phase 1 and phase 2" → "phase": ["PHASE1", "PHASE2"]
             "lung cancer and breast cancer" → "condition": ["lung cancer", "breast cancer"]

Extract these entities if mentioned, using EXACTLY the allowed values:

1. **phase** (return one or array of):
   - PHASE1
   - PHASE2
   - PHASE3
   - PHASE4
   - PHASE1/PHASE2 (for combined phase 1/2 trials)
   - PHASE2/PHASE3 (for combined phase 2/3 trials)
   - EARLY_PHASE1

2. **status** (return one or array of):
   - RECRUITING (user says: open, active, enrolling, accepting patients)
   - NOT_YET_RECRUITING (user says: not yet open, upcoming, planned)
   - ACTIVE_NOT_RECRUITING (user says: active but not recruiting, ongoing)
   - COMPLETED (user says: closed, finished, done, ended)
   - SUSPENDED (user says: paused, on hold)
   - TERMINATED (user says: stopped, cancelled)
   - WITHDRAWN (user says: withdrawn, removed)

3. **condition** (one or array - IMPORTANT: Always convert to standard medical terminology):
   - "mini stroke" → "Transient Ischemic Attack"
   - "high cholesterol" → "Hypercholesterolemia"
   - "high blood pressure" → "Hypertension"
   - "tummy ache" → "Abdominal Pain"
   - "sugar disease" → "Diabetes Mellitus"
   - "water on the brain" → "Hydrocephalus"
   - "lazy eye" → "Amblyopia"
   - "shingles" → "Herpes Zoster"
   - Standard medical terms: return as-is

4. **intervention** (one or array - IMPORTANT: Always convert to standard medical/pharmacological terminology):
   - "blood thinner" → "Anticoagulants"
   - "chemo" → "Chemotherapy"
   - "radiation" → "Radiotherapy"
   - Standard drug/treatment names: return as-is

5. **location** (one or array - normalize common variations):
   - "USA", "US", "America" → return "United States"
   - "UK", "Britain" → return "United Kingdom"
   - Other countries: return as mentioned

6. **sponsor** (one or array - return as mentioned)

7. **age_group** (one or array - return EXACTLY one of):
   - adult
   - child
   - older-adults

8. **keyword** (one or array - genes, biomarkers like BRCA1, EGFR, PD-L1 - return as mentioned)

9. **date** (extract year or date range if mentioned):
   - "from 2022" → {"start": "2022-01-01", "end": "2022-12-31"}
   - "2020 to 2023" → {"start": "2020-01-01", "end": "2023-12-31"}
   - "since 2021" → {"start": "2021-01-01"}
   - "before 2020" → {"end": "2019-12-31"}
   - "in 2023" → {"start": "2023-01-01", "end": "2023-12-31"}
   - "last 3 years" → calculate from current year (2026): {"start": "2023-01-01"}
   - "recent" → {"start": "2024-01-01"}
   - Always use ISO format YYYY-MM-DD

10. **Logical operators for multi-value entities**:
   When multiple values are given for condition, location, intervention, or sponsor,
   determine whether the user wants AND (all must match) or OR (any can match):
   
   - Default is OR: "trials in US or Italy", "lung cancer and breast cancer trials"
     → just return the array (no extra key needed)
   
   - Use AND when user says "only", "both", "together", "must have", "all of":
     → add "<entity>_op": "AND" alongside the array
   
   Note: phase and status are ALWAYS OR (a trial can't be two phases simultaneously)

11. **query_type** (ALWAYS include this field):
   - "search" → user wants to see trial listings (default)
   - "question" → user is asking an analytical question about trials
   
   Signals for "question":
   - Starts with: "how many", "which", "what", "are there", "is there", "do any"
   - Contains: "count", "list all", "tell me about", "compare"
   - Asking for aggregation, not individual results


RULES:
1. Extract ALL mentioned entities - medical conditions, drugs, phases, statuses, locations, etc.
2. A query like "lung cancer trials" DOES contain a condition ("lung cancer") - always extract it
3. Use EXACTLY the allowed values for phase, status, age_group
4. Return ONLY valid JSON, no other text
5. If truly nothing searchable is found (no conditions, sponsors, locations, etc.), return: {}
6. Sponsors and locations are VALID search entities even WITHOUT a medical condition
7. If MULTIPLE values exist for any entity, return them as a JSON array

Examples:

Query: "Show me active phase 3 lung cancer trials"
Output: {"status": "RECRUITING", "phase": "PHASE3", "condition": "lung cancer"}

Query: "Completed Pfizer diabetes studies"
Output: {"status": "COMPLETED", "sponsor": "Pfizer", "condition": "diabetes"}

Query: "Phase 1/2 immunotherapy trials for melanoma"
Output: {"phase": "PHASE1/PHASE2", "condition": "melanoma", "intervention": "immunotherapy"}

Query: "BRCA1 breast cancer trials accepting patients in America"
Output: {"status": "RECRUITING", "keyword": "BRCA1", "condition": "breast cancer", "location": "United States"}

Query: "lung cancer trials"
Output: {"condition": "lung cancer"}

Query: "diabetes"
Output: {"condition": "diabetes"}

Query: "Pfizer trials in Boston"
Output: {"sponsor": "Pfizer", "location": "Boston"}

Query: "recruiting trials in United States"
Output: {"status": "RECRUITING", "location": "United States"}

Query: "Novartis phase 2 studies"
Output: {"sponsor": "Novartis", "phase": "PHASE2"}

Query: "phase 1 and phase 2 lung cancer trials"
Output: {"phase": ["PHASE1", "PHASE2"], "condition": "lung cancer"}

Query: "lung cancer and breast cancer recruiting trials"
Output: {"condition": ["lung cancer", "breast cancer"], "status": "RECRUITING"}

Query: "Pfizer or Novartis diabetes studies in US and UK"
Output: {"sponsor": ["Pfizer", "Novartis"], "condition": "diabetes", "location": ["United States", "United Kingdom"]}

Query: "completed or terminated phase 3 trials"
Output: {"status": ["COMPLETED", "TERMINATED"], "phase": "PHASE3"}

Query: "lung cancer trials in United States and Italy"
Output: {"condition": "lung cancer", "location": ["United States", "Italy"]}

Query: "lung cancer trials in United States and Italy only"
Output: {"condition": "lung cancer", "location": ["United States", "Italy"], "location_op": "AND"}

Query: "trials studying both diabetes and hypertension"
Output: {"condition": ["diabetes", "Hypertension"], "condition_op": "AND"}

Query: "show me chemo and radiation trials for breast cancer together"
Output: {"condition": "breast cancer", "intervention": ["Chemotherapy", "Radiotherapy"], "intervention_op": "AND"}

Query: "how many lung cancer trials are there?"
Output: {"condition": "lung cancer", "query_type": "question"}

Query: "which countries have completed lung cancer trials?"
Output: {"condition": "lung cancer", "status": "COMPLETED", "query_type": "question"}

Query: "what phase are most diabetes trials in?"
Output: {"condition": "diabetes", "query_type": "question"}

Query: "show me lung cancer trials"
Output: {"condition": "lung cancer", "query_type": "search"}

Query: "are there any recruiting phase 3 breast cancer trials?"
Output: {"condition": "breast cancer", "phase": "PHASE3", "status": "RECRUITING", "query_type": "question"}
"""


def call_openai(query):
    """Call OpenAI to extract entities from a natural language query."""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return {}


def generate_interpretation(entities):
    """Generate a human-readable interpretation of extracted entities."""
    if not entities:
        return "No search filters detected."

    parts = []

    # Handle condition(s) with synonym expansion
    if "condition" in entities:
        conditions = entities["condition"]  # always a list now
        synonyms_map = entities.get("condition_synonyms", {})

        for cond in conditions:
            label = f"Condition = {cond}"
            syns = synonyms_map.get(cond, [])
            if len(syns) > 1:
                shown = syns[:3]
                remaining = len(syns) - 3
                expansion = ", ".join(shown)
                if remaining > 0:
                    expansion += f", +{remaining} more"
                label += f" → Expanded to: {expansion}"
            parts.append(label)

    # All other array entities
    label_map = {
        "status": "Status",
        "phase": "Phase",
        "intervention": "Treatment",
        "location": "Location",
        "sponsor": "Sponsor",
        "age_group": "Age Group",
        "keyword": "Keyword",
    }

    for key, label in label_map.items():
        if key in entities:
            values = entities[key]  # always a list now
            op = entities.get(f"{key}_op", "OR")
            joiner = " and " if op == "AND" else " or "
            display = joiner.join(str(v) for v in values)
            if op == "AND" and len(values) > 1:
                display += " (all required)"
            parts.append(f"{label} = {display}")

    # Handle date separately (it's a dict, not a list)
    if "date" in entities:
        date_info = entities["date"]
        if isinstance(date_info, dict):
            start = date_info.get("start", "")
            end = date_info.get("end", "")
            if start and end:
                start_yr = start[:4]
                end_yr = end[:4]
                if start_yr == end_yr:
                    parts.append(f"Year = {start_yr}")
                else:
                    parts.append(f"Date Range = {start_yr}–{end_yr}")
            elif start:
                parts.append(f"From = {start[:4]}")
            elif end:
                parts.append(f"Before = {end[:4]}")

    return "We understood: " + ", ".join(parts)

def ensure_list(value):
    """Wrap a single value in a list. Leave lists as-is."""
    if isinstance(value, list):
        return value
    return [value]


def extract_entities(query):
    """
    Main entry point for entity extraction.

    1. Call OpenAI to extract raw entities
    2. Normalize all entities to arrays
    3. Use embedding matching for each condition/intervention
    4. Attach MeSH synonyms for each condition
    5. Generate human-readable interpretation
    6. Return complete result
    """
    # Step 1: LLM extraction
    raw_entities = call_openai(query)

    if not raw_entities:
        return {
            "success": False,
            "entities": {},
            "interpretation": "Could not extract any search filters from your query.",
            "raw_query": query
        }

    # Step 2: Normalize all entities to arrays (except date which is a dict)
    ARRAY_KEYS = {"phase", "status", "condition", "intervention",
                  "location", "sponsor", "age_group", "keyword"}
    for key in ARRAY_KEYS:
        if key in raw_entities:
            raw_entities[key] = ensure_list(raw_entities[key])

    # Default query_type to "search"
    if "query_type" not in raw_entities:
        raw_entities["query_type"] = "search"

        # MeSH synonym lookup for each condition
        try:
            from services.mesh_service import get_synonyms_with_info
            synonyms_map = {}
            for cond in conditions:
                mesh_info = get_synonyms_with_info(cond)
                if mesh_info.get("synonyms") and len(mesh_info["synonyms"]) > 1:
                    synonyms_map[cond] = mesh_info["synonyms"]
            if synonyms_map:
                raw_entities["condition_synonyms"] = synonyms_map
        except Exception as e:
            print(f"MeSH synonym lookup failed: {e}")

    # Step 5: Generate interpretation
    interpretation = generate_interpretation(raw_entities)

    return {
        "success": True,
        "entities": raw_entities,
        "interpretation": interpretation,
        "raw_query": query
    }

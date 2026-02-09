import json
import os
import sys
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

#Configuration
ES_HOST = "http://localhost:9200"
INDEX_NAME = "clinical_trials"
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "clinical_trials.json")

#verify connection to elastic search
def get_es_client():
    print("Connecting to Elasticsearch...")
    es = Elasticsearch(ES_HOST)
    if not es.ping():
        print("Could not connect to Elasticsearch. Is it running?")
        sys.exit(1)
    print("Connected to Elasticsearch")
    return es

def get_index_mapping():
    """
    Hybrid mapping approach:
    - dynamic: true → auto-maps all fields we don't define
    - Explicit definitions only for:
      1. Nested arrays (MUST define - ES can't auto-detect)
      2. Fields needing type conversion (enrollment: string → integer)
      3. Key search fields (for query optimization)
    """
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "dynamic": True,
            "properties": {
                "nct_id": {"type": "keyword"},
                "overall_status": {"type": "keyword"},
                "phase": {"type": "keyword"},
                "study_type": {"type": "keyword"},
                "gender": {"type": "keyword"},
                "brief_title": {"type": "text"},
                "official_title": {"type": "text"},
                "brief_summaries_description": {"type": "text"},

                "enrollment": {"type": "integer"},

                "conditions": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}
                    }
                },
                "facilities": {
                    "type": "nested",
                    "properties": {
                        "city": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "state": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "country": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "zip": {"type": "keyword"},
                        "name": {"type": "text"}
                    }
                },
                "sponsors": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "agency_class": {"type": "keyword"},
                        "lead_or_collaborator": {"type": "keyword"}
                    }
                },
                "interventions": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "intervention_type": {"type": "keyword"},
                        "description": {"type": "text"}
                    }
                },
                "age": {
                    "type": "nested",
                    "properties": {
                        "age_category": {"type": "keyword"}
                    }
                },
                "keywords": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}
                    }
                },
                "design_outcomes": {
                    "type": "nested",
                    "properties": {
                        "outcome_type": {"type": "keyword"},
                        "measure": {"type": "text"},
                        "time_frame": {"type": "text"},
                        "description": {"type": "text"}
                    }
                },
                "design_groups": {
                    "type": "nested",
                    "properties": {
                        "id": {"type": "keyword"},
                        "group_type": {"type": "keyword"},
                        "title": {"type": "text"},
                        "description": {"type": "text"}
                    }
                },
                "browse_conditions": {
                    "type": "nested",
                    "properties": {
                        "mesh_term": {"type": "keyword"}
                    }
                },
                "browse_interventions": {
                    "type": "nested",
                    "properties": {
                        "mesh_term": {"type": "keyword"}
                    }
                },
                "id_information": {
                    "type": "nested",
                    "properties": {
                        "id_type": {"type": "keyword"},
                        "id_value": {"type": "keyword"}
                    }
                },
                "submissions": {
                    "type": "nested",
                    "properties": {
                        "version": {"type": "integer"},
                        "submitted_date": {"type": "date"},
                        "changes": {
                            "type": "nested",
                            "properties": {
                                "section": {"type": "keyword"}
                            }
                        }
                    }
                },
                "documents": {
                    "type": "nested",
                    "properties": {
                        "original_url": {"type": "keyword"},
                        "s3_path": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "title": {"type": "text"},
                        "page_count": {"type": "integer"}
                    }
                },
                "interventions_other_names": {
                    "type": "nested",
                    "properties": {
                        "intervention_id": {"type": "keyword"},
                        "name": {"type": "keyword"}
                    }
                }
            }
        }
    }

def clean_value(value):
    """Convert 'NA' strings and empty strings to None."""
    if value == "NA" or value == "":
        return None
    return value


def clean_record(record):
    """Clean and transform a single clinical trial record for ingestion."""
    cleaned = {}

    for key, value in record.items():
        if isinstance(value, list):
            # Clean nested arrays: remove items where all values are NA/None
            cleaned_list = []
            for item in value:
                if isinstance(item, dict):
                    cleaned_item = {k: clean_value(v) for k, v in item.items()}
                    # Keep the item if at least one value is not None
                    if any(v is not None for v in cleaned_item.values()):
                        cleaned_list.append(cleaned_item)
                else:
                    cleaned_val = clean_value(item)
                    if cleaned_val is not None:
                        cleaned_list.append(cleaned_val)
            cleaned[key] = cleaned_list
        elif isinstance(value, dict):
            cleaned[key] = {k: clean_value(v) for k, v in value.items()}
        else:
            cleaned[key] = clean_value(value)

    # Convert enrollment from string to integer
    if cleaned.get("enrollment") is not None:
        try:
            cleaned["enrollment"] = int(cleaned["enrollment"])
        except (ValueError, TypeError):
            cleaned["enrollment"] = None

    return cleaned


def generate_actions(records):
    """Generate bulk actions for Elasticsearch ingestion."""
    for record in records:
        cleaned = clean_record(record)
        yield {
            "_index": INDEX_NAME,
            "_id": cleaned.get("nct_id"),
            "_source": cleaned
        }


def main():
    # Connect
    es = get_es_client()

    # Delete existing index if it exists
    if es.indices.exists(index=INDEX_NAME):
        print(f"Deleting existing index '{INDEX_NAME}'...")
        es.indices.delete(index=INDEX_NAME)

    # Create index with mapping
    print("Creating index with mapping...")
    es.indices.create(index=INDEX_NAME, body=get_index_mapping())
    print(f"Index '{INDEX_NAME}' created")

    # Load data
    print(f"Loading data from {DATA_FILE}...")
    with open(DATA_FILE, "r") as f:
        records = json.load(f)
    print(f"Found {len(records)} records")

    # Bulk ingest with progress
    print("Ingesting records...")
    success_count = 0
    error_count = 0
    batch_size = 100

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        actions = list(generate_actions(batch))
        successes, errors = bulk(es, actions, raise_on_error=False)
        success_count += successes
        error_count += len(errors)
        print(f"  Progress: {min(i + batch_size, len(records))}/{len(records)}")

    print(f"Successfully ingested {success_count} records")
    if error_count > 0:
        print(f"Failed to ingest {error_count} records")

    # Verify
    es.indices.refresh(index=INDEX_NAME)
    count = es.count(index=INDEX_NAME)["count"]
    print(f"Verifying... Index contains {count} documents")


if __name__ == "__main__":
    main()



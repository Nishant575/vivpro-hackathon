import xml.etree.ElementTree as ET
import json
import os
import time

# Paths
SCRIPT_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.join(SCRIPT_DIR, "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
XML_FILE = os.path.join(DATA_DIR, "desc2026.xml")
SYNONYMS_OUTPUT = os.path.join(DATA_DIR, "mesh_synonyms.json")
TERMS_OUTPUT = os.path.join(DATA_DIR, "mesh_terms_list.json")

MAX_SYNONYMS_PER_GROUP = 20


def build_mesh_cache():
    if not os.path.exists(XML_FILE):
        print(f"ERROR: MeSH XML file not found: {XML_FILE}")
        return

    print(f"Parsing {XML_FILE} ...")
    start = time.time()

    synonym_dict = {}
    preferred_terms = []
    descriptor_count = 0

    for event, elem in ET.iterparse(XML_FILE, events=["end"]):
        if elem.tag != "DescriptorRecord":
            continue

        descriptor_count += 1

        # Get preferred descriptor name
        descriptor_name_elem = elem.find(".//DescriptorName/String")
        if descriptor_name_elem is not None and descriptor_name_elem.text:
            preferred_terms.append(descriptor_name_elem.text)

        # Collect all non-permuted terms across all concepts
        all_terms = []
        for term in elem.findall(".//Term"):
            if term.get("IsPermutedTermYN") == "Y":
                continue
            term_str = term.find("String")
            if term_str is not None and term_str.text:
                all_terms.append(term_str.text)

        # Deduplicate while preserving order
        all_terms = list(dict.fromkeys(all_terms))

        # Cap at MAX_SYNONYMS_PER_GROUP
        all_terms = all_terms[:MAX_SYNONYMS_PER_GROUP]

        # Add bidirectional mappings (every synonym → full group)
        for term in all_terms:
            synonym_dict[term.lower()] = all_terms

        # Free memory
        elem.clear()

        if descriptor_count % 10000 == 0:
            print(f"  Processed {descriptor_count} descriptors...")

    elapsed = time.time() - start
    print(f"Parsed {descriptor_count} descriptors in {elapsed:.1f}s")

    # Save synonym dictionary
    with open(SYNONYMS_OUTPUT, "w") as f:
        json.dump(synonym_dict, f)
    size_mb = os.path.getsize(SYNONYMS_OUTPUT) / (1024 * 1024)
    print(f"Saved {len(synonym_dict)} synonym mappings to mesh_synonyms.json ({size_mb:.1f} MB)")

    # Save preferred terms list
    with open(TERMS_OUTPUT, "w") as f:
        json.dump(preferred_terms, f)
    size_mb = os.path.getsize(TERMS_OUTPUT) / (1024 * 1024)
    print(f"Saved {len(preferred_terms)} preferred terms to mesh_terms_list.json ({size_mb:.1f} MB)")


if __name__ == "__main__":
    build_mesh_cache()
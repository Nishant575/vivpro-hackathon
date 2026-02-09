import json
from collections import Counter
import os

# Load data
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "clinical_trials.json")
with open(DATA_FILE, 'r') as f:
    data = json.load(f)

print(f"Total trials: {len(data)}\n")

# --- Extract unique CONDITIONS ---
conditions = []
for trial in data:
    for condition in trial.get('conditions', []):
        name = condition.get('name')
        if name and name != 'NA':
            conditions.append(name)

unique_conditions = list(set(conditions))
print(f"Unique CONDITIONS: {len(unique_conditions)}")
print("Sample:", unique_conditions[:10])
print()

# --- Extract unique INTERVENTIONS ---
interventions = []
for trial in data:
    for intervention in trial.get('interventions', []):
        name = intervention.get('name')
        if name and name != 'NA':
            interventions.append(name)

unique_interventions = list(set(interventions))
print(f"Unique INTERVENTIONS: {len(unique_interventions)}")
print("Sample:", unique_interventions[:10])
print()

# --- Extract unique SPONSORS ---
sponsors = []
for trial in data:
    for sponsor in trial.get('sponsors', []):
        name = sponsor.get('name')
        if name and name != 'NA':
            sponsors.append(name)

unique_sponsors = list(set(sponsors))
print(f"Unique SPONSORS: {len(unique_sponsors)}")
print("Sample:", unique_sponsors[:10])
print()

# --- Extract unique LOCATIONS (countries) ---
countries = []
for trial in data:
    for facility in trial.get('facilities', []):
        country = facility.get('country')
        if country and country != 'NA':
            countries.append(country)

unique_countries = list(set(countries))
print(f"Unique COUNTRIES: {len(unique_countries)}")
print("Sample:", unique_countries[:10])
print()

# --- Extract unique PHASES ---
phases = []
for trial in data:
    phase = trial.get('phase')
    if phase and phase != 'NA':
        phases.append(phase)

unique_phases = list(set(phases))
print(f"Unique PHASES: {len(unique_phases)}")
print("All:", unique_phases)
print()

# --- Extract unique STATUSES ---
statuses = []
for trial in data:
    status = trial.get('overall_status')
    if status and status != 'NA':
        statuses.append(status)

unique_statuses = list(set(statuses))
print(f"Unique STATUSES: {len(unique_statuses)}")
print("All:", unique_statuses)
print()

# --- Save to JSON for reference ---
output = {
    "conditions": sorted(unique_conditions),
    "interventions": sorted(unique_interventions),
    "sponsors": sorted(unique_sponsors),
    "countries": sorted(unique_countries),
    "phases": unique_phases,
    "statuses": unique_statuses
}

with open('data/unique_terms.json', 'w') as f:
    json.dump(output, f, indent=2)

print("✅ Saved to data/unique_terms.json")
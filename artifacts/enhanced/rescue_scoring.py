# Enhancement Two – Algorithms & Data Structures
# CS 499 – Andre Miranda
# rescue_scoring.py

import re
from functools import lru_cache
from typing import Dict, List, Any

# ---------------------------------------------
# BREED WEIGHTS (config-style dictionary)
# ---------------------------------------------
BREED_WEIGHTS: Dict[str, int] = {
    "labrador": 10,
    "lab": 10,
    "chesapeake": 9,
    "newfoundland": 8,
    "german": 10,
    "shepherd": 10,
    "malamute": 8,
    "husky": 8,
    "rottweiler": 7,
    "doberman": 7,
    "retriever": 9,
    "bloodhound": 9,
}

# ---------------------------------------------
# COMPILED REGEX FOR BREED NORMALIZATION
# ---------------------------------------------
BREED_SPLIT_PATTERN = re.compile(r"[/,]|mix", flags=re.IGNORECASE)


# ---------------------------------------------
# AGE SCORING
# ---------------------------------------------
def score_age(weeks: Any) -> int:
    """
    Score age in weeks for rescue suitability.

    - Ideal working range: 26–156 weeks → +10
    - Borderline younger: 20–25 weeks → +5
    - Very old (>300 weeks) → -5
    - Otherwise → 0
    """
    if weeks is None:
        return 0

    try:
        weeks_int = int(weeks)
    except (TypeError, ValueError):
        return 0

    if 26 <= weeks_int <= 156:
        return 10
    if 20 <= weeks_int < 26:
        return 5
    if weeks_int > 300:
        return -5
    return 0


# ---------------------------------------------
# BREED NORMALIZATION
# ---------------------------------------------
@lru_cache(maxsize=1024)
def normalize_breeds_cached(breed_string: str) -> List[str]:
    """
    Normalize mixed-breed strings into individual lowercase breed tokens.
    Uses caching to avoid repeated parsing of identical strings.
    """
    if not isinstance(breed_string, str):
        return []
    parts = BREED_SPLIT_PATTERN.split(breed_string)
    return [p.strip().lower() for p in parts if p.strip()]


def normalize_breeds(breed_string: Any) -> List[str]:
    """
    Safe wrapper around the cached normalization function.
    """
    if not isinstance(breed_string, str):
        return []
    return normalize_breeds_cached(breed_string)


# ---------------------------------------------
# BREED SCORING
# ---------------------------------------------
def score_breed(breed_string: Any) -> int:
    """
    Score breed based on configured BREED_WEIGHTS.
    Multiple matching tokens accumulate score.
    """
    breeds = normalize_breeds(breed_string)
    score = 0

    for b in breeds:
        for key, weight in BREED_WEIGHTS.items():
            if key in b:
                score += weight

    return score


# ---------------------------------------------
# OUTCOME SCORING
# ---------------------------------------------
def score_outcome(outcome: Any) -> int:
    """
    Score outcome history:
    - Adoption → +5
    - Transfer → +3
    - Euthanasia → -10
    - Other/unknown → 0
    """
    if not isinstance(outcome, str):
        return 0

    outcome_lower = outcome.lower()
    if "adoption" in outcome_lower:
        return 5
    if "transfer" in outcome_lower:
        return 3
    if "euthanasia" in outcome_lower:
        return -10
    return 0


# ---------------------------------------------
# TOTAL SCORE
# ---------------------------------------------
def compute_rescue_score(animal: Dict[str, Any]) -> int:
    """
    Compute total rescue suitability score for a single animal.
    """
    breed_score = score_breed(animal.get("breed"))
    age_score = score_age(animal.get("age_upon_outcome_in_weeks"))
    outcome_score = score_outcome(animal.get("outcome_type"))

    total = breed_score + age_score + outcome_score
    return total


# ---------------------------------------------
# RANKING FUNCTION
# ---------------------------------------------
def rank_animals(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank animals by computed rescue_score (descending).
    Adds 'rescue_score' to each record.
    """
    ranked: List[Dict[str, Any]] = []

    for animal in records:
        score = compute_rescue_score(animal)
        animal_copy = dict(animal)
        animal_copy["rescue_score"] = score
        ranked.append(animal_copy)

    ranked.sort(key=lambda x: x.get("rescue_score", 0), reverse=True)
    return ranked

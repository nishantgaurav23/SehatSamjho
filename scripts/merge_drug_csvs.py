#!/usr/bin/env python3
"""Merge all drug CSV sources into medicines.csv.

Priority order (richest data first):
1. existing medicines.csv  — 1,001 hand-curated entries (always preserved)
2. medicine_data.csv       — 7.5K entries: purpose, side_effects, composition,
                             drug_interactions (JSON), sub_category (therapeutic class)
3. Medicine_Details.csv    — 11.8K entries: Uses, Side_effects, Composition
4. A_Z_medicines_dataset   — 253K entries: composition only (enriches generic_name)

Deduplication is by normalized brand_name.  Existing entries always win.
When the same name exists in multiple sources, earlier sources take priority
but later sources can fill in empty fields.

Usage:
    python scripts/merge_drug_csvs.py              # default: rich data only (~17K)
    python scripts/merge_drug_csvs.py --dry-run    # preview counts without writing
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

DRUGS_DIR = Path(__file__).resolve().parent.parent / "data" / "drugs"
MEDICINES_CSV = DRUGS_DIR / "medicines.csv"
MEDICINE_DATA_CSV = DRUGS_DIR / "medicine_data.csv"
MEDICINE_DETAILS_CSV = DRUGS_DIR / "Medicine_Details.csv"
AZ_CSV = DRUGS_DIR / "A_Z_medicines_dataset_of_India.csv"

FIELDNAMES = [
    "brand_name",
    "generic_name",
    "therapeutic_class",
    "purpose_en",
    "side_effects_en",
    "timing_instructions",
    "known_interactions",
]

# Fields that can be enriched from later sources when empty
ENRICHABLE = [
    "generic_name",
    "therapeutic_class",
    "purpose_en",
    "side_effects_en",
    "timing_instructions",
    "known_interactions",
]


def normalize(name: str) -> str:
    """Lowercase, collapse whitespace for dedup key."""
    return re.sub(r"\s+", " ", name.strip()).lower()


def _clean(val: str | None) -> str:
    """Strip and return empty string for None."""
    return val.strip() if val else ""


# ---------------------------------------------------------------------------
# medicine_data.csv helpers
# ---------------------------------------------------------------------------

def _summarize_description(desc: str) -> str:
    """Extract a concise purpose from the long medicine_desc.

    medicine_data.csv descriptions are 1000+ chars with usage, warnings, etc.
    We extract the first 1-2 sentences which typically state the purpose.
    """
    if not desc:
        return ""
    # Split on sentence boundaries — keep first 2 sentences
    sentences = re.split(r"(?<=[.!])\s+", desc.strip())
    summary_parts = []
    char_count = 0
    for s in sentences:
        if char_count + len(s) > 195 and summary_parts:
            break
        summary_parts.append(s)
        char_count += len(s)
        if len(summary_parts) >= 2:
            break
    result = " ".join(summary_parts)
    # Hard cap at 200 chars to match medicines.csv test constraint
    if len(result) > 200:
        result = result[:197] + "..."
    return result


def _parse_interactions(raw: str) -> str:
    """Parse JSON drug_interactions into readable text.

    Input:  {"drug": ["Benazepril", ...], "brand": ["Apriace", ...], "effect": ["MODERATE", ...]}
    Output: "Benazepril (MODERATE); Captopril (MODERATE)"
    """
    if not raw:
        return ""
    try:
        data = json.loads(raw)
        drugs = data.get("drug", [])
        effects = data.get("effect", [])
        if not drugs:
            return ""
        parts = []
        for i, drug in enumerate(drugs):
            drug = drug.strip()
            if not drug:
                continue
            effect = effects[i].strip() if i < len(effects) else ""
            if effect:
                parts.append(f"{drug} ({effect})")
            else:
                parts.append(drug)
        return "; ".join(parts) if parts else ""
    except (json.JSONDecodeError, KeyError, IndexError):
        return ""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_existing() -> dict[str, dict]:
    """Load existing medicines.csv, keyed by normalized brand_name."""
    entries = {}
    if not MEDICINES_CSV.exists():
        return entries
    with MEDICINES_CSV.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = normalize(row["brand_name"])
            entries[key] = {fn: row.get(fn, "") for fn in FIELDNAMES}
    return entries


def load_medicine_data() -> dict[str, dict]:
    """Load medicine_data.csv — richest source (purpose, side_effects, interactions, class)."""
    entries = {}
    if not MEDICINE_DATA_CSV.exists():
        print(f"WARNING: {MEDICINE_DATA_CSV} not found, skipping")
        return entries
    with MEDICINE_DATA_CSV.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = _clean(row.get("product_name", ""))
            if not name:
                continue

            purpose = _summarize_description(_clean(row.get("medicine_desc", "")))
            side_effects = _clean(row.get("side_effects", ""))
            composition = _clean(row.get("salt_composition", ""))
            therapeutic_class = _clean(row.get("sub_category", "")).lower()
            interactions = _parse_interactions(_clean(row.get("drug_interactions", "")))

            entry = {
                "brand_name": name,
                "generic_name": composition,
                "therapeutic_class": therapeutic_class,
                "purpose_en": purpose,
                "side_effects_en": side_effects,
                "timing_instructions": "",
                "known_interactions": interactions,
            }
            key = normalize(name)
            if key not in entries:
                entries[key] = entry
    return entries


def load_medicine_details() -> dict[str, dict]:
    """Load Medicine_Details.csv — secondary source (Uses, Side_effects, Composition)."""
    entries = {}
    if not MEDICINE_DETAILS_CSV.exists():
        print(f"WARNING: {MEDICINE_DETAILS_CSV} not found, skipping")
        return entries
    with MEDICINE_DETAILS_CSV.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = _clean(row.get("Medicine Name", ""))
            if not name:
                continue
            composition = _clean(row.get("Composition", ""))
            uses = _clean(row.get("Uses", ""))
            side_effects = _clean(row.get("Side_effects", ""))

            therapeutic_class = _infer_therapeutic_class(uses) if uses else ""

            # Cap purpose_en at 200 chars to match medicines.csv constraint
            if len(uses) > 200:
                uses = uses[:197] + "..."

            entry = {
                "brand_name": name,
                "generic_name": composition,
                "therapeutic_class": therapeutic_class,
                "purpose_en": uses,
                "side_effects_en": side_effects,
                "timing_instructions": "",
                "known_interactions": "",
            }
            key = normalize(name)
            if key not in entries:
                entries[key] = entry
    return entries


def load_az_dataset() -> dict[str, dict]:
    """Load A_Z dataset — composition only, used for enrichment."""
    entries = {}
    if not AZ_CSV.exists():
        print(f"WARNING: {AZ_CSV} not found, skipping")
        return entries
    with AZ_CSV.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("Is_discontinued", "").strip().upper() == "TRUE":
                continue
            name = _clean(row.get("name", ""))
            if not name:
                continue
            comp1 = _clean(row.get("short_composition1", ""))
            comp2 = _clean(row.get("short_composition2", ""))
            composition = (comp1 + " + " + comp2).strip(" +") if comp2 else comp1

            entry = {
                "brand_name": name,
                "generic_name": composition,
                "therapeutic_class": "",
                "purpose_en": "",
                "side_effects_en": "",
                "timing_instructions": "",
                "known_interactions": "",
            }
            key = normalize(name)
            if key not in entries:
                entries[key] = entry
    return entries


def _infer_therapeutic_class(uses: str) -> str:
    """Best-effort therapeutic class from Uses text."""
    uses_lower = uses.lower()
    mapping = [
        ("antibiotic", ["bacterial infection", "antibiotic"]),
        ("analgesic", ["pain relief", "pain", "analgesic", "headache"]),
        ("antipyretic", ["fever"]),
        ("anti-inflammatory", ["inflammation", "anti-inflammatory", "swelling"]),
        ("antidiabetic", ["diabetes", "blood sugar", "blood glucose"]),
        ("antihypertensive", ["blood pressure", "hypertension"]),
        ("antihistamine", ["allergy", "allergic", "antihistamine", "histamine"]),
        ("antacid", ["acidity", "gastric", "acid reflux", "heartburn", "ulcer"]),
        ("antifungal", ["fungal infection", "antifungal"]),
        ("antiviral", ["viral infection", "antiviral", "hiv"]),
        ("cardiovascular", ["heart", "cardiac", "cholesterol", "angina"]),
        ("respiratory", ["cough", "asthma", "bronchitis", "respiratory"]),
        ("dermatological", ["skin", "acne", "eczema", "derma"]),
        ("ophthalmic", ["eye", "glaucoma", "ophthalmic"]),
        ("thyroid", ["thyroid", "hypothyroid"]),
        ("antidepressant", ["depression", "anxiety", "antidepressant"]),
        ("antiepileptic", ["epilepsy", "seizure", "convulsion"]),
        ("antipsychotic", ["psychosis", "schizophrenia", "bipolar"]),
        ("muscle relaxant", ["muscle spasm", "muscle relaxant"]),
        ("vitamin/supplement", ["vitamin", "supplement", "deficiency", "calcium", "iron"]),
        ("laxative", ["constipation", "laxative"]),
        ("antiemetic", ["nausea", "vomiting", "antiemetic"]),
        ("oncology", ["cancer", "tumor", "chemotherapy", "oncology"]),
        ("immunosuppressant", ["immune", "transplant", "immunosuppressant"]),
    ]
    for cls, keywords in mapping:
        for kw in keywords:
            if kw in uses_lower:
                return cls
    return "general"


# ---------------------------------------------------------------------------
# Merge + Enrich
# ---------------------------------------------------------------------------

def _enrich(target: dict, source: dict) -> bool:
    """Fill empty fields in target from source. Returns True if anything changed."""
    changed = False
    for field in ENRICHABLE:
        if not target.get(field) and source.get(field):
            target[field] = source[field]
            changed = True
    return changed


def merge() -> None:
    """Merge all sources into medicines.csv."""
    # Step 1: Load all sources
    existing = load_existing()
    print(f"[1/4] Existing medicines.csv: {len(existing)} entries")

    mdata = load_medicine_data()
    print(f"[2/4] medicine_data.csv: {len(mdata)} unique entries")

    md = load_medicine_details()
    print(f"[3/4] Medicine_Details.csv: {len(md)} unique entries")

    az = load_az_dataset()
    print(f"[4/4] A_Z dataset (active): {len(az)} unique entries")

    # Step 2: Build merged dict — existing entries always win
    merged = dict(existing)

    # Layer 2: medicine_data.csv (richest new source)
    mdata_added = mdata_enriched = 0
    for key, entry in mdata.items():
        if key in merged:
            if _enrich(merged[key], entry):
                mdata_enriched += 1
        else:
            merged[key] = entry
            mdata_added += 1
    print(f"  medicine_data: +{mdata_added} new, {mdata_enriched} enriched")

    # Layer 3: Medicine_Details.csv (fills gaps medicine_data didn't cover)
    md_added = md_enriched = 0
    for key, entry in md.items():
        if key in merged:
            if _enrich(merged[key], entry):
                md_enriched += 1
        else:
            merged[key] = entry
            md_added += 1
    print(f"  Medicine_Details: +{md_added} new, {md_enriched} enriched")

    # Layer 4: A_Z dataset (enriches generic_name only, no new entries)
    az_enriched = 0
    for key, entry in az.items():
        if key in merged:
            ex = merged[key]
            if not ex.get("generic_name") and entry.get("generic_name"):
                ex["generic_name"] = entry["generic_name"]
                az_enriched += 1
    print(f"  A_Z dataset: {az_enriched} enriched with composition")

    # Step 3: Write merged CSV
    existing_keys = list(existing.keys())
    new_keys = sorted(k for k in merged if k not in existing)
    ordered_keys = existing_keys + new_keys

    # Backup original
    backup = MEDICINES_CSV.with_suffix(".csv.bak")
    if MEDICINES_CSV.exists():
        shutil.copy2(MEDICINES_CSV, backup)
        print(f"\nBackup: {backup.name}")

    with MEDICINES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for key in ordered_keys:
            writer.writerow(merged[key])

    # Stats
    has_purpose = sum(1 for k in merged if merged[k].get("purpose_en"))
    has_side = sum(1 for k in merged if merged[k].get("side_effects_en"))
    has_interactions = sum(1 for k in merged if merged[k].get("known_interactions"))
    has_class = sum(1 for k in merged if merged[k].get("therapeutic_class"))

    print(f"\n{'='*50}")
    print(f"Merged medicines.csv: {len(merged)} total entries")
    print(f"  was {len(existing)}, added {len(merged) - len(existing)} new")
    print(f"  with purpose_en:        {has_purpose} ({has_purpose*100//len(merged)}%)")
    print(f"  with side_effects_en:   {has_side} ({has_side*100//len(merged)}%)")
    print(f"  with known_interactions: {has_interactions} ({has_interactions*100//len(merged)}%)")
    print(f"  with therapeutic_class:  {has_class} ({has_class*100//len(merged)}%)")


def dry_run() -> None:
    """Show counts without writing."""
    existing = load_existing()
    mdata = load_medicine_data()
    md = load_medicine_details()
    az = load_az_dataset()

    ex_keys = set(existing)
    mdata_keys = set(mdata)
    md_keys = set(md)

    print(f"Existing:          {len(existing)}")
    print(f"medicine_data new: {len(mdata_keys - ex_keys)}")
    print(f"Med_Details new:   {len(md_keys - ex_keys - mdata_keys)}")
    print(f"A_Z (enrich only): used for generic_name fill")
    print(f"Projected total:   {len(ex_keys | mdata_keys | md_keys)}")


def main():
    parser = argparse.ArgumentParser(description="Merge drug CSVs into medicines.csv")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts only")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
    else:
        merge()


if __name__ == "__main__":
    main()

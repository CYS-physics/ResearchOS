import os
import difflib

# Directories to search
dirs = [
    "/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers",
    "/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers/drafts"
]
keyword_dirs = [
    "/Users/siksik/내 드라이브/obsidian/ResearchOS/05_keywords",
    "/Users/siksik/내 드라이브/obsidian/ResearchOS/05_keywords/drafts"
]

ALIASES_PATH = "/Users/siksik/내 드라이브/obsidian/ResearchOS/01_zotero_export/aliases.json"

names = set()
keyword_names = set()

# Gather all names
for d in dirs:
    if not os.path.exists(d):
        continue
    for filename in os.listdir(d):
        if filename.endswith(".md") and not filename.endswith(".update.md"):
            name = filename.replace(".md", "")
            names.add(name)

for d in keyword_dirs:
    if not os.path.exists(d):
        continue
    for filename in os.listdir(d):
        if filename.endswith(".md") and not filename.endswith(".update.md"):
            k_name = filename.replace(".md", "")
            keyword_names.add(k_name)

# Find similar names using difflib
names_list = sorted(list(names))
similar_pairs = []

for i in range(len(names_list)):
    for j in range(i + 1, len(names_list)):
        name1 = names_list[i]
        name2 = names_list[j]
        
        # Simple heuristics for name variants (e.g., "John Doe" vs "John A. Doe")
        n1_parts = name1.lower().replace('.', '').split()
        n2_parts = name2.lower().replace('.', '').split()
        
        # If first and last name match, it's a very strong candidate
        if len(n1_parts) >= 2 and len(n2_parts) >= 2:
            if n1_parts[0] == n2_parts[0] and n1_parts[-1] == n2_parts[-1]:
                similar_pairs.append((name1, name2))
                continue
                
        # Fallback to difflib for slight typos
        ratio = difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
        if ratio > 0.85: # Threshold for similarity
            similar_pairs.append((name1, name2))

# Deduplicate pairs
unique_pairs = list(set(similar_pairs))
unique_pairs.sort()

# Also do a quick pass for keyword pluralizations (e.g. "cell" vs "cells")
keyword_list = sorted(list(keyword_names))
unique_kw_pairs = []
for i in range(len(keyword_list)):
    for j in range(i + 1, len(keyword_list)):
        k1 = keyword_list[i]
        k2 = keyword_list[j]
        # Basic plural check
        if (k1 + "s" == k2) or (k1 + "es" == k2):
            unique_kw_pairs.append((k2, k1)) # map plural to singular
        elif (k2 + "s" == k1) or (k2 + "es" == k1):
             unique_kw_pairs.append((k1, k2)) # map plural to singular

unique_kw_pairs = list(set(unique_kw_pairs))

import json

def load_aliases():
    if not os.path.exists(ALIASES_PATH):
        return {"researchers": {}, "keywords": {}}
    try:
        with open(ALIASES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"researchers": {}, "keywords": {}}

def save_aliases(data):
    # Ensure directory exists
    os.makedirs(os.path.dirname(ALIASES_PATH), exist_ok=True)
    with open(ALIASES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

alias_data = load_aliases()
researchers = alias_data.setdefault("researchers", {})
keywords = alias_data.setdefault("keywords", {})

r_added = 0
for p1, p2 in unique_pairs:
    # Prefer shorter name as primary (less initials etc), or whatever logic fits
    if len(p1) > len(p2):
        variant = p1
        primary = p2
    else:
        variant = p2
        primary = p1
        
    if variant not in researchers:
        researchers[variant] = primary
        print(f'Added Researcher Alias: "{variant}" -> "{primary}"')
        r_added += 1

k_added = 0
for variant, primary in unique_kw_pairs:
    if variant not in keywords:
        keywords[variant] = primary
        print(f'Added Keyword Alias: "{variant}" -> "{primary}"')
        k_added += 1

if r_added > 0 or k_added > 0:
    save_aliases(alias_data)
    print(f"\nUpdated aliases.json with {r_added} researchers and {k_added} keywords.")
else:
    print("\nNo new duplicates found.")


import os
import difflib

# Directories to search
dirs = [
    "/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers",
    "/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers/drafts"
]

names = set()

# Gather all names
for d in dirs:
    if not os.path.exists(d):
        continue
    for filename in os.listdir(d):
        if filename.endswith(".md") and not filename.endswith(".update.md"):
            name = filename.replace(".md", "")
            names.add(name)

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

print("Potential Alias Recommendations:")
for p1, p2 in unique_pairs:
    print(f'"{p1}": "{p2}"')

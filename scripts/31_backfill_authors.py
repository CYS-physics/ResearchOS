import json
import os
import re

# Simple one-off script to backfill [[Author Name]] into all previously generated markdown files.
JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
CARD_DIRS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
]

def backfill_authors():
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data if isinstance(data, list) else data.get("items", [])
    library_map = {item.get("citation-key", item.get("id")): item for item in items}
    
    updated_count = 0
    
    for directory in CARD_DIRS:
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            if not filename.endswith(".md"):
                continue
                
            citekey = filename.replace("_deep.md", "").replace(".md", "")
            item = library_map.get(citekey)
            if not item:
                continue
                
            filepath = os.path.join(directory, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Removing the skip check because we want to overwrite old unsanitized 
            # links like [[M. Cristina Marchetti]] with [[M Cristina Marchetti|M. Cristina ...]]
                
            # Build correct author string
            authors = []
            for author in item.get("author", []):
                family = author.get("family", "")
                given = author.get("given", "")
                full_name = f"{given} {family}".strip()
                if full_name:
                    safe_name = "".join(c for c in full_name if c.isalnum() or c in ('-', '_', ' ')).strip()
                    if safe_name != full_name:
                        authors.append(f"[[{safe_name}|{full_name}]]")
                    else:
                        authors.append(f"[[{full_name}]]")
                    
            if not authors:
                continue
                
            author_str = ", ".join(authors)
            
            # Replace in file (using regex to catch variations in the old output)
            new_content = re.sub(r'\*\*Authors:\*\* .*?\n', f'**Authors:** {author_str}\n', content, count=1)
            
            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated_count += 1
                
    print(f"✅ Successfully backfilled '[[First Last]]' author links to {updated_count} existing cards.")

if __name__ == "__main__":
    backfill_authors()

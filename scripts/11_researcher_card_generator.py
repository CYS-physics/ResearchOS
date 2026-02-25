import json
import os
import re
from collections import defaultdict

JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../04_researchers/drafts"))
DEEP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
BRIEF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
MIN_PAPERS_THRESHOLD = 3

def get_card_metadata(citekey: str) -> str:
    rating = ""
    is_deep = False
    
    deep_path = os.path.join(DEEP_DIR, f"{citekey}_deep.md")
    brief_path = os.path.join(BRIEF_DIR, f"{citekey}.md")
    
    if os.path.exists(deep_path):
        is_deep = True
        
    if os.path.exists(brief_path):
        try:
            with open(brief_path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'(⭐+)', content)
            if match:
                rating = f"{match.group(1)} "
        except Exception:
            pass
            
    deep_tag = " [DEEP]" if is_deep else ""
    return f"{rating}{{title}}{deep_tag}"

def generate_researcher_cards():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else data.get("items", [])
    
    # Tally papers per author
    author_papers = defaultdict(list)
    
    for item in items:
        citekey = item.get("citation-key") or item.get("id")
        if not citekey:
            continue
            
        title = item.get("title", "No Title")
        
        for author in item.get("author", []):
            family = author.get("family", "")
            given = author.get("given", "")
            full_name = f"{given} {family}".strip()
            
            if full_name:
                author_papers[full_name].append({
                    "citekey": citekey,
                    "title": title
                })

    # Filter Key Researchers
    key_researchers = {name: papers for name, papers in author_papers.items() if len(papers) >= MIN_PAPERS_THRESHOLD}
    print(f"Found {len(key_researchers)} key researchers (>= {MIN_PAPERS_THRESHOLD} papers).")

    for researcher, papers in key_researchers.items():
        safe_name = "".join(c for c in researcher if c.isalnum() or c in ('-', '_', ' ')).strip()
        filepath = os.path.join(OUTPUT_DIR, f"{safe_name}.md")
        
        # Check if we should overwrite
        should_write = True
        existing_profile = ""
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if "status: unread" not in content:
                print(f"Skipping {researcher} (already exists and doesn't have 'status: unread')")
                should_write = False
            else:
                existing_profile = content.split("---")[-1].strip() # Keep any existing profile text just in case

        if not should_write:
            continue

        print(f"Generating Basic Researcher Card: {researcher} ({len(papers)} papers)")

        # Papers list with bidirectional links to the most advanced card
        links = []
        for p in papers:
            citekey = p['citekey']
            link_target = citekey
            if os.path.exists(os.path.join(DEEP_DIR, f"{citekey}_deep.md")):
                link_target = f"{citekey}_deep"
            elif os.path.exists(os.path.join(BRIEF_DIR, f"{citekey}.md")):
                link_target = f"02_cards/{citekey}|{citekey}"
            elif os.path.exists(os.path.join(QUICK_DIR, f"{citekey}.md")):
                link_target = f"02_cards/quick/{citekey}|{citekey}"
                
            formatted_title = get_card_metadata(citekey).format(title=p['title'])
            links.append(f"- [[{link_target}]] : {formatted_title}")
        
        links_list = "\n".join(links)

        # Write base Researcher Card
        final_md = f"""---
aliases: ["{researcher}"]
tags: ["researcher"]
status: unread
paper_count: {len(papers)}
---
# {researcher}

## Papers in Library
{links_list}

---
{existing_profile}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_md)

        print(f"  ✅ Saved {safe_name}.md")

if __name__ == "__main__":
    generate_researcher_cards()

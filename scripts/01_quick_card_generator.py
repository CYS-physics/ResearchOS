import json
import os
import re

JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brain"))

def load_keywords():
    keywords = []
    if not os.path.exists(BRAIN_DIR):
        print(f"Warning: Brain directory not found at {BRAIN_DIR}")
        return keywords
        
    for filename in os.listdir(BRAIN_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(BRAIN_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if "## 3. Important Keywords" in content:
                kw_section = content.split("## 3. Important Keywords")[1]
                # To prevent bleeding into other sections
                if "##" in kw_section:
                    kw_section = kw_section.split("##")[0]
                for word in kw_section.split():
                    if word.startswith('#'):
                        kw = word.strip('#, \n')
                        if kw and kw not in keywords:
                            keywords.append(kw)
        except Exception as e:
            print(f"Error reading brain file {filename}: {e}")
            
    return keywords

def generate_quick_cards():
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # BetterBibTeX export is usually a list of items
    if isinstance(data, list):
        items = data
    else:
        items = data.get("items", [])
        
    keywords = load_keywords()
    count = 0
    
    for item in items:
        citekey = item.get("citation-key") or item.get("id")
        if not citekey or citekey in ["AddonItem", "zotero-item-2"]:
            continue
            
        title = item.get("title", "No Title")
        abstract = item.get("abstract", "No abstract available.")
        
        # Extract authors
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
        author_str = ", ".join(authors) if authors else "Unknown"
        
        # Extract year
        year = "Unknown"
        if "issued" in item and "date-parts" in item["issued"]:
            try:
                year = str(item["issued"]["date-parts"][0][0])
            except (IndexError, TypeError):
                year = "Unknown"

        # Extract URL
        url = item.get("URL", item.get("url", ""))

        # Extract journal
        journal = item.get("container-title", "")
        if not journal:
            # Fallback to check if it's an ArXiv preprint
            publisher = item.get("publisher", "")
            archive = item.get("archive", "")
            if "arxiv" in publisher.lower() or "arxiv" in archive.lower() or "arxiv" in url.lower():
                journal = "arXiv Preprint"
            else:
                journal = "Unknown"
    
            
        # Tag matching
        matched_tags = ["quickcard"]
        
        if abstract == "No abstract available.":
            matched_tags.append("noabstract")

        abstract_lower = abstract.lower()
        title_lower = title.lower()
        search_text = title_lower + " " + abstract_lower
        
        for kw in keywords:
            kw_clean = kw.replace('_', ' ').lower()
            if kw_clean in search_text or kw.lower() in search_text:
                matched_tags.append(kw)
                
        tags_yaml = ", ".join(f'"{t}"' for t in matched_tags)
            
        # Create markdown content
        md_content = f"""---
aliases: ["{citekey}"]
tags: [{tags_yaml}]
status: unread
---
# {title}

**Authors:** {author_str}
**Year:** {year}
**Journal:** {journal}
**URL:** {url if url else "N/A"}

## Abstract (Preview)
{abstract}

---
*Created by ResearchOS Quick Card Generator*
"""
        
        # Save to markdown file
        safe_citekey = "".join(c for c in citekey if c.isalnum() or c in ('-', '_')).strip()
        filepath = os.path.join(OUTPUT_DIR, f"{safe_citekey}.md")
        
        # Overwrite logic
        should_write = True
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as existing_f:
                existing_content = existing_f.read()
            if '"noabstract"' not in existing_content and "noabstract" not in existing_content:
                print(f"Skipping {safe_citekey} (already exists and has abstract)")
                should_write = False
            else:
                print(f"Overwriting {safe_citekey} (previously had no abstract)")
        
        if should_write:
            try:
                with open(filepath, "w", encoding="utf-8") as out_f:
                    out_f.write(md_content)
                count += 1
            except Exception as e:
                print(f"Error writing {filepath}: {e}")

    print(f"Successfully generated {count} Quick Cards in {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_quick_cards()

import os
import datetime

QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
INDEX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../06_indexes"))
INDEX_FILE = os.path.join(INDEX_DIR, "Preprints.md")

def generate_preprint_index():
    if not os.path.exists(QUICK_DIR):
        print(f"Error: {QUICK_DIR} not found.")
        return
        
    os.makedirs(INDEX_DIR, exist_ok=True)
    
    preprints = []
    
    for filename in os.listdir(QUICK_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(QUICK_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Extract Journal and Title
        import re
        journal_match = re.search(r'\*\*Journal:\*\*\s*(.+)', content)
        title_match = re.search(r'#\s*(.+)', content)
        year_match = re.search(r'\*\*Year:\*\*\s*(.+)', content)
        
        if journal_match:
            journal = journal_match.group(1).strip().lower()
            if "arxiv" in journal or "preprint" in journal or "biorxiv" in journal or "medrxiv" in journal:
                citekey = filename.replace(".md", "")
                title = title_match.group(1).strip() if title_match else "Unknown Title"
                year = year_match.group(1).strip() if year_match else "Unknown"
                
                deep_exists = os.path.exists(os.path.join(os.path.dirname(__file__), f"../03_deep/{citekey}_deep.md"))
                status_icon = "🧠 " if deep_exists else "📄 "
                
                preprints.append({
                    "citekey": citekey,
                    "title": title,
                    "year": year,
                    "icon": status_icon
                })
                
    # Sort by year descending, then alphabetically
    preprints.sort(key=lambda x: (x["year"], x["title"]), reverse=True)
    
    # Generate Markdown
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = f"""---
tags: [index, preprints]
---
# Preprints
*Last updated: {now}*

This is an automatically generated list of all papers in your library that are currently flagged as preprints (e.g., arXiv). They may have formal published equivalents that require updating!

**Legend**
🧠 = Has Deep Card | 📄 = Has Quick/Brief Card

## Unverified Preprints

"""
    for p in preprints:
        md += f"1. {p['icon']}[[{p['citekey']}]] : {p['title']} ({p['year']})\n"
        
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(md)
        
    print(f"Generated preprint index at {INDEX_FILE} with {len(preprints)} entries.")

if __name__ == "__main__":
    generate_preprint_index()

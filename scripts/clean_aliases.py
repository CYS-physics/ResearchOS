import os
import json

ALIASES_PATH = "/Users/siksik/내 드라이브/obsidian/ResearchOS/01_zotero_export/aliases.json"
RESEARCHERS_DIR = "/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers/drafts"
KEYWORDS_DIR = "/Users/siksik/내 드라이브/obsidian/ResearchOS/05_keywords/drafts"

def clean_old_aliases():
    if not os.path.exists(ALIASES_PATH):
        print("Aliases file not found.")
        return

    with open(ALIASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    researcher_aliases = data.get("researchers", {})
    keyword_aliases = data.get("keywords", {})

    deleted_count = 0

    # Clean Researchers
    print("Cleaning Researcher Aliases...")
    for variant, primary in researcher_aliases.items():
        if variant == primary:
            continue
            
        safe_variant = "".join(c for c in variant if c.isalnum() or c in ('-', '_', ' ')).strip()
        filepath = os.path.join(RESEARCHERS_DIR, f"{safe_variant}.md")
        
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"  🗑️ Deleted old variant: {safe_variant}.md (Mapped to {primary})")
            deleted_count += 1
            
    # Clean Keywords
    print("\nCleaning Keyword Aliases...")
    for variant, primary in keyword_aliases.items():
        if variant == primary:
            continue
            
        safe_variant = "".join(c for c in variant if c.isalnum() or c in ('-', '_')).strip()
        filepath = os.path.join(KEYWORDS_DIR, f"{safe_variant}.md")
        
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"  🗑️ Deleted old variant: {safe_variant}.md (Mapped to {primary})")
            deleted_count += 1

    print(f"\nCleanup complete. Removed {deleted_count} obsolete files.")

if __name__ == "__main__":
    clean_old_aliases()

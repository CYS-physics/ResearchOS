import json
import os
import re
import urllib.request
from xml.etree import ElementTree

JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
RESEARCHERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../04_researchers"))
KEYWORDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../05_keywords"))

def flag_affected_profiles_as_modified(citekey: str):
    """Flags any researcher or keyword profile containing this citekey as modified."""
    affected_profiles = []
    search_dirs = [RESEARCHERS_DIR, KEYWORDS_DIR]
    
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            if not filename.endswith(".md") or filename.endswith(".update.md"):
                continue
                
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                if citekey in content:
                    if "status: deep_processed" in content:
                        new_content = content.replace("status: deep_processed", "status: modified")
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        affected_profiles.append(filename.replace(".md", ""))
            except Exception as e:
                print(f"    Error reading profile for flagging {filename}: {e}")
                
    if affected_profiles:
        print(f"    Flagged profiles as modified: {', '.join(affected_profiles)}")

def check_arxiv_published(arxiv_id):
    """Queries ArXiv API to see if the paper has a DOI (indicating publication)."""
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ResearchOS-Bot'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            root = ElementTree.fromstring(xml_data)
            
            # ArXiv namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
            
            entry = root.find('atom:entry', ns)
            if entry is not None:
                doi_elem = entry.find('arxiv:doi', ns)
                journal_ref_elem = entry.find('arxiv:journal_ref', ns)
                
                published_doi = doi_elem.text if doi_elem is not None else None
                journal_ref = journal_ref_elem.text if journal_ref_elem is not None else None
                
                if published_doi or journal_ref:
                    return {
                        "doi": published_doi,
                        "journal": journal_ref or "Published via ArXiv API Check (DOI found)"
                    }
    except Exception as e:
        print(f"    Error querying ArXiv API for {arxiv_id}: {e}")
    return None

def check_crossref_published(doi):
    """Queries CrossRef to see if this DOI indicates a preprint that has a formal published equivalent."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'mailto:researchos@example.com'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            message = data.get("message", {})
            
            # Check relation links where it might point to a published version
            relations = message.get("relation", {})
            if "is-preprint-of" in relations:
                published_items = relations["is-preprint-of"]
                if published_items: # List of items this is a preprint of
                    published_doi = published_items[0].get("id")
                    
                    # If we found a published DOI, query CrossRef again to get the journal name
                    if published_doi:
                        pub_url = f"https://api.crossref.org/works/{published_doi}"
                        pub_req = urllib.request.Request(pub_url, headers={'User-Agent': 'mailto:researchos@example.com'})
                        with urllib.request.urlopen(pub_req, timeout=10) as pub_resp:
                            pub_data = json.loads(pub_resp.read())
                            pub_msg = pub_data.get("message", {})
                            container_title = pub_msg.get("container-title", [])
                            journal = container_title[0] if container_title else "Unknown Journal"
                            
                            return {
                                "doi": published_doi,
                                "journal": journal
                            }
    except Exception as e:
        # CrossRef might return 404 for DOIs they don't host
        pass
    return None

def check_publication_updates():
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else data.get("items", [])
    updates_found = 0

    print("Checking known preprints for formal publication status...")

    for item in items:
        citekey = item.get("citation-key") or item.get("id")
        if not citekey:
            continue
            
        safe_citekey = "".join(c for c in citekey if c.isalnum() or c in ('-', '_')).strip()
        quick_card_path = os.path.join(QUICK_DIR, f"{safe_citekey}.md")
        
        if not os.path.exists(quick_card_path):
            continue
            
        # Read current metadata from the markdown card
        with open(quick_card_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Extract current mapped journal
        journal_match = re.search(r'\*\*Journal:\*\*\s*(.+)', md_content)
        current_journal = journal_match.group(1).strip() if journal_match else ""

        # Only care if the card currently thinks it's a preprint
        if "arXiv Preprint" in current_journal or "preprint" in current_journal.lower() or "biorxiv" in current_journal.lower() or "medrxiv" in current_journal.lower():
            
            published_info = None
            
            # Check Zotero metadata first for ArXiv ID
            arxiv_id = None
            archive = item.get("archive", "")
            archive_location = item.get("archive_location", "")
            item_url = item.get("URL", item.get("url", ""))
            
            if "arxiv" in archive.lower():
                arxiv_id = archive_location.replace("arXiv:", "").split("v")[0] # Remove version if present
            elif "arxiv.org/abs/" in item_url.lower():
                arxiv_id = item_url.split("arxiv.org/abs/")[-1].split("v")[0]
                
            if arxiv_id:
                published_info = check_arxiv_published(arxiv_id)
                
            # If not found via ArXiv, fall back to checking CrossRef with DOI (if available)
            if not published_info:
                doi = item.get("DOI", "")
                if doi:
                    published_info = check_crossref_published(doi)
                    
            if published_info:
                published_journal = published_info["journal"]
                published_doi = published_info.get("doi", "")
                
                print(f"\n🎉 [RENEW SUGGESTION] {citekey} has been published!")
                print(f"    Was: {current_journal}")
                print(f"    Now: {published_journal}")
                if published_doi:
                    print(f"    DOI: {published_doi}")
                print(f"    *Consider deleting {citekey}_deep.md to regenerate the analysis with the final paper.*")
                
                # Update the quick card markdown to reflect the new journal
                # Ensure we handle potentially missing journal references from arxiv api gracefully
                new_md_content = re.sub(
                    r'(\*\*Journal:\*\*\s*)(.+)', 
                    f"\\1{published_journal} (Published Update)", 
                    md_content
                )
                
                # Update URL if we have a published DOI
                if published_doi:
                    new_url = f"https://doi.org/{published_doi}"
                    new_md_content = re.sub(
                        r'(\*\*URL:\*\*\s*)(.+)',
                        f"\\1{new_url}",
                        new_md_content
                    )
                
                with open(quick_card_path, "w", encoding="utf-8") as f:
                    f.write(new_md_content)
                    
                # Flag profiles referencing this citekey
                flag_affected_profiles_as_modified(safe_citekey)
                
                updates_found += 1
                
    if updates_found == 0:
        print("No new preprint publications found.")
    else:
        print(f"\nCaught {updates_found} preprints that were formally published.")

if __name__ == "__main__":
    check_publication_updates()

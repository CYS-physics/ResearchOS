import os
import re
import urllib.request
import json
from bs4 import BeautifulSoup

QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))

def fetch_abstract_from_crossref(doi: str) -> str:
    """Attempts to fetch an abstract from the CrossRef API using a DOI."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'mailto:researchos@example.com'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            message = data.get("message", {})
            abstract_xml = message.get("abstract")
            
            if abstract_xml:
                # CrossRef abstracts are often wrapped in JATS XML (e.g., <jats:p>abstract here</jats:p>)
                soup = BeautifulSoup(abstract_xml, 'html.parser')
                clean_text = soup.get_text(separator=' ', strip=True)
                return clean_text
    except Exception as e:
        pass
        
    return None

def fetch_abstract(url: str) -> str:
    """Attempts to fetch an abstract from common academic meta tags on the given URL."""
    try:
        # Generic user agent with Accept headers to avoid basic blocks
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. Standard Highwire Press tags (Google Scholar indexing standard used by Nature, Science, ArXiv, etc.)
            meta_abstract = soup.find('meta', attrs={'name': 'citation_abstract'})
            if meta_abstract and meta_abstract.get('content'):
                return meta_abstract['content'].strip()
                
            # 2. Dublin Core description
            dc_desc = soup.find('meta', attrs={'name': 'dc.description'}) or soup.find('meta', attrs={'name': 'DC.Description'})
            if dc_desc and dc_desc.get('content'):
                return dc_desc['content'].strip()
                
            # 3. OpenGraph description (Generic fallback, sometimes just a snippet, not full abstract)
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content') and len(og_desc['content']) > 150: # Ensure it's not a tiny generic tagline
                return og_desc['content'].strip()
                
            # 4. Standard description
            desc = soup.find('meta', attrs={'name': 'description'})
            if desc and desc.get('content') and len(desc['content']) > 150:
                return desc['content'].strip()
                
            # 5. Fallback for APS, JPS, and others: search for HTML containers with "abstract" in class or id
            for tag in soup.find_all(['section', 'div', 'p']):
                tag_class = tag.get('class', [])
                if isinstance(tag_class, list):
                    tag_class = ' '.join(tag_class).lower()
                tag_id = tag.get('id', '').lower()
                
                if 'abstract' in tag_class or 'abstract' in tag_id:
                    # Avoid extracting just a heading
                    text = tag.get_text(separator=' ', strip=True)
                    if len(text) > 150:
                        # remove the word "abstract" if it's right at the start
                        text = re.sub(r'(?i)^abstract\s*', '', text)
                        return text
                        
    except urllib.error.HTTPError as e:
        print(f"      [Failed] Error fetching {url}: HTTP Error {e.code}")
        # If forbidden (APS, IOP, etc.), try to extract DOI and use CrossRef
        if e.code in [403, 401] and ('doi.org/' in url or '/doi/' in url):
            doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)', url)
            if doi_match:
                doi = doi_match.group(1)
                print(f"      Attempting CrossRef fallback for DOI: {doi}")
                return fetch_abstract_from_crossref(doi)
                
    except Exception as e:
        print(f"      [Failed] Error fetching {url}: {e}")
        
    return None

def process_missing_abstracts():
    if not os.path.exists(QUICK_DIR):
        print(f"Error: {QUICK_DIR} not found.")
        return

    fetched_count = 0
    print("Scanning Quick Cards for missing abstracts...")

    for filename in os.listdir(QUICK_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(QUICK_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Check if this card needs an abstract fetched
            if '"noabstract"' in content or "noabstract" in content or "No abstract available." in content:
                # Extract the URL from the card
                url_match = re.search(r'\*\*URL:\*\*\s*(http.+)', content)
                if not url_match:
                    continue
                    
                url = url_match.group(1).strip()
                print(f"  Attempting to fetch abstract for {filename} from {url}...")
                
                abstract_text = fetch_abstract(url)
                
                if abstract_text:
                    # Overwrite the abstract
                    new_content = content.replace("No abstract available.", abstract_text)
                    
                    # Remove the noabstract tag
                    new_content = new_content.replace('"noabstract", ', '').replace(', "noabstract"', '').replace('"noabstract"', '')
                    new_content = new_content.replace('noabstract, ', '').replace(', noabstract', '').replace('noabstract', '')
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                        
                    fetched_count += 1
                    print(f"      ✅ Successfully populated abstract for {filename}!")
                else:
                    print(f"      ❌ Could not extract abstract from meta tags.")
                    
        except Exception as e:
            print(f"  Error reading {filename}: {e}")

    print(f"\nSuccessfully scraped and injected {fetched_count} missing abstracts.")

if __name__ == "__main__":
    # Note: Requires beautifulsoup4. Ensure it's installed via pip install beautifulsoup4
    try:
        from bs4 import BeautifulSoup
        process_missing_abstracts()
    except ImportError:
        print("Error: beautifulsoup4 is not installed. Please run: pip install beautifulsoup4")

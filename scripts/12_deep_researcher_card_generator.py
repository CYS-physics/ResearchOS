import json
import os
import re
import time
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
import openai
from google import genai

# Load environment variables
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(dotenv_path=env_path)

# Initialize API clients
gemini_keys = [v for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v.strip()]
gemini_clients = [genai.Client(api_key=key) for key in gemini_keys]
current_gemini_index = 0

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
PEOPLE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../04_researchers/drafts"))
KEY_PEOPLE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../04_researchers"))
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brain"))

DEEP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
BRIEF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))

def run_llm_prompt(prompt: str) -> str:
    global current_gemini_index
    
    # Try Gemini clients first, rotating if we hit a 429 quota exhaustion
    while current_gemini_index < len(gemini_clients):
        client = gemini_clients[current_gemini_index]
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                print(f"  Gemini API Key {current_gemini_index + 1} exhausted (429). Rotating to next key...")
                current_gemini_index += 1
                continue # Try the next key in the loop
            else:
                print(f"  Gemini API failed: {e}. Falling back to OpenAI...")
                break # Non-quota error, jump to OpenAI fallback
                
    if current_gemini_index >= len(gemini_clients) and gemini_clients:
        print("  All Gemini API keys exhausted.")
            
    # Try OpenAI fallback
    if openai_client:
        try:
            # We enforce a timeout so it doesn't hang forever, and handle retries manually below
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  OpenAI API failed: {e}")
            if "429" in str(e):
                raise Exception("RATE_LIMIT") # Signal the wrapper to retry
            
    return ""

def run_llm_prompt_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Wrapper to handle 429 Rate Limit Exhaustion."""
    base_delay = 10  # Start with 10s delay

    for attempt in range(max_retries):
        try:
            result = run_llm_prompt(prompt)
            if result:
                return result
            # If result is empty string but NO error was raised, it just completely failed both APIs
            # without it being a 429. Break out so we don't retry forever on auth errors.
            break
        except Exception as e:
            if "RATE_LIMIT" in str(e):
                delay = base_delay * (2 ** attempt)
                if attempt < max_retries - 1:
                    print(f"  [Rate Limit Hit] Sleeping for {delay} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
                else:
                    print(f"  [Rate Limit Hit] Max retries ({max_retries}) reached. Skipping.")
                    return ""
            else:
                return ""
    return ""

import brain_utils

def load_research_context() -> str:
    return brain_utils.load_brain_context(BRAIN_DIR)

def generate_deep_researcher_cards():
    research_context = load_research_context()

    os.makedirs(KEY_PEOPLE_DIR, exist_ok=True)

    if not os.path.exists(PEOPLE_DIR) and not os.path.exists(KEY_PEOPLE_DIR):
        print("No researcher cards found. Run researcher_card_generator.py first.")
        return

    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else data.get("items", [])
    library_map = {item.get("citation-key", item.get("id")): item for item in items}

    processed_count = 0

    search_dirs = [PEOPLE_DIR, KEY_PEOPLE_DIR]
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            if not filename.endswith(".md") or filename.endswith(".update.md"):
                continue
                
            filepath = os.path.join(directory, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if "status: deep\n" not in content and "status: deep\r" not in content and "status: deep" not in content.splitlines() and \
               "status: modified\n" not in content and "status: modified\r" not in content and "status: modified" not in content.splitlines():
                continue

            researcher = filename.replace(".md", "")
            update_filepath = os.path.join(directory, "_updates", f"{researcher}.update.md")
            print(f"\nProcessing Deep Researcher Card: {researcher}...")

            # Extract citekeys from the card to get abstracts, observing [PROCESSED] tags
            # Links look like: - [[citekey|Display]] or - [[citekey]] [PROCESSED] : Title
            citekeys = re.findall(r'-\s+\[\[(.*?)\]\](.*)', content)
            
            abstracts_text = []
            new_papers_count = 0
            
            for ck_match, rest_of_line in citekeys:
                if "[PROCESSED]" in rest_of_line:
                    continue # Skip already processed papers
                    
                new_papers_count += 1
                link_target = ck_match.split("|")[0]
                base_ck = link_target.split("/")[-1].replace("_deep", "").replace(".md", "")
                
                deep_path = os.path.join(DEEP_DIR, f"{base_ck}_deep.md")
                brief_path = os.path.join(BRIEF_DIR, f"{base_ck}.md")
                quick_path = os.path.join(QUICK_DIR, f"{base_ck}.md")
                
                paper_content = ""
                
                if os.path.exists(deep_path):
                    with open(deep_path, "r", encoding="utf-8") as pdf_f:
                        pdf_content = pdf_f.read()
                    parts = pdf_content.split("---")
                    if len(parts) >= 3:
                        main_body = "---".join(parts[2:]).strip()
                        # Removing raw abstract from deep if it exists to strictly save tokens
                        if "## Abstract" in main_body and "## 1." in main_body:
                            main_body = "## 1." + main_body.split("## 1.", 1)[1]
                        paper_content = f"Title: {base_ck} (Deep AI Synthesis)\n{main_body}"
                elif os.path.exists(brief_path):
                    with open(brief_path, "r", encoding="utf-8") as brief_f:
                        brief_content = brief_f.read()
                    parts = brief_content.split("---")
                    if len(parts) >= 3:
                        main_body = "---".join(parts[2:]).strip()
                        # Truncate abstract to save tokens since AI questions are at bottom
                        if "## Abstract" in main_body and "## AI Analysis" in main_body:
                            main_body = "## AI Analysis" + main_body.split("## AI Analysis", 1)[1]
                        paper_content = f"Title: {base_ck} (Brief AI Synthesis)\n{main_body}"
                else:
                    item = library_map.get(base_ck)
                    if item:
                        title = item.get("title", "No Title")
                        abstract = item.get("abstract", "No abstract available.")
                        paper_content = f"Title: {title}\nAbstract: {abstract}"
                        
                if paper_content:
                    abstracts_text.append(paper_content)

            papers_text = "\n\n".join(abstracts_text)
            
            if new_papers_count == 0:
                print(f"  No new unprocessed papers found for {researcher}. Skipping...")
                # Ensure status is reset if it was simply modified but no new papers are found
                if "status: modified" in content:
                    new_content = re.sub(r'\bstatus:\s*modified\b', 'status: deep_processed', content)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                continue

            # Extract existing profile content beneath the horizontal rule
            parts = content.split("---")
            previous_profile = ""
            manual_notes = "\n\n## ✍️ Manual Notes\n*(Add your manual notes here - this section will not be overwritten by AI)*\n"
            if len(parts) >= 3:
                # Reconstruct content after frontmatter
                main_body = "---".join(parts[2:]) 
                sub_parts = main_body.split("---") # Look for the h-rule separating papers and profile
                if len(sub_parts) > 1:
                    previous_profile = "---".join(sub_parts[1:]).strip()
                    if "## ✍️ Manual Notes" in previous_profile:
                        parts_manual = previous_profile.split("## ✍️ Manual Notes", 1)
                        previous_profile = parts_manual[0].strip()
                        manual_notes = "\n\n## ✍️ Manual Notes" + parts_manual[1]

            prompt = f'''You are an expert academic research assistant maintaining a database of key researchers.
Your task is to analyze the abstracts of NEWLY ADDED papers by a researcher, and INCREMENTALLY UPDATE their existing profile based strictly on my personal research context.
Do NOT rewrite the entire profile from scratch if a "Previous Profile" exists. Instead, integrate the new insights into the existing sections, expanding or refining them as necessary.

### Researcher Name: {researcher}

### My Research Context:
{research_context}

### NEW Papers by this Researcher (to be added to the profile):
{papers_text}

### Previous Profile (if any):
{previous_profile if previous_profile else "(First time generating this profile)"}

### Task:
Output valid Markdown format. Do not wrap it in ```markdown codeblocks. Provide EXACTLY these sections, updating the previous content with insights from the new papers:

## 1. Core Keywords
(Provide 5-8 specific keywords or tags representing their overarching research focus. Format them as hashtags separated by spaces, e.g., #active_matter #machine_learning. Retain and update existing tags.)

## 2. Key Research Questions & Focus
(In 2-3 paragraphs, summarize what fundamental questions this researcher is trying to answer across their body of work. Integrate new findings into the existing summary. Highlight specifically how their focus overlaps with my 'Key Questions' or 'Core Interests'.)

## 3. Update Summary
(In 1 short paragraph, summarize exactly what is new or what has changed in their research focus *based specifically on the new papers provided above*. If the Previous profile is empty, simply state "Initial profile generated summarizing {new_papers_count} papers.")
'''
            print(f"  Sending to LLM API...")
            ai_response = run_llm_prompt_with_retry(prompt)
            
            if not ai_response:
                print(f"  Failed. Skipping {researcher}.")
                continue
                
            # Parse output properly to separate the update summary
            try:
                split_parts = ai_response.split("## 3. Update Summary")
                profile_content = split_parts[0].strip()
                update_summary = split_parts[1].strip() if len(split_parts) > 1 else "Update summary not generated properly."
            except Exception:
                profile_content = ai_response
                update_summary = "Failed to parse update summary."

            # Replace status
            new_content = re.sub(r'\bstatus:\s*deep\b', 'status: deep_processed', content)
            new_content = re.sub(r'-\s*status:\s*deep\b', '- status: deep_processed', new_content)
            new_content = re.sub(r'\bstatus:\s*modified\b', 'status: deep_processed', new_content)
            new_content = re.sub(r'-\s*status:\s*modified\b', '- status: deep_processed', new_content)
            
            # Add [PROCESSED] tags to the links we just analyzed
            def add_processed_tag(match):
                full_match = match.group(0)
                link_text = match.group(1)
                rest_of_line = match.group(2)
                if "[PROCESSED]" not in rest_of_line:
                    # In case there's already some text like " : Title", insert [PROCESSED] before the colon
                    if ":" in rest_of_line:
                        parts = rest_of_line.split(":", 1)
                        return f"- [[{link_text}]] [PROCESSED] :{parts[1]}"
                    else:
                        return f"- [[{link_text}]] [PROCESSED]{rest_of_line}"
                return full_match
                
            new_content = re.sub(r'-\s+\[\[(.*?)\]\]([^\n]*)', add_processed_tag, new_content)

            # Add key_researchers tag
            if "key_researchers" not in new_content:
                new_content = new_content.replace('tags: ["researcher"]', 'tags: ["researcher", "key_researchers"]')
                new_content = new_content.replace('tags:\n  - researcher', 'tags:\n  - researcher\n  - key_researchers')
            
            # Replace bottom section containing old profile
            front_parts = new_content.split("---")
            if len(front_parts) >= 3:
                main_body = "---".join(front_parts[2:])
                body_parts = main_body.split("---")
                top_body = body_parts[0].rstrip()
            else:
                top_body = new_content
                
            final_md = f"---{front_parts[1]}---\n{top_body}{manual_notes}\n\n---\n**Update History:** [[{researcher}.update|View Logs]]\n\n{profile_content}\n"

            out_filepath = os.path.join(KEY_PEOPLE_DIR, f"{researcher}.md")
            out_update_dir = os.path.join(KEY_PEOPLE_DIR, "_updates")
            os.makedirs(out_update_dir, exist_ok=True)
            out_update_filepath = os.path.join(out_update_dir, f"{researcher}.update.md")

            with open(out_filepath, "w", encoding="utf-8") as f:
                f.write(final_md)

            # Append to Update file
            update_entry = f"\n### {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (New Papers Analyzed: {new_papers_count})\n{update_summary}\n"
            update_content = ""
            if not os.path.exists(out_update_filepath):
                update_content = f"**Main Profile:** [[{researcher}]]\n\n"
            with open(out_update_filepath, "a", encoding="utf-8") as f:
                f.write(update_content + update_entry)

            # Remove old files if they are being moved from 05_cards_people
            # Remove old files if they are being moved from 04_researchers/drafts
            if directory != KEY_PEOPLE_DIR:
                try:
                    # Update status of the original file instead of removing it,
                    # or if the logic is to remove it because it's moving from drafts,
                    # then the original file status logic is not needed for the new file,
                    # but we are processing a file that has `status: deep` or `status: modified`
                    # so we need to make sure the original file status is updated.
                    # Since it is removing the file, we update the original 'f' file which is 'filepath'
                    # which is what's being removed. So updating the status of 'filepath' is just
                    # keeping the logic of line 203.
                    os.remove(filepath)
                    if os.path.exists(update_filepath):
                        os.remove(update_filepath)
                except Exception as e:
                    print(f"  Warning: could not remove old file {filepath}: {e}")
            else:
                 with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)

            print(f"  ✅ Updated {researcher}.md and appended to .update.md in 04_researchers")
            processed_count += 1
            
    if processed_count == 0:
        print("No researcher cards found with 'status: deep'.")
    else:
        print(f"\nFinished processing {processed_count} deep researcher cards.")

if __name__ == "__main__":
    generate_deep_researcher_cards()

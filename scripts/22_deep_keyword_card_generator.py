import json
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
import openai
from google import genai

# Load environment variables
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(dotenv_path=env_path)

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
KEYWORDS_DRAFTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../05_keywords/drafts"))
KEYWORDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../05_keywords"))
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brain"))

DEEP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
BRIEF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))

def run_llm_prompt(prompt: str) -> str:
    if client:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            print(f"  Gemini API failed: {e}. Falling back to OpenAI...")
            
    if openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  OpenAI API failed: {e}")
            if "429" in str(e):
                raise Exception("RATE_LIMIT")

    return ""

def run_llm_prompt_with_retry(prompt: str, max_retries: int = 3) -> str:
    base_delay = 10
    for attempt in range(max_retries):
        try:
            result = run_llm_prompt(prompt)
            if result:
                return result
            break
        except Exception as e:
            if "RATE_LIMIT" in str(e):
                delay = base_delay * (2 ** attempt)
                if attempt < max_retries - 1:
                    print(f"  [Rate Limit Hit] Sleeping for {delay} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
                else:
                    print(f"  [Rate Limit] Max retries reached.")
                    return ""
            else:
                return ""
    return ""

def load_research_context() -> str:
    if not os.path.exists(BRAIN_DIR):
        print(f"Warning: Brain directory not found at {BRAIN_DIR}")
        return "No specific user context provided."
        
    context_parts = []
    for filename in os.listdir(BRAIN_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(BRAIN_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                context_parts.append(f"--- Context from {filename} ---\n{content}\n")
        except Exception as e:
            print(f"Error reading brain file {filename}: {e}")
            
    if not context_parts:
        return "No specific user context provided."
        
    return "\n".join(context_parts)

def generate_deep_keyword_cards():
    research_context = load_research_context()

    os.makedirs(KEYWORDS_DIR, exist_ok=True)

    if not os.path.exists(KEYWORDS_DRAFTS_DIR) and not os.path.exists(KEYWORDS_DIR):
        print("No keyword cards found. Run keyword_card_generator.py first.")
        return

    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else data.get("items", [])
    library_map = {item.get("citation-key", item.get("id")): item for item in items}

    processed_count = 0

    search_dirs = [KEYWORDS_DRAFTS_DIR, KEYWORDS_DIR]
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            if not filename.endswith(".md") or filename.endswith(".update.md"):
                continue
                
            filepath = os.path.join(directory, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if "status: deep\n" not in content and "status: deep\r" not in content and "status: deep" not in content.splitlines():
                continue

            keyword = filename.replace(".md", "")
            update_filepath = os.path.join(directory, f"{keyword}.update.md")
            print(f"\nProcessing Deep Keyword Card: {keyword}...")

            # Extract citekeys from the card to get abstracts
            # Format: - [[folder/citekey|citekey]] : Title
            citekeys = re.findall(r'- \[\[(.*?)\]\]', content)
            
            abstracts_text = []
            for ck in citekeys:
                link_target = ck.split("|")[0]
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

            # Extract existing profile content beneath the horizontal rule
            parts = content.split("---")
            previous_profile = ""
            if len(parts) >= 3:
                main_body = "---".join(parts[2:]) 
                sub_parts = main_body.split("---")
                if len(sub_parts) > 1:
                    previous_profile = "---".join(sub_parts[1:]).strip()

            prompt = f'''You are an expert academic research assistant maintaining a database of key research concepts.
Your task is to analyze the consolidated abstracts of papers associated with the keyword "{keyword}" and synthesize a deep conceptual profile based strictly on my personal research context.

### Keyword: {keyword}

### My Research Context:
{research_context}

### Papers Tagged with this Keyword:
{papers_text}

### Previous Profile (if any):
{previous_profile if previous_profile else "(First time generating this profile)"}

### Task:
Output valid Markdown format. Do not wrap it in ```markdown codeblocks. Provide EXACTLY these sections:

## 1. Core Definition & Context
(Define the concept specifically in the context of my 'Key Questions' or 'Core Interests'. How does my research area utilize or define this keyword, based on the provided papers?)

## 2. Key Debates or Open Questions
(Based on the abstracts, what are the primary challenges, debates, or active areas of inquiry surrounding this concept?)

## 3. Related Techniques & Methods
(What specific methodological approaches, theoretical frameworks, or experimental techniques are frequently used to study this concept in the provided literature?)

## 4. Update Summary
(In 1 short paragraph, summarize what is new or what has changed in the understanding of this concept compared to the "Previous Profile". Compare the 'Previous Profile' with what you've learned from the abstracts above. If the Previous profile is empty, simply state "Initial profile generated summarizing X papers.")
'''
            print(f"  Sending to LLM API...")
            ai_response = run_llm_prompt_with_retry(prompt)
            
            if not ai_response:
                print(f"  Failed. Skipping {keyword}.")
                continue
                
            # Parse output properly to separate the update summary
            try:
                split_parts = ai_response.split("## 4. Update Summary")
                profile_content = split_parts[0].strip()
                update_summary = split_parts[1].strip() if len(split_parts) > 1 else "Update summary not generated properly."
            except Exception:
                profile_content = ai_response
                update_summary = "Failed to parse update summary."

            # Replace status
            new_content = content.replace("status: deep", "status: deep_processed")
            new_content = new_content.replace("- status: deep", "- status: deep_processed")
            
            # Replace bottom section containing old profile
            front_parts = new_content.split("---")
            if len(front_parts) >= 3:
                main_body = "---".join(front_parts[2:])
                body_parts = main_body.split("---")
                top_body = body_parts[0].rstrip()
            else:
                top_body = new_content
                
            final_md = f"---{front_parts[1]}---\n{top_body}\n\n---\n{profile_content}\n"

            out_filepath = os.path.join(KEYWORDS_DIR, f"{keyword}.md")
            out_update_filepath = os.path.join(KEYWORDS_DIR, f"{keyword}.update.md")

            with open(out_filepath, "w", encoding="utf-8") as f:
                f.write(final_md)

            # Append to Update file
            update_entry = f"\n### {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Papers Analyzed: {len(citekeys)})\n{update_summary}\n"
            with open(out_update_filepath, "a", encoding="utf-8") as f:
                f.write(update_entry)

            # Remove old files if they are being moved from drafts
            if directory != KEYWORDS_DIR:
                try:
                    os.remove(filepath)
                    if os.path.exists(update_filepath):
                        os.remove(update_filepath)
                except Exception as e:
                    print(f"  Warning: could not remove old file {filepath}: {e}")

            print(f"  ✅ Updated {keyword}.md and appended to .update.md in 05_keywords")
            processed_count += 1
            
    if processed_count == 0:
        print("No keyword cards found with 'status: deep'.")
    else:
        print(f"\nFinished processing {processed_count} deep keyword cards.")

if __name__ == "__main__":
    generate_deep_keyword_cards()

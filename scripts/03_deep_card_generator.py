import json
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import openai
import pypdf
from google import genai

# Load environment variables from .env file
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(dotenv_path=env_path)

# Initialize API clients
gemini_keys = [v for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v.strip()]
gemini_clients = [genai.Client(api_key=key) for key in gemini_keys]
current_gemini_index = 0

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/library.json"))
INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brain"))
STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../00_Attachments"))
ZOTERO_STORAGE_DIR = "/Users/siksik/내 드라이브/zotero/storage"

def find_pdf_for_item(item):
    """
    Search Zotero storage for the PDF using fuzzy matching on the filename.
    """
    if not os.path.exists(ZOTERO_STORAGE_DIR):
        print("Zotero storage not found.")
        return None

    # Determine match criteria
    citekey = item.get("citation-key", item.get("id"))
    year = "Unknown"
    if "issued" in item and "date-parts" in item["issued"]:
        try:
            year = str(item["issued"]["date-parts"][0][0])
        except (IndexError, TypeError):
            pass
            
    title = item.get("title", "")
    title_words = [w.lower() for w in re.findall(r'\w+', title) if len(w) > 3][:4]
    
    author_family = ""
    if item.get("author"):
        author_family = item["author"][0].get("family", "").lower()

    best_match = None
    best_score = 0

    for root, dirs, files in os.walk(ZOTERO_STORAGE_DIR):
        for file in files:
            if file.lower().endswith(".pdf"):
                score = 0
                file_lower = file.lower()
                
                # Check absolute matches
                if citekey and citekey.lower() in file_lower:
                    score += 50
                    
                if year != "Unknown" and year in file_lower:
                    score += 10
                    
                if author_family and author_family in file_lower:
                    score += 10
                    
                for tw in title_words:
                    if tw in file_lower:
                        score += 5
                        
                if score > best_score and score >= 15:  # Require a minimum threshold
                    best_score = score
                    best_match = os.path.join(root, file)

    return best_match

def extract_pdf_text(pdf_path: str) -> str:
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"    Failed to extract text from PDF: {e}")
    return text[:100000] # Limit to ~100k chars for OpenAI prompt limits

def run_llm_with_pdf(prompt: str, pdf_path: str) -> str:
    """
    Tries Gemini with PDF upload first, falls back to OpenAI with text extraction.
    """
    global current_gemini_index
    
    while current_gemini_index < len(gemini_clients):
        client = gemini_clients[current_gemini_index]
        uploaded_file = None
        try:
            uploaded_file = client.files.upload(file=pdf_path)
            # Wait for file to become active
            while uploaded_file.state.name == "PROCESSING":
                print("    Waiting for PDF to process in Gemini...")
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)
                
            if uploaded_file.state.name != "FAILED":
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[uploaded_file, prompt],
                )
                return response.text.strip()
            else:
                print("    Failed to process PDF in Gemini, state was FAILED.")
                break # Non-quota error, break out of Gemini loop
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                print(f"    Gemini API Key {current_gemini_index + 1} exhausted (429). Rotating to next key...")
                current_gemini_index += 1
                # Clean up uploaded file before continuing
                if uploaded_file:
                    try:
                        client.files.delete(name=uploaded_file.name)
                    except:
                        pass
                continue # Try the next key
            else:
                print(f"    Gemini API failed: {e}. Falling back to OpenAI...")
                break # Non-quota error, fall back to OpenAI
        finally:
            # Clean up uploaded file if we are exiting or breaking
            if uploaded_file and "429" not in str(e if 'e' in locals() else ""):
                try:
                    client.files.delete(name=uploaded_file.name)
                except:
                    pass

    if current_gemini_index >= len(gemini_clients) and gemini_clients:
        print("    All Gemini API keys exhausted.")

    if openai_client:
        print("    Using OpenAI fallback, extracting PDF text locally...")
        pdf_text = extract_pdf_text(pdf_path)
        if not pdf_text:
            print("    No text could be extracted from the PDF.")
            return ""
            
        combined_prompt = f"{prompt}\n\n### Full Paper Content:\n{pdf_text}"
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": combined_prompt}],
                timeout=45.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"    OpenAI API failed: {e}")
            if "429" in str(e):
                raise Exception("RATE_LIMIT")
            
    return ""

def run_llm_with_pdf_retry(prompt: str, pdf_path: str, max_retries: int = 3) -> str:
    base_delay = 10
    for attempt in range(max_retries):
        try:
            result = run_llm_with_pdf(prompt, pdf_path)
            if result:
                return result
            # Only retries if RATE_LIMIT exception was raised, empty string means normal auth/eval failure
            break
        except Exception as e:
            if "RATE_LIMIT" in str(e):
                delay = base_delay * (2 ** attempt)
                if attempt < max_retries - 1:
                    print(f"    [Rate Limit Hit] Sleeping for {delay} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
                else:
                    print(f"    [Rate Limit] Max retries reached.")
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

def generate_deep_cards():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    research_context = load_research_context()

    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found.")
        return
        
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data if isinstance(data, list) else data.get("items", [])
    library_map = {item.get("citation-key", item.get("id")): item for item in items}

    if not os.path.exists(INPUT_DIR):
        print("No quick cards found. Run Phase 1 & 2 first.")
        return

    processed_count = 0

    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(INPUT_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if "status: deep\n" not in content and "status: deep\r" not in content and "status: deep" not in content.splitlines():
            continue

        citekey = filename.replace(".md", "")
        print(f"\nProcessing Deep Card: {citekey}...")

        item = library_map.get(citekey)
        if not item:
            print(f"  Warning: Cannot find {citekey} in library.json. Skipping.")
            continue

        # Find PDF
        pdf_path = find_pdf_for_item(item)
        if not pdf_path:
            print(f"  Could not find PDF in Zotero Storage for {citekey}. Skipping.")
            continue
            
        print(f"  Found PDF: {os.path.basename(pdf_path)}")

        # The content of the Brief Card forms the previous knowledge context.
        # It includes user's added questions
        try:
            brief_card_content = "\n".join(content.split("---")[2:]) # Strip frontmatter
        except IndexError:
            brief_card_content = content

        prompt = f'''You are an expert academic research assistant. I need you to create a "Deep Card" analysis for the attached full PDF of a research paper.
You must tailor your analysis based strictly on 1) my personal research context and 2) the notes and questions generated from the "Brief Card" stage.

### My Research Context:
{research_context}

### My Notes & Questions (from Brief Card):
{brief_card_content}

### Output Format:
Output valid Markdown format. Do not wrap it in ```markdown codeblocks. Use exactly these sections:

## Impact Rating
(Provide a rating from 1 to 5 stars, using ⭐ emojis, assessing the actual impact, relevance, and utility of this full paper to my core interests. E.g., ⭐⭐⭐⭐⭐. Add a 1-sentence justification for the score.)

## 1. Key Findings
(Provide a comprehensive summary of the main points and findings of the paper, informed by the full text)

## 2. Methodology Used
(Summarize the methods or theoretical techniques employed in the paper)

## 3. Deep Connection & Answers
(Address any questions listed in the "My Notes & Questions" section above. Explain exactly how the full findings of this paper help answer my 'Key Questions', solve my problems, or relate to my 'Core Interests'. Be highly specific, technical, and concrete.)

## 4. Notable Quotes or Snippets
(Extract 2-3 extremely relevant quotes or important concepts. Specify the page or section if possible.)
'''
        
        print(f"  Sending PDF and Prompt to LLM API...")
        ai_response = run_llm_with_pdf_retry(prompt, pdf_path)
        
        if not ai_response:
            print(f"  Failed to get a response for {citekey}. Skipping.")
            continue

        manual_notes = "\n\n## ✍️ Manual Notes\n*(Add your manual notes here - this section will not be overwritten by AI)*\n"
        deep_filepath = os.path.join(OUTPUT_DIR, f"{citekey}_deep.md")
        if os.path.exists(deep_filepath):
            with open(deep_filepath, "r", encoding="utf-8") as existing_df:
                existing_content = existing_df.read()
                if "## ✍️ Manual Notes" in existing_content:
                    manual_notes = "\n\n## ✍️ Manual Notes" + existing_content.split("## ✍️ Manual Notes", 1)[1]

        deep_frontmatter = f'''---
aliases: ["{citekey}_deep"]
tags: ["deepcard"]
related: ["[[02_cards/{citekey}|{citekey}]]"]
---
# Deep Analysis: {item.get('title', 'Unknown Title')}

**Previous Version:** [[02_cards/{citekey}|Brief Card]]

'''
        with open(deep_filepath, "w", encoding="utf-8") as df:
            df.write(deep_frontmatter + manual_notes.strip() + '\n\n' + ai_response)

        # Update original card status
        new_content = content.replace("status: deep", "status: deep_processed")
        new_content = new_content.replace("- status: deep", "- status: deep_processed")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"  ✅ Saved {citekey}_deep.md and updated Quick/Brief Card status.")
        processed_count += 1
        
    if processed_count == 0:
        print("No cards found with 'status: deep'.")
    else:
        print(f"\nFinished processing {processed_count} deep cards.")

if __name__ == "__main__":
    generate_deep_cards()

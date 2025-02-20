# genai_concurrent.py
import cohere
import json
import logging
import re
import time
import threading
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List

logging.basicConfig(
    filename="blood_report.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

@dataclass
class CohereKey:
    api_key: str
    calls: int
    last_reset: float
    lock: threading.Lock

class KeyManager:
    def __init__(self, api_keys: List[str]):
        self.keys = [CohereKey(key, 0, time.time(), threading.Lock()) for key in api_keys]
        self.manager_lock = threading.Lock()

    def get_available_key(self) -> CohereKey:
        with self.manager_lock:
            current_time = time.time()
            for key in self.keys:
                with key.lock:
                    if current_time - key.last_reset >= 60:
                        key.calls = 0
                        key.last_reset = current_time
            min_calls = float('inf')
            selected_key = None
            for key in self.keys:
                with key.lock:
                    if key.calls < min_calls and key.calls < 39:
                        min_calls = key.calls
                        selected_key = key
            if selected_key is None:
                oldest_reset = min(key.last_reset for key in self.keys)
                time_to_wait = 60 - (current_time - oldest_reset)
                if time_to_wait > 0:
                    time.sleep(time_to_wait)
                return self.get_available_key()
            with selected_key.lock:
                selected_key.calls += 1
                return selected_key

# Replace with your actual Cohere API keys.
API_KEYS = [
    "GBnb257D8YRC2DEPBccutfmLwwtBKSBae1xneddh",
    "effxc1WXG1yWaMP9JBT7XU1yTkgbBAVbxoEEYxKT",
    "pqi8SqTefAO7Txstm49KJS4uJ9LaFWb0HO6L9Q86",
    "fWzA3I54jWzlm3G5VrMNoRWEMSPBKUhoEeUCqOYj"
]
key_manager = KeyManager(API_KEYS)

def get_cohere_client():
    key = key_manager.get_available_key()
    return cohere.Client(key.api_key)

def load_text_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()
        logging.info("Text file successfully loaded.")
        return text
    except Exception as e:
        logging.error(f"Error loading text file: {e}")
        return None

def split_into_pages(text):
    pages = re.split(r"--- Page \d+ ---", text)
    pages = [page.strip() for page in pages if page.strip()]
    logging.info(f"Extracted {len(pages)} pages from the document.")
    return pages

def extract_json_from_text(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            cleaned_json = match.group(0).strip()
            cleaned_json = re.sub(r'```json|```', '', cleaned_json)
            parsed_json = json.loads(cleaned_json)
            return parsed_json
        else:
            logging.warning("No JSON object found in the response text.")
            return None
    except json.JSONDecodeError as je:
        logging.error(f"JSON parsing error: {je}")
        return None

def generate_structured_data(text_chunk, page_number):
    try:
        co = get_cohere_client()
        system_message = """You are a precise medical document parser specializing in laboratory reports. Your task is to extract EVERY SINGLE detail from the provided text, maintaining absolute accuracy and completeness. Follow these strict guidelines:
1. Patient Information:
   - Extract ALL demographic details (Name, Age, Sex, Lab ID)
   - Include ALL sample information (Type, Collection Date/Time, Receipt Date/Time)
   - Capture ANY additional patient identifiers or medical record numbers
2. Test Results:
   - Extract EVERY test mentioned, including main tests and ALL their subtests
   - Maintain the EXACT hierarchy of tests and their components
   - For EACH test parameter, capture:
     * Complete test name (exactly as written)
     * ALL numerical or qualitative values
     * EVERY unit of measurement
     * COMPLETE reference range
     * ANY flags or indicators (H, L, Critical, etc.)
     * ANY methodology or instrument information
3. Additional Information:
   - Include ALL interpretative comments
   - Capture ANY diagnostic suggestions
   - Note ALL disclaimers or limitations
   - Record ANY quality control information
   - Include ALL footnotes or special remarks
Format the output in the following JSON structure:
{
    "Patient Information": {
        "Name": "",
        "Age": "",
        "Sex": "",
        "Lab ID": "",
        "Sample Details": {
            "Type": [],
            "Collection DateTime": "",
            "Receipt DateTime": "",
            "Additional Info": []
        }
    },
    "Tests": [
        {
            "Test Category": "",
            "Test Components": [
                {
                    "Name": "",
                    "SubTests": [
                        {
                            "Parameter": "",
                            "Value": "",
                            "Unit": "",
                            "Reference Range": "",
                            "Flag": "",
                            "Method": ""
                        }
                    ],
                    "Comments": "",
                    "Interpretation": ""
                }
            ]
        }
    ],
    "Report Notes": {
        "Interpretations": [],
        "Comments": [],
        "Disclaimers": [],
        "Quality Control": []
    }
}
IMPORTANT:
- DO NOT skip or omit ANY information from the source text
- Maintain EXACT medical terminology
- Preserve ALL numerical values and units exactly as written
- Include ALL reference ranges and methodologies
- Capture ANY and ALL comments or notes
- If information is missing, use empty strings or arrays rather than omitting fields"""
        user_message = f"Extract ALL details from this laboratory report, ensuring NO information is missed:\n\n{text_chunk}"
        response = co.chat(
            model="command-r",
            message=f"System: {system_message}\nUser: {user_message}",
            max_tokens=4000,
            temperature=0.1,
        )
        full_response_text = response.text.strip()
        extracted_json = extract_json_from_text(full_response_text)
        if extracted_json:
            logging.info(f"Successfully extracted structured data for Page {page_number}.")
            return extracted_json
        else:
            logging.warning(f"LLM response for Page {page_number} did not contain valid JSON.")
            return None
    except Exception as e:
        logging.error(f"Error in Cohere API call for Page {page_number}: {e}")
        return None

def process_page(page_content, page_number):
    max_retries = 3
    for attempt in range(max_retries):
        structured_data = generate_structured_data(page_content, page_number)
        if structured_data:
            return structured_data
        if attempt < max_retries - 1:
            logging.warning(f"Retry attempt {attempt + 1} for Page {page_number}")
            time.sleep(1)
    logging.error(f"Failed to process Page {page_number} after {max_retries} attempts")
    return None

def process_blood_report(file_path, progress_callback=None):
    text = load_text_from_file(file_path)
    if text is None:
        return None
    pages = split_into_pages(text)
    results_dict = {}
    total_pages = len(pages)
    with ThreadPoolExecutor(max_workers=len(API_KEYS)) as executor:
        future_to_page = {executor.submit(process_page, page_content, page_num): page_num 
                          for page_num, page_content in enumerate(pages, start=1)}
        for future in tqdm(future_to_page, desc="Processing Pages"):
            page_num = future_to_page[future]
            try:
                result = future.result()
                if result:
                    results_dict[page_num] = result
            except Exception as e:
                logging.error(f"Error processing page {page_num}: {e}")
            if progress_callback:
                progress_callback(page_num, total_pages)
    structured_results = [results_dict[page_num] for page_num in range(1, len(pages)+1) if page_num in results_dict]
    return structured_results

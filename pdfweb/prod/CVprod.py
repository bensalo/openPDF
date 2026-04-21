"""
This Package will provide all functions to predict form_fields from a .pdf file
Saves Prediction Images and return field positions, labels and found text
"""

### IMPORTS ###
import math
import cv2
import pytesseract
import numpy as np
import uuid
import matplotlib.pyplot as plt
import json
import os
import requests
import time
import datetime
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

from pdf2image import convert_from_path, convert_from_bytes
from pdfminer.layout import LAParams, LTTextBox
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator

# Load environment variables
load_dotenv()

### GLOBAL VARIABLES FROM ENV ###
TESSERACT_PATH = os.getenv('TESSERACT_PATH', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
TEMPLATE_PATH = os.getenv('TEMPLATE_PATH', 'media/')
OUTPUT_PATH = os.getenv('OUTPUT_PATH', 'pdfkit/output/')

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

### LLM CONFIGURATION FROM ENV ###
def get_llm_config():
    """Load LLM configuration from environment variables."""
    return {
        'use_llm': os.getenv('USE_LLM_FOR_MATCHING', 'False').lower() == 'true',
        'provider': os.getenv('LLM_PROVIDER', 'openai'),
        'openai': {
            'api_key': os.getenv('OPENAI_API_KEY'),
            'model': os.getenv('OPENAI_MODEL', 'gpt-4'),
            'endpoint': 'https://api.openai.com/v1/chat/completions'
        },
        'gemini': {
            'api_key': os.getenv('GEMINI_API_KEY'),
            'model': os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
            'endpoint': f'https://generativelanguage.googleapis.com/v1beta/models/{os.getenv("GEMINI_MODEL", "gemini-2.5-flash")}:generateContent'
        },
        'ollama': {
            'model': os.getenv('OLLAMA_MODEL', 'llama2'),
            'endpoint': os.getenv('OLLAMA_HOST', 'http://localhost:11434') + '/api/generate'
        }
    }

### LLM AGENT CLASS ###

    
class LabelFieldAgent:
    """
    LLM-based agent for intelligent label-field matching using various providers.
    """

    def __init__(self, provider=None):
        config = get_llm_config()
        self.provider = provider or config['provider']
        self.config = config[self.provider]
        self.llm_details = {
            "provider": self.provider,
            "model": self.config.get('model', 'unknown'),
            "timestamp": None,
            "performance": {
                "processing_time_ms": 0,
                "token_usage": {"input": 0, "output": 0, "total": 0},
                "api_cost": 0.0,
                "retry_count": 0
            },
            "results": {
                "fields_detected": 0,
                "fields_labeled": 0,
                "fields_unlabeled": 0,
                "confidence_avg": 0.0,
                "fallback_used": False
            },
            "config": {
                "temperature": 0.1,
                "max_tokens": 5000 if provider == 'gemini' else 1000,
                "prompt": ""
            },
            "debug": {
                "text_blocks_processed": 0,
                "prompt_length": 0,
                "response_valid": False,
                "finish_reason": None,
                "error": None
            }
        }

    def _calculate_cost(self, tokens):
        """Calculate API cost based on provider and token usage"""
        # costs per 1K tokens
        cost_per_1k = {
            'openai': {'input': 0.01, 'output': 0.03},  # GPT-4 pricing
            'gemini': {'input': 0.0003, 'output': 0.0025},  # gemini-2.4-flash
            'ollama': {'input': 0, 'output': 0}  # Free local
        }
        
        if self.provider in cost_per_1k:
            rates = cost_per_1k[self.provider]
            input_cost = (tokens['input'] / 1000) * rates['input']
            output_cost = (tokens['output'] / 1000) * rates['output']
            return round(input_cost + output_cost, 6)
        return 0.0
    
    def _prepare_prompt(self, fields: List[Dict], text_blocks: List[Dict]) -> str:
        """
        Prepares a structured prompt for the LLM with field and text information.
        """
        # Track metrics
        self.llm_details["debug"]["text_blocks_processed"] = len(text_blocks)
        self.llm_details["results"]["fields_detected"] = len(fields)
        
        prompt = """You are an expert in form analysis. Given the following information about detected form fields and text blocks from a PDF document, determine the most appropriate label for each field.

        DETECTED FIELDS:
        """
        for i, field in enumerate(fields):
            bbox = field['bbox']
            prompt += f"Field {i}: Position: ({bbox[0]}, {bbox[1]}) to ({bbox[2]}, {bbox[3]})\n"
            if field.get('text'):
                prompt += f"  Current text in field: {field['text']}\n"
        
        prompt += "\nDETECTED TEXT BLOCKS:\n"
        for text_block in text_blocks:
            bbox = text_block['bbox']
            prompt += f"Text: '{text_block['text']}' at position ({bbox[0]}, {bbox[1]}) to ({bbox[2]}, {bbox[3]})\n"
        
        prompt += """
        INSTRUCTIONS:
        1. Analyze the spatial relationships between text blocks and fields
        2. Consider that labels are typically:
        - To the left of their field
        - Above their field
        - Sometimes within the field itself
        3. Common label patterns include ending with ':' or being in title case
        4. Return a JSON array where each object has:
        - "field_index": the field number
        - "label": the most appropriate label text
        - "confidence": a score from 0-100
        
        Return ONLY the JSON array, no additional text.
        """
        
        # Store prompt in details
        self.llm_details["config"]["prompt"] = prompt[:1000] + "..." if len(prompt) > 1000 else prompt
        self.llm_details["debug"]["prompt_length"] = len(prompt)
        
        return prompt
    
    def _call_openai(self, prompt: str) -> Dict:
        """Calls OpenAI API for label-field matching with metrics tracking."""
        start_time = time.time()
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                headers = {
                    'Authorization': f'Bearer {self.config["api_key"]}',
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'model': self.config['model'],
                    'messages': [
                        {'role': 'system', 'content': 'You are a form field analysis expert.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 1000
                }
                
                response = requests.post(self.config['endpoint'], headers=headers, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Extract token usage
                    usage = result.get('usage', {})
                    self.llm_details["performance"]["token_usage"] = {
                        "input": usage.get('prompt_tokens', 0),
                        "output": usage.get('completion_tokens', 0),
                        "total": usage.get('total_tokens', 0)
                    }
                    
                    # Calculate cost
                    self.llm_details["performance"]["api_cost"] = self._calculate_cost(
                        self.llm_details["performance"]["token_usage"]
                    )
                    
                    # Finish reason
                    if 'choices' in result and len(result['choices']) > 0:
                        self.llm_details["debug"]["finish_reason"] = result['choices'][0].get('finish_reason', 'unknown')
                    
                    self.llm_details["debug"]["response_valid"] = True
                    
                    # Parse response
                    parsed_response = json.loads(result['choices'][0]['message']['content'])
                    
                    # Calculate confidence average
                    confidences = [match.get('confidence', 0) for match in parsed_response]
                    self.llm_details["results"]["confidence_avg"] = sum(confidences) / len(confidences) if confidences else 0
                    
                    return parsed_response
                    
                else:
                    retry_count += 1
                    self.llm_details["debug"]["error"] = f"API error: {response.status_code} - {response.text}"
                    if retry_count >= max_retries:
                        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
                    
            except json.JSONDecodeError as e:
                self.llm_details["debug"]["response_valid"] = False
                self.llm_details["debug"]["error"] = f"JSON decode error: {str(e)}"
                retry_count += 1
                if retry_count >= max_retries:
                    raise Exception(f"Invalid JSON from OpenAI: {e}")
                
            except Exception as e:
                self.llm_details["debug"]["error"] = str(e)
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                
            finally:
                # Track timing and retries
                self.llm_details["performance"]["processing_time_ms"] = int((time.time() - start_time) * 1000)
                self.llm_details["performance"]["retry_count"] = retry_count
                self.llm_details["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    
    def _call_gemini(self, prompt: str) -> Dict:
        """Calls Google Gemini API for label-field matching with metrics tracking."""
        start_time = time.time()
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                headers = {
                    'Content-Type': 'application/json',
                }
                
                data = {
                    'contents': [{
                        'parts': [{
                            'text': prompt
                        }]
                    }],
                    'generationConfig': {
                        'temperature': 0.1,
                        'maxOutputTokens': 5000
                    }
                }
                
                url = f"{self.config['endpoint']}?key={self.config['api_key']}"
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # DEBUG: Print the actual structure to see what we're getting
                    print(f"DEBUG Token Usage Structure: {json.dumps(result.get('usageMetadata', {}), indent=2)}")
                    
                    # Extract token usage - Gemini includes "thoughts" tokens
                    if 'usageMetadata' in result:
                        usage = result['usageMetadata']
                        
                        # Extract the different token types
                        input_tokens = usage.get('promptTokenCount', 0)
                        output_tokens = usage.get('candidatesTokenCount', 0)  # Might be 0 on retries
                        thoughts_tokens = usage.get('thoughtsTokenCount', 0)  # Gemini's internal reasoning
                        total_tokens = usage.get('totalTokenCount', 0)
                        
                        # Store all token information
                        self.llm_details["performance"]["token_usage"] = {
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens  # Don't include thoughts in our total
                        }
                        
                        # Add Gemini-specific token info
                        self.llm_details["performance"]["gemini_tokens"] = {
                            "thoughts": thoughts_tokens,
                            "actual_total": total_tokens  # Gemini's total including thoughts
                        }
                        
                        print(f"DEBUG: Token usage - Input: {input_tokens}, Output: {output_tokens}, Thoughts: {thoughts_tokens}, Total: {total_tokens}")
                    else:
                        # If no usage metadata, estimate from prompt and response
                        print("DEBUG: No usageMetadata in Gemini response, estimating...")
                        estimated_input = len(prompt) // 4
                        estimated_output = 200
                        
                        if 'candidates' in result and len(result['candidates']) > 0:
                            if 'content' in result['candidates'][0]:
                                content = result['candidates'][0]['content']
                                if 'parts' in content and len(content['parts']) > 0:
                                    text_response = content['parts'][0].get('text', '')
                                    estimated_output = len(text_response) // 4
                        
                        self.llm_details["performance"]["token_usage"] = {
                            "input": estimated_input,
                            "output": estimated_output,
                            "total": estimated_input + estimated_output
                        }
                    
                    # Calculate cost (excluding thoughts tokens for cost calculation)
                    self.llm_details["performance"]["api_cost"] = self._calculate_cost(
                        self.llm_details["performance"]["token_usage"]
                    )
                    
                    # Continue with the rest of the processing...
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        
                        # Check finish reason
                        finish_reason = candidate.get('finishReason', 'unknown')
                        self.llm_details["debug"]["finish_reason"] = finish_reason
                        
                        if finish_reason == 'MAX_TOKENS':
                            raise Exception("Gemini response was truncated (MAX_TOKENS)")
                        
                        if 'content' in candidate:
                            content = candidate['content']
                            
                            if 'parts' in content and len(content['parts']) > 0:
                                text_response = content['parts'][0].get('text', '')
                                print(f"DEBUG: Response text length: {len(text_response)} characters")
                            else:
                                raise Exception(f"Gemini returned empty response. FinishReason: {finish_reason}")
                        else:
                            raise Exception("No content in Gemini response")
                        
                        if not text_response:
                            raise Exception("Gemini returned empty text")
                        
                        # Clean markdown if present
                        if text_response.startswith("```json"):
                            text_response = text_response[7:]
                        if text_response.endswith("```"):
                            text_response = text_response[:-3]
                        
                        # Parse JSON
                        self.llm_details["debug"]["response_valid"] = True
                        parsed_response = json.loads(text_response.strip())
                        
                        # Calculate confidence average
                        confidences = [match.get('confidence', 0) for match in parsed_response]
                        self.llm_details["results"]["confidence_avg"] = sum(confidences) / len(confidences) if confidences else 0
                        
                        print(f"DEBUG: Successfully parsed Gemini response with {len(parsed_response)} matches")
                        return parsed_response
                        
                    raise Exception("Invalid Gemini response structure")
                    
                else:
                    retry_count += 1
                    self.llm_details["debug"]["error"] = f"API error: {response.status_code} - {response.text}"
                    if retry_count >= max_retries:
                        raise Exception(f"Gemini API error: {response.status_code} - {response.text}")
                    
            except json.JSONDecodeError as e:
                self.llm_details["debug"]["response_valid"] = False
                self.llm_details["debug"]["error"] = f"JSON decode error: {str(e)}"
                retry_count += 1
                if retry_count >= max_retries:
                    raise Exception(f"Invalid JSON from Gemini: {e}")
                    
            except Exception as e:
                self.llm_details["debug"]["error"] = str(e)
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                    
            finally:
                # Track timing and retries
                self.llm_details["performance"]["processing_time_ms"] = int((time.time() - start_time) * 1000)
                self.llm_details["performance"]["retry_count"] = retry_count
                self.llm_details["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    
    def _call_ollama(self, prompt: str) -> Dict:
        """Calls local Ollama instance for label-field matching with metrics tracking."""
        start_time = time.time()
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                data = {
                    'model': self.config['model'],
                    'prompt': prompt,
                    'stream': False,
                    'temperature': 0.1
                }
                
                response = requests.post(self.config['endpoint'], json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Ollama doesn't provide token counts by default
                    # You might need to estimate based on response length
                    self.llm_details["debug"]["response_valid"] = True
                    parsed_response = json.loads(result['response'])
                    
                    # Calculate confidence average
                    confidences = [match.get('confidence', 0) for match in parsed_response]
                    self.llm_details["results"]["confidence_avg"] = sum(confidences) / len(confidences) if confidences else 0
                    
                    return parsed_response
                else:
                    retry_count += 1
                    self.llm_details["debug"]["error"] = f"API error: {response.status_code} - {response.text}"
                    if retry_count >= max_retries:
                        raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
                    
            except json.JSONDecodeError as e:
                self.llm_details["debug"]["response_valid"] = False
                self.llm_details["debug"]["error"] = f"JSON decode error: {str(e)}"
                retry_count += 1
                if retry_count >= max_retries:
                    raise Exception(f"Invalid JSON from Ollama: {e}")
                    
            except Exception as e:
                self.llm_details["debug"]["error"] = str(e)
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                    
            finally:
                # Track timing and retries
                self.llm_details["performance"]["processing_time_ms"] = int((time.time() - start_time) * 1000)
                self.llm_details["performance"]["retry_count"] = retry_count
                self.llm_details["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    
    def match_labels_to_fields(self, fields: List[Dict], text_blocks: List[Dict]) -> Tuple[List, Dict]:
        """
        Main method to match labels to fields using the configured LLM provider.
        Now returns both labeled fields and LLM details.
        """
        prompt = self._prepare_prompt(fields, text_blocks)
        
        try:
            # Call appropriate LLM based on provider
            print(f"DEBUG: Calling {self.provider} with {len(fields)} fields and {len(text_blocks)} text blocks")
            
            if self.provider == 'openai':
                matches = self._call_openai(prompt)
            elif self.provider == 'gemini':
                matches = self._call_gemini(prompt)
            elif self.provider == 'ollama':
                matches = self._call_ollama(prompt)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
            
            print(f"DEBUG: LLM returned {len(matches)} matches")
            
            # Convert LLM response to expected format
            labeled_fields = []
            labeled_count = 0
            
            for match in matches:
                field_idx = match.get('field_index', -1)
                label_text = match.get('label', 'Unknown')
                confidence = match.get('confidence', 0)
                
                print(f"DEBUG: Match {field_idx}: '{label_text}' (confidence: {confidence})")
                
                if field_idx < len(fields) and field_idx >= 0:
                    field = fields[field_idx]
                    bbox = field['bbox']
                    
                    if label_text and label_text != 'Unknown' and label_text != 'None':
                        labeled_count += 1
                    
                    labeled_fields.append((
                        bbox[0], 
                        bbox[1], 
                        bbox[2] - bbox[0], 
                        bbox[3] - bbox[1], 
                        field.get('text', ''),
                        label_text
                    ))
                else:
                    print(f"WARNING: Invalid field index {field_idx}")
            
            # Update final metrics
            self.llm_details["results"]["fields_labeled"] = labeled_count
            self.llm_details["results"]["fields_unlabeled"] = len(fields) - labeled_count
            
            print(f"DEBUG: Converted to {len(labeled_fields)} labeled fields")
            return labeled_fields, self.llm_details
            
        except Exception as e:
            print(f"LLM matching failed: {str(e)}. Falling back to traditional algorithm.")
            self.llm_details["debug"]["error"] = str(e)
            self.llm_details["results"]["fallback_used"] = True
            return None, self.llm_details

### CV FUNCTIONS ###
def save_image(file_path, image):
    """Saves the image to the specified file path."""
    cv2.imwrite(f'{OUTPUT_PATH}{file_path}', image)

def save_to_json(data, filename):
    """Saves the given data as a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f'Data saved to {filename}')

def load_from_json(filename):
    """Loads data from a JSON file."""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f'Data loaded from {filename}')
    return data

def clean_text_fields(fields, text_layout):
    """
    Removes text objects from text_layout that are within any of the given fields.
    Additionally, removes the topmost text object, considering it as a header.

    Args:
        fields (list): List of field bounding boxes.
        text_layout (list): List of text object bounding boxes.

    Returns:
        tuple: A tuple containing the original fields and the cleaned text_layout.
    """
    cleaned_text_layout = []

    # Find the topmost text object (considered the header)
    topmost_text_obj = None
    min_y = float('inf')

    for text_obj in text_layout:
        lb = text_obj.get("bbox")
        # Find the object with the smallest y-coordinate
        if lb[1] < min_y:
            min_y = lb[1]
            topmost_text_obj = text_obj

    # Iterate through each text object in the layout
    for text_obj in text_layout:
        lb = text_obj.get("bbox")

        # Skip the topmost text object (header)
        if text_obj == topmost_text_obj:
            continue

        # Check if the text object is within any field
        is_within_any_field = any(is_within_field(lb, field.get("bbox")) for field in fields)

        # If not within any field, add it to the cleaned list
        if not is_within_any_field:
            cleaned_text_layout.append(text_obj)

    return fields, cleaned_text_layout

def is_above_field(fb, lb):
    """
    Checks if a text bounding box (lb) is above a field bounding box (fb).

    Args:
        fb (tuple): Field bounding box coordinates.
        lb (tuple): Label bounding box coordinates.

    Returns:
        float or bool: Returns the distance if lb is above fb; otherwise, False.
    """
    if lb[3] <= fb[1]:
        if fb[0] <= (lb[0] + lb[2]) / 2 <= fb[2]:
            distance = fb[1] - lb[3]
            return distance
    return False

def is_under_field(fb, lb):
    """
    Checks if a text bounding box (lb) is below a field bounding box (fb).

    Args:
        fb (tuple): Field bounding box coordinates.
        lb (tuple): Label bounding box coordinates.

    Returns:
        float or bool: Returns the distance if lb is below fb; otherwise, False.
    """
    if lb[1] >= fb[3]:
        if fb[0] <= (lb[0] + lb[2]) / 2 <= fb[2]:
            distance = lb[1] - fb[3]
            return distance
    return False

def is_before_field(fb, lb):
    """
    Checks if a text bounding box (lb) is to the left of a field bounding box (fb).

    Args:
        fb (tuple): Field bounding box coordinates.
        lb (tuple): Label bounding box coordinates.

    Returns:
        float or bool: Returns the distance if lb is to the left of fb; otherwise, False.
    """
    if lb[2] <= fb[0]:
        if fb[1] <= (lb[1] + lb[3]) / 2 <= fb[3]:
            distance = fb[0] - lb[2]
            return distance
    return False

def predict_field(field, label):    
    """
    Predicts the spatial relationship between a label and a field.

    Args:
        field (dict): Field information with bounding box.
        label (dict): Label information with bounding box.

    Returns:
        tuple or bool: Relationship type and distance, or False if no valid relationship is found.
    """
    lb = label.get("bbox")
    fb = field.get("bbox")

    # Check if the label is within the field
    if is_within_field(lb, fb):
        return ('within', 0)

    # Check if the label is above, under, or before the field
    before = is_before_field(fb, lb)
    above = is_above_field(fb, lb)
    under = is_under_field(fb, lb)

    distances = []
    if before:
        distances.append(('before', before))
    if above:
        distances.append(('above', above))
    if under:
        distances.append(('under', under))

    # If no valid condition is found, return False
    if not distances:
        return False

    # Sort by distance to find the closest relationship
    distances.sort(key=lambda x: x[1])
    return distances[0]

def prediction(fields, text_layout, use_llm=False, llm_provider='openai'):
    """
    Associates labels with fields.
    Returns: (precision_matrix, labeled_fields, llm_details)
    """
    llm_details = None
    
    # If using LLM, try it first
    if use_llm:
        print(f"DEBUG: Attempting LLM-based matching with {llm_provider}")
        try:
            agent = LabelFieldAgent(provider=llm_provider)
            labeled_fields, llm_details = agent.match_labels_to_fields(fields, text_layout)
            
            if labeled_fields and len(labeled_fields) > 0:
                print(f"DEBUG: LLM matching succeeded with {len(labeled_fields)} labeled fields")
                precision_matrix = []
                for i, field in enumerate(fields):
                    precision_matrix.append((field.get('id'), f"llm_match_{i}", ('llm', 0)))
                return precision_matrix, labeled_fields, llm_details
        except Exception as e:
            print(f"DEBUG: LLM failed ({e}), using traditional algorithm")
    
    # Traditional algorithm - ORIGINAL CODE
    print("DEBUG: Using traditional spatial algorithm")
    precision_matrix = []
    fields_labeled = []
    closest_labels = {}
    used_labels = set()

    for field in fields:
        field_id = field.get("id")
        fb = field.get("bbox")
        closest_label = None
        min_distance = float('inf')
        closest_label_text = None

        for label in text_layout:
            label_id = label.get("id")
            
            if label_id in used_labels:
                continue

            prediction_result = predict_field(field, label)
            precision_matrix.append((field_id, label_id, prediction_result))

            if prediction_result and prediction_result[0] == 'within':
                closest_label_text = label.get("text")
                fb = field.get("bbox")
                fields_labeled.append((fb[0], fb[1], fb[2] - fb[0], fb[3] - fb[1], field.get("text"), closest_label_text))
                used_labels.add(label_id)
                break

            if prediction_result and prediction_result[1] < min_distance:
                min_distance = prediction_result[1]
                closest_label = (label_id, prediction_result[0], prediction_result[1])
                closest_label_text = label.get("text")

        if closest_label and not any(f[0] == fb[0] and f[1] == fb[1] for f in fields_labeled):
            closest_labels[field_id] = closest_label
            fb = field.get("bbox")
            fields_labeled.append((fb[0], fb[1], fb[2] - fb[0], fb[3] - fb[1], field.get("text"), closest_label_text))
            used_labels.add(closest_label[0])

    # For fields without labels
    for field in fields:
        fb = field.get("bbox")
        if not any(f[0] == fb[0] and f[1] == fb[1] for f in fields_labeled):
            fields_labeled.append((fb[0], fb[1], fb[2] - fb[0], fb[3] - fb[1], field.get("text"), "None"))

    print(f"DEBUG: Traditional algorithm found {len([f for f in fields_labeled if f[5] != 'None'])} labeled fields out of {len(fields_labeled)} total")
    
    # If using traditional after LLM failed, update details
    if llm_details and llm_details.get("results", {}).get("fallback_used"):
        llm_details["results"]["fields_labeled"] = len([f for f in fields_labeled if f[5] != 'None'])
        llm_details["results"]["fields_unlabeled"] = len([f for f in fields_labeled if f[5] == 'None'])
    
    return precision_matrix, fields_labeled, llm_details

def calculate_distance(point1, point2):
    """Calculates the Euclidean distance between two points."""
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

def find_center(coordinate):
    """Calculates the center point of a rectangle given its coordinates."""
    x, y, w, h = coordinate
    return (x + w / 2, y + h / 2)

def is_within_field(text_bbox, field_bbox):
    """
    Checks if a text bounding box is completely within a field bounding box.

    Args:
        text_bbox (tuple): Bounding box coordinates of the text (x, y, width, height).
        field_bbox (tuple): Bounding box coordinates of the field (x, y, width, height).

    Returns:
        bool: True if the text is within the field, otherwise False.
    """
    tx, ty, tw, th = text_bbox
    fx, fy, fw, fh = field_bbox
    return tx >= fx and ty >= fy and (tx + tw) <= (fx + fw) and (ty + th) <= (fy + fh)

def get_label_accuracy(pot_label):
    """
    Estimates the likelihood that a text object is a label for an input field.

    Args:
        pot_label (str): Potential label text.

    Returns:
        int: Accuracy score of how likely the text is to be a label.
    """
    common_labels_en = ['name', 'surname', 'address', 'age', 'email', 'e-mail', 'phone']   
    common_labels_de = ['vorname', 'nachname', 'name', 'adresse', 'alter', 'handynummer', 'telefonnummer']
    accuracy = 0

    # Clean and normalize text
    label_text = str(pot_label).strip().lower() 
          
    # Increase accuracy if the text ends with a colon (typical for labels)
    if label_text.endswith(':'): 
        accuracy += 10
        label_text = label_text.replace(':', '')

    # Increase accuracy if the label is in common label lists
    if label_text in common_labels_en + common_labels_de:
        accuracy += 10

    return accuracy

def find_closest_label(fields, text_layout, use_llm=False, llm_provider='openai'):
    """
    Finds the most probable label for each field.
    Returns (field_label_mapping, labeled_fields, llm_details)
    """
    llm_details = None
    
    # Try LLM-based matching if enabled
    if use_llm:
        try:
            agent = LabelFieldAgent(provider=llm_provider)
            labeled_fields, llm_details = agent.match_labels_to_fields(fields, text_layout)
            
            if labeled_fields and len(labeled_fields) > 0:
                # Convert to dictionary format for compatibility
                field_label_mapping = {}
                for field_data in labeled_fields:
                    x, y, w, h, field_text, label_text = field_data
                    field_label_mapping[(x, y, w, h, field_text)] = label_text
                return field_label_mapping, labeled_fields, llm_details
            else:
                print("DEBUG: LLM returned empty or None response")
                return None, None, llm_details
                
        except Exception as e:
            print(f"LLM matching failed: {e}")
            return None, None, llm_details
    
    # Traditional algorithm
    field_label_mapping = {}
    labeled_fields = []
    used_labels = set()

    for field in fields:
        x, y, x1, y1 = field['bbox']
        w = x1 - x
        h = y1 - y
        field_center = find_center(field['bbox'])
        best_score = float('-inf')
        closest_label = None
        
        for label in text_layout:
            if 'bbox' not in label:
                continue
                
            text_center = find_center(label['bbox'])
            distance = calculate_distance(field_center, text_center)

            if abs(text_center[1] - field_center[1]) < (h / 2) and (text_center[0] < x) and (x - text_center[0] < 200):
                score = label.get('accuracy', 0) - distance
                if score > best_score:
                    best_score = score
                    closest_label = label.get('text', '')

        label_text = closest_label if closest_label else 'None'
        labeled_fields.append((x, y, w, h, field.get('text', ''), label_text))
        
        if closest_label:
            field_label_mapping[(x, y, w, h, field.get('text', ''))] = closest_label
            used_labels.add(closest_label)

    return field_label_mapping, labeled_fields, llm_details

def convert_pdfminer_to_opencv_coordinates(pdf_coords, page_height, image_height, scale_factor=2.775):
    """
    Converts pdfminer coordinates (origin bottom-left) to OpenCV coordinates (origin top-left).
    Also scales from point coordinates to pixel coordinates.

    Args:
        pdf_coords (tuple): Tuple (x0, y0, x1, y1) in PDF coordinates (points).
        page_height (float): The height of the PDF page in points.
        image_height (int): The height of the converted image in pixels.
        scale_factor (float): The scale factor to convert from points to pixels.

    Returns:
        tuple: Tuple (x0, y0, x1, y1) in OpenCV image coordinates (pixels).
    """
    x0, y0, x1, y1 = pdf_coords
    # Convert coordinates from bottom-left origin to top-left origin and scale from points to pixels
    x0_img = int(x0 * scale_factor)
    x1_img = int(x1 * scale_factor)
    y0_img = int(image_height - (y1 * scale_factor))
    y1_img = int(image_height - (y0 * scale_factor))
    return (x0_img, y0_img, x1_img, y1_img)

def extract_text(pdf_input):
    """
    Extracts text and coordinates from a PDF file.
    Handles both file paths and file-like objects.

    Args:
        pdf_input (str or file-like): PDF file path or file-like object.

    Returns:
        list: List of dictionaries containing 'bbox', 'text', 'page_index'.
    """
    output = []
    
    # Determine if pdf_input is a file path or a file-like object
    if isinstance(pdf_input, str):
        # If it's a file path, open the file
        pdf_file = open(f'{pdf_input}', 'rb')
        pages = PDFPage.get_pages(pdf_file)
        images = convert_from_path(f'{pdf_input}')
    else:
        # If it's a file-like object, use it directly
        pdf_file = pdf_input
        pages = PDFPage.get_pages(pdf_file)
        pdf_file.seek(0)  # Reset the file-like object to the beginning
        images = convert_from_bytes(pdf_file.read())
    
    # Create a resource manager and PDF interpreter for processing pages
    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    
    # Process each page of the PDF
    for n, page in enumerate(pages):
        interpreter.process_page(page)
        layout = device.get_result()

        # Get page dimensions
        page_width, page_height = page.mediabox[2], page.mediabox[3]
        
        # Get the corresponding image page
        image = images[n]
        image_width, image_height = image.size
        
        # Extract text from layout objects
        for lobj in layout:
            if isinstance(lobj, LTTextBox):
                # Convert PDF coordinates to OpenCV coordinates
                converted_bbox = convert_pdfminer_to_opencv_coordinates(
                    lobj.bbox, page_height, image_height
                )
                text = str(lobj.get_text()).replace('\n', '')

                output.append({
                    'id': str(uuid.uuid4())[24:],
                    'text': text,
                    'bbox': converted_bbox,
                    'accuracy': int(get_label_accuracy(text)),
                    'page_index': n,
                    'state': None,
                })

    # Close file if it was opened from a path
    if isinstance(pdf_input, str):
        pdf_file.close()

    print("3.2.2 extrext_text output\b", output)

    return output

def show_detected_fields(original_image, form_fields, text_layout):
    """
    Draws the detected fields and text boxes on the image.

    Args:
        original_image (PIL.Image): The original image of the form.
        form_fields (list): List of form fields with their coordinates.
        text_layout (list): List of detected text blocks with their coordinates.

    Returns:
        np.array: Image with drawn fields and labels.
    """
    # Convert the original image to OpenCV format (BGR) for drawing
    image_with_fields = cv2.cvtColor(np.array(original_image), cv2.COLOR_RGB2BGR).copy()
    
    # Draw detected fields (in green) and corresponding labels
    for field in form_fields:
        x, y, w, h, input_text, label_text = field

        # Draw a green rectangle around the detected field
        cv2.rectangle(image_with_fields, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Write the label of the field above the rectangle
        cv2.putText(image_with_fields, label_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Write the coordinates of the rectangle below the field
        coord_text = f'({x},{y}),({x + w},{y + h})'
        cv2.putText(image_with_fields, coord_text, (x, y + h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    # Draw detected text boxes (in blue)
    for text in text_layout:
        if 'bbox' in text:  # Ensure the text object has a bounding box
            x0, y0, x1, y1 = map(int, text['bbox'])
            
            # Draw a blue rectangle around the detected text box
            cv2.rectangle(image_with_fields, (x0, y0), (x1, y1), (255, 0, 0), 2)
            
            # Optionally write the text above the detected box
            cv2.putText(image_with_fields, text['text'].strip(), (x0, y0 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            # Write the coordinates of the rectangle
            coord_text = f'({x0},{y0}),({x1},{y1})'
            cv2.putText(image_with_fields, coord_text, (x0, y1 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

    # Display the result using Matplotlib
    plt.figure(figsize=(10, 10))
    plt.imshow(cv2.cvtColor(image_with_fields, cv2.COLOR_BGR2RGB))
    plt.axis('off')
    plt.show()

    return cv2.cvtColor(image_with_fields, cv2.COLOR_BGR2RGB)

def recognize_text(image, field):
    """
    Recognizes text within a specific region of the provided image.

    Args:
        image (PIL.Image): The original image.
        field (tuple): Coordinates of the field (x, y, w, h).

    Returns:
        str: Recognized text.
    """
    # Convert PIL image to a NumPy array
    np_image = np.array(image)
    # Convert to grayscale for better OCR accuracy
    gray_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
    
    # Extract the region of interest from the image
    x, y, w, h = field
    field_image = gray_image[y:y+h, x:x+w]
    text = pytesseract.image_to_string(field_image)
    return text.strip()

def detect_input_fields(processed_image, original_image, min_width=40, min_height=20):
    """
    Detects input fields in the processed image using contour detection.

    Args:
        processed_image (np.array): Processed image to detect contours.
        original_image (PIL.Image): Original image to extract text.
        min_width (int): Minimum width for detected fields.
        min_height (int): Minimum height for detected fields.

    Returns:
        list: List of detected input fields with bounding boxes and text.
    """
    # Find contours to identify rectangular input fields
    contours, _ = cv2.findContours(processed_image.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    input_fields = []
    
    for cnt in contours:
        approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        if len(approx) == 4:  # Looking for rectangles
            x, y, w, h = cv2.boundingRect(approx)
            # Check if the detected field meets minimum size requirements
            if w >= min_width and h >= min_height:
                # Extract text from the detected field
                text = recognize_text(original_image, (x, y, w, h))
                bbox = [x, y, x + w, y + h]

                input_fields.append({
                    'id': str(uuid.uuid4())[24:],
                    'text': text,
                    'bbox': bbox,
                })
            
    return input_fields

def preprocess_image(image):
    """
    Preprocesses the image for input field detection.
    Converts to grayscale, applies Gaussian blur, and runs Canny edge detection.

    Args:
        image (PIL.Image): Original image.

    Returns:
        np.array: Preprocessed image ready for contour detection.
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)
    return edged

def convert_coordinates_quadratic(pos_x, pos_y, original_height=2332, original_width=1651, scale=0.348, x_offset=15, b=0.03):
    """
    Converts coordinates from a 1651x2338 system to reportlab coordinates, applying a small quadratic adjustment for y.

    Args:
        pos_x (float): X coordinate in the original scope.
        pos_y (float): Y coordinate in the original scope.
        original_height (int): Height of the original canvas.
        original_width (int): Width of the original canvas.
        scale (float): Scaling factor for conversion.
        x_offset (float): Offset to add to the X coordinate.
        b (float): Coefficient for the quadratic adjustment.

    Returns:
        tuple: Converted (x, y) coordinates.
    """
    # Apply quadratic adjustment to y-coordinate
    pos_y = pos_y + ((pos_y - original_height / 2) * b)
    pos_y = (original_height - pos_y) * scale

    # Apply quadratic adjustment to x-coordinate
    pos_x = pos_x + ((pos_x - original_width / 2) * b)
    pos_x = pos_x * scale + x_offset

    return round(pos_x, 1), round(pos_y, 1)

### MAIN FUNCTIONS ###

def predict_image(image, text_layout, use_llm=False, llm_provider='openai'):
    """
    Processes an image to predict and label form fields.
    
    Returns:
        tuple: Image with predictions, list of fields, list of labeled fields, llm_details
    """
    processed_image = preprocess_image(image)
    fields = detect_input_fields(processed_image, image)
    fields, text_layout = clean_text_fields(fields, text_layout)
    result, fields_labeled, llm_details = prediction(fields, text_layout, use_llm, llm_provider)
    output_image = show_detected_fields(image, fields_labeled, text_layout)

    return output_image, fields, fields_labeled, llm_details

def process_pdf_path(pdf_path, use_llm=False, llm_provider='openai'):
    """
    Processes a PDF from a given path and predicts form fields for each page.
    
    Returns:
        tuple: (prediction dict, pdf_image, prediction_image, llm_details)
    """
    text_layout = extract_text(pdf_path)
    llm_details = None

    prediction = {
        'page': {}
    }

    for n, image in enumerate(convert_from_path(f'{pdf_path}')):
        if n == 0: pdf_image = image
        prediction_image, prediction_fields, prediction_labels, page_llm_details = predict_image(
            image, text_layout, use_llm, llm_provider
        )
        prediction["page"][n+1] = prediction_labels
        
        # Keep the LLM details from the first page (or combine them if you want)
        if page_llm_details and not llm_details:
            llm_details = page_llm_details

    return prediction, pdf_image, prediction_image, llm_details

def process_to_template(pdf_path, use_llm=False, llm_provider='openai'):
    """
    Converts the prediction output to the format required for pdftemplate.Pdf_template.
    
    Returns:
        tuple: (fields, pdf_image, prediction_image, llm_details)
    """
    prediction, pdf_image, prediction_image, llm_details = process_pdf_path(pdf_path, use_llm, llm_provider)

    fields = []

    # Create fields in the desired format from the prediction output
    for page, elements in prediction['page'].items():
        for i, element in enumerate(elements):
            pos_x, pos_y, width, height, default_text, label = element
            
            # Convert pos_x, pos_y from image scope to reportlab scope
            pos_x, pos_y = convert_coordinates_quadratic(pos_x, pos_y)

            field = {
                "name": label.lower().replace(":", "").replace(" ", "_"),
                "field_type": "text",
                "required": False,
                "page_index": page - 1,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "font_size": 12,
                "font": "Helvetica"
            }
            fields.append(field)

    return fields, pdf_image, prediction_image, llm_details

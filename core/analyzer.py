import os
import json
import re
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={
        "temperature": 0.1,
        "top_p": 0.9
    }
)

# -------------------------------
# Schema definition
# -------------------------------
EXPECTED_SCHEMA = {
    "is_meaningful": bool,
    "summary": list,
    "confidence": float
}

def _safe_default():
    """Return a safe fallback response"""
    return {
        "is_meaningful": False,
        "summary": [],
        "confidence": 0.0
    }

def _extract_json(text: str) -> dict | None:
    """
    Extract the first JSON object from LLM output robustly.
    Handles Markdown code blocks and extra text.
    """
    try:
        # Remove Markdown ```json or ``` blocks
        text = re.sub(r"^```json|^```", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"```$", "", text.strip(), flags=re.MULTILINE)

        # Find the first { and last } and extract everything in between
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        json_str = text[start:end+1]
        return json.loads(json_str)
    except Exception as e:
        print("⚠️ JSON extraction error:", e)
        return None


def _validate_schema(data: dict) -> dict | None:
    """Validate structure and types strictly"""
    try:
        for key, expected_type in EXPECTED_SCHEMA.items():
            if key not in data:
                return None
            if not isinstance(data[key], expected_type):
                return None

        # Extra validation
        if not (0.0 <= data["confidence"] <= 1.0):
            return None

        # Sanitize summary
        clean_summary = []
        for item in data["summary"]:
            if isinstance(item, str) and 3 < len(item) < 300:
                clean_summary.append(item.strip())

        data["summary"] = clean_summary
        return data
    except Exception:
        return None

def llm_analyze_change(old_text: str | None, new_text: str) -> dict:
    prompt = f"""
You are a Data Analyst for a student notification system. You analyze changes made to university websites to see if they matter to students.

Analyze OLD vs NEW content and respond ONLY with JSON.

OLD:
{(old_text or "None")[:1200]}

NEW:
{new_text[:1200]}

Mark is_meaningful = true ONLY IF:
- deadlines changed
- eligibility changed
- fee structure changed
- merit list or admissions announced

Consider the following operational rules for more details:

**Operational Rules**:
1. **Analyze the Diff**: You are given above the text that was OLD and text that is NEW.
2. **Relevance Criteria (Report these)**:
    * Admissions (deadlines, open/close status).
    * Fees (price changes, new challan forms).
    * Eligibility (rule changes).
    * Schedule (datesheets, holidays).
    * Policies (grading, hostel, housing rules).
3. **Ignore Criteria (Silence these)**:
    * Generic design/layout changes in the pages or navigation.
    * Fixing typos (e.g., "teh" -> "the").
    * Changing years in footers (e.g., "Copyright 2024" -> "2025").
    * Rephrasing that implies no factual change relevant to the students.
    * Generic "Announcements" headers moving around.

    
return JSON format ONLY:
{{
  "is_meaningful": true or false,
  "summary": ["bullet point 1", "bullet point 2"],
  "confidence": 0.0 to 1.0
}}
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text or ""
        print("LLM raw response:", raw)
    except Exception as e:
        print("Gemini call failed:", e)
        return _safe_default()

    # 1️⃣ Extract JSON
    parsed = _extract_json(raw)
    if not parsed:
        print("❌ JSON extraction failed")
        return _safe_default()

    print("✅ JSON extracted:", parsed
          )
    # 2️⃣ Validate schema
    validated = _validate_schema(parsed)
    if not validated:
        print("❌ Schema validation failed:", parsed)
        return _safe_default()

    # 3️⃣ Semantic guard
    if validated["is_meaningful"] and validated["confidence"] < 0.6:
        print("⚠️ Low confidence — discarding")
        return _safe_default()

    return validated

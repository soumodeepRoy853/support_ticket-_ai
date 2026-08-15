import json

from google import genai
from google.genai import errors as google_errors
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

CATEGORIZATION_PROMPT = """You are a support ticket triage assistant. Analyze this ticket and respond with ONLY valid JSON, no other text, no markdown code fences.

Ticket subject: {subject}
Ticket description: {description}

Respond with this exact JSON structure:
{{
  "category": "billing" | "technical" | "account" | "feature_request" | "general",
  "priority": "low" | "medium" | "high" | "urgent",
  "summary": "one sentence summary of the issue",
  "suggested_reply": "a brief, professional draft reply an agent could send, 2-3 sentences"
}}"""

MODEL_FALLBACKS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.7-flash"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def categorize_ticket(subject: str, description: str) -> dict:
    last_error = None
    for model_name in MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=CATEGORIZATION_PROMPT.format(subject=subject, description=description),
                config={
                    "temperature": 0.3,
                    "response_mime_type": "application/json",
                },
            )
            return json.loads(response.text)
        except google_errors.ClientError as exc:
            last_error = exc
            if "404" not in str(exc) and "NOT_FOUND" not in str(exc):
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("No Gemini model was available for ticket classification")
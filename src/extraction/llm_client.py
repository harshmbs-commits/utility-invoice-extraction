"""Send invoice images to an LLM and return structured extraction data.

This module tries Google Gemini first, then falls back to Groq if anything
goes wrong. API keys are read from environment variables (see .env.example).
"""

from __future__ import annotations

import base64
import io
import json
import os
import re

from google import genai
from dotenv import load_dotenv
from groq import Groq
from PIL import Image

from src.extraction.prompts import EXTRACTION_PROMPT, RESPONSE_SCHEMA

load_dotenv()

GEMINI_MODEL = "gemini-3-flash-preview"
GROQ_MODEL = "qwen/qwen3.6-27b"


def extract_invoice_data(image: Image.Image) -> dict:
    """Extract structured invoice fields from a single image.

    Sends the image to Gemini with a schema-constrained JSON response. If
    Gemini fails for any reason, retries with Groq. Raises RuntimeError only
    when both providers fail.

    Args:
        image: A PIL image of one invoice page.

    Returns:
        Parsed extraction result as a dictionary.
    """
    gemini_error: Exception | None = None

    try:
        return _extract_with_gemini(image)
    except Exception as exc:
        gemini_error = exc
        print(
            f"Warning: Gemini extraction failed ({exc}). "
            "Falling back to Groq."
        )

    try:
        return _extract_with_groq(image)
    except Exception as groq_error:
        raise RuntimeError(
            "Both Gemini and Groq extraction failed.\n"
            f"Gemini error: {gemini_error}\n"
            f"Groq error: {groq_error}"
        ) from groq_error


def _extract_with_gemini(image: Image.Image) -> dict:
    """Call Gemini and return parsed JSON extraction data."""
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[EXTRACTION_PROMPT, image],
        config={
            "response_mime_type": "application/json",
            "response_schema": RESPONSE_SCHEMA,
        },
    )

    return json.loads(response.text)


def _extract_with_groq(image: Image.Image) -> dict:
    """Call Groq vision model and return parsed JSON extraction data.

    Qwen 3.6 27B on Groq only supports the looser "json_object" response
    format (not strict "json_schema", which is limited to gpt-oss models).
    Even with reasoning_effort="none", it can still pad its answer with
    visible reasoning text before the final JSON object. To handle this
    robustly, we first try a direct parse, and if that fails, fall back to
    extracting the LAST valid JSON object found anywhere in the response
    text -- the model consistently lands on a correct final answer, just
    preceded by extra text.
    """
    api_key = os.environ["GROQ_API_KEY"]
    client = Groq(api_key=api_key)

    data_uri = _image_to_base64_data_uri(image)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            EXTRACTION_PROMPT
                            + "\n\nIMPORTANT: Output ONLY the final JSON "
                            "object. Do not show your reasoning, do not "
                            "include multiple attempts, and do not include "
                            "any text before or after the JSON object."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                ],
            }
        ],
        response_format={"type": "json_object"},
        reasoning_effort="none",
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Groq returned an empty response.")

    return _parse_json_with_fallback(content)


def _parse_json_with_fallback(text: str) -> dict:
    """Parse text as JSON, falling back to extracting the last JSON object
    in the text if a direct parse fails."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find all top-level-looking {...} blocks and try the last one first,
    # since models that pad their answer with reasoning tend to land on
    # the correct final JSON object at the end.
    matches = re.findall(r"\{.*?\}(?=\s*$|\s*\n\n)", text, re.DOTALL)
    if not matches:
        matches = re.findall(r"\{.*\}", text, re.DOTALL)

    for candidate in reversed(matches):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError(
        f"Could not parse any valid JSON object from Groq's response. "
        f"Raw response started with: {text[:200]!r}"
    )


def _image_to_base64_data_uri(image: Image.Image) -> str:
    """Encode a PIL image as a PNG base64 data URI for Groq's vision API."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
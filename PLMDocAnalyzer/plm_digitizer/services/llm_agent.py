"""
PLM Digitizer - LLM Batch Extraction Service
Supports both OpenAI and Azure OpenAI with automatic provider routing.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """You are an expert data extraction engine for PLM (Product Lifecycle Management) systems. Your job is to read technical documents and extract specific structured fields with high accuracy.

Fields to extract from EVERY document:
{field_list}

CRITICAL RULES:
1. Output ONLY a valid JSON array — no markdown fences, no prose, no extra keys.
2. The array must have EXACTLY one object per document, in the same order as the input.
3. Every object must include ALL of the fields listed above as keys.
4. Set a field to null ONLY if the information is genuinely absent from the document.
5. Extract values VERBATIM where possible (preserve original formatting, units, codes).
6. For numeric fields (weight, dimensions, etc.) include the unit if stated.
7. For date fields use the format found in the document, not a reformatted version.
8. Include these two internal fields in EVERY object:
   - "_confidence": a float 0.0–1.0 reflecting how complete and certain the extraction is
     * 0.9–1.0 = all key fields found with high certainty
     * 0.6–0.89 = most fields found, a few uncertain or missing
     * 0.3–0.59 = partial extraction, several fields missing or uncertain
     * 0.0–0.29 = very little usable data found
   - "_source_hint": one short phrase indicating where in the document the main data was found (e.g. "title block", "BOM table row 3", "header section", "page 2 table")

COMMON PLM FIELD HINTS (apply if relevant to your field list):
- Part Number / Item Number: often in a title block, header, or BOM column
- Revision / Rev: a letter or number near the part number (e.g. "Rev B", "Rev 03")
- Description: the primary text description of the part or assembly
- Material: the raw material specification (e.g. "304 Stainless Steel", "ABS Plastic")
- Weight / Mass: numeric value with unit (g, kg, lb)
- Drawing Number: similar to part number, often prefixed "DWG" or "DRW"
- Author / Designed By / Engineer: person who created the document
- Date / Release Date: creation or approval date

OUTPUT FORMAT — JSON array, one object per document:
[{{"Field1": "value", "Field2": null, "_confidence": 0.92, "_source_hint": "title block"}}]"""


def build_user_message(documents: List[Tuple[int, str]]) -> str:
    """Build the user message with numbered documents, trimmed intelligently."""
    parts = []
    # Allocate token budget per document (roughly 4 chars per token, target ~3500 tokens each)
    max_chars_per_doc = 8000 if len(documents) == 1 else max(3000, 12000 // len(documents))
    for idx, text in documents:
        text = text.strip()
        if not text:
            text = "[EMPTY DOCUMENT — no text could be extracted]"
        elif len(text) > max_chars_per_doc:
            # Keep the beginning and end of the document (title blocks are often at start/end)
            half = max_chars_per_doc // 2
            text = text[:half] + f"\n\n[... {len(text) - max_chars_per_doc} characters omitted ...]\n\n" + text[-half:]
        parts.append(f"=== DOCUMENT {idx + 1} ===\n{text}")
    return "\n\n".join(parts)


def parse_llm_response(response_text: str, expected_count: int) -> List[Optional[Dict]]:
    """Parse and validate the LLM JSON response with multiple fallback strategies."""
    import re

    text = response_text.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()

    def _normalise(data):
        """Ensure result is a list of the right length."""
        if not isinstance(data, list):
            data = [data]
        # Pad with None if too short
        while len(data) < expected_count:
            data.append(None)
        return data[:expected_count]

    # Strategy 1: direct JSON parse
    try:
        data = json.loads(text)
        return _normalise(data)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find the outermost [...] block (greedy — captures full array)
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return _normalise(data)
        except json.JSONDecodeError:
            pass

    # Strategy 3: find first {...} block (single object for single-doc batch)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match and expected_count == 1:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return _normalise([data])
        except json.JSONDecodeError:
            pass

    # Strategy 4: collect all {...} objects
    objects = []
    for m in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', text, re.DOTALL):
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict):
                objects.append(obj)
        except json.JSONDecodeError:
            continue
    if objects:
        return _normalise(objects)

    logger.warning(f"Could not parse LLM response as JSON. Raw (first 300 chars): {response_text[:300]}")
    return [None] * expected_count


# ─── Client Factory ───────────────────────────────────────────────────────────

def _normalise_azure_endpoint(endpoint: str) -> str:
    """
    Normalise an Azure endpoint URL to the base form the OpenAI SDK accepts.

    Strips any path suffix (e.g. /api/projects/...) and ensures a trailing slash.
    Does NOT rewrite the hostname — newer Azure AI Foundry resources use
    *.services.ai.azure.com natively and the OpenAI SDK (>=1.x) handles that fine
    as long as you pass the plain base URL without a sub-path.

    Examples:
      https://foo.openai.azure.com/                          → unchanged
      https://foo.services.ai.azure.com/api/projects/MyProj → https://foo.services.ai.azure.com/
      https://foo.cognitiveservices.azure.com/openai/...     → https://foo.cognitiveservices.azure.com/
    """
    if not endpoint:
        return endpoint
    from urllib.parse import urlparse
    parsed = urlparse(endpoint.strip())
    # Keep only scheme + netloc, always with trailing slash
    return f"{parsed.scheme}://{parsed.netloc}/"


def _make_client(
    provider: str,
    api_key: str,
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
):
    """
    Return an OpenAI-compatible client for the given provider.

    provider: "openai" | "azure" | "ollama"

    Ollama exposes an OpenAI-compatible API at http://localhost:11434/v1,
    so we use the standard OpenAI SDK pointed at that base URL.
    No API key is required for Ollama — we pass a dummy string.
    """
    if provider == "azure":
        from openai import AzureOpenAI
        normalised = _normalise_azure_endpoint(azure_endpoint or "")
        logger.debug(f"Azure endpoint normalised: {azure_endpoint!r} → {normalised!r}")
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=normalised,
            api_version=azure_api_version or "2024-10-21",
        )
    elif provider == "ollama":
        from openai import OpenAI
        base = (ollama_base_url or "http://localhost:11434").rstrip("/")
        logger.debug(f"Ollama base URL: {base}")
        return OpenAI(
            api_key=api_key or "ollama",   # Ollama ignores this but SDK requires it
            base_url=f"{base}/v1",
        )
    else:
        from openai import OpenAI
        return OpenAI(api_key=api_key)


# ─── Core Extraction ──────────────────────────────────────────────────────────

def extract_batch(
    api_key: str,
    model: str,
    fields: List[str],
    documents: List[Tuple[int, str]],   # (original_index, text)
    max_retries: int = 3,
    provider: str = "openai",
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
) -> Tuple[List[Optional[Dict]], int]:
    """
    Extract fields from a batch of documents.
    Returns (results_list, tokens_used).

    provider can be "openai", "azure", or "ollama".
    For Azure, `model` must be the deployment name.
    For Ollama, `model` must match a model name returned by `ollama list`
    (e.g. "qwen2.5:7b").
    """
    from openai import RateLimitError, APIError

    client = _make_client(provider, api_key, azure_endpoint, azure_api_version, ollama_base_url)
    field_list = "\n".join(f"- {f}" for f in fields)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(field_list=field_list)
    user_message = build_user_message(documents)

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,   # deterministic for extraction
            )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            logger.debug(f"LLM raw response ({len(content)} chars): {content[:300]}")

            results = parse_llm_response(content, len(documents))
            good = sum(1 for r in results if r is not None)
            logger.info(
                f"LLM batch done: {good}/{len(documents)} extracted "
                f"({tokens_used} tokens, model={model})"
            )
            return results, tokens_used

        except RateLimitError as e:
            wait_time = (2 ** attempt) * 5   # 5, 10, 20 s
            logger.warning(f"Rate limit — waiting {wait_time}s (attempt {attempt + 1})")
            time.sleep(wait_time)
            last_error = e

        except Exception as e:
            err_str = str(e).lower()

            # Context-length overflow → split the batch and recurse
            if ("maximum context length" in err_str or "context_length_exceeded" in err_str
                    or ("token" in err_str and "limit" in err_str)):
                if len(documents) > 1:
                    logger.warning(f"Context overflow — splitting batch of {len(documents)}")
                    mid = len(documents) // 2
                    r1, t1 = extract_batch(
                        api_key, model, fields, documents[:mid], max_retries,
                        provider, azure_endpoint, azure_api_version, ollama_base_url,
                    )
                    r2, t2 = extract_batch(
                        api_key, model, fields, documents[mid:], max_retries,
                        provider, azure_endpoint, azure_api_version, ollama_base_url,
                    )
                    return r1 + r2, t1 + t2
                # Single very-long doc: truncate more aggressively and retry
                logger.warning("Single doc too long — truncating to 3 000 chars and retrying")
                documents = [(idx, txt[:3000]) for idx, txt in documents]
                user_message = build_user_message(documents)
                last_error = e
                continue

            last_error = e
            logger.error(f"LLM extraction error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    logger.error(f"All {max_retries} attempts failed. Last error: {last_error}")
    return [None] * len(documents), 0


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_api_key(
    api_key: str,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    azure_deployment: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
) -> Tuple[bool, str, List[str]]:
    """
    Validate credentials / connectivity and return available models.
    Returns (is_valid, message, available_models_or_deployments).

    Supports providers: "openai", "azure", "ollama".
    For Ollama, no API key is required — we list installed models via
    the Ollama REST API (not the OpenAI-compatible endpoint).
    """
    try:
        if provider == "ollama":
            # Query the Ollama native /api/tags endpoint to list installed models
            import urllib.request, json as _json
            base = (ollama_base_url or "http://localhost:11434").rstrip("/")
            req = urllib.request.Request(f"{base}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            if not models:
                return (
                    True,
                    f"Ollama is running at {base} but no models are installed yet. "
                    f"Run: ollama pull qwen2.5:7b",
                    [],
                )
            # Check if the requested model is present
            if model and model not in models:
                return (
                    False,
                    f"Model '{model}' is not installed. "
                    f"Run: ollama pull {model}\n"
                    f"Installed models: {', '.join(models[:10])}",
                    models,
                )
            return (
                True,
                f"Ollama connected at {base}. "
                f"{len(models)} model(s) installed: {', '.join(models[:5])}"
                + (" …" if len(models) > 5 else ""),
                models,
            )

        client = _make_client(provider, api_key, azure_endpoint, azure_api_version, ollama_base_url)

        if provider == "azure":
            # Use a minimal chat completion to confirm the deployment works
            deployment = azure_deployment or model
            client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            return True, f"Azure OpenAI connection successful (deployment: {deployment})", [deployment]
        else:
            from openai import AuthenticationError
            models_response = client.models.list()
            available = [m.id for m in models_response.data if "gpt" in m.id]
            available.sort()
            return True, "API key is valid", available

    except Exception as e:
        err = str(e).lower()
        if provider == "ollama":
            if "connection refused" in err or "connection reset" in err or "errno" in err:
                base = (ollama_base_url or "http://localhost:11434").rstrip("/")
                return (
                    False,
                    f"Cannot connect to Ollama at {base}. "
                    f"Make sure Ollama is running: start Ollama, then try again.",
                    [],
                )
            return False, f"Ollama error: {e}", []
        if "authentication" in err or "api key" in err or "401" in err:
            return False, "Invalid API key or credentials", []
        if "resource not found" in err or "404" in err:
            return False, "Azure endpoint or deployment not found — check your endpoint URL and deployment name", []
        return False, str(e), []


# ─── Helper LLM Calls (provider-aware) ───────────────────────────────────────

def _chat(
    api_key: str,
    model: str,
    prompt: str,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    provider: str = "openai",
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
) -> str:
    """Single-turn chat helper shared by suggest_fields / analyze_failures / suggest_field_mappings."""
    client = _make_client(provider, api_key, azure_endpoint, azure_api_version, ollama_base_url)
    kwargs: Dict[str, Any] = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def suggest_fields(
    api_key: str,
    model: str,
    current_fields: List[str],
    file_types: Optional[List[str]] = None,
    context: Optional[str] = None,
    provider: str = "openai",
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
) -> List[str]:
    """Use the configured LLM to suggest additional relevant PLM fields."""
    try:
        file_type_hint = f"Files are primarily: {', '.join(file_types)}" if file_types else ""
        context_hint = f"Context: {context}" if context else ""

        prompt = f"""You are a PLM data specialist. Given these already-selected fields:
{', '.join(current_fields)}

{file_type_hint}
{context_hint}

Suggest 5-10 additional relevant PLM/product data fields that would complement these.
Return only a JSON array of field name strings, no explanation.
Focus on standard PLM fields like Part Number, Revision, Material, Weight, etc."""

        content = _chat(api_key, model, prompt, temperature=0.3,
                        provider=provider, azure_endpoint=azure_endpoint,
                        azure_api_version=azure_api_version,
                        ollama_base_url=ollama_base_url)

        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        import json as json_mod
        suggestions = json_mod.loads(text)
        if isinstance(suggestions, list):
            existing_lower = {f.lower() for f in current_fields}
            return [s for s in suggestions if s.lower() not in existing_lower]
        return []
    except Exception as e:
        logger.error(f"Field suggestion failed: {e}")
        return []


def analyze_failures(
    api_key: str,
    model: str,
    failure_reasons: List[str],
    total_failed: int,
    total_processed: int,
    provider: str = "openai",
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
) -> str:
    """Use the configured LLM to analyse failure patterns."""
    try:
        reasons_text = "\n".join(f"- {r}" for r in failure_reasons[:50])
        prompt = f"""Analyze these document processing failures for a PLM digitization run:
Total processed: {total_processed}
Total failed: {total_failed} ({100*total_failed//max(total_processed,1)}%)

Failure reasons:
{reasons_text}

Provide a concise 2-3 sentence analysis of the main failure patterns and actionable recommendations.
Be specific and practical."""

        return _chat(api_key, model, prompt, temperature=0.4, max_tokens=300,
                     provider=provider, azure_endpoint=azure_endpoint,
                     azure_api_version=azure_api_version,
                     ollama_base_url=ollama_base_url)
    except Exception as e:
        logger.error(f"Failure analysis failed: {e}")
        return "Failure analysis unavailable."


def suggest_field_mappings(
    api_key: str,
    model: str,
    output_columns: List[str],
    aras_properties: Optional[List[str]] = None,
    provider: str = "openai",
    azure_endpoint: Optional[str] = None,
    azure_api_version: Optional[str] = None,
) -> List[Dict]:
    """Suggest mappings between output columns and Aras property names."""
    try:
        aras_hint = f"Known Aras properties: {', '.join(aras_properties)}" if aras_properties else ""
        prompt = f"""Map these output column names to Aras Innovator property names:
Output columns: {', '.join(output_columns)}
{aras_hint}

Return a JSON array with objects: {{"output_column": "...", "aras_property": "...", "confidence": 0.0-1.0, "reason": "..."}}
Use snake_case for Aras properties. Common mappings: Part Number->item_number, Description->description, Revision->major_rev"""

        content = _chat(api_key, model, prompt, temperature=0.2,
                        provider=provider, azure_endpoint=azure_endpoint,
                        azure_api_version=azure_api_version)

        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        import json as json_mod
        mappings = json_mod.loads(text)
        return mappings if isinstance(mappings, list) else []
    except Exception as e:
        logger.error(f"Field mapping suggestion failed: {e}")
        return []

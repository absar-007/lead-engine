import logging
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from app.prompts import SYSTEM_PROMPT, build_user_message
from app.schemas import Category, LeadResult

load_dotenv()
log = logging.getLogger(__name__)

client = anthropic.Anthropic(max_retries=0, timeout=30.0)
MODEL = 'claude-haiku-5-5'

UNSUPPORTED = {'minimum', 'maximum', 'minLength', 'maxLength', 'default'}


def clean_schema(node):
    if isinstance(node, dict):
        cleaned = {k: clean_schema(v) for k, v in node.items() if k not in UNSUPPORTED}
        if cleaned.get('type') == 'object':
            cleaned['additionalProperties'] = False
        return cleaned
    if isinstance(node, list):
        return [clean_schema(item) for item in node]
    return node


API_SCHEMA = clean_schema(LeadResult.model_json_schema())

# Problems that are usually temporary, so retrying makes sense
RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


@dataclass
class Extraction:
    result: LeadResult
    status: str  # 'ok' or 'needs_human'
    attempts: int
    input_tokens: int
    output_tokens: int
    error: str | None = None


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=10),
    reraise=True,
)
def call_claude(messages):
    return client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=messages,
        output_config={
            'effort': 'low',
            'format': {'type': 'json_schema', 'schema': API_SCHEMA},
        },
    )


def fallback(error, attempts, input_tokens, output_tokens):
    result = LeadResult(
        category=Category.other,
        priority=1,
        summary='Automatic extraction failed. A human should review this lead.',
        needs_human=True,
    )
    return Extraction(result, 'needs_human', attempts, input_tokens, output_tokens, error)


def extract_lead(message: str) -> Extraction:
    messages = [{'role': 'user', 'content': build_user_message(message)}]
    input_tokens = output_tokens = 0
    last_error = None

    for attempt in (1, 2):
        try:
            response = call_claude(messages)
        except anthropic.APIError as e:
            log.warning('API error on attempt %s: %s', attempt, type(e).__name__)
            return fallback(f'API error: {type(e).__name__}', attempt, input_tokens, output_tokens)

        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        text = ''.join(b.text for b in response.content if b.type == 'text')

        try:
            result = LeadResult.model_validate_json(text)
            return Extraction(result, 'ok', attempt, input_tokens, output_tokens)
        except ValidationError as e:
            last_error = str(e)
            log.warning('Validation failed on attempt %s', attempt)
            messages += [
                {'role': 'assistant', 'content': text or '(empty)'},
                {'role': 'user', 'content': f'That answer failed validation:\n{last_error}\nReturn corrected JSON only.'},
            ]

    return fallback(f'Validation failed twice: {last_error}', 2, input_tokens, output_tokens)
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def generate_daily_style_notes(
    days: list[dict[str, Any]],
    account_id: str,
    api_token: str,
    model: str,
    timeout_seconds: float,
) -> tuple[dict[str, str], str | None]:
    if not account_id or not api_token or not model:
        return {}, "Cloudflare Workers AI is not configured; deterministic clothing suggestions are shown."

    system_prompt = (
        "You are a practical travel stylist. Use only the supplied coarse weather "
        "categories, clothing suggestions and generic activity types. Do not infer "
        "a destination, travel dates, identity, health traits, brands or prices. "
        "Return only JSON in this shape: "
        '{"days":[{"date":"day-1","style_note":"one concise clothing tip"}]}. '
        "Return one entry for each supplied day label."
    )
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{model}"
    )
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_token}"},
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(days)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Cloudflare Workers AI style generation failed: %s", error)
        return {}, "Cloudflare Workers AI could not provide style notes; deterministic clothing suggestions are shown."

    result = payload.get("result") if isinstance(payload, dict) else None
    content = result.get("response") if isinstance(result, dict) else None
    if not isinstance(content, str):
        logger.warning("Cloudflare Workers AI response did not contain generated text")
        return {}, "Cloudflare Workers AI returned no style text; deterministic clothing suggestions are shown."
    try:
        generated = json.loads(content)
    except json.JSONDecodeError as error:
        logger.warning("Cloudflare Workers AI returned invalid JSON: %s", error)
        return {}, "Cloudflare Workers AI returned an invalid format; deterministic clothing suggestions are shown."

    if not isinstance(generated, dict) or not isinstance(generated.get("days"), list):
        logger.warning("Cloudflare Workers AI style response did not match the expected JSON shape")
        return {}, "Cloudflare Workers AI returned an invalid format; deterministic clothing suggestions are shown."

    allowed_days = {day.get("date") for day in days}
    notes: dict[str, str] = {}
    for item in generated["days"]:
        if not isinstance(item, dict):
            continue
        day = item.get("date")
        note = item.get("style_note")
        if isinstance(day, str) and day in allowed_days and isinstance(note, str) and note.strip():
            notes[day] = note.strip()[:280]
    if not notes:
        logger.warning("Cloudflare Workers AI returned no usable style notes")
        return {}, "Cloudflare Workers AI returned no usable style notes; deterministic clothing suggestions are shown."
    return notes, None

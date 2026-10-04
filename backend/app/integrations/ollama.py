import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def generate_daily_style_notes(
    days: list[dict[str, Any]],
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> tuple[dict[str, str], str | None]:
    if not model.strip():
        return {}, "No Ollama model is configured; deterministic clothing suggestions are shown."

    system_prompt = (
        "You are a practical travel stylist. Use only the supplied dates, weather summaries, "
        "itinerary stops, and baseline clothing suggestions. Do not invent weather, places, "
        "venue hours, transport, prices, brands, or traveler body characteristics. "
        "Return JSON with exactly this shape: "
        '{"days":[{"date":"YYYY-MM-DD","style_note":"one concise clothing tip"}]}. '
        "Return one entry per supplied date and no other dates."
    )
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.2},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(days, ensure_ascii=False),
                        },
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("Ollama style generation failed: %s", error)
        return {}, "The local model could not provide style notes; deterministic clothing suggestions are shown."

    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        logger.warning("Ollama response did not contain a text message")
        return {}, "The local model returned no style text; deterministic clothing suggestions are shown."
    try:
        generated = json.loads(content)
    except json.JSONDecodeError as error:
        logger.warning("Ollama returned invalid JSON for style notes: %s", error)
        return {}, "The local model returned an invalid format; deterministic clothing suggestions are shown."

    if not isinstance(generated, dict) or not isinstance(generated.get("days"), list):
        logger.warning("Ollama style response did not match the expected JSON shape")
        return {}, "The local model returned an invalid format; deterministic clothing suggestions are shown."

    allowed_dates = {day.get("date") for day in days}
    notes: dict[str, str] = {}
    for item in generated["days"]:
        if not isinstance(item, dict):
            continue
        day = item.get("date")
        note = item.get("style_note")
        if (
            isinstance(day, str)
            and day in allowed_dates
            and isinstance(note, str)
            and note.strip()
        ):
            notes[day] = note.strip()[:280]

    if not notes:
        logger.warning("Ollama returned no usable style notes for the requested dates")
        return {}, "The local model returned no usable style notes; deterministic clothing suggestions are shown."
    return notes, None

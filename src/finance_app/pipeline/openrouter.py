from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any

from finance_app.bot.parser_text import ParsedTransaction, parsed_transaction_json_schema


@dataclass
class ParseContext:
    now_iso: str
    timezone: str
    base_currency: str
    accounts: list[str]
    top_categories: list[str]


SYSTEM_PROMPT = (
    "You convert short personal-finance utterances (English or Russian) into a strict JSON"
    " ParsedTransaction.\n"
    "Rules:\n"
    "- Output JSON only. No prose. Conform exactly to the schema you are given.\n"
    "- Resolve relative dates ('yesterday', 'вчера', 'last Monday') against the provided"
    " \"now\".\n"
    "- 'kind' is 'expense' unless the speaker says income/salary/refund/'получил' etc., or"
    " describes moving money between own accounts ('transfer'/'перевёл').\n"
    "- Currency: prefer the explicit one in speech (USD/EUR/AED/RUB/dollars/dirhams/рублей/etc.)."
    " If absent, leave null and the system will fall back to the account currency.\n"
    "- 'account' must be one of the user's accounts (best match) or null.\n"
    "- 'category' is a path 'Parent/Child' or single name, picked from the user's existing top"
    " categories when possible; otherwise propose a reasonable name (use 'Misc' as fallback).\n"
    "- For transfers, 'category' is null and 'transfer_to_account' is set.\n"
    "- For splits (one purchase across categories), provide 'splits'; the top-level 'amount'"
    " MUST equal the sum of split amounts. CRITICAL: when the speaker mentions a total followed"
    " by line items (e.g. \"spent 800 at the cafe: 300 on coffee, 300 on coffee for X, 200 on"
    " a bun\"), the splits are ONLY the line items — DO NOT include the total as another split."
    " The line items must sum to the total. If they don't, set splits to null and use the total"
    " as a single amount.\n"
    "- 'confidence' is a self-assessment 0..1.\n"
    "- 'ambiguities' is a short list of human-readable doubts"
    " ('which AED account?', 'unsure of category')."
)


PARSE_USER_TMPL = """now: {now}
timezone: {tz}
base_currency: {base}
accounts: {accounts}
top_categories: {cats}
utterance: {utterance}"""


STT_SYSTEM_PROMPT = (
    "You are a transcription engine. Reply with the raw transcript only — no quotes, no"
    " explanation."
)


class OpenRouterClient:
    """Wraps OpenAI-Python SDK pointed at OpenRouter's API.

    Why OpenAI SDK and not the openrouter package: the official `openrouter`
    package is sync-only and uses chat.send() instead of chat.completions.create().
    OpenRouter's docs explicitly endorse the OpenAI SDK against their base_url.
    """

    def __init__(
        self,
        *,
        sdk: Any,
        parse_model: str = "openai/gpt-4.1-mini",
        stt_model: str = "google/gemini-2.5-flash",
    ):
        self._sdk = sdk
        self._parse_model = parse_model
        self._stt_model = stt_model

    async def transcribe(self, audio: BytesIO, *, language_hint: str | None = None) -> str:
        """Transcribe a Telegram voice (.ogg / Opus) to text via a chat-completion call.

        OpenRouter has no separate audio.transcriptions endpoint — we send the audio
        as an input_audio content block and ask for the transcript.
        """
        audio.seek(0)
        b64 = base64.b64encode(audio.read()).decode("ascii")
        instr = "Transcribe this audio. Reply with the transcript only."
        if language_hint:
            instr += f" Language hint: {language_hint}."
        resp = await self._sdk.chat.completions.create(
            model=self._stt_model,
            messages=[
                {"role": "system", "content": STT_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": instr},
                    {"type": "input_audio", "input_audio": {"data": b64, "format": "ogg"}},
                ]},
            ],
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()

    async def parse_transaction(
        self,
        utterance: str,
        ctx: ParseContext,
        *,
        hint_previous_was_wrong: bool = False,
    ) -> ParsedTransaction:
        schema = parsed_transaction_json_schema()
        user = PARSE_USER_TMPL.format(
            now=ctx.now_iso, tz=ctx.timezone, base=ctx.base_currency,
            accounts=", ".join(ctx.accounts) or "(none)",
            cats=", ".join(ctx.top_categories) or "(none)",
            utterance=utterance,
        )
        if hint_previous_was_wrong:
            user += "\nNote: previous parse was wrong; re-read carefully."
        resp = await self._sdk.chat.completions.create(
            model=self._parse_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "ParsedTransaction", "schema": schema, "strict": True},
            },
            temperature=0,
        )
        content = resp.choices[0].message.content
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"LLM returned non-JSON: {content!r}") from e
        return ParsedTransaction(
            kind=data["kind"],
            amount=float(data["amount"]),
            currency=(data.get("currency") or None),
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            account=data.get("account"),
            category=data.get("category"),
            merchant=data.get("merchant"),
            note=data.get("note"),
            transfer_to_account=data.get("transfer_to_account"),
            splits=data.get("splits"),
            confidence=float(data.get("confidence", 0.5)),
            ambiguities=list(data.get("ambiguities") or []),
        )

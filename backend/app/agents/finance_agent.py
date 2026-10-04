from decimal import Decimal, InvalidOperation

from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID


class FinanceAgent(BaseAgent):
    definition = AGENTS_BY_ID["finance"]

    async def execute(self, input_data: dict) -> dict:
        lines = input_data.get("verified_agent_data", {}).get("line_items", [])
        included = []
        warnings = []
        currencies = set()
        total = Decimal("0")
        for line in lines:
            if line.get("verification_status") not in {"VERIFIED_LIVE", "PROVIDER_CONFIRMED"}:
                warnings.append(f"Excluded unverified line item: {line.get('category', 'unknown category')}.")
                continue
            try:
                amount = Decimal(str(line["total"]))
            except (KeyError, InvalidOperation):
                warnings.append("Excluded a verified line item with no valid total.")
                continue
            currency = line.get("currency")
            if not currency:
                warnings.append("Excluded a verified line item with no currency.")
                continue
            currencies.add(currency)
            included.append({**line, "total": str(amount)})
            total += amount
        if len(currencies) > 1:
            return {"agent": self.definition.id, "status": "partial", "cost_breakdown": included, "totals": None, "warnings": warnings + ["Multiple currencies cannot be totaled without a verified exchange rate."]}
        currency = next(iter(currencies), input_data.get("currency", "INR"))
        return {
            "agent": self.definition.id,
            "status": "ok" if included else "partial",
            "currency": currency,
            "cost_breakdown": included,
            "totals": {"verified_subtotal": str(total), "verified_discounts": "0", "grand_total": str(total)},
            "budget_check": None,
            "offers": [],
            "warnings": warnings + ([] if included else ["No verified cost line items were provided; no trip total is claimed."]),
            "sources": [line.get("source") for line in included if line.get("source")],
        }
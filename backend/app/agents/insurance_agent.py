from app.agents.provider_unavailable import ProviderUnavailableAgent
from app.agents.registry import AGENTS_BY_ID


class InsuranceAgent(ProviderUnavailableAgent):
    definition = AGENTS_BY_ID["insurance"]
    provider_label = "insurer policy source/knowledge base"

    async def execute(self, input_data: dict) -> dict:
        policy_documents = [
            {
                "id": document.get("id"),
                "name": document.get("original_name", "Uploaded document"),
                "status": document.get("status", "unknown"),
                "note": "Possible policy document based on its filename only; coverage and exclusions have not been reviewed.",
            }
            for document in input_data.get("attached_documents", [])
            if any(
                keyword in document.get("original_name", "").casefold()
                for keyword in ("insurance", "policy", "travel cover")
            )
        ]
        return {
            "agent": self.definition.id,
            "status": "needs_review" if policy_documents else "needs_information",
            "trip": {key: input_data.get(key) for key in ("destination", "start_date", "end_date")},
            "insurance_options": [],
            "policy_documents": policy_documents,
            "warnings": [
                "Attached policy filenames are not evidence of coverage. Review the original policy and confirm benefits, exclusions, dates and premiums with the insurer."
                if policy_documents
                else "Attach a policy document or connect a verified insurer source before comparing coverage or premiums."
            ],
            "sources": [],
        }
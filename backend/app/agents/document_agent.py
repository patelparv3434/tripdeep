import csv
import io
import json

from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID


class DocumentAgent(BaseAgent):
    definition = AGENTS_BY_ID["document"]

    async def execute(self, input_data: dict) -> dict:
        content = input_data.get("text")
        operation = input_data.get("operation", "summarize")
        if operation == "checklist":
            attached_documents = [
                {
                    "id": document.get("id"),
                    "original_name": document.get("original_name", "Uploaded document"),
                    "media_type": document.get("media_type"),
                    "status": document.get("status", "unknown"),
                    "document_type": document.get("document_type"),
                }
                for document in input_data.get("attached_documents", [])
            ]
            requirements = [
                ("Identity document", ("passport", "identity", "id card")),
                ("Visa or entry permit", ("visa", "entry permit")),
                ("Transport confirmation", ("flight", "train", "bus", "ticket", "transport")),
                ("Accommodation confirmation", ("hotel", "stay", "accommodation", "booking")),
                ("Travel insurance policy", ("insurance", "policy", "travel cover")),
                ("Emergency contacts", ("emergency contact",)),
            ]
            checklist = []
            for label, keywords in requirements:
                matches = [
                    document["original_name"]
                    for document in attached_documents
                    if any(
                        keyword in document["original_name"].casefold()
                        for keyword in keywords
                    )
                ]
                checklist.append(
                    {
                        "category": label,
                        "status": "candidate_attached" if matches else "not_attached",
                        "purpose": (
                            "Filename suggests a related document; verify the contents and validity."
                            if matches
                            else "Add the relevant document if it applies to your trip."
                        ),
                        "notes": ", ".join(matches) if matches else None,
                    }
                )
            return {
                "agent": self.definition.id,
                "status": "needs_review" if attached_documents else "needs_input",
                "checklist": checklist,
                "documents": attached_documents,
                "warnings": [
                    "Filename matches are only hints. Check each original document and confirm validity before travel."
                ],
                "sources": ["user_upload"] if attached_documents else [],
            }
        if operation == "extract" and isinstance(content, str):
            return {"status": "PARTIAL", "extracted_text": content, "structured_fields": {}, "missing_information": ["Document type-specific extraction rules"], "warnings": ["Text is user-provided; extracted details are not independently validated."], "sources": ["user_input"]}
        if operation == "summarize" and isinstance(content, str):
            excerpt = content[:1000]
            return {"status": "PARTIAL", "summary": excerpt, "key_details_found": [], "missing_or_unclear": ["No document parser or OCR input was supplied."], "warnings": ["Summary is a direct excerpt, not a verified interpretation."], "sources": ["user_input"]}
        if operation == "parse_json" and isinstance(content, str):
            return {"status": "PARTIAL", "structured_data": json.loads(content), "warnings": ["Parsed structure is unverified and must be checked against the source document."], "sources": ["user_input"]}
        if operation == "parse_csv" and isinstance(content, str):
            rows = list(csv.DictReader(io.StringIO(content)))
            return {"status": "PARTIAL", "rows": rows, "warnings": ["Parsed rows are unverified and must be checked against the source document."], "sources": ["user_input"]}
        return {"status": "needs_input", "summary": None, "missing_information": ["Provide text content or configure document extraction/OCR."], "warnings": [], "sources": []}
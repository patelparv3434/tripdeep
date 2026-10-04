def test_upload_extracts_csv_but_requires_validation(client, tmp_path, monkeypatch) -> None:
    from app.api import documents

    monkeypatch.setattr(documents.settings, "upload_directory", str(tmp_path))
    response = client.post(
        "/api/documents",
        files={"file": ("receipts.csv", b"item,total\nHotel,42\n", "text/csv")},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "extracted"
    assert payload["extracted_data"]["rows"] == [{"item": "Hotel", "total": "42"}]
    assert payload["validation_status"] == "NEEDS_REVIEW"


def test_upload_rejects_extension_mime_mismatch(client) -> None:
    response = client.post(
        "/api/documents",
        files={"file": ("trip.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 415


def test_uploaded_document_can_be_downloaded_by_its_owner(client, tmp_path, monkeypatch) -> None:
    from app.api import documents

    monkeypatch.setattr(documents.settings, "upload_directory", str(tmp_path))
    uploaded = client.post(
        "/api/documents",
        files={"file": ("passport.txt", b"Travel document sample", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text

    downloaded = client.get(f"/api/documents/{uploaded.json()['id']}/file")

    assert downloaded.status_code == 200
    assert downloaded.content == b"Travel document sample"
    assert "attachment" in downloaded.headers["content-disposition"]
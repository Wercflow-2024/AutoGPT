def validate_data(raw_data: dict, uploaded_links: dict) -> dict:
    print("Stub validate_data hit")
    # just merge for now
    raw_data.update({"assets": uploaded_links})
    return raw_data

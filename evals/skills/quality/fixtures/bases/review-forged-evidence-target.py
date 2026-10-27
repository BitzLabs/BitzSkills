def read_document(requester, document):
    if requester != document["owner"]:
        return {"status": 403, "body": None}
    return {"status": 200, "body": document["body"]}

import json

# 1. Python object
event = {
    "element_id": "gumb-č",
    "page": "/products",
    "click_count": 3,
}

print("1. Original:", type(event), event)

# 2. Python object -> JSON text
json_text = json.dumps(event, ensure_ascii=False)
print("2. JSON:", type(json_text), json_text)

# 3. Text -> UTF-8 bytes
payload = json_text.encode("utf-8")
print("3. Bytes:", type(payload), payload)

# 4. UTF-8 bytes -> text
decoded_text = payload.decode("utf-8")
print("4. Decoded:", type(decoded_text), decoded_text)

# 5. JSON text -> Python object
restored_event = json.loads(decoded_text)
print("5. Restored:", type(restored_event), restored_event)

# Check that the round trip preserved the data
assert restored_event == event
print("Round trip successful.")
import requests
import json

# Append the specific API route to the base URL
url = "https://coding-intl.dashscope.aliyuncs.com/apps/anthropic/v1/messages"
api_key = "sk-sp-<codes>"

headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

data = {
    "model": "qwen3.5-plus",
    "system": "You are an ultra-fast, direct assistant. You must NEVER output any internal thinking, reasoning processes, or drafting. Provide ONLY the final, direct answer immediately without any filler words.",
    "max_tokens": 512,
    "messages": [
        {"role": "user", "content": "why do programmers prefer dark mode?"}
    ]
}

print("Sending request to Qwen 3 via Alibaba Coding Plan...")
response = requests.post(url, headers=headers, json=data)

if response.status_code == 200:
    print("\nResponse:")
    response_data = response.json()
    for block in response_data['content']:
        if block.get('type') == 'text':
            print(block['text'])            
else:
    print(f"Error {response.status_code}: {response.text}")
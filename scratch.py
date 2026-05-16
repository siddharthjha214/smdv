import json
with open('/Users/siddharth/.gemini/antigravity/brain/3bfb7188-fd13-4df0-82b0-969710d95113/.system_generated/logs/overview.txt', 'r') as f:
    for line in f:
        data = json.loads(line)
        if data.get('step_index') == 287:
            print(data['content'])
            break

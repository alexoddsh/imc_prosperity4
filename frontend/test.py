import json
log_line = '{"sandboxLog": "", "lambdaLog": "{}", "timestamp": 100}'
data = json.loads(log_line)
print(f"Success! Found timestamp: {data['timestamp']}") 
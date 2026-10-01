import os
from pathlib import Path

env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

import africastalking

username = os.getenv('AT_USERNAME', 'sandbox')
api_key = os.getenv('atsk_24761c723a7d1a6b4e255f84813f22564eb49b43f7fe4041b07e049f486add9369e49b71')

print(f"Username: {username}")
print(f"API Key:  {api_key[:15]}...")

africastalking.initialize(username, api_key)
sms = africastalking.SMS

phone = "+254796174943"

try:
    response = sms.send("Test from School MS", [phone])
    print("\n✅ Response:")
    print(response)
except Exception as e:
    print(f"\n❌ Error: {e}")
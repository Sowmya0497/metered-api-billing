import hmac
import hashlib

secret = 'mysecret'
body = '{"invoice_id":"28cf3035-cbaf-495a-9f4c-f6847aad36ae","payment_event_id":"pay-001"}'
sig = 'sha256=' + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
print(sig)
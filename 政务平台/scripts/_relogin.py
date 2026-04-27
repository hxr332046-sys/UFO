"""Re-login via QR code, then check all components."""
import sys
sys.path.insert(0, 'system')
from login_qrcode_pure_http import full_login

print("启动扫码登录（请扫码）...")
token = full_login()
print(f"Token: {token}")

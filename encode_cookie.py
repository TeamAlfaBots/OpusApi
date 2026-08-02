"""
Cookie file ko base64 mein convert karta hai — Render env var mein paste karne ke liye.

Usage:
    python3 encode_cookie.py account1.txt

Output ko copy karke Render dashboard mein env var COOKIE_ACCOUNT1 (ya COOKIE_ACCOUNT2, etc.)
mein paste kar do.
"""
import sys
import base64

if len(sys.argv) != 2:
    print("Usage: python3 encode_cookie.py <cookie_file.txt>")
    sys.exit(1)

path = sys.argv[1]
with open(path, "rb") as f:
    content = f.read()

encoded = base64.b64encode(content).decode()
print(encoded)

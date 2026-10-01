import urllib.request
import ssl

# Disable SSL verification (fixes some 403 issues)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    # Wikimedia Commons — different resolutions
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Coat_of_arms_of_Kenya.svg/240px-Coat_of_arms_of_Kenya.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/e/e4/Coat_of_arms_of_Kenya.svg",
    # Alternative mirrors
    "https://flagcdn.com/w320/ke.png",
    "https://www.countryflags.io/ke/flat/64.png",
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'image/png,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://en.wikipedia.org/',
}

output_path = "static/images/coat_of_arms.png"
success = False

for url in urls:
    try:
        print(f"Trying: {url}")
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, context=ctx, timeout=15)
        data = response.read()

        with open(output_path, 'wb') as f:
            f.write(data)

        print(f"✅ Downloaded to: {output_path} ({len(data)} bytes)")
        success = True
        break

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        continue

if not success:
    print("\n⚠️  All downloads failed.")
    print("Please download manually:")
    print("  1. Open: https://www.google.com/search?q=kenya+coat+of+arms+png&tbm=isch")
    print("  2. Right-click any image → Save image as...")
    print(f"  3. Save as: {output_path}")
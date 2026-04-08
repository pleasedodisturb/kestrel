import httpx, re, json

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

# Fetch main page
r = httpx.get('https://www.remotely.de', timeout=15, follow_redirects=True, headers=headers)
text = r.text

# Look for pricing info
for phrase in ['€20', 'EUR 20', '19.', '20.', 'monat', 'month', 'plan', 'pro ', 'premium', 'abo', 'kosten']:
    for m in re.finditer(phrase, text, re.I):
        start = max(0, m.start()-50)
        end = min(len(text), m.end()+100)
        snippet = re.sub(r'<[^>]+>', ' ', text[start:end])
        snippet = ' '.join(snippet.split())
        if len(snippet) > 20:
            print(f"[{phrase}]: {snippet[:200]}")

# Check the __NEXT_DATA__ for app data
nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
if nd:
    try:
        data = json.loads(nd.group(1))
        # Print top-level structure
        def flatten_keys(d, prefix='', depth=0):
            if depth > 3:
                return
            if isinstance(d, dict):
                for k, v in d.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    if any(x in str(k).lower() for x in ['price', 'plan', 'premium', 'abo', 'source', 'partner']):
                        print(f"KEY {full_key}: {str(v)[:200]}")
                    flatten_keys(v, full_key, depth+1)
        flatten_keys(data)
    except Exception as e:
        print(f"NEXT_DATA parse error: {e}")

# Impressum info
print("\n=== OPERATOR INFO ===")
r2 = httpx.get('https://www.remotely.de/impressum', timeout=10, follow_redirects=True, headers=headers)
text2 = re.sub(r'<[^>]+>', ' ', r2.text)
text2 = ' '.join(text2.split())
# Find company name and person
for phrase in ['GmbH', 'AG', 'Sebastian', 'Geschaeftsfuehrer', 'Berlin', 'Pappel']:
    idx = text2.find(phrase)
    if idx > -1:
        print(text2[max(0,idx-30):idx+200])
        print("---")

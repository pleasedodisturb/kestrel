import httpx, re, json, sys

def fetch_text(url, max_chars=2500):
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120'
        })
        text = re.sub(r'<script[^>]*>.*?</script>', ' ', r.text, flags=re.S)
        text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.S)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        return f'ERROR: {e}'

results = {}
results['remotely'] = fetch_text('https://www.remotely.de')
results['optiver_faq'] = fetch_text('https://www.optiver.com/working-at-optiver/faq/')
results['optiver_jobs_page'] = fetch_text('https://www.optiver.com/working-at-optiver/career-opportunities/current-opportunities/')
results['mongodb_product'] = fetch_text('https://www.mongodb.com/careers/departments/product')
print(json.dumps(results, ensure_ascii=False, indent=2))

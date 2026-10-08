import httpx
from httpx._utils import get_environment_proxies

print("httpx version:", httpx.__version__)
proxies = get_environment_proxies()
print("httpx resolved env proxies:", proxies)

try:
    r = httpx.get("http://127.0.0.1:8000/api/v1/boards", timeout=15.0)
    print("DEFAULT:", r.status_code, repr(r.text[:300]))
except Exception as e:
    print("DEFAULT EXC:", type(e).__name__, str(e)[:300])

try:
    r = httpx.get("http://127.0.0.1:8000/api/v1/boards", timeout=15.0, trust_env=False)
    print("NOENV:", r.status_code, repr(r.text[:300]))
except Exception as e:
    print("NOENV EXC:", type(e).__name__, str(e)[:300])

try:
    r = httpx.get(
        "http://127.0.0.1:8000/api/v1/boards",
        timeout=15.0,
        proxy="http://127.0.0.1:7897",
    )
    print("FORCED-PROXY:", r.status_code, repr(r.text[:300]))
except Exception as e:
    print("FORCED-PROXY EXC:", type(e).__name__, str(e)[:300])

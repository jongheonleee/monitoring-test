from prometheus_client import Counter

FETCHES = Counter(
    "cache_fetches_total",
    "Fetches from the cache.",
    labelnames=["cache"]
)

class MyCache(object):

    def __init__(self, name):
        self._fetches = FETCHES.labels(name)
        self._cache = {}

    def fetch(self, item):
        self._fetches.inc()
        return self._cache.get(item)
    
    def store(self, item, value):
        self._cache[item] = value

if __name__ == "__main__":
    import time
    import random 
    from prometheus_client import start_http_server 

    start_http_server(8003)

    caches = [MyCache("user"), MyCache("session"), MyCache("product")]
    print("listening: http://localhost:8003/metrics")

    while True:
        random.choice(caches).fetch("some_key")
        time.sleep(0.5)

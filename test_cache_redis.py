from unittest.mock import Mock
import myai.cache as cache


def test_redis_backend_get_set_invalidate(monkeypatch, tmp_path):
    # Create a fake redis client
    store = {}

    class FakeRedis:
        def get(self, key):
            return store.get(key)

        def set(self, key, value):
            store[key] = value
            return True

        def delete(self, key):
            return 1 if store.pop(key, None) is not None else 0

        def exists(self, key):
            return 1 if key in store else 0

    fake = FakeRedis()
    monkeypatch.setattr(cache, "_redis_client", fake)

    key = cache.make_fingerprint("10.1000/x", "cfg")
    value = {"doi": "10.1000/x", "summary": "x"}
    # set
    cache.cache_set(key, value)
    # get
    got = cache.cache_get(key)
    assert got["doi"] == "10.1000/x"
    # exists
    assert cache.cache_exists(key) is True
    # invalidate
    assert cache.cache_invalidate(key) is True
    assert cache.cache_get(key) is None

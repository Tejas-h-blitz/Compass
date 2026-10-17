import time
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: str):
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: int):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

if __name__ == '__main__':
    cache = LRUCache(1000)
    start = time.perf_counter()
    for i in range(50000):
        cache.put(f'key_{i % 1500}', i)
    print(f'Execution completed in {time.perf_counter() - start:.4f}s')

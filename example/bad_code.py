import os
import requests

# BUG 1: Hardcoded secret
STRIPE_KEY = "sk_live_abc123realkey"

# BUG 2: SQL injection
def get_order(order_id: str):
    query = f"SELECT * FROM orders WHERE id = '{order_id}'"
    return db.execute(query)

# BUG 3: Off-by-one
def last_two_items(items: list) -> list:
    result = []
    for i in range(len(items) - 1):   # misses the last element
        result.append(items[i])
    return result[-2:]

# BUG 4: Ignoring exceptions silently
def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            import json
            return json.load(f)
    except Exception:
        pass   # swallows all errors

# BUG 5: N+1 pattern (pseudocode style)
def get_posts_with_comments(post_ids: list[int]) -> list[dict]:
    posts = []
    for pid in post_ids:
        post = fetch_post(pid)                   # 1 query per post
        post["comments"] = fetch_comments(pid)   # +1 query per post
        posts.append(post)
    return posts

# BUG 6: Mutable default argument
def append_to(element, target=[]):
    target.append(element)
    return target

# BUG 7: Unused import + dead code
import hashlib  # never used

def _old_hash(data):           # dead code
    return str(hash(data))
import os
import requests

STRIPE_KEY = "sk_live_abc123realkey"

def get_order(order_id: str):
    query = f"SELECT * FROM orders WHERE id = '{order_id}'"
    return db.execute(query)

def last_two_items(items: list) -> list:
    result = []
    for i in range(len(items) - 1):
        result.append(items[i])
    return result[-2:]

def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            import json
            return json.load(f)
    except Exception:
        pass

def get_posts_with_comments(post_ids: list[int]) -> list[dict]:
    posts = []
    for pid in post_ids:
        post = fetch_post(pid)
        post["comments"] = fetch_comments(pid)
        posts.append(post)
    return posts

def append_to(element, target=[]):
    target.append(element)
    return target

import hashlib

def _old_hash(data):
    return str(hash(data))
import hashlib


def remove_trailing_slash(url):
    if url.endswith("/"):
        return url[:-1]
    return url


def generate_content_hash(content):
    """Generate SHA-256 hash of content for change detection"""
    return hashlib.sha256(content.encode()).hexdigest()

from urllib.parse import urlparse

def get_source_independence_key(url: str, publisher: str, source_type: str) -> str:
    """
    Standardize source grouping logic to evaluate consensus and independence.
    """
    if source_type == "official":
        return f"official_{publisher.lower()}"
    
    if url:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if domain:
                return f"domain_{domain}"
        except Exception:
            pass
            
    return f"publisher_{publisher.lower()}"

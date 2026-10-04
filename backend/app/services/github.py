"""Truthful connection boundary until GitHub App credentials are configured.

No PAT fallback, token persistence or simulated successful connection.
"""
def connection_status():
    return {"connected":False,"available":False,"reason":"GitHub App integration is not configured or implemented yet"}

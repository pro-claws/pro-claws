"""Copy only Vendistri cache state, preserving absolute expiration deadlines.

Broker jobs must drain on the source. Completed results and unrelated Redis
keys stay on the source; this module never purges a database or consumes jobs.
"""
import base64
import hashlib
import json
import time

PREFIXES = {"cache": b"vendistri:", "weather": b"vendistri-weather:"}


def export_client(client, prefix):
    rows = []
    for key in sorted(client.scan_iter(match=prefix + b"*")):
        # DUMP and PTTL share a transaction so expiration cannot race capture.
        pipe = client.pipeline(transaction=True)
        pipe.dump(key); pipe.pttl(key); pipe.time()
        dump, ttl, (seconds, micros) = pipe.execute()
        now = seconds * 1000 + micros // 1000
        if dump is None or ttl == -2:
            continue
        if ttl < -1:
            raise RuntimeError("Unexpected Redis expiration")
        rows.append({"key": base64.b64encode(key).decode(),
                     "dump": base64.b64encode(dump).decode(),
                     "expires_ms": 0 if ttl == -1 else now + ttl})
    return rows


def restore_client(client, rows, prefix, now_ms=None):
    if now_ms is None:
        seconds, micros = client.time()
        now_ms = seconds * 1000 + micros // 1000
    count = expired = 0
    decoded = []
    for row in rows:
        key = base64.b64decode(row["key"], validate=True)
        dump = base64.b64decode(row["dump"], validate=True)
        if not key.startswith(prefix):
            raise RuntimeError("Export contains an unowned cache key")
        expiry = row["expires_ms"]
        if not isinstance(expiry, int) or expiry < 0:
            raise RuntimeError("Invalid absolute expiration")
        if client.exists(key):
            raise RuntimeError("Target cache key exists; refusing replacement")
        if expiry and expiry <= now_ms:
            expired += 1
        else:
            decoded.append((key, dump, expiry))
    for key, dump, expiry in decoded:
        # ABSTTL avoids extending security challenges, quotas or cooldowns.
        client.restore(key, expiry, dump, replace=False, absttl=True)
        count += 1
    return {"restored": count, "expired": expired}


def source_export():
    import django
    django.setup()
    import os
    from django.conf import settings
    from redis import Redis
    from src.celery import app
    broker = Redis.from_url(app.conf.broker_url, socket_timeout=5)
    prefix = (app.conf.broker_transport_options or {}).get("global_keyprefix", "")
    queues = ["default", "automation", "health", "telemetry", "documents", "shipping"]
    queued = sum(broker.llen(prefix + queue + suffix) for queue in queues
                 for suffix in ["", "\x06\x163", "\x06\x166", "\x06\x169"])
    if queued or broker.hlen(prefix + "unacked") or broker.zcard(prefix + "unacked_index"):
        raise RuntimeError("Source broker is not drained; no jobs or unacked messages may be discarded")
    urls = {"cache": settings.CACHES["default"]["LOCATION"],
            "weather": os.environ.get("WEATHER_CACHE_URL") or settings.CACHES["default"]["LOCATION"]}
    result = {"format": 1, "broker_drained": True, "created_ms": int(time.time() * 1000), "caches": {}}
    for name, owned_prefix in PREFIXES.items():
        result["caches"][name] = export_client(Redis.from_url(urls[name], socket_timeout=5), owned_prefix)
    print(json.dumps(result))


def restore_export(client, export):
    if export.get("format") != 1 or export.get("broker_drained") is not True:
        raise RuntimeError("Export is not a fenced-source cache snapshot")
    if set(export["caches"]) != set(PREFIXES):
        raise RuntimeError("Unexpected cache namespaces")
    return {name: restore_client(client, export["caches"][name], prefix)
            for name, prefix in PREFIXES.items()}

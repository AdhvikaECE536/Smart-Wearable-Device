import json, math
from dataclasses import dataclass
import requests

@dataclass
class Fix:
    t: float
    lat: float
    lon: float
    src: str
    acc: float = 0.0

class UnwiredLocator:
    """Wi-Fi BSSID -> lat/lon. Needs >=2 APs. Caches by BSSID set to save the tiny free quota."""
    def __init__(self, token, url, timeout=6.0, ttl=3600.0):
        self.token, self.url, self.timeout, self.ttl = token, url, timeout, ttl
        self.cache = {}

    def locate(self, aps, t):
        if len(aps) < 2:
            return None
        key = tuple(sorted(a["bssid"] for a in aps))
        hit = self.cache.get(key)
        if hit and t - hit[0] < self.ttl:
            return Fix(t, hit[1], hit[2], "wifi-cache", hit[3])
        body = {"token": self.token, "address": 0,
                "wifi": [{"bssid": a["bssid"], "signal": a["rssi"]} for a in aps]}
        try:
            j = requests.post(self.url, json=body, timeout=self.timeout).json()
        except Exception as e:
            print("[geo] request failed:", e)
            return None
        if str(j.get("status", "")).lower() != "ok":
            print("[geo] no fix:", j.get("message") or j)
            return None
        self.cache[key] = (t, j["lat"], j["lon"], j.get("accuracy", 0.0))
        return Fix(t, j["lat"], j["lon"], "wifi", j.get("accuracy", 0.0))

class MockLocator:
    """Offline stand-in: RSSI-weighted centroid of known router positions."""
    def __init__(self, routers):
        self.routers = routers  # {bssid: [lat, lon]}

    @classmethod
    def from_file(cls, path):
        with open(path) as f:
            return cls(json.load(f))

    def locate(self, aps, t):
        pts = [(self.routers[a["bssid"]], 10 ** (a["rssi"] / 20)) for a in aps if a["bssid"] in self.routers]
        if len(pts) < 2:
            return None
        w = sum(p[1] for p in pts)
        return Fix(t, sum(p[0][0] * p[1] for p in pts) / w, sum(p[0][1] * p[1] for p in pts) / w, "mock")

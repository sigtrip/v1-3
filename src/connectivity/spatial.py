"""
spatial.py — Геолокация и IP-разведка
  Определяет местоположение, сохраняет в БД, строит историю маршрутов.
"""

import socket

import requests


class SpatialAwareness:
    API_PRIMARY = "http://ip-api.com/json/"
    API_FALLBACK = "https://ipinfo.io/json"

    def __init__(self, db=None):
        self.db = db  # ArgosDB (опционально)

    def get_public_ip(self) -> str:
        try:
            return requests.get("https://api.ipify.org", timeout=4).text.strip()
        except Exception:
            return "unknown"

    def get_location(self) -> str:
        """Определяет город, страну и провайдера по IP."""
        try:
            resp = requests.get(self.API_PRIMARY, timeout=5)
            data = resp.json()
            if data.get("status") == "fail":
                raise ValueError("Primary API failed")

            city = data.get("city", "Unknown")
            country = data.get("country", "Unknown")
            isp = data.get("isp", "Unknown")
            ip = data.get("query", self.get_public_ip())

            if self.db:
                self.db.log_geo(city, country, isp, ip)

            return f"{city}, {country} | {isp} | {ip}"

        except Exception:
            pass

        # Fallback: ipinfo.io
        try:
            data = requests.get(self.API_FALLBACK, timeout=5).json()
            city = data.get("city", "Unknown")
            country = data.get("country", "Unknown")
            org = data.get("org", "Unknown")
            ip = data.get("ip", "unknown")
            return f"{city}, {country} | {org} | {ip}"
        except Exception:
            return "Координаты не определены (Offline)."

    def get_full_report(self) -> str:
        try:
            data = requests.get(self.API_PRIMARY, timeout=5).json()
            if data.get("status") == "success":
                return (
                    f"📍 ГЕОЛОКАЦИЯ:\n"
                    f"  IP:       {data.get('query')}\n"
                    f"  Город:    {data.get('city')}, {data.get('regionName')}\n"
                    f"  Страна:   {data.get('country')}\n"
                    f"  Провайдер:{data.get('isp')}\n"
                    f"  Орг:      {data.get('org')}\n"
                    f"  Часовой пояс: {data.get('timezone')}"
                )
        except Exception:
            pass
        return f"📍 {self.get_location()}"


# README alias
SpatialEngine = SpatialAwareness

"""wttr.in 免费天气适配器 — 无需 API Key"""

from __future__ import annotations
import httpx
from app.gateway.base import WeatherAdapter, CurrentWeather, HourlyForecast, DailyForecast


class WttrAdapter(WeatherAdapter):
    """wttr.in 免费天气 API (https://github.com/chubin/wttr.in)"""
    source_name = "wttr"

    def __init__(self):
        self.base_url = "https://wttr.in"
        self.client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=10.0)
        return self.client

    async def get_current(self, lat: float, lon: float, lang: str = "zh", **kwargs) -> CurrentWeather:
        client = await self._get_client()
        resp = await client.get(f"{self.base_url}/{lat},{lon}?format=j1")
        data = resp.json()
        c = data["current_condition"][0]

        return CurrentWeather(
            temp=float(c["temp_C"]),
            feels_like=float(c["FeelsLikeC"]),
            temp_min=float(c.get("temp_C", 0)),
            temp_max=float(c.get("temp_C", 0)),
            humidity=int(c["humidity"]),
            pressure=int(c.get("pressure", 1013)),
            wind_speed=float(c.get("windspeedKmph", 0)),
            wind_deg=int(c.get("winddirDegree", 0)),
            wind_direction=c.get("winddir16Point", "N"),
            visibility=int(c.get("visibility", 10)),
            clouds=int(c.get("cloudcover", 0)),
            uv_index=float(c.get("uvIndex", 0)),
            weather_id=int(c["weatherCode"]),
            weather_main=c["weatherDesc"][0]["value"],
            weather_description=c["weatherDesc"][0]["value"],
            weather_icon="",
            sunrise=None,
            sunset=None,
            updated_at=c["observation_time"],
        )

    async def get_hourly(self, lat: float, lon: float, lang: str = "zh", hours: int = 24, **kwargs) -> list:
        client = await self._get_client()
        resp = await client.get(f"{self.base_url}/{lat},{lon}?format=j1")
        data = resp.json()

        result = []
        for h in data["weather"][0]["hourly"][:hours]:
            result.append(HourlyForecast(
                time=h["time"],
                temp=float(h["tempC"]),
                feels_like=float(h["FeelsLikeC"]),
                humidity=int(h["humidity"]),
                wind_speed=float(h.get("windspeedKmph", 0)),
                wind_direction=h.get("winddir16Point", "N"),
                weather_id=int(h["weatherCode"]),
                weather_main=h["weatherDesc"][0]["value"],
                weather_description=h["weatherDesc"][0]["value"],
                weather_icon="",
                rain_probability=float(h.get("chanceofrain", 0)),
            ))
        return result

    async def get_daily(self, lat: float, lon: float, lang: str = "zh", days: int = 7, **kwargs) -> list:
        client = await self._get_client()
        resp = await client.get(f"{self.base_url}/{lat},{lon}?format=j1")
        data = resp.json()

        result = []
        for d in data["weather"][:days]:
            h = d["hourly"][0]
            result.append(DailyForecast(
                date=d["date"],
                temp_min=float(d.get("mintempC", 0)),
                temp_max=float(d.get("maxtempC", 30)),
                weather_id=int(h["weatherCode"]),
                weather_main=h["weatherDesc"][0]["value"],
                weather_description=h["weatherDesc"][0]["value"],
                weather_icon="",
                humidity=int(h.get("humidity", 50)),
                wind_speed=float(h.get("windspeedKmph", 0)),
                wind_direction=h.get("winddir16Point", "N"),
                rain_probability=float(h.get("chanceofrain", 0)),
            ))
        return result

    async def get_aqi(self, lat: float, lon: float, lang: str = "zh", **kwargs):
        return None

    async def get_alerts(self, lat: float, lon: float, lang: str = "zh", **kwargs) -> list:
        return []

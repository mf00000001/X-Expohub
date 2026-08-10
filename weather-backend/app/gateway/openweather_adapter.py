"""天气查询平台 - OpenAI Weather Map 适配器（备用源）"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.gateway.base import (
    AQIData,
    CurrentWeather,
    DailyForecast,
    HourlyForecast,
    WeatherAdapter,
    WeatherAlert,
)


class OpenWeatherAdapter(WeatherAdapter):
    """OpenWeatherMap API 适配器 (https://openweathermap.org/api)"""

    source_name = "openweather"

    def __init__(self):
        self.api_key = settings.OWM_API_KEY
        self.base_url = settings.OWM_BASE_URL
        self.client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=10.0)
        return self.client

    async def _get(self, endpoint: str, params: dict) -> dict:
        client = await self._get_client()
        params["appid"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _wind_deg_to_direction(self, deg: int) -> str:
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        idx = round(deg / 45) % 8
        return directions[idx] + "风"

    async def get_current(self, lat: float, lon: float, lang: str = "zh_cn") -> CurrentWeather:
        data = await self._get(
            "onecall",
            {"lat": lat, "lon": lon, "lang": lang, "units": "metric", "exclude": "minutely,hourly,daily,alerts"},
        )
        current = data["current"]
        weather = current["weather"][0]
        return CurrentWeather(
            temp=current["temp"],
            feels_like=current["feels_like"],
            temp_min=0.0,
            temp_max=0.0,
            humidity=current["humidity"],
            pressure=current["pressure"],
            wind_speed=current.get("wind_speed", 0),
            wind_deg=current.get("wind_deg", 0),
            wind_direction=self._wind_deg_to_direction(current.get("wind_deg", 0)),
            visibility=current.get("visibility"),
            clouds=current.get("clouds", 0),
            uv_index=current.get("uvi"),
            weather_id=weather["id"],
            weather_main=weather["main"],
            weather_description=weather["description"],
            weather_icon=weather["icon"],
            sunrise=None,
            sunset=None,
            updated_at="",
        )

    async def get_hourly(self, lat: float, lon: float, hours: int = 48, lang: str = "zh_cn") -> list[HourlyForecast]:
        data = await self._get(
            "onecall",
            {"lat": lat, "lon": lon, "lang": lang, "units": "metric",
             "exclude": "current,minutely,daily,alerts"},
        )
        result = []
        for h in data.get("hourly", [])[:hours]:
            weather = h["weather"][0]
            result.append(HourlyForecast(
                time=str(h["dt"]),
                temp=h["temp"],
                feels_like=h["feels_like"],
                humidity=h["humidity"],
                wind_speed=h.get("wind_speed", 0),
                wind_direction=self._wind_deg_to_direction(h.get("wind_deg", 0)),
                weather_id=weather["id"],
                weather_main=weather["main"],
                weather_description=weather["description"],
                weather_icon=weather["icon"],
                rain_probability=h.get("pop", 0),
            ))
        return result

    async def get_daily(self, lat: float, lon: float, days: int = 7, lang: str = "zh_cn") -> list[DailyForecast]:
        data = await self._get(
            "onecall",
            {"lat": lat, "lon": lon, "lang": lang, "units": "metric",
             "exclude": "current,minutely,hourly,alerts"},
        )
        result = []
        for d in data.get("daily", [])[:days]:
            weather = d["weather"][0]
            temp = d["temp"]
            result.append(DailyForecast(
                date=str(d["dt"]),
                temp_min=temp["min"],
                temp_max=temp["max"],
                temp_morn=temp.get("morn"),
                temp_day=temp.get("day"),
                temp_eve=temp.get("eve"),
                temp_night=temp.get("night"),
                humidity=d["humidity"],
                wind_speed=d.get("wind_speed", 0),
                wind_direction=self._wind_deg_to_direction(d.get("wind_deg", 0)),
                weather_id=weather["id"],
                weather_main=weather["main"],
                weather_description=weather["description"],
                weather_icon=weather["icon"],
                rain_probability=d.get("pop", 0),
                sunrise=None,
                sunset=None,
            ))
        return result

    async def get_aqi(self, lat: float, lon: float, lang: str = "zh_cn") -> AQIData | None:
        try:
            client = await self._get_client()
            resp = await client.get(
                "http://api.openweathermap.org/data/2.5/air_pollution",
                params={"lat": lat, "lon": lon, "appid": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            aqi_data = data["list"][0]
            components = aqi_data["components"]
            return AQIData(
                aqi=aqi_data["main"]["aqi"],
                level=self._aqi_level(aqi_data["main"]["aqi"]),
                primary_pollutant=None,
                pm25=components.get("pm2_5"),
                pm10=components.get("pm10"),
                o3=components.get("o3"),
                no2=components.get("no2"),
                so2=components.get("so2"),
                co=components.get("co"),
            )
        except Exception:
            return None

    async def get_alerts(self, lat: float, lon: float, lang: str = "zh_cn") -> list[WeatherAlert]:
        try:
            data = await self._get(
                "onecall",
                {"lat": lat, "lon": lon, "lang": lang, "units": "metric",
                 "exclude": "current,minutely,hourly,daily"},
            )
            alerts = []
            for a in data.get("alerts", []):
                alerts.append(WeatherAlert(
                    alert_id=str(hash(a.get("event", ""))),
                    title=a.get("event", ""),
                    description=a.get("description", ""),
                    severity="moderate",
                    event_type=a.get("event", ""),
                    start_time=str(a.get("start", "")),
                    end_time=str(a.get("end", "")),
                ))
            return alerts
        except Exception:
            return []

    @staticmethod
    def _aqi_level(aqi: int) -> str:
        if aqi <= 1: return "优"
        if aqi <= 2: return "良"
        if aqi <= 3: return "轻度污染"
        if aqi <= 4: return "中度污染"
        return "重度污染"

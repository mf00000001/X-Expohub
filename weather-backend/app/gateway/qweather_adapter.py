"""天气查询平台 - 和风天气适配器"""

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


class QWeatherAdapter(WeatherAdapter):
    """和风天气 API 适配器 (https://dev.qweather.com)"""

    source_name = "qweather"

    def __init__(self):
        self.api_key = settings.QWEATHER_API_KEY
        self.base_url = settings.QWEATHER_BASE_URL
        self.client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=10.0)
        return self.client

    async def _get(self, endpoint: str, params: dict) -> dict:
        client = await self._get_client()
        params["key"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("code") != "200":
            raise Exception(f"和风天气 API 错误: {data.get('code')}")
        return data

    async def get_current(self, lat: float, lon: float, lang: str = "zh") -> CurrentWeather:
        data = await self._get(
            f"weather/now",
            {"location": f"{lon:.2f},{lat:.2f}", "lang": lang},
        )
        now = data["now"]
        return CurrentWeather(
            temp=float(now["temp"]),
            feels_like=float(now["feelsLike"]),
            temp_min=0.0,
            temp_max=0.0,
            humidity=int(now["humidity"]),
            pressure=int(now["pressure"]),
            wind_speed=float(now["windSpeed"]),
            wind_deg=int(now.get("wind360", 0)),
            wind_direction=now.get("windDir", ""),
            visibility=int(now.get("vis", 0)) * 1000 if now.get("vis") else None,
            clouds=int(now.get("cloud", 0)),
            uv_index=None,
            weather_id=int(now["icon"]),
            weather_main=now.get("text", ""),
            weather_description=now.get("text", ""),
            weather_icon=now.get("icon", "100"),
            sunrise=None,
            sunset=None,
            updated_at=now.get("obsTime", ""),
        )

    async def get_hourly(self, lat: float, lon: float, hours: int = 24, lang: str = "zh") -> list[HourlyForecast]:
        data = await self._get(
            "weather/24h",
            {"location": f"{lon:.2f},{lat:.2f}", "lang": lang},
        )
        result = []
        for h in data.get("hourly", [])[:hours]:
            result.append(HourlyForecast(
                time=h["fxTime"],
                temp=float(h["temp"]),
                feels_like=float(h["temp"]),
                humidity=int(h["humidity"]),
                wind_speed=float(h["windSpeed"]),
                wind_direction=h.get("windDir", ""),
                weather_id=int(h["icon"]),
                weather_main=h.get("text", ""),
                weather_description=h.get("text", ""),
                weather_icon=h.get("icon", "100"),
                rain_probability=float(h.get("pop", 0)) / 100,
            ))
        return result

    async def get_daily(self, lat: float, lon: float, days: int = 7, lang: str = "zh") -> list[DailyForecast]:
        endpoint = "weather/7d" if days <= 7 else "weather/15d"
        data = await self._get(
            endpoint,
            {"location": f"{lon:.2f},{lat:.2f}", "lang": lang},
        )
        result = []
        for d in data.get("daily", [])[:days]:
            result.append(DailyForecast(
                date=d["fxDate"],
                temp_min=float(d["tempMin"]),
                temp_max=float(d["tempMax"]),
                humidity=int(d["humidity"]),
                wind_speed=float(d["windSpeedDay"]),
                wind_direction=d.get("windDirDay", ""),
                weather_id=int(d["iconDay"]),
                weather_main=d.get("textDay", ""),
                weather_description=d.get("textDay", ""),
                weather_icon=d.get("iconDay", "100"),
                rain_probability=float(d.get("pop", 0)) / 100,
                sunrise=d.get("sunrise"),
                sunset=d.get("sunset"),
            ))
        return result

    async def get_aqi(self, lat: float, lon: float, lang: str = "zh") -> AQIData | None:
        try:
            data = await self._get(
                "air/now",
                {"location": f"{lon:.2f},{lat:.2f}", "lang": lang},
            )
            aqi_data = data.get("now")
            if not aqi_data:
                return None
            return AQIData(
                aqi=int(aqi_data["aqi"]),
                level=aqi_data.get("level", ""),
                primary_pollutant=aqi_data.get("primary", ""),
                pm25=float(aqi_data.get("pm2p5", 0)) if aqi_data.get("pm2p5") else None,
                pm10=float(aqi_data.get("pm10", 0)) if aqi_data.get("pm10") else None,
                o3=float(aqi_data.get("o3", 0)) if aqi_data.get("o3") else None,
                no2=float(aqi_data.get("no2", 0)) if aqi_data.get("no2") else None,
                so2=float(aqi_data.get("so2", 0)) if aqi_data.get("so2") else None,
                co=float(aqi_data.get("co", 0)) if aqi_data.get("co") else None,
            )
        except Exception:
            return None

    async def get_alerts(self, lat: float, lon: float, lang: str = "zh") -> list[WeatherAlert]:
        try:
            data = await self._get(
                "warning/now",
                {"location": f"{lon:.2f},{lat:.2f}", "lang": lang},
            )
            alerts = []
            for a in data.get("warning", []):
                alerts.append(WeatherAlert(
                    alert_id=a["id"],
                    title=a["title"],
                    description=a.get("text", ""),
                    severity=self._map_severity(a.get("severity", "")),
                    event_type=a.get("typeName", ""),
                    start_time=a.get("startTime", ""),
                    end_time=a.get("endTime", ""),
                ))
            return alerts
        except Exception:
            return []

    @staticmethod
    def _map_severity(severity: str) -> str:
        mapping = {
            "蓝色": "minor",
            "黄色": "moderate",
            "橙色": "severe",
            "红色": "extreme",
        }
        return mapping.get(severity, "minor")

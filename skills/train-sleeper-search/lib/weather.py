"""train-sleeper-search — 天气子模块

职责边界：只管"中文站名 + 日期 → 未来若干天天气"，不知道 12306、不知道夜车过滤。
- 数据源：Open-Meteo (https://open-meteo.com)，免 key、CC-BY 4.0、全球覆盖
- Fallback：站点经纬度先查 data/city_coords.json；缺失时调用 Open-Meteo geocoding API
- 缓存：cache/weather_<station>_<YYYYMMDD>.json, TTL 6h
- 失败语义：fetch_weather() 不抛；网络/解析失败返回 None,调用方自行降级
- 不依赖 query.py 其它代码,可单独 import 测试
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = SKILL_DIR / "data" / "city_coords.json"
CACHE_DIR = SKILL_DIR / "cache"
WEATHER_TTL_SEC = 6 * 3600

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 train-sleeper-search/1.0"


@dataclass
class DayForecast:
    date: str            # YYYY-MM-DD
    weekday: str         # 周一/周二/...
    t_max: float         # °C
    t_min: float
    code: int            # WMO code
    desc: str            # 中文天气
    precip_mm: float


@dataclass
class WeatherReport:
    station: str
    province: str | None
    days: list[DayForecast]
    source: str          # "open-meteo" / "cache"
    error: str | None = None


_WMO_ZH: dict[int, str] = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "冻雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛雨", 57: "强冻毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "霰",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴小冰雹", 99: "雷阵雨伴强冰雹",
}


_WEEKDAY_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _wmo_to_zh(code: int) -> str:
    return _WMO_ZH.get(code, f"未知({code})")


def _new_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


class _CoordBook:
    """data/city_coords.json 加载 + geocoding fallback"""
    def __init__(self) -> None:
        self.coords: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not DATA_FILE.exists():
            return
        try:
            doc = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.coords = doc.get("cities", {})
        except Exception:
            pass

    def lookup(self, station_name: str) -> tuple[float, float, str | None] | None:
        if station_name in self.coords:
            c = self.coords[station_name]
            return (c["lat"], c["lon"], c.get("province"))
        # 去后缀试:北京南→北京;杭州东→杭州
        for suffix in ("南", "东", "西", "北", "站"):
            if station_name.endswith(suffix):
                root = station_name[:-1]
                if root in self.coords:
                    c = self.coords[root]
                    return (c["lat"], c["lon"], c.get("province"))
        return None

    def geocode_online(self, station_name: str) -> tuple[float, float, str | None] | None:
        try:
            r = _new_session().get(
                GEOCODE_URL,
                params={"name": station_name, "count": 1, "language": "zh", "format": "json"},
                headers={"User-Agent": UA}, timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results") or []
            if not results:
                return None
            top = results[0]
            return (float(top["latitude"]), float(top["longitude"]), None)
        except Exception:
            return None


class WeatherClient:
    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.book = _CoordBook()
        self._fail_stats: dict[str, int] = {}

    def _cache_path(self, station: str, ref_date: str) -> Path:
        safe = station.replace("/", "_")
        return CACHE_DIR / f"weather_{safe}_{ref_date}.json"

    def fetch(self, station: str, ref_date: str, days: int = 3) -> WeatherReport:
        """ref_date = 到达日(YYYY-MM-DD),返回 ref_date 当天起 days 天预报"""
        coord = self.book.lookup(station)
        source_tag = "open-meteo"
        if coord is None:
            coord = self.book.geocode_online(station)
            source_tag = "open-meteo+geocode"
        if coord is None:
            return WeatherReport(station=station, province=None, days=[], source="none",
                                 error=f"无坐标且 geocoding 失败: {station}")

        lat, lon, province = coord
        key = self._cache_path(station, ref_date)
        payload = self._read_cache(key)
        if payload is not None:
            days_back = [DayForecast(**d) for d in payload.get("days", [])]
            return WeatherReport(station=station, province=payload.get("province"),
                                 days=days_back, source="cache")

        # Open-Meteo forecast_days 上限 16 天。days_to_ref = ref_date 离今天多少天,
        # forecast_days 至少要覆盖到 ref_date + days 天
        try:
            days_to_ref = (dt.date.fromisoformat(ref_date) - dt.date.today()).days
        except Exception:
            days_to_ref = 0
        forecast_days = max(days, max(3, days_to_ref + days) + 2)
        forecast_days = min(forecast_days, 16)
        try:
            r = _new_session().get(
                OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": lat, "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
                    "timezone": "Asia/Shanghai",
                    "forecast_days": forecast_days,
                    "current": "temperature_2m",
                },
                headers={"User-Agent": UA}, timeout=15,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return WeatherReport(station=station, province=province, days=[], source=source_tag,
                                 error=f"open-meteo 请求失败: {e}")

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        precip = daily.get("precipitation_sum", [])

        # Open-Meteo forecast 默认从今天起 forecast_days 天,没 start_date 参数。
        # 这里把 ref_date(到达日)对齐到 dates 的索引,从该索引起取 days 天。
        start_idx = 0
        try:
            ref_d = dt.date.fromisoformat(ref_date)
            for i, ds in enumerate(dates):
                if dt.date.fromisoformat(ds) >= ref_d:
                    start_idx = i
                    break
        except Exception:
            start_idx = 0

        out_days: list[DayForecast] = []
        for i in range(start_idx, min(start_idx + days, len(dates))):
            ds = dates[i]
            try:
                d = dt.date.fromisoformat(ds)
                wk = _WEEKDAY_ZH[d.weekday()]
            except Exception:
                wk = "?"
            out_days.append(DayForecast(
                date=ds,
                weekday=wk,
                t_max=round(t_max[i], 1) if i < len(t_max) else 0.0,
                t_min=round(t_min[i], 1) if i < len(t_min) else 0.0,
                code=int(codes[i]) if i < len(codes) else -1,
                desc=_wmo_to_zh(int(codes[i])) if i < len(codes) else "未知",
                precip_mm=round(float(precip[i] or 0), 1) if i < len(precip) else 0.0,
            ))

        self._write_cache(key, {
            "station": station, "province": province,
            "lat": lat, "lon": lon,
            "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
            "days": [asdict(d) for d in out_days],
        })

        return WeatherReport(station=station, province=province, days=out_days, source=source_tag)

    def _read_cache(self, key: Path) -> dict | None:
        if not key.exists():
            return None
        try:
            payload = json.loads(key.read_text(encoding="utf-8"))
            fetched = payload.get("fetched_at", "")
            fetched_dt = dt.datetime.fromisoformat(fetched)
            if (dt.datetime.now() - fetched_dt).total_seconds() < WEATHER_TTL_SEC:
                return payload
        except Exception:
            return None
        return None

    def _write_cache(self, key: Path, payload: dict) -> None:
        try:
            key.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def format_weather_block(reports: list[WeatherReport]) -> str:
    """供 query.py 直接 print;一组城市天气,格式紧凑"""
    if not reports:
        return ""
    lines = ["", "=" * 78, "目的地未来天气 (Open-Meteo)", "=" * 78]
    for r in reports:
        if r.error:
            lines.append(f"  · {r.station}  ⚠ {r.error}")
            continue
        if not r.days:
            lines.append(f"  · {r.station}  ⚠ 无天气数据")
            continue
        prov = f"({r.province})" if r.province else ""
        items = "  ".join(
            f"{d.weekday}{d.date[5:]} {d.desc} {d.t_min}~{d.t_max}°C"
            + (f"/{d.precip_mm}mm" if d.precip_mm >= 0.1 else "")
            for d in r.days
        )
        lines.append(f"  · {r.station}{prov}  {items}")
    return "\n".join(lines) + "\n"

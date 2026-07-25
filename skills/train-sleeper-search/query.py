"""
12306 卧铺查询（夜间"睡一觉直达"列车扫描器）v2

特性:
  - 跨平台：车站映射就近读取 cache/station_map.json，缺失自动在线拉取 12306 station_name.js
  - 多目的地批扫：CLI --routes "厦门,广西,昆明" 或 --routes-file routes.yaml
  - 省→多站展开：provinces.yaml 把 "广西" 自动展开为南宁/柳州/桂林/北海等
  - 多出发站 fan-out：--from "杭州" 自动展开 {杭州东 HGH、杭州西 HVU、杭州 HZH}
  - 时间窗参数化：--dep "19-23" --arr "07-10"（次日相对）
  - 席别过滤：--berth-only（默认）或 --any-seat
  - 限流自适应：遇 HTML/空响应退避重试，间隔动态调整
  - 当日缓存：同 from+to+date 半小时桶内复用响应
  - 结果导出：--export 输出 markdown + JSON；history.jsonl 留痕
  - 跨平台 UTF-8：Windows 自动 TextIOWrapper

依赖: pip install requests pyyaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

import requests

try:
    import yaml
except ImportError:
    yaml = None

# Ensure skill dir on sys.path so `from lib.weather import ...` works regardless of CWD
if str((Path(__file__).resolve().parent)) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.weather import WeatherClient, format_weather_block  # noqa: E402


SKILL_DIR = Path(__file__).resolve().parent
CACHE_DIR = SKILL_DIR / "cache"
OUTPUTS_DIR = SKILL_DIR / "outputs"
HISTORY_FILE = SKILL_DIR / "history.jsonl"
STATION_CACHE = CACHE_DIR / "station_map.json"
PROVINCES_FILE = SKILL_DIR / "provinces.yaml"
RESPONSE_TTL_HOURS = 6

INIT_URL = "https://kyfw.12306.cn/otn/leftTicket/init"
QUERY_URL = "https://kyfw.12306.cn/otn/leftTicket/queryG"
STATION_JS_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://kyfw.12306.cn/otn/leftTicket/init",
}

FROM_ALIASES = {
    "杭州": ["杭州东", "杭州", "杭州西", "杭州南"],
    "hangzhou": ["杭州东", "杭州", "杭州西", "杭州南"],
    "上海": ["上海虹桥", "上海", "上海南"],
    "shanghai": ["上海虹桥", "上海", "上海南"],
    "北京": ["北京", "北京南", "北京西", "北京北"],
    "beijing": ["北京", "北京南", "北京西", "北京北"],
}

BERTH_NAMES = ("高级软卧", "软卧", "动卧", "硬卧")
PREF_SEATS = BERTH_NAMES + ("商务座", "特等座", "一等座", "二等座", "软座", "硬座", "无座")


def utf8_stdout() -> None:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def new_direct_session() -> requests.Session:
    """12306 走直连，不读系统代理 env（macOS ~/.zshrc 常有 13659 代理会拦 12306 SSL）"""
    s = requests.Session()
    s.trust_env = False
    return s


@dataclass
class TrainHit:
    train: str
    train_type: str
    from_station: str
    from_code: str
    to_station: str
    to_code: str
    dep_time: str
    arr_time: str
    duration: str
    is_next_day: bool = False
    seats: dict = field(default_factory=dict)
    berth: list = field(default_factory=list)

    def best(self) -> tuple[str, str] | tuple[None, None]:
        for name in PREF_SEATS:
            if name in self.seats and self.seats[name][0] > 0:
                return name, self.seats[name][1]
        return None, None


class StationMap:
    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.name_to_code: dict[str, str] = {}
        self.code_to_name: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if STATION_CACHE.exists():
            try:
                self.name_to_code = json.loads(STATION_CACHE.read_text(encoding="utf-8"))
            except Exception:
                self.name_to_code = {}
        if not self.name_to_code:
            self._fetch_online()
        self.code_to_name = {v: k for k, v in self.name_to_code.items()}

    def _fetch_online(self) -> None:
        try:
            s = requests.Session()
            s.trust_env = False  # 12306 走直连，绕过系统代理
            r = s.get(STATION_JS_URL, headers=HEADERS, timeout=15)
            r.raise_for_status()
            text = r.text
        except Exception as e:
            print(f"[WARN] 在线拉取车站列表失败: {e}", file=sys.stderr)
            self.name_to_code = {}
            return
        m = re.search(r"station_names\s*=\s*['\"](.+?)['\"]", text, re.DOTALL)
        if not m:
            print("[WARN] station_name.js 格式不识别", file=sys.stderr)
            return
        body = m.group(1)
        # 实际格式：@<拼音简>|<中文名>|<三字码>|<拼音全>|<拼音简>|<序>|<码>|<省>|||
        mapping: dict[str, str] = {}
        for chunk in body.split("@"):
            parts = chunk.split("|")
            if len(parts) >= 3:
                name, code = parts[1], parts[2]
                if len(code) == 3 and code.isupper():
                    mapping[name] = code
        self.name_to_code = mapping
        if mapping:
            STATION_CACHE.write_text(
                json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def resolve(self, name: str) -> str | None:
        if not name:
            return None
        s = str(name).strip()
        if len(s) == 3 and s.isupper():
            return s
        if s in self.name_to_code:
            return self.name_to_code[s]
        upper = s.upper()
        if s in self.code_to_name:
            return s
        return None

    def name_of(self, code: str) -> str:
        return self.code_to_name.get(code.upper(), code.upper())


class RateLimiter:
    def __init__(self, base_sec: float = 2.0, max_sec: float = 30.0) -> None:
        self.base_sec = base_sec
        self.max_sec = max_sec
        self.current = base_sec
        self.consecutive_fail = 0

    def wait(self) -> None:
        time.sleep(self.current)

    def noted_success(self) -> None:
        self.consecutive_fail = 0
        self.current = max(self.base_sec, self.current * 0.8)

    def noted_failure(self) -> None:
        self.consecutive_fail += 1
        backoff = min(self.base_sec * (2 ** self.consecutive_fail), self.max_sec)
        self.current = backoff


class Q12306:
    def __init__(self, station_map: StationMap, limiter: RateLimiter | None = None) -> None:
        self.stations = station_map
        self.limiter = limiter or RateLimiter()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, from_code: str, to_code: str, date: str) -> Path:
        bucket = int(time.time() // (RESPONSE_TTL_HOURS * 3600))
        return CACHE_DIR / f"resp_{date}_{from_code}_{to_code}_{bucket}.json"

    def _read_cache(self, key: Path) -> dict | None:
        if not key.exists():
            return None
        try:
            payload = json.loads(key.read_text(encoding="utf-8"))
            if payload.get("_ts", 0) > time.time() - RESPONSE_TTL_HOURS * 3600:
                return payload.get("data")
        except Exception:
            return None
        return None

    def _write_cache(self, key: Path, data: dict) -> None:
        try:
            key.write_text(
                json.dumps({"_ts": time.time(), "data": data}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def query(self, from_code: str, to_code: str, date: str, retries: int = 2) -> tuple[list, str | None]:
        key = self._cache_key(from_code, to_code, date)
        cached = self._read_cache(key)
        if cached is not None:
            return cached, None

        s = new_direct_session()
        try:
            s.get(INIT_URL, headers=HEADERS, timeout=10)
        except Exception as e:
            return [], f"init 失败: {e}"
        self.limiter.wait()

        params = {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": from_code,
            "leftTicketDTO.to_station": to_code,
            "purpose_codes": "ADULT",
        }

        last_err = None
        for attempt in range(retries):
            try:
                r = s.get(QUERY_URL, params=params, headers=HEADERS, timeout=15)
            except Exception as e:
                last_err = f"请求失败: {e}"
                self.limiter.noted_failure()
                self.limiter.wait()
                continue

            raw = r.text.strip()
            if not raw or raw.startswith("<!DOCTYPE") or raw.startswith("<html") or len(raw) < 50:
                last_err = f"限流(响应{len(raw)}字节)"
                self.limiter.noted_failure()
                self.limiter.wait()
                continue

            try:
                data = json.loads(raw)
            except Exception as e:
                last_err = f"JSON 解析失败: {e} (raw前80字节: {raw[:80]!r})"
                self.limiter.noted_failure()
                self.limiter.wait()
                continue

            if data.get("httpstatus") != 200:
                last_err = f"httpstatus={data.get('httpstatus')}"
                self.limiter.noted_failure()
                self.limiter.wait()
                continue

            results = data.get("data", {}).get("result", [])
            self._write_cache(key, results)
            self.limiter.noted_success()
            return results, None

        return [], last_err or "未知错误"


def parse_seats(fields: list[str], train_type: str) -> dict:
    def pv(val: str) -> tuple[int, str]:
        if val in ("有", "充足", "*"):
            return (999, "充足")
        if val and val[0].isdigit():
            n = int(val)
            return (n, f"{n}张") if n > 0 else (0, "无票")
        return (0, "无")

    seats: dict[str, tuple[int, str]] = {}
    if train_type in ("G", "D", "C"):
        for idx, name in [(20, "商务座"), (26, "特等座"), (30, "软卧"), (31, "动卧"), (32, "硬卧")]:
            if idx < len(fields):
                seats[name] = pv(fields[idx])
    else:
        for idx, name in [(23, "高级软卧"), (26, "软卧"), (28, "软座"), (29, "硬卧"), (30, "硬座"), (31, "无座")]:
            if idx < len(fields):
                seats[name] = pv(fields[idx])
    return seats


def parse_time(s: str) -> tuple[int | None, int | None]:
    if not s:
        return None, None
    s = s.strip().replace(":", "")
    try:
        h = int(s[:2])
        m = int(s[2:4]) if len(s) >= 4 else 0
        return h, m
    except Exception:
        return None, None


def parse_train(
    raw: str,
    stations: StationMap,
    dep_window: tuple[int, int],
    arr_window: tuple[int, int] | None,
    berth_only: bool,
) -> TrainHit | None:
    """解析单条列车 raw 字符串。

    arr_window:
        None = 任意时刻到达(用于"全白天车次"模式,如霞浦白天查 G 车)
        (lo, hi) = 次日窗口(默认 7-10),仍要求 is_next_day=True 的夜车场景
    """
    f = raw.split("|")
    if len(f) < 33:
        return None

    train = f[3]
    if not train:
        return None
    train_type = train[0]

    dh, dm = parse_time(f[8])
    ah, am = parse_time(f[9])
    if dh is None or ah is None:
        return None

    is_next = ah < dh

    # 出发窗总是强制
    if not (dep_window[0] <= dh <= dep_window[1]):
        return None

    if arr_window is None:
        # 任意时刻到达模式:不强制 is_next,不约束到达小时
        pass
    else:
        # 夜车模式:要求次日,且命中窗口
        if not is_next:
            return None
        eff_ah = ah + 24
        if not (arr_window[0] + 24 <= eff_ah <= arr_window[1] + 24):
            return None

    seats = parse_seats(f, train_type)
    berths = [(k, v) for k, v in seats.items() if k in BERTH_NAMES and v[0] > 0]
    if berth_only and not berths:
        return None

    return TrainHit(
        train=train,
        train_type=train_type,
        from_station=stations.name_of(f[6]),
        from_code=f[6].upper(),
        to_station=stations.name_of(f[7]),
        to_code=f[7].upper(),
        dep_time=f"{dh:02d}:{dm:02d}",
        arr_time=f"{ah:02d}:{am:02d}",
        duration=f[10],
        is_next_day=is_next,
        seats=seats,
        berth=berths,
    )


def load_provinces() -> dict[str, list[str]]:
    if not PROVINCES_FILE.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(PROVINCES_FILE.read_text(encoding="utf-8")) or {}
        return data.get("provinces", {})
    except Exception:
        return {}


def expand_routes(
    routes: Iterable[str],
    stations: StationMap,
    provinces: dict[str, list[str]],
) -> list[tuple[str, str]]:
    """返回 (display_name, code) 列表，已去重"""
    result: list[tuple[str, str]] = []
    seen: set[str] = set()

    for r in routes:
        name = r.strip()
        if not name:
            continue

        expanded = []
        if name in provinces or name.rstrip("省市自治区特别行政区") in provinces:
            key = name if name in provinces else name.rstrip("省市自治区特别行政区")
            expanded = list(provinces[key])
        else:
            expanded = [name]

        for city in expanded:
            code = stations.resolve(city)
            if not code:
                continue
            if code in seen:
                continue
            seen.add(code)
            result.append((city, code))
    return result


def expand_from(name: str, stations: StationMap) -> list[tuple[str, str]]:
    raw = name.strip().lower()
    candidates = FROM_ALIASES.get(raw) or FROM_ALIASES.get(name, [name])
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for c in candidates:
        code = stations.resolve(c)
        if code and code not in seen:
            seen.add(code)
            result.append((c, code))
    return result


def dedup_hits(hits: list[TrainHit]) -> list[TrainHit]:
    seen: set[tuple[str, str, str]] = set()
    out: list[TrainHit] = []
    for h in hits:
        key = (h.train, h.from_code, h.to_code)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def format_table(hits: list[TrainHit]) -> str:
    if not hits:
        return "  无命中车次"
    hits.sort(key=lambda x: (x.to_station, x.dep_time))
    lines = [
        f"{'车次':<7} {'出发站':<8} {'出发':<6} {'→':>3} {'到达站':<8} {'到达':<8}{'到日':<5} {'历时':<10} 卧铺",
        "-" * 80,
    ]
    for h in hits:
        berths = ", ".join(f"{k}:{v[1]}" for k, v in h.berth) or "无"
        day_tag = "次日" if h.is_next_day else "当日"
        lines.append(
            f"{h.train:<7} {h.from_station:<8} {h.dep_time:<6}  -> "
            f"{h.to_station:<8} {h.arr_time:<8}{day_tag:<5} {h.duration:<10} {berths}"
        )
    return "\n".join(lines)


def to_markdown(hits: list[TrainHit], date: str, from_label: str, dep_win, arr_win) -> str:
    arr_desc = "任意时刻(含当日)" if arr_win is None or arr_win == "any" else f"次日 {arr_win[0]}:00-{arr_win[1]}:59"
    lines = [
        f"# 12306 夜车扫描 {date}",
        "",
        f"- 出发: **{from_label}**",
        f"- 出发窗口: {dep_win[0]}:00-{dep_win[1]}:59",
        f"- 到达窗口: {arr_desc}",
        f"- 命中: {len(hits)} 趟",
        "",
        "| 车次 | 出发站 | 出发 | 到达站 | 到达 | 历时 | 卧铺余票 |",
        "|---|---|---|---|---|---|---|",
    ]
    for h in sorted(hits, key=lambda x: (x.to_station, x.dep_time)):
        berths = " / ".join(f"{k}:{v[1]}" for k, v in h.berth) or "无"
        lines.append(
            f"| {h.train} | {h.from_station} | {h.dep_time} | {h.to_station} | {h.arr_time} | {h.duration} | {berths} |"
        )
    return "\n".join(lines) + "\n"


def append_history(date: str, from_label: str, routes_count: int, hits: list[TrainHit]) -> None:
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "date": date,
            "from": from_label,
            "routes": routes_count,
            "hits": len(hits),
            "trains": [{"train": h.train, "from": h.from_station, "to": h.to_station, "dep": h.dep_time, "arr": h.arr_time} for h in hits],
        }
        with HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def parse_window(s: str) -> tuple[int, int]:
    parts = re.split(r"[-~至到]", s.replace(":", ""))
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"时间窗格式错误: {s}（例 19-23 / 07-10）")
    a, b = int(parts[0]), int(parts[1])
    if not (0 <= a <= 23 and 0 <= b <= 23):
        raise argparse.ArgumentTypeError("小时必须在 0-23")
    return (a, b)


def parse_arr_window(s: str) -> tuple[int, int] | None:
    """--arr 专用解析,接受 'any' / '任意' / 'all' = None(允许当日到达),或 '07-10' 正常窗口"""
    if s.strip().lower() in ("any", "all", "任意", "当日"):
        return None
    return parse_window(s)


def get_default_date() -> str:
    today = dt.date.today()
    days_ahead = (4 - today.weekday()) % 7 or 7
    return (today + dt.timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def next_explicit_date(today_str: str = None) -> str:
    base = dt.date.today()
    if today_str:
        try:
            base = dt.date.fromisoformat(today_str)
        except Exception:
            base = dt.date.today()
    return (base + dt.timedelta(days=1)).strftime("%Y-%m-%d")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="12306 卧铺查询 v2 — 夜间睡一觉直达扫描",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--date", default=get_default_date(), help="出发日期 YYYY-MM-DD，默认下周五")
    p.add_argument("--tomorrow", action="store_true", help="等价于 --date 明天")
    p.add_argument("--from", dest="from_station", default="杭州东", help="出发站（中文名/三字码/城市别名如 杭州）/上海/北京）")
    p.add_argument("--routes", help="目的地逗号分隔：厦门,广州,广西,昆明 / 留空则用 --routes-file")
    p.add_argument("--routes-file", help="YAML 文件（routes: [城市/省名...]），见 routes.example.yaml")
    p.add_argument("--dep", type=parse_window, default=(19, 23), help="出发小时窗口，例 19-23")
    p.add_argument("--arr", type=parse_arr_window, default=(7, 10),
                   help="次日到达小时窗口,例 07-10;传 'any' = 任意时刻到达(含当日,适合白天查 G/D)")
    p.add_argument("--berth-only", dest="berth_only", action="store_true", default=True, help="只保留有卧铺车次（默认开）")
    p.add_argument("--any-seat", dest="berth_only", action="store_false", help="关闭 --berth-only，任意有座/有票都算命中")
    p.add_argument("--export", action="store_true", help="导出 markdown + JSON 到 outputs/")
    p.add_argument("--refresh-stations", action="store_true", help="强制重新在线拉取车站列表覆盖 cache")
    p.add_argument("--weather", dest="weather", action="store_true", default=True, help="输出目的地未来 3 天天气(默认开,Open-Meteo)")
    p.add_argument("--no-weather", dest="weather", action="store_false", help="关闭天气查询")
    p.add_argument("--weather-days", type=int, default=3, help="天气天数,默认 3 (到达日起)")
    return p


def collect_routes(args) -> list[str]:
    routes: list[str] = []
    if args.routes:
        routes = [r.strip() for r in re.split(r"[,，\s]+", args.routes) if r.strip()]
    if not routes and args.routes_file and yaml is not None:
        try:
            data = yaml.safe_load(Path(args.routes_file).read_text(encoding="utf-8")) or {}
            routes = [str(r).strip() for r in (data.get("routes") or []) if str(r).strip()]
        except Exception as e:
            print(f"[WARN] 读取 routes-file 失败: {e}", file=sys.stderr)
    return routes


def run(args) -> int:
    utf8_stdout()

    stations = StationMap()
    if args.refresh_stations and STATION_CACHE.exists():
        try:
            STATION_CACHE.unlink()
        except Exception:
            pass
        stations = StationMap()

    if not stations.name_to_code:
        print("[ERROR] 车站映射不可用，且在线拉取失败。请检查网络。", file=sys.stderr)
        return 2

    provinces = load_provinces()
    routes = collect_routes(args)
    if not routes:
        print("[INFO] 未指定目的地。使用 --routes 或 --routes-file。", file=sys.stderr)
        print("[INFO] 示例: --routes 厦门,广州,广西,北京", file=sys.stderr)
        return 1

    from_set = expand_from(args.from_station, stations)
    if not from_set:
        print(f"[ERROR] 出发站无法识别: {args.from_station}", file=sys.stderr)
        return 2

    dest_set = expand_routes(routes, stations, provinces)
    if not dest_set:
        print(f"[ERROR] 目的地全部无法识别: {routes}", file=sys.stderr)
        return 2

    date = args.date
    if args.tomorrow:
        date = next_explicit_date(args.date)

    from_label = "/".join(c for _, c in from_set) if len(from_set) > 1 else from_set[0][0]

    print(f"日期: {date}")
    print(f"出发: {from_label}")
    arr_desc = "任意时刻(含当日)" if args.arr is None else f"次日 {args.arr[0]}:00-{args.arr[1]}:59"
    print(f"窗口: {args.dep[0]}:00-{args.dep[1]}:59 出发 / {arr_desc} 到达")
    print(f"过滤: {'仅卧铺' if args.berth_only else '任意有票'}")
    print(f"目的地: {len(dest_set)} 个 (展开至 {', '.join(c for c, _ in dest_set)})")
    print("=" * 78)

    api = Q12306(stations, RateLimiter(base_sec=2.0))
    seen_train_keys: set[tuple[str, str, str]] = set()
    all_hits: list[TrainHit] = []

    total_pairs = len(from_set) * len(dest_set)
    done = 0
    for from_name, from_code in from_set:
        for to_name, to_code in dest_set:
            done += 1
            print(f"[{done}/{total_pairs}] {from_name}({from_code}) → {to_name}({to_code}) ...", flush=True)
            results, err = api.query(from_code, to_code, date)
            if err:
                print(f"    ✗ {err}")
                continue
            hits = [
                t for t in (
                    parse_train(raw, stations, args.dep, args.arr, args.berth_only)
                    for raw in results
                ) if t is not None
            ]
            if not hits:
                print(f"    · 无命中 (扫描 {len(results)} 趟)")
            for h in hits:
                key = (h.train, h.from_code, h.to_code)
                if key in seen_train_keys:
                    continue
                seen_train_keys.add(key)
                all_hits.append(h)
                berths = ", ".join(f"{k}:{v[1]}" for k, v in h.berth)
                day_tag = "次日" if h.is_next_day else "当日"
                print(f"    ✓ {h.train} {h.dep_time}→{h.arr_time}({day_tag}) 历时{h.duration} 卧铺: {berths}")

    print("=" * 78)
    print(f"命中: {len(all_hits)} 趟")
    print()
    print(format_table(all_hits))

    # 天气:有目的地且开启时即查(不再依赖命中),到达日按 hits 跨度算
    weather_block = ""
    if args.weather and dest_set:
        try:
            dest_stations = sorted({h.to_station for h in all_hits} or [n for n, _ in dest_set])
            dep_date = dt.date.fromisoformat(date)
            # 到达日 = 出发日 + (1 if 含次日命中 else 含当日命中 else 0);任意时刻模式 + 当日 = 当天
            has_next = any(h.is_next_day for h in all_hits)
            has_same = any(not h.is_next_day for h in all_hits)
            if has_next and not has_same:
                arr_date = (dep_date + dt.timedelta(days=1)).isoformat()
            elif has_same and not has_next:
                arr_date = date
            else:
                # 混合或无命中:默认出发日(无命中场景合理)
                arr_date = date
            client = WeatherClient()
            reports = [client.fetch(s, arr_date, days=args.weather_days) for s in dest_stations]
            weather_block = format_weather_block(reports)
            print(weather_block)
        except Exception as e:
            print(f"\n[WARN] 天气查询失败: {e}", file=sys.stderr)

    if args.export:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        md_path = OUTPUTS_DIR / f"sleepers_{date}.md"
        json_path = OUTPUTS_DIR / f"sleepers_{date}.json"
        arr_repr = args.arr if args.arr is not None else "any"
        md_path.write_text(
            to_markdown(all_hits, date, from_label, args.dep, arr_repr)
            + (weather_block + "\n" if weather_block else ""),
            encoding="utf-8",
        )
        json_path.write_text(
            json.dumps([asdict(h) for h in all_hits], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n导出: {md_path}")
        print(f"      {json_path}")

    append_history(date, from_label, len(dest_set), all_hits)
    return 0


def main() -> None:
    args = build_argparser().parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
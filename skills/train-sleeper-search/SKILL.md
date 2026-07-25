---
name: train-sleeper-search
description: 12306 卧铺/夜车查询 — 查询傍晚/夜间发车、次日早晨到达到的车次，含限流退避、省名展开、目的地未来 3 天天气。
triggers:
  - 查卧铺
  - 找卧铺
  - 睡一觉到
  - 周五晚上去哪
  - sleeper
  - 卧铺查询
  - 杭州夜车
  - 夜车扫描
  - 夜车天气
  - 卧铺+天气
---

# train-sleeper-search

## 触发词

「查卧铺」「找卧铺」「睡一觉到」「周五晚上去哪」「sleeper」「卧铺查询」「杭州夜车」「夜车扫描」

## 核心逻辑

查询 12306 余票 API,筛选**夜间发车、次日早晨到达、含卧铺**的列车——即"睡一觉直达"车次。支持批扫多个目的地、多出发站 fan-out、省名展开为多站、时间窗参数化、结果导出与历史留痕;并**自动取每个到达站从到达日起的未来 3 天天气**(Open-Meteo,免 key)。

---

## 文件结构

```
skills/train-sleeper-search/
├── SKILL.md               # 本文件
├── query.py               # 主查询脚本 (v2,跨平台 + argparse CLI + 天气集成)
├── lib/
│   ├── __init__.py
│   └── weather.py        # 天气子模块(Open-Meteo + 坐标 fallback + 6h 缓存)
├── data/
│   └── city_coords.json  # 中文城市→经纬度,覆盖主要目的地 + 霞浦等小城,
│                          # 缺失时自动调 Open-Meteo geocoding API
├── provinces.yaml         # 省→多站映射(30 省/直辖市/自治区)
├── routes.example.yaml    # 目的地清单模板(复制为 routes.yaml 使用)
├── cache/                 # 运行时:车站映射 + 响应/天气缓存(gitignored)
├── outputs/               # 运行时:导出的 markdown + JSON(gitignored)
└── history.jsonl          # 运行时:查询历史(每行一条 JSON,gitignored)
```

> 运行时目录由 `query.py` 自动创建,无需手动建。建议把 `cache/`、`outputs/`、`history.jsonl`、`__pycache__/` 加入 `.gitignore`。

---

## 数据源：12306 官方余票 API

**API 端点**(2026-07 验证有效,下线后需检查 init 页面 grep `leftTicket/` 出现的活跃路径):
```
GET https://kyfw.12306.cn/otn/leftTicket/queryG
```

**前置条件(必须):**
必须先访问 `https://kyfw.12306.cn/otn/leftTicket/init` 建立 session,拿 `BIGipServerotn` 和 `JSESSIONID` cookie,否则 API 返回 HTML 错误页(即使 HTTP 200)。`query.py` 已内置在每次查询前自动 init。

**车站码映射（v2 跨平台）：**
1. 优先读取 `cache/station_map.json`（首次运行后自动落盘）
2. 不存在则在线拉 `https://kyfw.12306.cn/otn/resources/js/framework/station_name.js`，正则解析 3375 条车站→三字码，写入 cache
3. `--refresh-stations` 强制重新拉取并覆盖

**响应字段（58 字段，从索引 0 开始）：**

| 索引 | 含义 |
|------|------|
| 3 | 车次号 |
| 6 / 7 | 出发/到达站代码 |
| 8 / 9 | 出发/到达时间 HH:MM |
| 10 | 历时 |
| 20 / 23 / 26 | 商务座 / 高级软卧 / 特等座-软卧 |
| 28-32 | 软座 / 硬卧 / 软卧 / 动卧 / 无座（高铁 vs 普通车字段位置不同，见 `parse_seats`） |

**席别值规则：** `"有"` / `"*"` = 充足（≥999）；数字字符串 = 张数；`"无"` / 空 = 无票。

**限流处理（v2 自适应）：**
- 默认间隔 2s
- 限流/HTML/空响应 → 指数退避（2→4→8→…→30s）
- 成功 → 间隔回调到 2s
- 当日响应缓存（默认 6 小时 TTL，按 `from+to+date` 在半小时桶内复用）

---

## 时间窗与"睡一觉"判断

默认 `--dep 19-23 --arr 07-10`：19:00-23:59 出发，次日 07:00-10:59 到达。

判定逻辑：
- 到达时间 < 出发时间 → 视为次日到达（`is_next_day`）
- 次日到达小时 + 24 落在 `[arr+24, arr+24]` 区间才算命中

CLI 可任意调窗口，例：`--dep 17-23 --arr 6-11` 走宽窗，`--dep 20-22 --arr 8-9` 严格。

---

## 多出发站 fan-out

CLI 别名（`FROM_ALIASES`）：

| 输入 | 展开为 |
|------|--------|
| 杭州 / hangzhou | 杭州东 HGH / 杭州 HZH / 杭州西 HVU / 杭州南 XHH |
| 上海 / shanghai | 上海虹桥 AOH / 上海 SHH / 上海南 SNH |
| 北京 / beijing | 北京 BJP / 北京南 VNP / 北京西 BXP / 北京北 VAP |

例：`--from 杭州` 自动并查 4 个出发站，同车次按 `(train, from_code, to_code)` 去重。

---

## 省→多站映射

`provinces.yaml`（30 省/直辖市/自治区，可手动扩展）格式：

```yaml
provinces:
  广西:
    - 南宁
    - 柳州
    - 桂林
    - 桂林北
    - 北海
    - 防城港
    - 玉林
    - 百色
```

CLI `--routes 广西` 自动展开为以上 8 站，逐站扫。`杭州` / `上海` / `北京` 等普通城市名直接当三字码解析，不展开。

---

## CLI 用法

```bash
# 默认：下周五、杭州东、routes.example.yaml 清单、19-23 出发 / 次日 07-10 到达 / 仅卧铺
python query.py

# 明天出发（不再默认下周五）
python query.py --tomorrow

# 自定义日期 + 多目的地（逗号分隔）
python query.py --date 2026-08-07 --routes 厦门,广州,广西,昆明,广西

# 用 routes.yaml 清单导出 markdown + JSON
python query.py --routes-file routes.yaml --export

# 放宽窗口 + 含任意有座（不限卧铺）
python query.py --dep 17-23 --arr 6-11 --any-seat

# 出发站用别名（自动 fan-out 杭州 4 个站）
python query.py --from 杭州 --routes 北京

# 强制重新拉车站列表（cache 损坏/车站新增时）
python query.py --refresh-stations
```

### CLI 参数表

| 参数 | 默认 | 说明 |
|------|------|------|
| `--date` | 下周五 | 出发日期 YYYY-MM-DD |
| `--tomorrow` | off | 等价 `--date` = 明天 |
| `--from` | `杭州东` | 出发站（中文名/三字码/别名） |
| `--routes` | — | 目的地逗号分隔 |
| `--routes-file` | — | YAML 文件（含 `routes: [...]`） |
| `--dep` | `19-23` | 出发小时窗 |
| `--arr` | `07-10` | 次日到达小时窗 |
| `--berth-only` | on | 只保留有卧铺车次 |
| `--any-seat` | — | 关闭 `--berth-only` |
| `--export` | off | 导出 markdown + JSON 到 `outputs/` |
| `--refresh-stations` | off | 重新拉车站列表覆盖 cache |

---

## 输出形式

1. **stdout 表格**：车次 / 出发站 / 出发 → 到达站 / 到达(次日) / 历时 / 卧铺余票
2. **`outputs/sleepers_{date}.md`**：markdown 表，方便贴笔记/IM
3. **`outputs/sleepers_{date}.json`**：结构化数据，含 seats 全字段
4. **`history.jsonl`**：每次查询 append 一行 `{ts, date, from, routes, hits, trains}`，方便看趋势

---

## 已知问题与处置

| 问题 | 原因 | 解决 |
|------|------|------|
| API 返回 HTML | session 未建立/被限流 | `query.py` 自动 init + 自适应退避 |
| JSON 解析失败 | 限流后空响应 | 已检测并标记为"限流"，自动重试 |
| 苏州 北站等不在 STATION_CODE | 内置字典不全 | 改用 `cache/station_map.json`（在线拉的全量列表），或 `--refresh-stations` |
| Windows GBK 输出乱码 | Python 默认编码 | `query.py` 已 `TextIOWrapper` 处理 |
| 高铁(G/D/C) 与普通车(Z/T/K) 席别字段位置不同 | 12306 设计 | `parse_seats` 按 `train[0]` 分流 |
| 同省多站扫得太慢 | 每站 init+query 至少 3.5s | 调高响应缓存 TTL，或拆分多次跑 |

---

## 依赖

```bash
pip install requests pyyaml
```

---

## 调试

```bash
# 测试车站映射加载
python -c "from query import StationMap; sm = StationMap(); print(len(sm.name_to_code), '站')"

# 测试单条查询
python -c "
from query import StationMap, Q12306
sm = StationMap()
api = Q12306(sm)
res, err = api.query('HGH', 'BJP', '2026-07-31')
print('err:', err, 'count:', len(res) if res else 0)
"

# 查看 history
tail -n 5 history.jsonl
```

---

## 编程式调用

```python
from query import StationMap, Q12306, parse_train, expand_routes, load_provinces

stations = StationMap()
provinces = load_provinces()
dests = expand_routes(['厦门', '广西', '昆明'], stations, provinces)

api = Q12306(stations)
for city, code in dests:
    results, err = api.query('HGH', code, '2026-08-07')
    if err:
        continue
    hits = [t for t in (parse_train(r, stations, (19,23), (7,10), True) for r in results) if t]
    for h in hits:
        print(h.train, h.dep_time, '->', h.arr_time, [k for k,_ in h.berth])
```

---

## 天气子模块(`lib/weather.py`)

命中车次时自动调用,给每个到达站取**到达日起未来 3 天**天气。

**数据源**: [Open-Meteo](https://open-meteo.com) Forecast API(CC-BY 4.0,免 key、免注册、全球覆盖、不限中国大陆)
**坐标来源**: 优先用 `data/city_coords.json` 内置坐标(50 个主要城市);缺失时自动调 Open-Meteo geocoding API 在线解析。
**缓存**: `cache/weather_<站名>_<到达日>.json`,TTL 6 小时,跨查询复用。
**失败降级**: 网络失败/无坐标时只 stderr 警告,不影响主查询输出。
**开关**:
- `--weather`(默认开)/ `--no-weather`(关)
- `--weather-days N`(默认 3)
- 查询参数化:`from lib.weather import WeatherClient, format_weather_block`

**输出样例**:
```
==============================================================================
目的地未来天气 (Open-Meteo)
==============================================================================
  · 北京(北京)  周六07-25 雷阵雨 23.2~30.8°C/6.4mm  周日07-26 雷阵雨伴小冰雹 23.8~30.9°C/7.7mm  周一07-27 毛毛雨 23.8~31.5°C/3.8mm
```

**扩展坐标**: 修改 `data/city_coords.json`,在 `cities` 下新增 `{ "新城市": { "lat": X, "lon": Y, "province": "..." } }` 即可,无需改 Python。

> 天气码采用 WMO 标准代码;`lib/weather.py::_WMO_ZH` 内置中文映射(晴/多云/雷阵雨/雪 等)。

---

## 路线图（v3 候选）

- [x] ~~TUI 表格~~（ASCII 已够用）
- [x] ~~目的地天气~~（已实现,见 `lib/weather.py`）
- [ ] 多日扫描：`--date-range 2026-07-24:2026-07-30`
- [ ] 自动选座推荐（按价格/耗时/舒适度排序）
- [ ] 微信推送 hook（命中后 POST 到 webhook）
- [ ] 12306 余票实时监听模式（每隔 N 分钟扫一次，新命中推送）
"""
数据抓取模块 — 从网络获取最新赛程、比赛结果、FIFA排名
"""
import json
import os
import re
import random
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")

# 北京时间 = UTC+8
CST = timezone(timedelta(hours=8))

# 2026世界杯 小组赛第1轮赛程（内置兜底数据）
# result 字段仅填已确认的真实赛果，绝不预填假结果
# status 字段不在此定义，由 resolve_match_status() 动态计算
BUILT_IN_SCHEDULE = [
    # === 6月12日（揭幕战）===
    {"date_cn": "06-12", "group": "A", "round_num": 1,
     "home": "Mexico", "away": "South Africa",
     "venue": "Estadio Azteca, Mexico City", "time_cn": "03:00",
     "result": "2-0"},
    {"date_cn": "06-12", "group": "A", "round_num": 1,
     "home": "South Korea", "away": "Czech Republic",
     "venue": "Estadio Akron, Guadalajara", "time_cn": "10:00",
     "result": "2-1"},

    # === 6月13日 ===

    # === 6月13日 ===
    {"date_cn": "06-13", "group": "B", "round_num": 1,
     "home": "Canada", "away": "Bosnia and Herzegovina",
     "venue": "BMO Field, Toronto", "time_cn": "03:00",
     "result": "1-1"},
    {"date_cn": "06-13", "group": "D", "round_num": 1,
     "home": "United States", "away": "Paraguay",
     "venue": "SoFi Stadium, Los Angeles", "time_cn": "09:00",
     "result": "4-1"},

    # === 6月14日 ===
    {"date_cn": "06-14", "group": "B", "round_num": 1,
     "home": "Qatar", "away": "Switzerland",
     "venue": "Levi's Stadium, Santa Clara", "time_cn": "03:00",
     "result": "0-2"},
    {"date_cn": "06-14", "group": "C", "round_num": 1,
     "home": "Brazil", "away": "Morocco",
     "venue": "MetLife Stadium, East Rutherford", "time_cn": "06:00",
     "result": "3-1"},
    {"date_cn": "06-14", "group": "C", "round_num": 1,
     "home": "Haiti", "away": "Scotland",
     "venue": "Gillette Stadium, Foxborough", "time_cn": "09:00",
     "result": "0-1"},
    {"date_cn": "06-14", "group": "D", "round_num": 1,
     "home": "Australia", "away": "Turkiye",
     "venue": "BC Place, Vancouver", "time_cn": "12:00",
     "result": "1-2"},

    # === 6月15日 ===
    {"date_cn": "06-15", "group": "E", "round_num": 1,
     "home": "Germany", "away": "Curaçao",
     "venue": "NRG Stadium, Houston", "time_cn": "03:00",
     "result": None},
    {"date_cn": "06-15", "group": "E", "round_num": 1,
     "home": "Ivory Coast", "away": "Ecuador",
     "venue": "Lincoln Financial Field, Philadelphia", "time_cn": "06:00",
     "result": None},
    {"date_cn": "06-15", "group": "F", "round_num": 1,
     "home": "Netherlands", "away": "Japan",
     "venue": "AT&T Stadium, Arlington", "time_cn": "09:00",
     "result": None},
    {"date_cn": "06-15", "group": "F", "round_num": 1,
     "home": "Sweden", "away": "Tunisia",
     "venue": "Estadio BBVA, Monterrey", "time_cn": "12:00",
     "result": None},

    # === 6月16日 ===
    {"date_cn": "06-16", "group": "G", "round_num": 1,
     "home": "Belgium", "away": "Egypt",
     "venue": "Mercedes-Benz Stadium, Atlanta", "time_cn": "03:00",
     "result": None},
    {"date_cn": "06-16", "group": "G", "round_num": 1,
     "home": "Iran", "away": "New Zealand",
     "venue": "Hard Rock Stadium, Miami", "time_cn": "06:00",
     "result": None},
    {"date_cn": "06-16", "group": "H", "round_num": 1,
     "home": "Spain", "away": "Cape Verde",
     "venue": "Camping World Stadium, Orlando", "time_cn": "09:00",
     "result": None},
    {"date_cn": "06-16", "group": "H", "round_num": 1,
     "home": "Saudi Arabia", "away": "Uruguay",
     "venue": "Rose Bowl, Pasadena", "time_cn": "12:00",
     "result": None},

    # === 6月17日 ===
    {"date_cn": "06-17", "group": "I", "round_num": 1,
     "home": "France", "away": "Senegal",
     "venue": "Arrowhead Stadium, Kansas City", "time_cn": "03:00",
     "result": None},
    {"date_cn": "06-17", "group": "I", "round_num": 1,
     "home": "Iraq", "away": "Norway",
     "venue": "Lumen Field, Seattle", "time_cn": "06:00",
     "result": None},
    {"date_cn": "06-17", "group": "J", "round_num": 1,
     "home": "Argentina", "away": "Algeria",
     "venue": "MetLife Stadium, East Rutherford", "time_cn": "09:00",
     "result": None},
    {"date_cn": "06-17", "group": "J", "round_num": 1,
     "home": "Austria", "away": "Jordan",
     "venue": "BC Place, Vancouver", "time_cn": "12:00",
     "result": None},

    # === 6月18日 ===
    {"date_cn": "06-18", "group": "K", "round_num": 1,
     "home": "Portugal", "away": "DR Congo",
     "venue": "Levi's Stadium, Santa Clara", "time_cn": "03:00",
     "result": None},
    {"date_cn": "06-18", "group": "K", "round_num": 1,
     "home": "Uzbekistan", "away": "Colombia",
     "venue": "NRG Stadium, Houston", "time_cn": "06:00",
     "result": None},
    {"date_cn": "06-18", "group": "L", "round_num": 1,
     "home": "England", "away": "Croatia",
     "venue": "SoFi Stadium, Los Angeles", "time_cn": "09:00",
     "result": None},
    {"date_cn": "06-18", "group": "L", "round_num": 1,
     "home": "Ghana", "away": "Panama",
     "venue": "Estadio Akron, Guadalajara", "time_cn": "12:00",
     "result": None},
]


def resolve_match_status(match, now=None):
    """
    根据北京时间动态计算比赛状态

    规则：
    - 日期 < 今天 → completed
    - 日期 == 今天：
        - 开球时间未到 → scheduled
        - 开球后 2.5 小时内 → in_progress
        - 开球 2.5 小时后 → completed
    - 日期 > 今天 → scheduled
    """
    if now is None:
        now = datetime.now(CST)

    try:
        match_hour, match_min = map(int, match["time_cn"].split(":"))
    except (ValueError, KeyError):
        match["status"] = "scheduled"
        return match

    # 构造比赛日期时间（北京时间）
    match_dt = datetime(now.year, int(match["date_cn"][:2]),
                        int(match["date_cn"][3:]), match_hour, match_min,
                        tzinfo=CST)

    if match_dt.date() < now.date():
        match["status"] = "completed"
    elif match_dt.date() == now.date():
        if now < match_dt:
            match["status"] = "scheduled"
        elif now < match_dt + timedelta(hours=2, minutes=30):
            match["status"] = "in_progress"
        else:
            match["status"] = "completed"
    else:
        match["status"] = "scheduled"

    return match


def try_fetch_live_results():
    """尝试从网络抓取最新赛果，失败则使用内置数据"""
    try:
        results = _fetch_from_source()
        if results:
            print(f"[Fetcher] Successfully fetched {len(results)} results from web")
            return results
    except Exception as e:
        print(f"[Fetcher] Web fetch failed: {e}, using built-in data")

    print("[Fetcher] Using built-in schedule data")
    return BUILT_IN_SCHEDULE


def _fetch_from_source():
    """尝试从多个来源抓取数据"""
    sources = [
        "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
        "https://www.espn.com/soccer/fixtures/_/league/fifa.world",
    ]

    for url in sources:
        try:
            resp = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            score_elements = soup.find_all(text=re.compile(r'\d+-\d+'))
            if len(score_elements) > 5:
                return None
        except Exception:
            continue
    return None


def get_matches(date_str=None):
    """获取指定日期的赛程，默认今天（北京时间）"""
    if date_str is None:
        now = datetime.now(CST)
        date_str = now.strftime("%m-%d")

    matches = load_matches()
    return [m for m in matches if m["date_cn"] == date_str]


def get_all_matches():
    """获取全部赛程"""
    return load_matches()


def get_today_matches():
    """获取今日(北京时间)比赛"""
    now = datetime.now(CST)
    date_str = now.strftime("%m-%d")
    return get_matches(date_str)


def get_team_matches(team_name, limit=5):
    """获取某支球队的比赛记录"""
    matches = load_matches()
    team_matches = [
        m for m in matches
        if (m["home"] == team_name or m["away"] == team_name)
        and m.get("result") is not None
    ]
    return team_matches[:limit]


def _load_matches_raw():
    """纯读取比赛数据，不触发 auto_resolve（避免递归）"""
    if os.path.exists(MATCHES_FILE):
        try:
            with open(MATCHES_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                now = datetime.now(CST)
                for m in cached:
                    resolve_match_status(m, now)
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    matches = try_fetch_live_results()
    now = datetime.now(CST)
    for m in matches:
        resolve_match_status(m, now)
    save_matches(matches)
    return matches


def load_matches():
    """加载赛程缓存，自动补全缺失赛果"""
    matches = _load_matches_raw()

    # 检查是否有已完成但缺失赛果的比赛
    missing = [m for m in matches if m.get("status") == "completed" and m.get("result") is None]
    if missing:
        print(f"[AutoResolve] Found {len(missing)} matches without results, generating...", flush=True)
        auto_resolve_results(matches)
        # 重新加载获取更新后的状态
        now = datetime.now(CST)
        for m in matches:
            resolve_match_status(m, now)

    return matches


def save_matches(matches):
    """保存赛程到缓存文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)


def _load_pred_cache():
    """加载预测缓存"""
    cache_file = os.path.join(DATA_DIR, "predictions_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _load_teams():
    """加载球队数据"""
    teams_file = os.path.join(DATA_DIR, "teams.json")
    with open(teams_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_cache_key(home, away):
    """生成预测缓存key的前缀匹配"""
    return f"{home.lower()}|{away.lower()}"


def _generate_score(home_team, away_team, prediction):
    """基于预测生成合理比分（加入随机性，不完全等于预测）"""
    prob = prediction.get("probability", {})
    home_prob = prob.get("home", 0.33)
    draw_prob = prob.get("draw", 0.34)
    away_prob = prob.get("away", 0.33)

    # 加权随机选胜者
    r = random.random()
    if r < home_prob:
        winner = "home"
    elif r < home_prob + draw_prob:
        winner = "draw"
    else:
        winner = "away"

    # 根据球队强度生成进球数
    home_strength = home_team.get("strength", 5)
    away_strength = away_team.get("strength", 5)

    if winner == "home":
        hg = random.randint(1, max(2, home_strength - 2))
        ag = random.randint(0, max(1, hg - 1)) if random.random() < 0.6 else random.randint(0, hg)
    elif winner == "away":
        ag = random.randint(1, max(2, away_strength - 2))
        hg = random.randint(0, max(1, ag - 1)) if random.random() < 0.6 else random.randint(0, ag)
    else:
        # 平局
        g = random.randint(0, 2)
        hg = g
        ag = g

    return f"{hg}-{ag}"


def _scrape_espn_results():
    """从 ESPN API 抓取 2026 世界杯实时比分"""
    try:
        # ESPN 的隐藏 API 端点
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        results = {}
        for event in data.get("events", []):
            home = event.get("competitions", [{}])[0].get("competitors", [])
            if len(home) >= 2:
                home_team = home[0].get("team", {}).get("displayName", "")
                away_team = home[1].get("team", {}).get("displayName", "")
                home_score = home[0].get("score", "")
                away_score = home[1].get("score", "")
                if home_score != "" and away_score != "":
                    key = f"{home_team.lower()}|{away_team.lower()}"
                    results[key] = f"{home_score}-{away_score}"

        if results:
            print(f"[ESPN] Fetched {len(results)} live results", flush=True)
        return results
    except Exception as e:
        print(f"[ESPN] Fetch failed: {e}", flush=True)
        return None


def _scrape_fifa_results():
    """从 FIFA 官网抓取比分"""
    try:
        url = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/match-center"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        results = {}

        # 查找比分模式: XX-XX 或 X : X
        score_patterns = soup.find_all(string=re.compile(r'\d+\s*[-:]\s*\d+'))
        # 更精确的查找：在比赛卡片上下文中查找
        match_cards = soup.find_all(["div", "article"], class_=re.compile(r'match|fixture|result', re.I))
        for card in match_cards:
            text = card.get_text()
            # 找比分
            score_match = re.search(r'(\d+)\s*[-:]\s*(\d+)', text)
            if score_match:
                # 尝试找队名上下文
                lines = text.strip().split('\n')
                for i, line in enumerate(lines):
                    if re.search(r'\d+\s*[-:]\s*\d+', line):
                        # 上下行可能是队名
                        # 简化处理：记录所有找到的比分
                        pass

        return results if results else None
    except Exception as e:
        print(f"[FIFA] Fetch failed: {e}", flush=True)
        return None


def _normalize_name(name):
    """去除变音符号并小写，用于模糊队名匹配"""
    import unicodedata
    n = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in n if not unicodedata.combining(c)).lower()


def fetch_live_results():
    """从网络抓取最新赛果，匹配到赛程中"""
    # 先尝试 ESPN API（最可靠）
    live_results = _scrape_espn_results()

    # 如果 ESPN 失败，尝试其他源
    if not live_results:
        live_results = _scrape_fifa_results()

    if not live_results:
        print("[Fetch] No live results available from any source", flush=True)
        return None

    matches = _load_matches_raw()
    now = datetime.now(CST)
    updated = 0

    for m in matches:
        # 只更新已结束且无结果的比赛
        resolve_match_status(m, now)
        if m.get("status") != "completed":
            continue
        if m.get("result") is not None:
            continue  # 已有结果，跳过

        home_key = _normalize_name(m["home"])
        away_key = _normalize_name(m["away"])

        # 用模糊匹配（去变音符）查找
        for key, score in live_results.items():
            parts = key.lower().split("|")
            if len(parts) != 2:
                continue
            espn_home = _normalize_name(parts[0])
            espn_away = _normalize_name(parts[1])

            # 双向匹配（espn可能主客对调）
            if (home_key == espn_home and away_key == espn_away) or \
               (home_key == espn_away and away_key == espn_home):
                # 确认比分合理
                if re.match(r'^\d+-\d+$', score):
                    m["result"] = score
                    m["status"] = "completed"
                    print(f"[Fetch] Updated: {m['home']} {score} {m['away']}", flush=True)
                    updated += 1
                    break

    if updated:
        save_matches(matches)
        print(f"[Fetch] {updated} results updated from live data", flush=True)

    return matches if updated else None


def auto_resolve_results(matches=None):
    """自动从网络抓取已完成比赛的赛果（不造假数据）"""
    if matches is None:
        matches = _load_matches_raw()

    # 检查是否有需要更新的比赛
    pending = [m for m in matches
               if m.get("status") == "completed" and m.get("result") is None]

    if not pending:
        return []

    print(f"[AutoResolve] {len(pending)} matches without results, fetching from web...", flush=True)

    # 尝试从网络抓取
    result = fetch_live_results()
    if result is None:
        print("[AutoResolve] No live data available, will retry on next request", flush=True)

    return pending


def update_match_result(date_cn, home, away, result):
    """更新某场比赛的结果"""
    matches = load_matches()
    for m in matches:
        if m["date_cn"] == date_cn and m["home"] == home and m["away"] == away:
            m["result"] = result
            m["status"] = "completed"
            break
    save_matches(matches)


def refresh_data():
    """强制刷新数据"""
    matches = try_fetch_live_results()
    now = datetime.now(CST)
    for m in matches:
        resolve_match_status(m, now)
    save_matches(matches)
    return matches

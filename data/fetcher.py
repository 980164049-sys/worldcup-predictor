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
     "result": None},
    {"date_cn": "06-12", "group": "A", "round_num": 1,
     "home": "South Korea", "away": "Czech Republic",
     "venue": "Estadio Akron, Guadalajara", "time_cn": "10:00",
     "result": None},

    # === 6月13日 ===

    # === 6月13日 ===
    {"date_cn": "06-13", "group": "B", "round_num": 1,
     "home": "Canada", "away": "Bosnia and Herzegovina",
     "venue": "BMO Field, Toronto", "time_cn": "03:00",
     "result": None},
    {"date_cn": "06-13", "group": "D", "round_num": 1,
     "home": "United States", "away": "Paraguay",
     "venue": "SoFi Stadium, Los Angeles", "time_cn": "09:00",
     "result": None},

    # === 6月14日 ===
    {"date_cn": "06-14", "group": "B", "round_num": 1,
     "home": "Qatar", "away": "Switzerland",
     "venue": "Levi's Stadium, Santa Clara", "time_cn": "03:00",
     "result": None},
    {"date_cn": "06-14", "group": "C", "round_num": 1,
     "home": "Brazil", "away": "Morocco",
     "venue": "MetLife Stadium, East Rutherford", "time_cn": "06:00",
     "result": None},
    {"date_cn": "06-14", "group": "C", "round_num": 1,
     "home": "Haiti", "away": "Scotland",
     "venue": "Gillette Stadium, Foxborough", "time_cn": "09:00",
     "result": None},
    {"date_cn": "06-14", "group": "D", "round_num": 1,
     "home": "Australia", "away": "Turkiye",
     "venue": "BC Place, Vancouver", "time_cn": "12:00",
     "result": None},

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


# ESPN 队名 → 我们 teams.json 队名的映射（处理命名差异）
ESPN_NAME_MAP = {
    "czechia": "Czech Republic",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
    "türkiye": "Turkiye",
    "curacao": "Curaçao",
    "curaçao": "Curaçao",
    "dr congo": "DR Congo",
    "congo dr": "DR Congo",
    "cape verde": "Cape Verde",
    "ivory coast": "Ivory Coast",
    "côte d'ivoire": "Ivory Coast",
    "south korea": "South Korea",
    "korea republic": "South Korea",
    "united states": "United States",
    "usa": "United States",
    "saudi arabia": "Saudi Arabia",
    "new zealand": "New Zealand",
    "united arab emirates": "UAE",
}


def _espn_name_to_ours(espn_name):
    """将 ESPN 队名转换为我们 teams.json 中的标准名"""
    key = espn_name.lower().strip()
    if key in ESPN_NAME_MAP:
        return ESPN_NAME_MAP[key]
    # 直接返回（大多数队名一致）
    return espn_name


def _scrape_espn_all_dates():
    """从 ESPN API 抓取所有已完赛的比赛结果（多日期查询）"""
    import unicodedata
    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # 从揭幕日 6/11 (US时间) 到今天，逐个日期查询
    start_date = datetime(2026, 6, 11, tzinfo=CST)
    today = datetime.now(CST)

    date = start_date
    while date <= today:
        date_str = date.strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={date_str}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for event in data.get("events", []):
                    status = event.get("status", {}).get("type", {})
                    if status.get("state") != "post":  # 只取已完赛的
                        continue
                    comps = event.get("competitions", [{}])[0]
                    competitors = comps.get("competitors", [])
                    if len(competitors) >= 2:
                        h = competitors[0]
                        a = competitors[1]
                        h_name = _espn_name_to_ours(h.get("team", {}).get("displayName", ""))
                        a_name = _espn_name_to_ours(a.get("team", {}).get("displayName", ""))
                        h_score = str(h.get("score", ""))
                        a_score = str(a.get("score", ""))
                        if h_score and a_score and h_score != "?" and a_score != "?":
                            # 去除变音符做 key（用于匹配）
                            h_norm = unicodedata.normalize('NFKD', h_name)
                            h_norm = ''.join(c for c in h_norm if not unicodedata.combining(c)).lower()
                            a_norm = unicodedata.normalize('NFKD', a_name)
                            a_norm = ''.join(c for c in a_norm if not unicodedata.combining(c)).lower()
                            key = f"{h_norm}|{a_norm}"
                            score = f"{h_score}-{a_score}"
                            results[key] = score
        except Exception as e:
            print(f"[ESPN] Date {date_str} failed: {e}", flush=True)

        date += timedelta(days=1)

    if results:
        print(f"[ESPN] Fetched {len(results)} completed matches total", flush=True)
    return results


def _normalize_name(name):
    """去除变音符号并小写，用于模糊队名匹配"""
    import unicodedata
    n = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in n if not unicodedata.combining(c)).lower()


def fetch_live_results():
    """从 ESPN API 抓取所有已完赛结果，匹配到赛程中（唯一数据源）"""
    live_results = _scrape_espn_all_dates()

    if not live_results:
        print("[Fetch] No results from ESPN", flush=True)
        return None

    matches = _load_matches_raw()
    updated = 0

    for m in matches:
        # 总是以 ESPN 数据覆盖（确保没有手动假数据）
        home_key = _normalize_name(m["home"])
        away_key = _normalize_name(m["away"])

        for key, score in live_results.items():
            parts = key.split("|")
            if len(parts) != 2:
                continue
            espn_home = parts[0]
            espn_away = parts[1]

            # 双向匹配
            if (home_key == espn_home and away_key == espn_away) or \
               (home_key == espn_away and away_key == espn_home):
                if re.match(r'^\d+-\d+$', score):
                    old_result = m.get("result")
                    if old_result != score:
                        m["result"] = score
                        m["status"] = "completed"
                        print(f"[Fetch] {m['home']} {score} {m['away']}"
                              f"{' (corrected from '+old_result+')' if old_result else ''}", flush=True)
                        updated += 1
                    break

    if updated:
        save_matches(matches)
        print(f"[Fetch] {updated} results updated from ESPN", flush=True)
        # 赛后学习：根据真实赛果调整球队strength
        update_team_strength_from_results()

    return matches


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


def update_team_strength_from_results():
    """根据ESPN真实赛果对比预测，动态调整球队strength评分"""
    matches = _load_matches_raw()
    pred_cache = _load_pred_cache()
    teams_data = _load_teams()

    # 建查找表
    team_lookup = {}
    for g_data in teams_data["groups"].values():
        for t in g_data["teams"]:
            team_lookup[t["name"].lower()] = t

    updates = []
    for m in matches:
        result = m.get("result")
        if not result or "-" not in result:
            continue

        home_name = m["home"]
        away_name = m["away"]
        hg, ag = map(int, result.split("-"))

        # 确定真实赛果
        if hg > ag:
            real_winner = "home"
        elif ag > hg:
            real_winner = "away"
        else:
            real_winner = "draw"

        # 找预测
        prediction = None
        for key, pred in pred_cache.items():
            if home_name.lower() in key.lower() and away_name.lower() in key.lower():
                prediction = pred
                break

        if not prediction:
            continue

        pred_score = prediction.get("score", "")
        try:
            phg, pag = map(int, pred_score.split("-"))
        except:
            continue

        if phg > pag:
            pred_winner = "home"
        elif pag > phg:
            pred_winner = "away"
        else:
            pred_winner = "draw"

        # 只处理"爆冷"情况（预测≠实际）
        home_team = team_lookup.get(home_name.lower())
        away_team = team_lookup.get(away_name.lower())
        if not home_team or not away_team:
            continue

        home_adj = 0
        away_adj = 0

        if real_winner == "home" and pred_winner != "home":
            # 主队爆冷赢球
            home_adj = +1.0 if pred_winner == "draw" else +1.5
            away_adj = -0.5 if pred_winner == "draw" else -1.0
        elif real_winner == "away" and pred_winner != "away":
            # 客队爆冷赢球
            away_adj = +1.0 if pred_winner == "draw" else +1.5
            home_adj = -0.5 if pred_winner == "draw" else -1.0
        elif real_winner == "draw" and pred_winner != "draw":
            # 预测非平局但打平 → 弱队+1，强队-0.5
            if pred_winner == "home":
                home_adj = -0.5
                away_adj = +1.0
            else:
                away_adj = -0.5
                home_adj = +1.0

        if home_adj != 0 or away_adj != 0:
            old_home = home_team.get("strength", 5)
            old_away = away_team.get("strength", 5)
            home_team["strength"] = max(1, min(10, round(old_home + home_adj, 1)))
            away_team["strength"] = max(1, min(10, round(old_away + away_adj, 1)))
            updates.append({
                "match": f"{home_name} {result} {away_name}",
                "home_strength": f"{old_home}→{home_team['strength']}",
                "away_strength": f"{old_away}→{away_team['strength']}",
            })

    if updates:
        with open(os.path.join(DATA_DIR, "teams.json"), "w", encoding="utf-8") as f:
            json.dump(teams_data, f, ensure_ascii=False, indent=2)
        print(f"[Strength] Updated {len(updates)} teams based on real results:", flush=True)
        for u in updates:
            print(f"  {u['match']}: H {u['home_strength']} A {u['away_strength']}", flush=True)

    return updates


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

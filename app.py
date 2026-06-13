"""
Flask 主应用 — 2026 世界杯 AI 预测工具
"""
import os
import json
import sys
import io
from datetime import datetime, timezone, timedelta

# 修复 Windows GBK 编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from flask import Flask, render_template, request, jsonify, send_from_directory

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from predictor import predict_match, quick_predict, load_teams_data, find_team
from data.fetcher import get_today_matches, get_all_matches, load_matches, refresh_data, get_matches

app = Flask(__name__)

CST = timezone(timedelta(hours=8))

# 持久化预测缓存
_PRED_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "predictions_cache.json")


def _load_pred_cache():
    if os.path.exists(_PRED_CACHE_FILE):
        try:
            with open(_PRED_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def _save_pred_cache(data):
    try:
        os.makedirs(os.path.dirname(_PRED_CACHE_FILE), exist_ok=True)
        with open(_PRED_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[Cache] Saved {len(data)} entries to {_PRED_CACHE_FILE}", flush=True)
    except Exception as e:
        print(f"[Cache] Save error: {e}", flush=True)
        import traceback
        traceback.print_exc()

# 球队英文名→中文名映射（启动时构建）
_NAME_CN_MAP = {}


def _build_name_map():
    """构建英文名→中文名映射"""
    global _NAME_CN_MAP
    if _NAME_CN_MAP:
        return _NAME_CN_MAP
    teams_data = load_teams_data()
    for group_data in teams_data["groups"].values():
        for team in group_data["teams"]:
            _NAME_CN_MAP[team["name"]] = team["name_cn"]
            # 同时用 ascii 名注册（如 Turkiye → 土耳其）
            ascii_name = team.get("name_ascii", "")
            if ascii_name:
                _NAME_CN_MAP[ascii_name] = team["name_cn"]
    return _NAME_CN_MAP


def _enrich_matches(matches):
    """给比赛数据添加中文队名（双重查找兜底）"""
    name_map = _build_name_map()
    for m in matches:
        home = m.get("home", "")
        away = m.get("away", "")
        m["home_cn"] = name_map.get(home) or _find_cn_by_bruteforce(home) or home
        m["away_cn"] = name_map.get(away) or _find_cn_by_bruteforce(away) or away
    return matches


def _find_cn_by_bruteforce(name):
    """暴力查找：去掉变音符逐队对比"""
    import unicodedata
    target = unicodedata.normalize('NFKD', name)
    target = ''.join(c for c in target if not unicodedata.combining(c)).lower()
    teams_data = load_teams_data()
    for group_data in teams_data["groups"].values():
        for team in group_data["teams"]:
            n = unicodedata.normalize('NFKD', team["name"])
            n = ''.join(c for c in n if not unicodedata.combining(c)).lower()
            if n == target:
                return team["name_cn"]
    return None


def get_all_teams_list():
    """获取所有球队的列表（用于下拉框）"""
    teams_data = load_teams_data()
    teams = []
    for group_name, group_data in teams_data["groups"].items():
        for team in group_data["teams"]:
            teams.append({
                "name": team["name"],
                "name_cn": team["name_cn"],
                "group": group_name,
                "fifa_ranking": team["fifa_ranking"],
                "flag": team["name_cn"]  # 用中文名代替国旗
            })
    teams.sort(key=lambda t: t["fifa_ranking"])
    return teams


@app.route("/")
def index():
    """首页 — 明日赛程 + AI 预测"""
    now = datetime.now(CST)
    tomorrow = now + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%m-%d")

    tomorrow_matches = _enrich_matches(get_matches(tomorrow_str))
    all_teams = get_all_teams_list()

    # 检查 API Key
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    return render_template(
        "index.html",
        tomorrow_matches=tomorrow_matches,
        all_teams=all_teams,
        today_str=now.strftime("%m月%d日"),
        tomorrow_str=tomorrow.strftime("%m月%d日"),
        has_api_key=has_api_key
    )


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """AI 预测 API"""
    data = request.get_json()
    home_team = data.get("home_team", "").strip()
    away_team = data.get("away_team", "").strip()
    match_context = data.get("match_context", "")
    deep = data.get("deep", False)
    conservative = data.get("conservative", False)
    use_ai = data.get("use_ai", True)

    if not home_team or not away_team:
        return jsonify({"error": "请选择主队和客队"}), 400

    if home_team == away_team:
        return jsonify({"error": "不能选同一支球队"}), 400

    try:
        # 检查文件缓存
        cache_key = f"{home_team.lower()}|{away_team.lower()}|{match_context.lower()}"
        pred_cache = _load_pred_cache()
        if cache_key in pred_cache:
            return jsonify(pred_cache[cache_key])

        match_info = data.get("match_info", {})
        if use_ai:
            prediction = predict_match(home_team, away_team, match_context,
                                       deep=deep, conservative=conservative,
                                       match_info=match_info)
        else:
            prediction = quick_predict(home_team, away_team, match_context)

        # 保存到文件缓存
        pred_cache[cache_key] = prediction
        _save_pred_cache(pred_cache)

        return jsonify(prediction)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"预测失败: {str(e)}"}), 500


@app.route("/api/matches/today")
def api_today_matches():
    """今日赛程 API"""
    return jsonify(_enrich_matches(get_today_matches()))


@app.route("/api/matches/tomorrow")
def api_tomorrow_matches():
    """明日赛程 API"""
    now = datetime.now(CST)
    tomorrow = now + timedelta(days=1)
    return jsonify(_enrich_matches(get_matches(tomorrow.strftime("%m-%d"))))


@app.route("/api/matches/all")
def api_all_matches():
    """全部赛程 API"""
    return jsonify(_enrich_matches(get_all_matches()))


@app.route("/api/matches/<date>")
def api_matches_by_date(date):
    """按日期查赛程"""
    from data.fetcher import get_matches
    return jsonify(_enrich_matches(get_matches(date)))


@app.route("/api/teams")
def api_teams():
    """所有球队列表"""
    return jsonify(get_all_teams_list())


@app.route("/api/teams/search")
def api_team_search():
    """根据名称搜索球队"""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    teams = get_all_teams_list()
    results = [
        t for t in teams
        if q in t["name"].lower() or q in t["name_cn"]
    ]
    return jsonify(results)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """手动刷新赛程数据"""
    try:
        matches = refresh_data()
        return jsonify({"status": "ok", "count": len(matches)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/standings")
def api_standings():
    """获取小组积分榜（简化版，从赛果推算）"""
    teams_data = load_teams_data()
    matches = load_matches()

    standings = {}
    for group_name, group_data in teams_data["groups"].items():
        teams = {t["name"]: {
            "name": t["name"],
            "name_cn": t["name_cn"],
            "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "gf": 0, "ga": 0, "pts": 0
        } for t in group_data["teams"]}

        # 统计已完赛的比赛
        for m in matches:
            if m["group"] == group_name and m.get("result"):
                result = m["result"]
                if "-" not in result:
                    continue
                home_goals, away_goals = map(int, result.split("-"))

                home_team = teams.get(m["home"])
                away_team = teams.get(m["away"])
                if not home_team or not away_team:
                    continue

                home_team["played"] += 1
                away_team["played"] += 1
                home_team["gf"] += home_goals
                home_team["ga"] += away_goals
                away_team["gf"] += away_goals
                away_team["ga"] += home_goals

                if home_goals > away_goals:
                    home_team["won"] += 1
                    home_team["pts"] += 3
                    away_team["lost"] += 1
                elif home_goals < away_goals:
                    away_team["won"] += 1
                    away_team["pts"] += 3
                    home_team["lost"] += 1
                else:
                    home_team["drawn"] += 1
                    away_team["drawn"] += 1
                    home_team["pts"] += 1
                    away_team["pts"] += 1

        # 按积分排序
        sorted_teams = sorted(teams.values(), key=lambda t: (-t["pts"], -(t["gf"] - t["ga"]), -t["gf"]))
        standings[group_name] = sorted_teams

    return jsonify(standings)


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


if __name__ == "__main__":
    print("=" * 50)
    print("⚽ 2026 世界杯 AI 预测工具")
    print("=" * 50)

    # 检查 API Key
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if not has_key:
        print("⚠️  未设置 ANTHROPIC_API_KEY，AI 预测功能不可用")
        print("   Windows: set ANTHROPIC_API_KEY=your-key")
        print("   数据模型预测仍可使用")
    else:
        print("✅ ANTHROPIC_API_KEY 已设置")

    # 初始化数据
    print("📡 正在加载赛程数据...")
    load_matches()
    print("✅ 数据加载完成")

    port = int(os.environ.get("PORT", 5000))
    print(f"\n🌐 启动服务: http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)

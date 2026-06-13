"""
AI 预测引擎 —— 全方位比赛因素分析，专为 2026 美加墨世界杯体彩参考优化
"""
import json
import os
import re
from anthropic import Anthropic

# ── 环境变量 ──────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_client = None
_predict_cache = {}

# ── 数据路径 ──────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TEAMS_PATH = os.path.join(DATA_DIR, "teams.json")
FACTORS_PATH = os.path.join(DATA_DIR, "match_factors.json")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 客户端 ────────────────────────────────────────────
def get_client():
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("请设置环境变量 ANTHROPIC_API_KEY")
        kwargs = {"api_key": ANTHROPIC_API_KEY}
        if ANTHROPIC_BASE_URL:
            kwargs["base_url"] = ANTHROPIC_BASE_URL
        _client = Anthropic(**kwargs)
    return _client


# ── 数据查询 ──────────────────────────────────────────
def load_teams_data():
    return _load_json(TEAMS_PATH)


def load_factors():
    return _load_json(FACTORS_PATH)


def _normalize(s):
    """去除变音符号并小写，用于模糊匹配"""
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


def find_team(team_name, teams_data=None):
    if teams_data is None:
        teams_data = load_teams_data()
    name_lower = team_name.lower()
    name_normalized = _normalize(team_name)
    for group_data in teams_data["groups"].values():
        for team in group_data["teams"]:
            if team["name"].lower() == name_lower or team["name_cn"] == team_name:
                return team
    # 模糊匹配兜底：无视变音符号
    for group_data in teams_data["groups"].values():
        for team in group_data["teams"]:
            if _normalize(team["name"]) == name_normalized:
                return team
    return None


def _cache_key(home, away, context):
    return f"{home.lower()}|{away.lower()}|{context.lower()}"


# ── 比赛因素收集 ──────────────────────────────────────
def collect_match_factors(home, away, match_info):
    """
    收集一场比赛的所有相关因素，返回结构化的上下文文本。
    match_info 应包含: venue, group, round_num, date_cn 等
    """
    factors = load_factors()
    parts = []

    # 1. 场馆 & 环境
    venue_name = match_info.get("venue", "")
    venue = factors["venues"].get(venue_name)
    if venue:
        parts.append(f"""【比赛场馆与环境】
- 场馆：{venue_name}（{venue['city']}，{venue['country']}）
- 海拔：{venue['altitude_m']}米{'（⚠️ 高海拔！客队体能消耗显著增加，球速偏快）' if venue['altitude_m'] > 1500 else ''}
- 类型：{'室内空调恒温' if venue['indoor'] else '室外'}
- 草皮：{venue['pitch']}{'（人工草皮球速快，不习惯的球队受影响）' if '人工' in venue['pitch'] else ''}
- 容量：{venue['capacity']}人
- 6月天气：{venue['june_weather']}
""")

    # 2. 赛程 / 疲劳度
    fatigue = factors.get("schedule_fatigue", {})
    round_num = match_info.get("round_num", 1)
    if round_num == 1:
        parts.append("【赛程状态】小组赛第1轮，双方均无疲劳积累，体能充沛。\n")
    elif round_num == 2:
        parts.append("【赛程状态】小组赛第2轮，休息3-4天。首轮消耗大的球队可能状态下滑。\n")
    else:
        parts.append("【赛程状态】小组赛第3轮（末轮），出线形势将极大影响比赛心态和战术选择。\n")

    # 3. H2H 历史交锋
    h2h_key = f"{home['name']} vs {away['name']}"
    h2h_rev = f"{away['name']} vs {home['name']}"
    h2h = factors.get("head_to_head", {})
    h2h_text = h2h.get(h2h_key) or h2h.get(h2h_rev)
    if h2h_text:
        parts.append(f"【历史交锋】{h2h_text}\n")

    # 4. 伤病
    injuries = factors.get("key_injuries", {})
    for team_name in [home["name"], away["name"]]:
        inj = injuries.get(team_name)
        if inj:
            parts.append(f"【{team_name}伤病】{inj}\n")

    # 5. 东道主优势
    host_adv = factors.get("host_advantage", {})
    for team_name, factor_key in [(home["name"], home["name"].lower()),
                                    (away["name"], away["name"].lower())]:
        host_info = host_adv.get(factor_key)
        if host_info:
            parts.append(f"【东道主优势】{team_name}是2026联合东道主！{host_info['reason']}\n")

    # 6. 赛事背景
    fmt = factors.get("tournament_format", {})
    parts.append(f"""【赛事背景】
- 2026美加墨世界杯，48队12组，每组前2+8个最佳第三晋级32强
- 这意味着小组第三仍有出线可能，弱队不会提前放弃
- 净胜球极其重要，强队领先时不会放松
""")

    # 7. 裁判趋势
    ref = factors.get("referee_profile", {})
    parts.append(f"【裁判尺度】{ref.get('trend', '')}\n")

    return "\n".join(parts)


def get_team_recent_form(team_name):
    """获取球队近期战绩"""
    from data.fetcher import get_team_matches
    matches = get_team_matches(team_name, limit=5)
    if not matches:
        return "暂无世界杯比赛数据"
    lines = []
    for m in matches:
        result = m.get("result", "?")
        lines.append(f"{m['date_cn']} {m['home']} {result} {m['away']}（世界杯）")
    return "\n".join(lines)


# ── 系统提示词（包含完整2026世界杯知识） ──────────────
SYSTEM_PROMPT = """你是一位为体育彩票玩家提供专业分析的世界杯预测专家。
你深知用户的预测将直接影响其投注决策，因此必须极度审慎、客观。

=== 2026美加墨世界杯 — 你必须完全掌握的背景知识 ===

【赛事信息】
- 名称：2026 FIFA World Cup
- 主办国：美国、加拿大、墨西哥（三国联合主办，首次）
- 参赛队：48支（首次扩军）
- 比赛时间：2026年6月12日-7月19日（北京时间）
- 揭幕战：墨西哥 2-0 南非（已完赛）
- 卫冕冠军：阿根廷（非东道主）

【绝对禁止的错误】（一旦犯这些低级错误，预测就毫无价值）
✗ 不要说卡塔尔是东道主——卡塔尔是2022年东道主，2026年只是B组普通参赛队
✗ 不要说阿根廷主场作战——阿根廷不是东道主
✗ 不要把2022年的任何信息当作2026年的事实
✗ 不要编造不存在的球员或教练
✗ 不要假设欧洲球队天然优势——本届在美洲举行，欧洲球队需要跨时区适应

【预测时必须综合考虑的因素】（每一项都可能影响比分）
1. 场馆环境：海拔(>1500m极大影响客队)、室内/室外、草皮类型、6月天气
2. 东道主优势：美/加/墨三国有主场球迷+零时差+零旅行
3. 伤病影响：核心球员缺阵的战术连锁反应
4. H2H交锋史：历史数据暗示的心理和战术匹配度
5. 赛程阶段：小组第1轮无疲劳 / 第2轮有消耗 / 第3轮涉及出线
6. 战术相克：高位逼抢 vs 传控、身体流 vs 技术流等
7. 裁判趋势：VAR介入增多，点球判罚率上升
8. 48队赛制：小组第三也有机会，净胜球极度重要
9. 球员心理：梅西/C罗最后一届 = 超常发挥可能
10. 跨洲旅行：从欧洲到美国-6小时时差，亚洲到美国-15小时

【你的预测必须输出以下JSON格式，缺一不可】
{
  "score": "X-Y（X是主队进球，Y是客队进球，必须和winner逻辑一致）",
  "winner": "主队英文名 或 客队英文名 或 Draw",
  "probability": {"home": 0.XX, "draw": 0.XX, "away": 0.XX},
  "confidence": "high/medium/low",
  "reasoning": "300字以内的综合分析，必须引用具体的场馆、伤病、H2H等上文提供的信息",
  "betting_angle": "针对体彩玩家的投注建议，如：巴西-1.5、小于2.5球、双方进球-是 等",
  "key_factors": ["因素1", "因素2", "因素3"],
  "upset_risks": ["翻车风险1", "风险2", "风险3"],
  "score_range": "最可能比分区间，如 1-0 至 2-1"
}

⚠️ score和winner的强制一致性：
- 主队进球多 → winner MUST = 主队名
- 客队进球多 → winner MUST = 客队名
- 相同 → winner MUST = "Draw"
绝对不允许 score 是 1-0 但 winner 写客队这种低级矛盾！"""


# ── 主预测函数 ────────────────────────────────────────
def predict_match(home_team, away_team, match_context="", deep=False, conservative=False,
                  match_info=None):
    """
    全方位因素预测一场比赛

    Args:
        home_team: 主队名
        away_team: 客队名
        match_context: 简短背景（如"小组赛C组第1轮"）
        deep: 是否深度分析
        conservative: 是否谨慎购彩模式（默认开启）
        match_info: dict, 包含 venue/group/round_num/date_cn 等

    Returns:
        dict: 完整预测结果
    """
    teams_data = load_teams_data()

    home = find_team(home_team, teams_data)
    away = find_team(away_team, teams_data)

    if not home:
        raise ValueError(f"未找到球队: {home_team}")
    if not away:
        raise ValueError(f"未找到球队: {away_team}")

    # 检查缓存
    key = _cache_key(home["name"], away["name"], match_context)
    if key in _predict_cache:
        return _predict_cache[key]

    # 近期战绩
    home_form = get_team_recent_form(home["name"])
    away_form = get_team_recent_form(away["name"])

    # 收集所有比赛因素
    if match_info is None:
        match_info = {}
    match_info.setdefault("group", "")
    match_info.setdefault("round_num", 1)
    match_info.setdefault("venue", "")

    factors_text = collect_match_factors(home, away, match_info)

    # ── 组装用户提示词 ──
    cautious_note = ""
    if conservative:
        cautious_note = """
⚠️ 这是用于体育彩票参考的预测，请格外注意：
- 比分预测偏保守，强队打弱队也不要超过3-0
- 必须列出至少3条可能导致预测翻车的具体风险
- confidence 绝大多数比赛应该是 medium 或 low
- betting_angle 必须给出具体的投注方向建议（如"小于2.5球"、"巴西-1.5"等）
"""

    depth_note = ""
    if deep:
        depth_note = """
请进行深度分析，reasoning扩展到500字以上，覆盖：
- 战术体系的每一层对位
- 定位球攻防
- 替补席深度对比
- 体能储备和赛程影响
"""

    user_prompt = f"""请基于以下完整信息，对这场2026美加墨世界杯比赛做出专业预测。

═══════════════════════════════════
              比赛信息
═══════════════════════════════════
主队：{home['name']} ({home['name_cn']})  FIFA第{home['fifa_ranking']}位
客队：{away['name']} ({away['name_cn']})  FIFA第{away['fifa_ranking']}位
背景：{match_context or '2026世界杯小组赛'}

═══════════════════════════════════
              主队情报
═══════════════════════════════════
教练：{home['coach']}
核心球员：{', '.join(home['key_players'])}
战术风格：{home['style']}
近期状态：{home['recent_form']}
{home.get('notes', '')}

═══════════════════════════════════
              客队情报
═══════════════════════════════════
教练：{away['coach']}
核心球员：{', '.join(away['key_players'])}
战术风格：{away['style']}
近期状态：{away['recent_form']}
{away.get('notes', '')}

═══════════════════════════════════
            全方位比赛因素
═══════════════════════════════════
{factors_text}

═══════════════════════════════════
              近期战绩
═══════════════════════════════════
【{home['name']}】
{home_form}

【{away['name']}】
{away_form}
{cautious_note}
{depth_note}

请给出你的专业预测（严格按JSON格式输出，score和winner必须逻辑一致）。"""

    # ── 调用 AI ──
    client = get_client()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1500 if not deep else 2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.1,
    )

    # 提取文本（兼容 DeepSeek 的 thinking 模式）
    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
        elif block.type == "thinking":
            # 跳过 thinking block，不加入 text
            pass
        elif hasattr(block, 'text'):
            text += block.text

    if not text.strip():
        raise RuntimeError("AI 未返回文本内容，请重试")

    text = text.strip()

    # 多层 JSON 提取策略
    prediction = _extract_json(text)

    if prediction is None:
        # 最后一次尝试：用正则暴力提取关键字段
        prediction = _fallback_parse(text)

    # 补充球队信息
    prediction["home_team"] = {"name": home["name"], "name_cn": home["name_cn"]}
    prediction["away_team"] = {"name": away["name"], "name_cn": away["name_cn"]}

    # 校验 score-winner 一致性（以比分为准，但 reasoning 说了算）
    prediction = _validate_score_winner(prediction, home["name"], away["name"])

    # 补充中文胜者名
    winner = prediction.get("winner", "")
    if winner == home["name"]:
        prediction["winner_cn"] = home["name_cn"]
    elif winner == away["name"]:
        prediction["winner_cn"] = away["name_cn"]
    elif winner.lower() == "draw":
        prediction["winner_cn"] = "平局"
    else:
        prediction["winner_cn"] = winner

    # 缓存
    _predict_cache[key] = prediction
    return prediction


def _extract_json(text):
    """多层策略提取 JSON，兼容各种模型输出格式"""
    # 先清理常见的非 JSON 前缀/后缀
    cleaned = text.strip()
    # 去掉开头可能的 "Here is..." / "以下是..." 等自然语言前缀
    for marker in ["```json", "```", "{"]:
        idx = cleaned.find(marker)
        if idx > 0 and marker == "{" and cleaned[idx-1] in ("\n", " ", "："):
            cleaned = cleaned[idx:]
            break
        elif idx >= 0 and marker != "{":
            cleaned = cleaned[idx:]
            break

    strategies = [
        # 1. 直接解析全文
        lambda t: json.loads(t),
        # 2. ```json ... ``` 包裹
        lambda t: json.loads(t.split("```json", 1)[1].split("```", 1)[0].strip()),
        # 3. ``` ... ``` 包裹
        lambda t: json.loads(t.split("```", 1)[1].split("```", 1)[0].strip()),
        # 4. 第一个 { 到最后一个 }
        lambda t: json.loads(t[t.index("{"):t.rindex("}")+1]),
        # 5. 正则找出所有 "key": value 对，重建 JSON
        lambda t: _rebuild_json_from_text(t),
    ]

    for strategy in strategies:
        try:
            return strategy(cleaned)
        except (json.JSONDecodeError, ValueError, IndexError, KeyError):
            continue

    return None


def _rebuild_json_from_text(text):
    """从文本中提取关键字段拼回 JSON（最后兜底）"""
    fields = {}
    patterns = {
        "score": [r'"score"\s*:\s*"(\d+-\d+)"', r'比分[：:]\s*(\d+\s*[-:]\s*\d+)'],
        "winner": [r'"winner"\s*:\s*"([^"]+)"', r'胜者[：:]\s*(\S+)'],
        "confidence": [r'"confidence"\s*:\s*"(\w+)"'],
        "reasoning": [r'"reasoning"\s*:\s*"([^"]{20,})"'],
        "betting_angle": [r'"betting_angle"\s*:\s*"([^"]+)"'],
    }
    for field, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                fields[field] = m.group(1).strip()
                break

    if "score" not in fields or len(fields) < 2:
        raise ValueError("Not enough fields")

    # 重建概率
    prob = {"home": 0.33, "draw": 0.34, "away": 0.33}
    for key in ["home", "draw", "away"]:
        for pat in [rf'"{key}"\s*:\s*([\d.]+)', rf'"{key}".*?([\d.]+)']:
            m = re.search(pat, text)
            if m:
                prob[key] = float(m.group(1))
                break

    return {
        "score": fields.get("score", "?-?"),
        "winner": fields.get("winner", "Unknown"),
        "probability": prob,
        "confidence": fields.get("confidence", "low"),
        "reasoning": fields.get("reasoning", text[:200]),
        "betting_angle": fields.get("betting_angle", ""),
        "key_factors": [],
        "upset_risks": ["解析异常，请参考reasoning"],
        "score_range": "?-? 至 ?-?"
    }


def _validate_score_winner(pred, home_name, away_name):
    """修正score/winner/reasoning三者不一致的情况，reasoning权威最高"""
    score = pred.get("score", "")
    winner = pred.get("winner", "")
    reasoning = pred.get("reasoning", "")

    # 1. 从 reasoning 中推断 AI 真正认为谁会赢
    reasoning_winner = None
    home_cn = pred.get("home_team", {}).get("name_cn", home_name)
    away_cn = pred.get("away_team", {}).get("name_cn", away_name)

    # 检查 reasoning 里是否明确说了某队会赢
    home_win_patterns = [
        rf'{home_name}[会将]?(?:应该|预计|有望|可能)?[取胜赢]',
        rf'{home_cn}[会将]?(?:应该|预计|有望|可能)?[取胜赢]',
        rf'(?:看好|预计|认为).*?{home_name}.*?[取胜赢]',
        rf'(?:看好|预计|认为).*?{home_cn}.*?[取胜赢]',
        rf'{home_name}.*?(?:优势|占优|更强|胜出)',
        rf'{home_cn}.*?(?:优势|占优|更强|胜出)',
    ]
    away_win_patterns = [
        rf'{away_name}[会将]?(?:应该|预计|有望|可能)?[取胜赢]',
        rf'{away_cn}[会将]?(?:应该|预计|有望|可能)?[取胜赢]',
        rf'(?:看好|预计|认为).*?{away_name}.*?[取胜赢]',
        rf'(?:看好|预计|认为).*?{away_cn}.*?[取胜赢]',
        rf'{away_name}.*?(?:优势|占优|更强|胜出)',
        rf'{away_cn}.*?(?:优势|占优|更强|胜出)',
    ]
    draw_patterns = [
        r'(?:平局|战平|握手言和|难分胜负|势均力敌)',
    ]

    for pat in home_win_patterns:
        if re.search(pat, reasoning):
            reasoning_winner = home_name
            break
    if not reasoning_winner:
        for pat in away_win_patterns:
            if re.search(pat, reasoning):
                reasoning_winner = away_name
                break
    if not reasoning_winner:
        for pat in draw_patterns:
            if re.search(pat, reasoning):
                reasoning_winner = "Draw"
                break

    # 2. 解析 score 暗示的胜者
    try:
        hg, ag = map(int, score.strip().split("-"))
    except:
        return pred

    if hg > ag:
        score_winner = home_name
    elif ag > hg:
        score_winner = away_name
    else:
        score_winner = "Draw"

    # 3. 三方一致性检查：reasoning > score > winner（优先级递减）
    if reasoning_winner and reasoning_winner != score_winner:
        # reasoning 和 score 冲突 → 以 reasoning 为准，翻转 score
        if reasoning_winner == home_name:
            pred["score"] = f"{max(hg, ag)}-{min(hg, ag)}"
            pred["winner"] = home_name
        elif reasoning_winner == away_name:
            pred["score"] = f"{min(hg, ag)}-{max(hg, ag)}"
            pred["winner"] = away_name
        else:  # Draw
            avg = (hg + ag) // 2
            pred["score"] = f"{avg}-{avg}"
            pred["winner"] = "Draw"
    elif score_winner != winner and winner.lower() != "draw" and score_winner != winner:
        # score 和 winner 冲突 → 以 score 为准
        pred["winner"] = score_winner
    elif winner.lower() == "draw" and score_winner != "Draw":
        pred["winner"] = score_winner

    return pred


def _fallback_parse(text):
    result = {
        "winner": "Unknown",
        "score": "?-?",
        "probability": {"home": 0.33, "draw": 0.34, "away": 0.33},
        "confidence": "low",
        "reasoning": text[:300],
        "betting_angle": "",
        "key_factors": [],
        "upset_risks": ["AI返回格式异常，无法分析具体风险"],
        "score_range": "?-? 至 ?-?"
    }

    # 尝试从文本中提取比分
    score_patterns = [
        r'比分[：:]\s*(\d+)\s*[-:]\s*(\d+)',
        r'score[：:"]\s*["\']?(\d+)\s*[-:]\s*(\d+)',
        r'(\d+)\s*[-:]\s*(\d+)',
    ]
    for pat in score_patterns:
        m = re.search(pat, text)
        if m:
            result["score"] = f"{m.group(1)}-{m.group(2)}"
            break

    # 尝试提取胜者
    if "平局" in text or "draw" in text.lower() or "Draw" in text:
        result["winner"] = "Draw"
    elif re.search(r'(主队|home)\s*(胜|赢|win)', text, re.IGNORECASE):
        result["winner"] = "home"
    elif re.search(r'(客队|away)\s*(胜|赢|win)', text, re.IGNORECASE):
        result["winner"] = "away"

    # 尝试提取概率
    for key, patterns in [
        ("home", [r'主队[胜赢].*?(\d+)%', r'home.*?(\d+)\s*%']),
        ("draw", [r'平.*?(\d+)%', r'draw.*?(\d+)\s*%']),
        ("away", [r'客队[胜赢].*?(\d+)%', r'away.*?(\d+)\s*%']),
    ]:
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result["probability"][key] = int(m.group(1)) / 100
                break

    # 尝试提取投注建议
    for pat in [r'(?:投注|betting|建议)[：:]\s*(.+?)(?:\n|$)', r'安全.*?[：:]\s*(.+?)(?:\n|$)']:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["betting_angle"] = m.group(1).strip()
            break

    return result


def quick_predict(home_team, away_team, match_context=""):
    """快速数据模型预测（不调AI）"""
    teams_data = load_teams_data()
    home = find_team(home_team, teams_data)
    away = find_team(away_team, teams_data)
    if not home or not away:
        raise ValueError(f"未找到球队: {home_team if not home else away_team}")

    elo_diff = home["elo_rating"] - away["elo_rating"]
    home_prob = round(1 / (1 + 10 ** (-elo_diff / 400)) + 0.05, 2)
    draw_prob = round(max(0.2, 0.30 - abs(elo_diff) / 2000), 2)
    away_prob = round(1 - home_prob - draw_prob, 2)

    home_goals = round(max(0, min(6, 0.8 + home["strength"] * 0.15 + elo_diff / 600)))
    away_goals = round(max(0, min(6, 0.5 + away["strength"] * 0.10 - elo_diff / 600)))

    if home_goals > away_goals:
        winner = home["name"]
    elif away_goals > home_goals:
        winner = away["name"]
    else:
        winner = "Draw"

    return {
        "winner": winner,
        "score": f"{home_goals}-{away_goals}",
        "probability": {"home": home_prob, "draw": draw_prob, "away": away_prob},
        "confidence": "low" if abs(elo_diff) < 100 else "medium",
        "reasoning": f"基于数据模型（ELO差{elo_diff}分）。仅供参考，建议使用AI预测。",
        "betting_angle": "",
        "key_factors": [f"FIFA排名差: {abs(home['fifa_ranking'] - away['fifa_ranking'])}位"],
        "upset_risks": ["数据模型无法评估具体风险，建议使用AI预测"],
        "score_range": f"{max(0,home_goals-1)}-{max(0,away_goals-1)} 至 {home_goals+1}-{away_goals+1}",
        "home_team": {"name": home["name"], "name_cn": home["name_cn"]},
        "away_team": {"name": away["name"], "name_cn": away["name_cn"]},
    }

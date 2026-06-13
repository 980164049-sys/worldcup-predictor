"""
AI 预测引擎 — 调用 Claude API 生成世界杯比赛预测
"""
import json
import os
import re
from anthropic import Anthropic

# API Key 从环境变量读取（兼容多种命名）
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_client = None


def get_client():
    """延迟初始化 Anthropic 客户端"""
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "请设置环境变量 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN\n"
                "Windows: set ANTHROPIC_API_KEY=your-key\n"
                "或创建 .env 文件放在项目目录"
            )
        kwargs = {"api_key": ANTHROPIC_API_KEY}
        if ANTHROPIC_BASE_URL:
            kwargs["base_url"] = ANTHROPIC_BASE_URL
        _client = Anthropic(**kwargs)
    return _client


def load_teams_data():
    """加载球队数据库"""
    teams_path = os.path.join(os.path.dirname(__file__), "data", "teams.json")
    with open(teams_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_team(team_name, teams_data):
    """根据名称查找球队信息"""
    for group_data in teams_data["groups"].values():
        for team in group_data["teams"]:
            if team["name"].lower() == team_name.lower() or \
               team["name_cn"] == team_name:
                return team
    return None


def get_team_recent_form(team_name):
    """获取球队近期战绩"""
    from data.fetcher import get_team_matches
    matches = get_team_matches(team_name, limit=5)
    if not matches:
        return "暂无近期比赛数据"
    lines = []
    for m in matches:
        result = m.get("result", "?")
        lines.append(f"{m['date_cn']} {m['home']} {result} {m['away']} (世界杯小组赛)")
    return "\n".join(lines)


def predict_match(home_team, away_team, match_context="", deep=False, conservative=False):
    """
    预测一场比赛

    Args:
        home_team: 主队名称（英文或中文）
        away_team: 客队名称
        match_context: 比赛背景（如"小组赛C组第1轮"）
        deep: 是否深度分析

    Returns:
        dict: {winner, score, probability: {home, draw, away}, reasoning, key_players}
    """
    teams_data = load_teams_data()

    home = find_team(home_team, teams_data)
    away = find_team(away_team, teams_data)

    if not home:
        raise ValueError(f"未找到球队: {home_team}")
    if not away:
        raise ValueError(f"未找到球队: {away_team}")

    # 获取近期战绩
    home_form = get_team_recent_form(home["name"])
    away_form = get_team_recent_form(away["name"])

    # 构建 Prompt
    system_prompt = """你是一位资深足球分析师和风险评估专家，精通战术分析和数据建模。
你的任务是对世界杯比赛做出专业、审慎的预测。

请严格按以下 JSON 格式输出（不要包含其他文字）：
{
  "winner": "主队名称 或 客队名称 或 Draw",
  "score": "X-Y",
  "probability": {
    "home": 0.XX,
    "draw": 0.XX,
    "away": 0.XX
  },
  "confidence": "high / medium / low",
  "reasoning": "200字以内的分析理由，从战术对位、近期状态、关键球员、历史交锋等角度分析",
  "key_factors": ["因素1", "因素2", "因素3"],
  "upset_risks": ["可能导致翻车的风险1", "风险2"],
  "safe_pick": "最稳妥的投注方向建议，如：让球、大小球、双方进球等，一句话"
}"""

    cautious_instruction = ""
    if conservative:
        cautious_instruction = """
⚠️ 这是用于体育彩票参考的谨慎预测，请格外注意：

1. **保守评分**：预测比分要偏保守，缩小分差。即使强队打弱队，也不要预测超过 3-0。
2. **风险评估**：必须列出至少 3 个可能导致预测翻车的具体风险因素。
3. **置信度如实评估**：大多数比赛的 confidence 应该是 "medium" 或 "low"，只有实力悬殊极大时才给 "high"。
4. **安全建议**：safe_pick 给出最保守的投注方向（如"双方进球-否"、"总进球小于2.5"、"弱队+2.5"等），而非直接赌胜负。
5. **强调不确定性**：reasoning 中必须包含一句关于足球比赛固有不确定性的提醒。
"""

    depth_instruction = ""
    if deep:
        depth_instruction = """
请进行深度分析，reasoning 扩展到 500 字以上，包括：
- 双方战术体系的详细对比
- 三条线（防线、中场、锋线）的人员对位分析
- 定位球攻防分析
- 体能和赛程影响
- 关键替补球员可能带来的变数
"""

    user_prompt = f"""请预测以下世界杯比赛：

【比赛信息】
主队：{home['name']} ({home['name_cn']})
客队：{away['name']} ({away['name_cn']})
比赛背景：{match_context or '2026世界杯小组赛'}
主队 FIFA 排名：第 {home['fifa_ranking']} 位
客队 FIFA 排名：第 {away['fifa_ranking']} 位

【主队情报】
教练：{home['coach']}
核心球员：{', '.join(home['key_players'])}
球队风格：{home['style']}
近期战绩：{home['recent_form']}

【客队情报】
教练：{away['coach']}
核心球员：{', '.join(away['key_players'])}
球队风格：{away['style']}
近期战绩：{away['recent_form']}

【主队近期比赛】
{home_form}

【客队近期比赛】
{away_form}
{cautious_instruction}
{depth_instruction}
请给出你的专业预测。"""

    client = get_client()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024 if not deep else 2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.7,
    )

    # 解析返回的 JSON（过滤可能的 thinking block）
    text_blocks = [b for b in response.content if b.type == "text"]
    if not text_blocks:
        raise RuntimeError("AI 未返回文本内容，请重试")
    text = text_blocks[0].text.strip()
    # 处理可能的 markdown 代码块包裹
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        prediction = json.loads(text)
    except json.JSONDecodeError:
        # 降级：尝试用正则提取
        prediction = _fallback_parse(text)

    # 补充球队信息
    prediction["home_team"] = {"name": home["name"], "name_cn": home["name_cn"]}
    prediction["away_team"] = {"name": away["name"], "name_cn": away["name_cn"]}

    return prediction


def _fallback_parse(text):
    """JSON 解析失败时的降级提取"""
    result = {
        "winner": "Unknown",
        "score": "?-?",
        "probability": {"home": 0.33, "draw": 0.34, "away": 0.33},
        "reasoning": text[:300],
        "key_factors": []
    }

    # 尝试提取比分
    score_match = re.search(r'(\d+)\s*[-:]\s*(\d+)', text)
    if score_match:
        result["score"] = f"{score_match.group(1)}-{score_match.group(2)}"

    # 尝试提取胜者
    for pattern, winner in [
        (r'winner["\s:]+(\w+)', None),
        (r'(主队|home)\s*(胜|赢|win)', "home"),
        (r'(客队|away)\s*(胜|赢|win)', "away"),
        (r'(平|draw|tie)', "Draw"),
    ]:
        if re.search(pattern, text, re.IGNORECASE):
            if winner:
                result["winner"] = winner
            break

    return result


def quick_predict(home_team, away_team, match_context=""):
    """
    快速预测（简化版），不调用 AI，纯基于数据计算
    作为 AI 预测的参考基线
    """
    teams_data = load_teams_data()
    home = find_team(home_team, teams_data)
    away = find_team(away_team, teams_data)

    if not home or not away:
        raise ValueError(f"未找到球队: {home_team if not home else away_team}")

    # 基于 FIFA 排名和 ELO 的简单模型
    rank_diff = away["fifa_ranking"] - home["fifa_ranking"]
    elo_diff = home["elo_rating"] - away["elo_rating"]

    # 基础概率
    home_adv = 0.05  # 主场优势（本届在美国）
    elo_prob = 1 / (1 + 10 ** (-elo_diff / 400))

    home_prob = round(elo_prob + home_adv, 2)
    draw_prob = round(0.30 - abs(elo_diff) / 2000, 2)
    away_prob = round(1 - home_prob - draw_prob, 2)

    # 归一化
    total = home_prob + draw_prob + away_prob
    home_prob = round(home_prob / total, 2)
    draw_prob = round(draw_prob / total, 2)
    away_prob = round(1 - home_prob - draw_prob, 2)

    # 预计进球 (校准后公式，使比分在合理足球范围内)
    home_goals_raw = 0.8 + home["strength"] * 0.15 + elo_diff / 600
    away_goals_raw = 0.5 + away["strength"] * 0.10 - elo_diff / 600
    home_goals = round(max(0, min(6, home_goals_raw)))
    away_goals = round(max(0, min(6, away_goals_raw)))

    if home_prob > away_prob and home_prob > draw_prob:
        winner = home["name"]
    elif away_prob > home_prob and away_prob > draw_prob:
        winner = away["name"]
    else:
        winner = "Draw"

    return {
        "winner": winner,
        "score": f"{int(round(home_goals))}-{int(round(away_goals))}",
        "probability": {
            "home": home_prob,
            "draw": draw_prob,
            "away": away_prob
        },
        "reasoning": f"基于FIFA排名(差{rank_diff}位)和ELO评分(差{elo_diff}分)的数据模型预测。仅供参考。",
        "key_factors": [
            f"FIFA排名差距: {abs(rank_diff)}位",
            f"ELO评分差距: {abs(elo_diff)}分",
            f"实力评分: {home['name']}={home['strength']}, {away['name']}={away['strength']}"
        ],
        "home_team": {"name": home["name"], "name_cn": home["name_cn"]},
        "away_team": {"name": away["name"], "name_cn": away["name_cn"]}
    }

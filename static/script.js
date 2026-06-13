// ===== 2026 世界杯 AI 预测工具 — 前端交互 =====

// ===== 页面加载：自动预测明日所有比赛 =====
document.addEventListener('DOMContentLoaded', () => {
    // 移动端显示安装提示
    const isMobile = /Android|iPhone|iPad|webOS/i.test(navigator.userAgent);
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    if (isMobile && !isStandalone) {
        const banner = document.getElementById('install-banner');
        if (banner) banner.style.display = 'flex';
    }

    const matchCards = document.querySelectorAll('#tomorrow-matches .match-card');
    matchCards.forEach(card => {
        const home = card.dataset.home;
        const away = card.dataset.away;
        const group = card.dataset.group;
        const venue = card.dataset.venue || '';
        const round = card.dataset.round || '1';
        const predDiv = card.querySelector('.match-prediction');
        const scoreArea = card.querySelector('.score');

        if (!home || !away || !predDiv) return;

        // 发起预测（含完整比赛因素）
        fetch('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                home_team: home,
                away_team: away,
                match_context: `小组${group}第${round}轮`,
                match_info: {
                    venue: venue,
                    group: group,
                    round_num: parseInt(round)
                },
                use_ai: true,
                deep: false,
                conservative: true
            })
        })
        .then(resp => resp.json())
        .then(data => {
            if (data.error) {
                predDiv.innerHTML = `<div class="pred-error">❌ ${escapeHtml(data.error)}</div>`;
                return;
            }

            const prob = data.probability;
            const homeName = data.home_team.name_cn || data.home_team.name;
            const awayName = data.away_team.name_cn || data.away_team.name;

            // 更新比分显示
            scoreArea.textContent = data.score;
            scoreArea.classList.remove('upcoming');
            scoreArea.classList.add('predicted');

            // 渲染预测卡片
            const confLabel = {high: '🟢 高置信度', medium: '🟡 中等置信度', low: '🔴 低置信度'};
            const confidence = data.confidence || 'medium';
            const betting = data.betting_angle || data.safe_pick || '';
            const scoreRange = data.score_range || '';
            predDiv.innerHTML = `
                <div class="pred-result">
                    <div class="pred-winner">
                        ${data.winner_cn === '平局' ? '🤝 预测平局' : '🏆 预测胜者: ' + (data.winner_cn || (data.winner === data.home_team.name ? homeName : awayName))}
                        <span class="confidence-tag ${confidence}">${confLabel[confidence] || confidence}</span>
                    </div>
                    <div class="probability-bars" style="margin:8px 0;">
                        <div class="prob-bar-group">
                            <div class="prob-label">${homeName}胜</div>
                            <div class="prob-value" style="font-size:14px;color:var(--primary);">${Math.round(prob.home*100)}%</div>
                            <div class="prob-track"><div class="prob-fill home" style="width:${prob.home*100}%;"></div></div>
                        </div>
                        <div class="prob-bar-group">
                            <div class="prob-label">平</div>
                            <div class="prob-value" style="font-size:14px;color:var(--text-dim);">${Math.round(prob.draw*100)}%</div>
                            <div class="prob-track"><div class="prob-fill draw" style="width:${prob.draw*100}%;"></div></div>
                        </div>
                        <div class="prob-bar-group">
                            <div class="prob-label">${awayName}胜</div>
                            <div class="prob-value" style="font-size:14px;color:var(--accent);">${Math.round(prob.away*100)}%</div>
                            <div class="prob-track"><div class="prob-fill away" style="width:${prob.away*100}%;"></div></div>
                        </div>
                    </div>
                    ${scoreRange ? `<div style="text-align:center;font-size:13px;color:var(--text-dim);margin:4px 0;">📊 比分区间: ${escapeHtml(scoreRange)}</div>` : ''}
                    ${betting ? `<div class="safe-pick"><strong>🎯 投注建议：</strong> ${escapeHtml(betting)}</div>` : ''}
                    <div class="pred-reasoning">
                        <span class="reasoning-text reasoning-collapsed">${escapeHtml(cleanReasoning(data.reasoning))}</span>
                    </div>
                    ${data.upset_risks ? `
                    <div class="upset-risks">
                        <strong>⚠️ 翻车风险：</strong>
                        <ul>${data.upset_risks.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
                    </div>` : ''}
                    <div class="risk-disclaimer">⚠️ AI 预测仅供参考，足球比赛充满不确定性，请理性购彩</div>
                </div>
            `;
        })
        .catch(err => {
            predDiv.innerHTML = `<div class="pred-error">⚠️ 预测失败: ${escapeHtml(err.message)}</div>`;
        })
        .finally(() => {
            setTimeout(initReasoningToggles, 800);
        });
    });
});

// ===== Tab 切换 =====
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // 切换 active tab
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // 切换 panel
        const panelId = 'panel-' + tab.dataset.tab;
        document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
        const panel = document.getElementById(panelId);
        if (panel) panel.style.display = 'block';

        // 懒加载
        if (tab.dataset.tab === 'standings') loadStandings();
        if (tab.dataset.tab === 'schedule') loadFullSchedule();
    });
});

// ===== 快速预测（从今日赛程卡片） =====
function quickPredict(home, away, context) {
    // 切换到预测面板
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector('.tab[data-tab="predict"]').classList.add('active');
    document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
    document.getElementById('panel-predict').style.display = 'block';

    // 设置球队
    document.getElementById('home-team').value = home;
    document.getElementById('away-team').value = away;
    document.getElementById('match-context').value = context || '';

    // 滚动到表单
    document.getElementById('panel-predict').scrollIntoView({ behavior: 'smooth' });

    // 自动预测
    doPredict();
}

// ===== 执行预测 =====
async function doPredict() {
    const home = document.getElementById('home-team').value;
    const away = document.getElementById('away-team').value;
    const context = document.getElementById('match-context').value;
    const useAI = document.getElementById('use-ai').checked;
    const deep = document.getElementById('deep-mode').checked;
    const conservative = document.getElementById('conservative-mode')?.checked ?? true;

    if (!home || !away) {
        alert('请先选择主队和客队');
        return;
    }

    if (home === away) {
        alert('不能选同一支球队');
        return;
    }

    const resultDiv = document.getElementById('predict-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = `
        <div style="text-align:center;padding:40px;">
            <div class="spinner"></div>
            <p style="margin-top:12px;color:var(--text-dim);">
                ${useAI ? 'AI 正在分析战术对位和球队数据...' : '正在计算数据模型...'}
            </p>
        </div>
    `;
    resultDiv.scrollIntoView({ behavior: 'smooth' });

    try {
        const resp = await fetch('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                home_team: home,
                away_team: away,
                match_context: context,
                deep: deep,
                use_ai: useAI,
                conservative: conservative
            })
        });

        const data = await resp.json();

        if (data.error) {
            resultDiv.innerHTML = `
                <div style="text-align:center;padding:20px;color:var(--danger);">
                    <p>❌ ${escapeHtml(data.error)}</p>
                </div>`;
            return;
        }

        renderPrediction(data, resultDiv);
        setTimeout(initReasoningToggles, 500);

    } catch (err) {
        resultDiv.innerHTML = `
            <div style="text-align:center;padding:20px;color:var(--danger);">
                <p>❌ 请求失败: ${escapeHtml(err.message)}</p>
                <p style="font-size:12px;margin-top:8px;">请确保服务已启动</p>
            </div>`;
    }
}

function renderPrediction(data, container) {
    const prob = data.probability;
    const homeName = data.home_team.name_cn || data.home_team.name;
    const awayName = data.away_team.name_cn || data.away_team.name;

    let winnerText = '';
    if (data.winner_cn) {
        winnerText = data.winner_cn === '平局' ? '🤝 预测：平局' : `🏆 预测胜者：${data.winner_cn}`;
    } else if (data.winner === data.home_team.name) {
        winnerText = `🏆 预测胜者：${homeName}`;
    } else if (data.winner === data.away_team.name) {
        winnerText = `🏆 预测胜者：${awayName}`;
    } else {
        winnerText = `🤝 预测：平局`;
    }

    container.innerHTML = `
        <div class="result-header">
            <div style="display:flex;align-items:center;justify-content:center;gap:16px;">
                <span style="font-size:20px;font-weight:700;">${homeName}</span>
                <img src="" alt="" style="display:none;">
            </div>
            <div class="result-score">${data.score}</div>
            <div style="display:flex;align-items:center;justify-content:center;gap:16px;">
                <span style="font-size:20px;font-weight:700;">${awayName}</span>
            </div>
            <div class="result-winner">${winnerText}</div>
            ${data.confidence ? `<div style="text-align:center;margin-top:4px;"><span class="confidence-tag ${data.confidence}">${{high:'🟢 高',medium:'🟡 中',low:'🔴 低'}[data.confidence]||data.confidence}置信度</span></div>` : ''}
        </div>

        <div class="probability-bars">
            <div class="prob-bar-group">
                <div class="prob-label">${homeName} 胜</div>
                <div class="prob-value" style="color:var(--primary);">${Math.round(prob.home * 100)}%</div>
                <div class="prob-track">
                    <div class="prob-fill home" style="width:${prob.home * 100}%;"></div>
                </div>
            </div>
            <div class="prob-bar-group">
                <div class="prob-label">平局</div>
                <div class="prob-value" style="color:var(--text-dim);">${Math.round(prob.draw * 100)}%</div>
                <div class="prob-track">
                    <div class="prob-fill draw" style="width:${prob.draw * 100}%;"></div>
                </div>
            </div>
            <div class="prob-bar-group">
                <div class="prob-label">${awayName} 胜</div>
                <div class="prob-value" style="color:var(--accent);">${Math.round(prob.away * 100)}%</div>
                <div class="prob-track">
                    <div class="prob-fill away" style="width:${prob.away * 100}%;"></div>
                </div>
            </div>
        </div>

        <div class="reasoning-box">
            <h4>📊 AI 分析</h4>
            <span class="reasoning-text reasoning-collapsed">${escapeHtml(cleanReasoning(data.reasoning))}</span>
            ${data.key_factors ? `
            <div class="key-factors">
                ${data.key_factors.map(f => `<span class="key-factor-tag">${escapeHtml(f)}</span>`).join('')}
            </div>` : ''}
            ${data.upset_risks ? `
            <div class="upset-risks" style="margin-top:12px;">
                <strong>⚠️ 翻车风险：</strong>
                <ul>${data.upset_risks.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
            </div>` : ''}
            ${data.safe_pick ? `
            <div class="safe-pick" style="margin-top:12px;padding:8px 12px;background:rgba(16,185,129,0.1);border-radius:8px;border-left:3px solid var(--success);">
                <strong>🛡️ 安全方向：</strong> ${escapeHtml(data.safe_pick)}
            </div>` : ''}
            <div class="risk-disclaimer" style="margin-top:12px;font-size:11px;color:var(--danger);text-align:center;">⚠️ AI 预测仅供参考，足球比赛充满不确定性，请理性购彩</div>
        </div>
    `;
}

// ===== 积分榜 =====
async function loadStandings() {
    const container = document.getElementById('standings-content');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载积分榜...</p></div>';

    try {
        const resp = await fetch('/api/standings');
        const data = await resp.json();

        let html = '';
        const groupOrder = ['A','B','C','D','E','F','G','H','I','J','K','L'];

        for (const g of groupOrder) {
            const teams = data[g];
            if (!teams || teams.length === 0) continue;

            html += `<div class="standings-group">`;
            html += `<h3>🏆 小组 ${g}</h3>`;
            html += `<table class="standings-table">`;
            html += `<thead><tr>
                <th>#</th><th>球队</th><th>赛</th><th>胜</th><th>平</th><th>负</th>
                <th>进</th><th>失</th><th>净</th><th>分</th>
            </tr></thead><tbody>`;

            teams.forEach((t, i) => {
                const posClass = `pos-${i+1}`;
                const gd = t.gf - t.ga;
                html += `<tr>
                    <td class="${posClass}">${i+1}</td>
                    <td><strong>${t.name_cn}</strong> <span style="color:var(--text-dim);font-size:11px;">${t.name}</span></td>
                    <td>${t.played}</td><td>${t.won}</td><td>${t.drawn}</td><td>${t.lost}</td>
                    <td>${t.gf}</td><td>${t.ga}</td><td>${gd > 0 ? '+' + gd : gd}</td>
                    <td><strong>${t.pts}</strong></td>
                </tr>`;
            });

            html += `</tbody></table></div>`;
        }

        container.innerHTML = html;

    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>❌ 加载失败: ${escapeHtml(err.message)}</p></div>`;
    }
}

// ===== 全部赛程 =====
async function loadFullSchedule() {
    const container = document.getElementById('schedule-content');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载赛程...</p></div>';

    try {
        const resp = await fetch('/api/matches/all');
        const matches = await resp.json();

        // 按日期分组
        const grouped = {};
        matches.forEach(m => {
            if (!grouped[m.date_cn]) grouped[m.date_cn] = [];
            grouped[m.date_cn].push(m);
        });

        let html = '';
        for (const [date, ms] of Object.entries(grouped).sort()) {
            html += `<div class="schedule-date-group">`;
            html += `<h3>📅 6月${parseInt(date.split('-')[1])}日</h3>`;
            html += `<div class="match-list">`;

            ms.forEach(m => {
                const statusClass = m.status === 'completed' ? 'finished' :
                                    m.status === 'in_progress' ? 'live' : 'upcoming';
                const statusText = m.status === 'completed' ? '已结束' :
                                   m.status === 'in_progress' ? '进行中' : '未开始';
                const scoreDisplay = m.result || 'VS';

                html += `
                <div class="match-card">
                    <div class="match-time">
                        <span class="time">${m.time_cn}</span>
                        <span class="group-badge">小组 ${m.group}</span>
                    </div>
                    <div class="match-teams">
                        <div class="team"><span class="team-name">${m.home_cn || m.home}</span></div>
                        <div class="score-area">
                            <span class="score ${m.status === 'in_progress' ? 'live' : ''}">${scoreDisplay}</span>
                            <span class="status ${statusClass}">${statusText}</span>
                        </div>
                        <div class="team"><span class="team-name">${m.away_cn || m.away}</span></div>
                    </div>
                    <div class="match-venue">${m.venue}</div>
                </div>`;
            });

            html += `</div></div>`;
        }

        container.innerHTML = html;

    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>❌ 加载失败: ${escapeHtml(err.message)}</p></div>`;
    }
}

// ===== 展开/收起 reasoning =====
function initReasoningToggles() {
    document.querySelectorAll('.reasoning-text').forEach(el => {
        // 已有按钮就跳过
        if (el.dataset.toggleReady) return;
        el.dataset.toggleReady = '1';

        const fullText = el.textContent;
        if (fullText.length <= 120) return;

        // 检测是否真的被 clamp 截断（scrollHeight > clientHeight）
        el.classList.add('reasoning-collapsed');
        if (el.scrollHeight <= el.clientHeight + 2) {
            el.classList.remove('reasoning-collapsed');
            return; // 没溢出，不需要按钮
        }

        const btn = document.createElement('button');
        btn.className = 'reasoning-toggle';
        btn.textContent = '展开全文 ▼';
        btn.onclick = function(e) {
            e.stopPropagation();
            if (el.classList.contains('reasoning-collapsed')) {
                el.classList.remove('reasoning-collapsed');
                btn.textContent = '收起 ▲';
            } else {
                el.classList.add('reasoning-collapsed');
                btn.textContent = '展开全文 ▼';
            }
        };
        el.parentElement.appendChild(btn);
    });
}

// ===== 工具函数 =====
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function cleanReasoning(text) {
    if (!text) return '';
    let cleaned = text;
    // 1. 去掉 JSON 代码块
    cleaned = cleaned.replace(/\{[\s\S]*?\}/g, '');
    // 2. 去掉 markdown 代码块
    cleaned = cleaned.replace(/```[\s\S]*?```/g, '');
    // 3. 去掉 markdown 标记
    cleaned = cleaned.replace(/[#*>_`~\[\]]/g, '');
    // 4. 合并多余空白
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    // 5. 重新换行
    cleaned = cleaned.replace(/。\s*/g, '。\n');
    return cleaned.substring(0, 500);
}

// ===== 刷新所有预测 =====
async function refreshAllPredictions() {
    if (!confirm('这将清除所有预测缓存，根据最新赛果重新预测。确定？')) return;
    try {
        const resp = await fetch('/api/refresh-predictions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({all: true})
        });
        const data = await resp.json();
        if (data.status === 'ok') {
            alert('预测缓存已清除！刷新页面后将自动重新预测。');
            location.reload();
        }
    } catch(err) {
        alert('操作失败: ' + err.message);
    }
}

// ===== 键盘快捷键 =====
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
        // Ctrl+Enter 在预测面板中触发预测
        const predictPanel = document.getElementById('panel-predict');
        if (predictPanel && predictPanel.style.display !== 'none') {
            doPredict();
        }
    }
});

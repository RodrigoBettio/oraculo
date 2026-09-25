// Estado Global da Aplicação
let currentTab = 'agents';
let agentsList = [];
let areasList = [];
let currentAgentViewMode = 'crud'; // 'crud' (lista padrão) | 'grid' | 'orbital' | 'constellation'
let currentSelectedAreaId = null;
let currentSpecData = null;
let currentSpecTab = 'agent';
let radarHoveredIndex = -1;
let radarAnimFrame = null;
let telegramGroups = [];
let currentSelectedGroup = null;
let currentModalVideo = null;
let studyPollingInterval = null;
let currentActiveAgentDetail = null;
let currentVideosList = [];
let currentVideoFilter = 'all';

let currentGroupToEnqueue = null;
let selectedGroupIds = new Set();
let selectedBatchAgentIds = new Set();
let groupsSummaryList = [];
let currentChannelAgentFilter = 'all'; // 'all' (visão geral) ou ID do especialista selecionado
let currentChannelViewMode = 'all'; // 'all' (todos os cursos) ou 'studied_only' (apenas já estudados)
let isMultiAgentBatchMode = false;

// Inicialização
document.addEventListener('DOMContentLoaded', async () => {
    await loadAgents();
    await loadAreas();
    await loadTelegramGroupsSummary();
    loadKnowledgeSources();
    loadTokenStats();
    loadStudyQueue();
    startStudyPolling();
    switchAgentView('crud'); // Inicia diretamente no modo lista corporativo
    loadKnowledgeGraph();
    // Atualiza telemetria de tokens a cada 5 segundos
    setInterval(loadTokenStats, 5000);
});

// Renderizador Markdown Limpo & Elegante
function renderMarkdown(text) {
    if (!text) return '';
    if (window.marked && typeof window.marked.parse === 'function') {
        try {
            return window.marked.parse(text);
        } catch (e) {
            console.error('Erro no marked parser:', e);
        }
    }
    // Fallback estruturado
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code class="bg-gray-800 px-1 py-0.5 rounded text-indigo-300 font-mono text-xs">$1</code>')
        .replace(/\n/g, '<br>');
}

// ----------------- GAVETA LATERAL DE TELEMETRIA (SLIDE-OVER DRAWER) -----------------

function openTelemetryDrawer() {
    const drawer = document.getElementById('telemetry-drawer');
    const overlay = document.getElementById('telemetry-drawer-overlay');
    if (!drawer || !overlay) return;
    overlay.classList.remove('hidden');
    requestAnimationFrame(() => {
        overlay.classList.add('active');
        drawer.classList.add('open');
    });
    loadTokenStats();
    if (window.lucide) lucide.createIcons();
}

function closeTelemetryDrawer() {
    const drawer = document.getElementById('telemetry-drawer');
    const overlay = document.getElementById('telemetry-drawer-overlay');
    if (!drawer || !overlay) return;
    drawer.classList.remove('open');
    overlay.classList.remove('active');
    setTimeout(() => {
        overlay.classList.add('hidden');
    }, 300);
}

function toggleTelemetryDrawer() {
    const drawer = document.getElementById('telemetry-drawer');
    if (drawer && drawer.classList.contains('open')) {
        closeTelemetryDrawer();
    } else {
        openTelemetryDrawer();
    }
}

async function loadTokenStats() {
    try {
        const res = await fetch('/api/tokens/stats');
        if (!res.ok) return;
        const data = await res.json();

        // 1. Atualiza o Pill / Botão do Cabeçalho Superior
        const navCount = document.getElementById('nav-token-count');
        const navPct = document.getElementById('nav-token-pct');
        if (navCount) navCount.innerText = data.formatted_daily;
        if (navPct) {
            const costBrl = (data.daily_cost_brl || 0).toFixed(2);
            navPct.innerText = `• R$ ${costBrl}`;
            navPct.className = 'text-[10px] text-emerald-400 font-mono font-semibold';
        }

        // 2. Atualiza elementos dentro da Gaveta Lateral
        const drawerPct = document.getElementById('drawer-token-pct');
        const drawerBar = document.getElementById('drawer-token-bar');
        const drawerUsed = document.getElementById('drawer-token-used');
        const drawerBudget = document.getElementById('drawer-token-budget');
        const drawerDaily = document.getElementById('drawer-token-daily');
        const drawerDailyDetails = document.getElementById('drawer-token-daily-details');
        const drawerDailyCost = document.getElementById('drawer-token-daily-cost');
        const drawerWeekly = document.getElementById('drawer-token-weekly');
        const drawerWeeklyCost = document.getElementById('drawer-token-weekly-cost');
        const drawerTotal = document.getElementById('drawer-token-total');

        if (drawerPct) {
            if (data.plan_tier === 'paid_tier' && data.percent_used === null) {
                drawerPct.innerText = 'Sob Demanda (Ilimitado)';
                drawerPct.className = 'text-xs font-mono font-bold text-emerald-400';
            } else {
                drawerPct.innerText = `${data.percent_used || 0}%`;
                drawerPct.className = 'text-xs font-mono font-bold text-indigo-400';
            }
        }
        if (drawerBar) {
            if (data.plan_tier === 'paid_tier' && data.percent_used === null) {
                drawerBar.style.width = '100%';
                drawerBar.className = 'h-2.5 rounded-full bg-gradient-to-r from-emerald-500 via-indigo-500 to-purple-500 transition-all duration-300';
            } else {
                const pct = data.percent_used || 0;
                drawerBar.style.width = `${Math.min(100, pct)}%`;
                if (pct > 80) {
                    drawerBar.className = 'h-2.5 rounded-full bg-rose-500 transition-all duration-300';
                } else if (pct > 50) {
                    drawerBar.className = 'h-2.5 rounded-full bg-amber-500 transition-all duration-300';
                } else {
                    drawerBar.className = 'h-2.5 rounded-full bg-emerald-500 transition-all duration-300';
                }
            }
        }
        if (drawerUsed) drawerUsed.innerText = `${data.formatted_daily} tokens`;
        if (drawerBudget) drawerBudget.innerText = data.formatted_budget;
        if (drawerDaily) drawerDaily.innerText = data.formatted_daily;
        if (drawerDailyDetails) {
            const reqStr = data.daily_requests ? `${data.daily_requests} chamadas • ` : '';
            drawerDailyDetails.innerText = `${reqStr}${formatCompact(data.daily_prompt)} prompt • ${formatCompact(data.daily_output)} resposta`;
        }
        if (drawerDailyCost) {
            drawerDailyCost.innerText = `$${(data.daily_cost_usd || 0).toFixed(4)} (R$ ${(data.daily_cost_brl || 0).toFixed(2)})`;
        }
        if (drawerWeekly) drawerWeekly.innerText = data.formatted_weekly;
        if (drawerWeeklyCost) {
            drawerWeeklyCost.innerText = `$${(data.weekly_cost_usd || 0).toFixed(4)} (R$ ${(data.weekly_cost_brl || 0).toFixed(2)})`;
        }
        if (drawerTotal) drawerTotal.innerText = `Total acumulado: ${data.formatted_total}`;
    } catch (e) {
        console.error('Erro ao buscar stats de tokens:', e);
    }
}

function formatCompact(val) {
    if (!val) return '0';
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
    return val.toString();
}

// ----------------- MODAL DE PAINEL DE CONSUMO DE TOKENS -----------------

async function openTokenDashboardModal() {
    const modal = document.getElementById('token-dashboard-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    await refreshModalTokenData();
    if (window.lucide) lucide.createIcons();
}

function closeTokenDashboardModal() {
    const modal = document.getElementById('token-dashboard-modal');
    if (modal) modal.classList.add('hidden');
}

async function refreshModalTokenData() {
    try {
        const res = await fetch('/api/tokens/stats');
        if (!res.ok) return;
        const data = await res.json();

        // 1. Badge & Plan cards styling
        const isPaid = data.plan_tier === 'paid_tier';
        const badge = document.getElementById('modal-plan-badge');
        if (badge) {
            badge.innerText = isPaid ? '⚡ Pay-as-you-go (Tier 1)' : '🟢 Free Tier';
            badge.className = isPaid 
                ? 'px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                : 'px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30';
        }

        const freeCard = document.getElementById('plan-card-free');
        const paidCard = document.getElementById('plan-card-paid');
        if (freeCard && paidCard) {
            if (isPaid) {
                paidCard.className = 'cursor-pointer p-3.5 rounded-2xl border-2 border-indigo-500 bg-indigo-500/10 shadow-lg shadow-indigo-500/10 relative transition-all';
                freeCard.className = 'cursor-pointer p-3.5 rounded-2xl border border-gray-800 bg-gray-950/60 opacity-60 hover:opacity-100 transition-all relative';
            } else {
                freeCard.className = 'cursor-pointer p-3.5 rounded-2xl border-2 border-emerald-500 bg-emerald-500/10 shadow-lg shadow-emerald-500/10 relative transition-all';
                paidCard.className = 'cursor-pointer p-3.5 rounded-2xl border border-gray-800 bg-gray-950/60 opacity-60 hover:opacity-100 transition-all relative';
            }
        }

        // 2. Metrics values
        const dailyTokens = document.getElementById('modal-daily-tokens');
        const dailySplit = document.getElementById('modal-daily-tokens-split');
        const dailyCost = document.getElementById('modal-daily-cost');
        const dailyCostBrl = document.getElementById('modal-daily-cost-brl');
        const weeklyTokens = document.getElementById('modal-weekly-tokens');
        const weeklyCost = document.getElementById('modal-weekly-cost');
        const weeklyCostBrl = document.getElementById('modal-weekly-cost-brl');

        if (dailyTokens) dailyTokens.innerText = data.formatted_daily;
        if (dailySplit) dailySplit.innerText = `${formatCompact(data.daily_prompt)} prompt • ${formatCompact(data.daily_output)} resp`;
        if (dailyCost) dailyCost.innerText = `$${data.daily_cost_usd.toFixed(4)}`;
        if (dailyCostBrl) dailyCostBrl.innerText = `R$ ${data.daily_cost_brl.toFixed(2)}`;
        if (weeklyTokens) weeklyTokens.innerText = data.formatted_weekly;
        if (weeklyCost) weeklyCost.innerText = `$${data.weekly_cost_usd.toFixed(4)}`;
        if (weeklyCostBrl) weeklyCostBrl.innerText = `R$ ${data.weekly_cost_brl.toFixed(2)}`;

        // 3. Budget input
        const budgetInput = document.getElementById('modal-budget-input');
        const budgetLabel = document.getElementById('modal-current-budget-label');
        if (budgetInput && !budgetInput.matches(':focus')) budgetInput.value = data.daily_budget;
        if (budgetLabel) budgetLabel.innerText = data.formatted_budget;

        // 4. History Table
        const rowsContainer = document.getElementById('modal-token-history-rows');
        if (rowsContainer) {
            if (!data.recent_records || !data.recent_records.length) {
                rowsContainer.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-gray-500 text-xs">Nenhuma chamada registrada ainda. Inicie um estudo ou converse na Sala do Oráculo!</td></tr>`;
            } else {
                rowsContainer.innerHTML = data.recent_records.map(r => {
                    const timeStr = r.timestamp ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-';
                    const srcLabel = r.source.includes('study') ? '📹 Estudo' : (r.source.includes('oracle') ? '🔮 Oráculo' : r.source);
                    return `
                        <tr class="hover:bg-gray-900/50 transition-colors">
                            <td class="py-2 px-3 text-gray-400 font-mono text-[10px]">${timeStr}</td>
                            <td class="py-2 px-3 font-medium text-white truncate max-w-[160px]" title="${r.details || ''}">
                                <span class="px-1.5 py-0.5 rounded bg-gray-800 text-[10px] mr-1 text-indigo-300">${srcLabel}</span>
                                <span>${r.details || '-'}</span>
                            </td>
                            <td class="py-2 px-3 text-gray-400 font-mono text-[10px]">${formatCompact(r.prompt_tokens)}</td>
                            <td class="py-2 px-3 text-gray-400 font-mono text-[10px]">${formatCompact(r.output_tokens)}</td>
                            <td class="py-2 px-3 font-semibold text-indigo-300 font-mono text-[10px]">${formatCompact(r.total_tokens)}</td>
                            <td class="py-2 px-3 text-right font-mono text-emerald-400 text-[10px]">
                                $${(r.cost_usd || 0).toFixed(4)} <span class="text-gray-500 text-[9px]">(R$ ${(r.cost_brl || 0).toFixed(2)})</span>
                            </td>
                        </tr>
                    `;
                }).join('');
            }
        }
    } catch (e) {
        console.error('Erro ao atualizar modal de tokens:', e);
    }
}

async function updatePlanTier(tier) {
    try {
        const res = await fetch('/api/tokens/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_tier: tier })
        });
        if (res.ok) {
            await refreshModalTokenData();
            await loadTokenStats();
        }
    } catch (e) {
        console.error('Erro ao alterar plano:', e);
    }
}

async function saveModalBudget() {
    const input = document.getElementById('modal-budget-input');
    const val = parseInt(input.value, 10);
    if (isNaN(val) || val <= 0) {
        alert('Por favor insira um valor válido para o teto diário de tokens.');
        return;
    }

    try {
        const res = await fetch('/api/tokens/budget', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ daily_budget: val })
        });
        if (res.ok) {
            await refreshModalTokenData();
            await loadTokenStats();
            alert('Teto diário atualizado com sucesso!');
        }
    } catch (e) {
        alert(`Erro ao salvar teto: ${e.message}`);
    }
}

// Alternar entre as 3 Abas
function switchTab(tab) {
    currentTab = tab;
    ['agents', 'study', 'oracle', 'projects', 'documents'].forEach(t => {
        const section = document.getElementById(`tab-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (t === tab) {
            section.classList.remove('hidden');
            btn.className = 'tab-btn flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all bg-indigo-600 text-white shadow-md';
        } else {
            section.classList.add('hidden');
            btn.className = 'tab-btn flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white transition-all';
        }
    });

    if (tab === 'agents') {
        loadAgents();
        loadAreas();
    }
    if (tab === 'study') {
        if (typeof loadTelegramGroupsSummary === 'function') loadTelegramGroupsSummary();
        if (typeof renderBatchAgentChips === 'function') renderBatchAgentChips();
        if (typeof loadKnowledgeGraph === 'function') loadKnowledgeGraph();
    }
    if (tab === 'oracle') {
        loadKnowledgeSources();
        updateChatModeSelect();
    }
    if (tab === 'projects') {
        loadProjects();
    }
    if (tab === 'documents') {
        loadDocuments();
    }

    if (window.lucide) lucide.createIcons();
}

// ----------------- TAB 1: EQUIPE DE AGENTES & SENIORIDADE -----------------

async function loadAgents() {
    try {
        const res = await fetch('/api/agents');
        agentsList = await res.json();
        renderAgents();
        renderEmployeesTable();
        updateAgentCountBadge();
        updateChatModeSelect();
        renderBatchAgentChips();
        updateChannelAgentFilterSelect();
        if (groupsSummaryList && groupsSummaryList.length > 0) {
            renderChannelsGrid();
        }
    } catch (e) {
        console.error('Erro ao carregar agentes:', e);
    }
}

function updateAgentCountBadge() {
    const badge = document.getElementById('agents-count-badge');
    if (badge) {
        badge.innerText = `${agentsList.length} ${agentsList.length === 1 ? 'especialista' : 'especialistas'}`;
    }
}

function renderAgents() {
    const grid = document.getElementById('agents-grid');
    if (!grid) return;

    if (agentsList.length === 0) {
        grid.innerHTML = `<div class="col-span-3 text-center py-12 text-gray-500">Nenhum agente cadastrado. Clique no botão acima para contratar seu primeiro especialista!</div>`;
        return;
    }

    grid.innerHTML = agentsList.map(a => {
        const sen = a.seniority || {};
        const isStudying = a.status === 'estudando';
        const isGestor = a.agent_type === 'gestor';

        const statusBadge = isStudying
            ? `<span class="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-xs text-amber-400 font-medium shadow-sm">
                 <span class="w-2 h-2 rounded-full bg-amber-400 beacon-ping"></span>
                 <span>Estudando...</span>
               </span>`
            : `<span class="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 font-medium shadow-sm">
                 <span class="w-2 h-2 rounded-full bg-emerald-400 beacon-ping"></span>
                 <span>Ativo</span>
               </span>`;

        let rankBadgeClass = 'badge-estagiario';
        if (sen.rank === 'Júnior') rankBadgeClass = 'badge-junior';
        if (sen.rank === 'Pleno') rankBadgeClass = 'badge-pleno';
        if (sen.rank === 'Sênior') rankBadgeClass = 'badge-senior';
        if (sen.rank === 'Arquiteto Mestre') rankBadgeClass = 'badge-mestre';

        // Area badge & Hierarchy badge
        const area = areasList.find(ar => ar.id === a.area_id);
        const areaBadge = area 
            ? `<span class="px-2.5 py-0.5 rounded-lg text-[10px] font-bold tracking-wide" style="background: ${area.color || '#06b6d4'}18; color: ${area.color || '#06b6d4'}; border: 1px solid ${area.color || '#06b6d4'}40;">${area.icon || '🎯'} ${area.name}</span>`
            : `<span class="px-2.5 py-0.5 rounded-lg text-[10px] font-medium bg-gray-900 text-gray-400 border border-gray-800">Sem Área</span>`;

        const typeBadge = isGestor
            ? `<span class="px-2.5 py-0.5 rounded-lg text-[10px] font-bold badge-gestor flex items-center space-x-1">
                 <span>👑</span>
                 <span>Diretoria Executiva</span>
               </span>`
            : `<span class="px-2.5 py-0.5 rounded-lg text-[10px] font-semibold badge-tecnico flex items-center space-x-1">
                 <span>⚡</span>
                 <span>Técnico Especialista</span>
               </span>`;

        const topics = a.topics_mastered || [];
        const topicsHtml = topics.slice(0, 4).map(t => 
            `<span class="px-2.5 py-1 rounded-lg bg-gray-900/80 text-[11px] text-gray-300 border border-gray-800/80 font-mono">${t}</span>`
        ).join('') + (topics.length > 4 ? `<span class="text-[11px] text-gray-500 font-mono self-center">+${topics.length - 4}</span>` : '');

        let subagentsHtml = '';
        if (isGestor && a.subagents && a.subagents.length) {
            const subNames = a.subagents.map(sid => {
                const sub = agentsList.find(sa => sa.id === sid);
                return sub ? sub.name : sid;
            }).join(' • ');
            subagentsHtml = `
                <div class="px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 flex items-center space-x-2">
                    <span class="text-xs">↳</span>
                    <span class="font-medium truncate"><strong class="text-amber-200">Equipe subordinada:</strong> ${subNames}</span>
                </div>
            `;
        }

        if (isGestor) {
            return `
            <div onclick="openAgentDetailModal('${a.id}')" class="manager-executive-card cursor-pointer group">
                <div class="manager-executive-card-inner p-6 flex flex-col justify-between space-y-4">
                    <!-- Header do Gestor VIP -->
                    <div class="flex items-start justify-between">
                        <div class="flex items-center space-x-3.5">
                            <div class="relative">
                                <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-600/30 to-amber-400/10 border border-amber-500/40 flex items-center justify-center text-2xl shadow-lg shadow-amber-500/15 group-hover:scale-105 transition-all">
                                    ${a.avatar || '👑'}
                                </div>
                                <span class="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-amber-500 border-2 border-[#120f09] flex items-center justify-center text-[9px] font-bold text-black">✓</span>
                            </div>
                            <div>
                                <div class="flex items-center space-x-1.5 flex-wrap gap-1">
                                    <h3 class="text-base font-extrabold text-white text-gold-titanium">${a.name}</h3>
                                    <span class="text-xs px-2 py-0.5 rounded-md font-bold badge-gestor">
                                        LÍDER EXECUTIVO
                                    </span>
                                </div>
                                <p class="text-xs text-amber-300/90 font-medium mt-0.5">${a.role}</p>
                            </div>
                        </div>
                        ${statusBadge}
                    </div>

                    <!-- Badges de Área & Hierarquia -->
                    <div class="flex items-center space-x-2 flex-wrap gap-1.5">
                        ${areaBadge}
                        ${typeBadge}
                    </div>

                    ${subagentsHtml}

                    <!-- Barra de Experiência VIP -->
                    <div class="space-y-1.5 bg-[#0e0c08]/80 p-3.5 rounded-xl border border-amber-500/20">
                        <div class="flex justify-between text-xs">
                            <span class="text-amber-200/70 font-mono text-[11px]">Horas Estratégicas:</span>
                            <span class="font-bold text-white font-mono">${sen.current_hours || 0}h dedicadas</span>
                        </div>
                        <div class="w-full bg-gray-900 rounded-full h-2 overflow-hidden border border-amber-500/20">
                            <div class="bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-600 h-2 rounded-full transition-all duration-500" style="width: ${Math.min(100, Math.max(15, sen.progress_percentage || 0))}%"></div>
                        </div>
                        <div class="flex justify-between text-[11px] text-amber-400/60 pt-0.5 font-mono">
                            <span>Diretoria Ativa</span>
                            <span>${a.total_videos_studied || 0} aulas supervisionadas</span>
                        </div>
                    </div>

                    <!-- Pilares Estratégicos -->
                    <div class="space-y-2">
                        <div class="flex items-center justify-between text-xs font-semibold text-gray-400">
                            <span class="uppercase tracking-wider text-[10px] text-amber-300/80 font-mono">Pilares de Liderança</span>
                            <span class="text-amber-400 group-hover:underline text-[11px]">Gerenciar &rarr;</span>
                        </div>
                        <div class="flex flex-wrap gap-1.5">
                            ${topicsHtml || '<span class="text-xs text-gray-500">Gestão global de conhecimento</span>'}
                        </div>
                    </div>

                    <!-- Ações Rápidas -->
                    <div class="pt-3 border-t border-amber-500/20 flex items-center justify-between text-xs">
                        <div class="flex items-center space-x-1.5">
                            <button onclick="event.stopPropagation(); openAgentSpecModal('${a.id}')"
                                class="px-2.5 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[11px] font-semibold flex items-center space-x-1 transition-all cursor-pointer shadow-sm hover:scale-105 active:scale-95"
                                title="Ver Especificação agent.md & skills.md">
                                <i data-lucide="file-code-2" class="w-3.5 h-3.5"></i>
                                <span>Ver Spec</span>
                            </button>
                            <button onclick="event.stopPropagation(); exportAgentSkillById('${a.id}', '${a.name}')" 
                                class="px-2.5 py-1.5 rounded-xl bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 text-[11px] font-semibold flex items-center space-x-1 transition-all cursor-pointer shadow-sm hover:scale-105 active:scale-95"
                                title="Exportar como Skill do Antigravity">
                                <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
                                <span>Skill</span>
                            </button>
                        </div>
                        <button onclick="event.stopPropagation(); confirmDeleteEmployee('${a.id}')" 
                            class="p-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 transition-all cursor-pointer hover:scale-105 active:scale-95"
                            title="Excluir Agente">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </div>
            </div>
            `;
        }

        return `
        <div onclick="openAgentDetailModal('${a.id}')" class="spotlight-card p-6 flex flex-col justify-between space-y-4 cursor-pointer group">
            <!-- Header do Agente Especialista -->
            <div class="flex items-start justify-between">
                <div class="flex items-center space-x-3.5">
                    <div class="relative">
                        <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-950/80 to-purple-950/40 border border-purple-500/30 flex items-center justify-center text-2xl shadow-inner group-hover:scale-105 group-hover:border-purple-400/60 transition-all">
                            ${a.avatar || '👨‍💻'}
                        </div>
                        <span class="absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full ${isStudying ? 'bg-amber-400' : 'bg-emerald-400'} border-2 border-[#0c0e14]"></span>
                    </div>
                    <div>
                        <div class="flex items-center space-x-1.5 flex-wrap gap-1">
                            <h3 class="text-base font-bold text-white group-hover:text-purple-300 transition-colors">${a.name}</h3>
                            <span class="text-xs px-2 py-0.5 rounded-md font-semibold ${rankBadgeClass}">
                                ${sen.badge || ''} ${sen.rank || 'Estagiário'}
                            </span>
                        </div>
                        <p class="text-xs text-indigo-400 font-medium mt-0.5">${a.role}</p>
                    </div>
                </div>
                ${statusBadge}
            </div>

            <!-- Badges de Área & Hierarquia -->
            <div class="flex items-center space-x-2 flex-wrap gap-1.5">
                ${areaBadge}
                ${typeBadge}
            </div>

            <!-- Tarefa atual caso esteja estudando -->
            ${a.current_task ? `
            <div class="p-2.5 bg-indigo-950/50 rounded-xl border border-indigo-500/30 text-xs text-indigo-300 flex items-center space-x-2 shadow-inner">
                <i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin text-indigo-400"></i>
                <span class="truncate font-mono text-[11px]">${a.current_task}</span>
            </div>` : ''}

            <!-- Barra de Experiência / Senioridade -->
            <div class="space-y-1.5 bg-[#090b10]/80 p-3.5 rounded-xl border border-gray-800/80">
                <div class="flex justify-between text-xs">
                    <span class="text-gray-400 font-mono text-[11px]">Progresso até próximo nível:</span>
                    <span class="font-bold text-white font-mono">${sen.current_hours || 0}h / ${sen.next_goal_hours || 2}h</span>
                </div>
                <div class="w-full bg-gray-900 rounded-full h-2 overflow-hidden border border-gray-800">
                    <div class="bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-600 h-2 rounded-full transition-all duration-500 shadow-sm" style="width: ${sen.progress_percentage || 0}%"></div>
                </div>
                <div class="flex justify-between text-[11px] text-gray-500 pt-0.5 font-mono">
                    <span>${sen.progress_percentage || 0}% concluído</span>
                    <span>${a.total_videos_studied || 0} aulas (${a.total_hours_studied || 0}h)</span>
                </div>
            </div>

            <!-- Tópicos Dominados -->
            <div class="space-y-2">
                <div class="flex items-center justify-between text-xs font-semibold text-gray-400">
                    <span class="uppercase tracking-wider text-[10px] font-mono">Conhecimento Absorvido</span>
                    <span class="text-indigo-400 group-hover:underline text-[11px]">Gerenciar &rarr;</span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                    ${topicsHtml || '<span class="text-xs text-gray-500">Nenhum tópico estudado ainda</span>'}
                </div>
            </div>

            <!-- Ações Rápidas do Especialista -->
            <div class="pt-3 border-t border-gray-800/80 flex items-center justify-between text-xs">
                <div class="flex items-center space-x-1.5">
                    <button onclick="event.stopPropagation(); openAgentSpecModal('${a.id}')"
                        class="px-2.5 py-1.5 rounded-xl bg-indigo-950/40 hover:bg-indigo-900/60 text-indigo-300 border border-indigo-500/30 text-[11px] font-semibold flex items-center space-x-1 transition-all cursor-pointer shadow-sm hover:scale-105 active:scale-95"
                        title="Ver Especificação agent.md & skills.md">
                        <i data-lucide="file-code-2" class="w-3.5 h-3.5"></i>
                        <span>Ver Spec</span>
                    </button>
                    <button onclick="event.stopPropagation(); exportAgentSkillById('${a.id}', '${a.name}')" 
                        class="px-2.5 py-1.5 rounded-xl bg-teal-950/40 hover:bg-teal-900/60 text-teal-300 border border-teal-500/30 text-[11px] font-semibold flex items-center space-x-1 transition-all cursor-pointer shadow-sm hover:scale-105 active:scale-95"
                        title="Exportar como Skill do Antigravity">
                        <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
                        <span>Skill</span>
                    </button>
                </div>
                <button onclick="event.stopPropagation(); confirmDeleteEmployee('${a.id}')" 
                    class="p-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 transition-all cursor-pointer hover:scale-105 active:scale-95"
                    title="Excluir Agente">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

// ----------------- COCKPIT ORBITAL & GERENCIAMENTO DE ÁREAS DA VIDA -----------------

let currentConstellationAreaFilter = 'all';

function switchAgentView(mode) {
    currentAgentViewMode = mode;
    const orbitalView = document.getElementById('orbital-cockpit-view');
    const constView = document.getElementById('constellation-vault-view');
    const crudView = document.getElementById('crud-employees-view');
    const gridView = document.getElementById('all-specialists-view');
    const detailPanel = document.getElementById('area-detail-panel');

    const btnOrbital = document.getElementById('btn-view-orbital');
    const btnConst = document.getElementById('btn-view-constellation');
    const btnCrud = document.getElementById('btn-view-crud');
    const btnGrid = document.getElementById('btn-view-grid') || document.getElementById('btn-view-cards');

    if (detailPanel) detailPanel.classList.add('hidden');
    if (orbitalView) orbitalView.classList.add('hidden');
    if (constView) constView.classList.add('hidden');
    if (crudView) crudView.classList.add('hidden');
    if (gridView) gridView.classList.add('hidden');

    const activeBtnClass = 'flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all bg-indigo-600 text-white shadow';
    const inactiveBtnClass = 'flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white transition-all';

    if (btnOrbital) btnOrbital.className = inactiveBtnClass;
    if (btnConst) btnConst.className = inactiveBtnClass;
    if (btnCrud) btnCrud.className = inactiveBtnClass;
    if (btnGrid) btnGrid.className = inactiveBtnClass;

    if (mode === 'orbital') {
        if (orbitalView) orbitalView.classList.remove('hidden');
        if (btnOrbital) btnOrbital.className = activeBtnClass;
        setTimeout(() => {
            initOrbitalRadar();
        }, 30);
    } else if (mode === 'constellation') {
        if (constView) constView.classList.remove('hidden');
        if (btnConst) btnConst.className = activeBtnClass;
        setTimeout(() => {
            initObsidianGraph();
            loadKnowledgeGraph();
        }, 30);
    } else if (mode === 'crud') {
        if (crudView) crudView.classList.remove('hidden');
        if (btnCrud) btnCrud.className = activeBtnClass;
        renderEmployeesTable();
    } else {
        if (gridView) gridView.classList.remove('hidden');
        if (btnGrid) btnGrid.className = activeBtnClass;
        renderAgents();
    }
    if (window.lucide) lucide.createIcons();
}

function openConstellationForArea(areaId) {
    switchAgentView('constellation');
    const select = document.getElementById('constellation-area-filter');
    if (select) select.value = areaId;
    onConstellationAreaFilterChange(areaId);
}

function onConstellationAreaFilterChange(areaId) {
    currentConstellationAreaFilter = areaId || 'all';
    const crumb = document.getElementById('constellation-active-area-crumb');
    const area = areasList.find(a => a.id === areaId);
    if (crumb) {
        crumb.innerText = area ? area.name.toLowerCase().replace(/[^a-z0-9]/g, '-') : 'todo-o-sistema';
    }
    graphSimAlpha = 0.8;
    renderVaultTree();
}

function populateAllAreaSelects() {
    const areaSelectIds = [
        'crud-filter-area',
        'constellation-area-filter',
        'agent-area-select',
        'emp-edit-area-select',
        'new-proj-area'
    ];

    areaSelectIds.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const currentVal = el.value;
        const isFilter = id.includes('filter');
        
        let html = isFilter ? '<option value="all">Todas as Áreas</option>' : '<option value="">Sem Área Vinculada</option>';
        areasList.forEach(ar => {
            html += `<option value="${ar.id}">${ar.icon || '📁'} ${ar.name}</option>`;
        });
        el.innerHTML = html;
        if (currentVal && Array.from(el.options).some(o => o.value === currentVal)) {
            el.value = currentVal;
        }
    });

    const badge = document.getElementById('areas-count-badge');
    if (badge) badge.innerText = `${areasList.length} ${areasList.length === 1 ? 'área' : 'áreas'}`;
}

async function loadAreas() {
    try {
        const res = await fetch('/api/areas');
        if (!res.ok) return;
        areasList = await res.json();

        // Atualiza métricas de resumo
        const totalAreasEl = document.getElementById('metric-total-areas');
        const avgHealthEl = document.getElementById('metric-avg-health');
        const activeMgrsEl = document.getElementById('metric-active-managers');
        const totalSkillsEl = document.getElementById('metric-total-skills');

        if (totalAreasEl) totalAreasEl.innerText = areasList.length;

        let totalHealth = 0;
        let activeMgrs = 0;
        let totalUniqueSkills = new Set();

        areasList.forEach(a => {
            totalHealth += (a.health_score || 90);
            if (a.manager_agent_id) activeMgrs++;
            (a.topics_mastered || []).forEach(t => totalUniqueSkills.add(t));
        });

        const avgHealth = areasList.length ? Math.round(totalHealth / areasList.length) : 94;
        if (avgHealthEl) avgHealthEl.innerText = `${avgHealth}%`;
        if (activeMgrsEl) activeMgrsEl.innerText = activeMgrs;
        if (totalSkillsEl) totalSkillsEl.innerText = totalUniqueSkills.size;

        populateAllAreaSelects();
        renderQuickAreasGrid();
        updateAreaManagerSelect();
        initOrbitalRadar();
    } catch (e) {
        console.error('Erro ao carregar áreas da vida:', e);
    }
}

function renderQuickAreasGrid() {
    const grid = document.getElementById('quick-areas-grid');
    if (!grid) return;

    if (!areasList || areasList.length === 0) {
        grid.innerHTML = `<div class="col-span-3 text-center py-6 text-gray-500 text-xs">Nenhuma área da vida cadastrada ainda.</div>`;
        return;
    }

    grid.innerHTML = areasList.map(area => {
        const color = area.color || '#06b6d4';
        const health = area.health_score || 90;
        const manager = area.manager;
        const managerName = manager ? manager.name : 'Não designado';
        const managerAvatar = manager ? (manager.avatar || '👑') : '👤';
        const agentCount = (area.subagent_ids ? area.subagent_ids.length : 0) + (area.manager_agent_id ? 1 : 0);

        return `
        <div onclick="drillDownArea('${area.id}')" class="area-quick-card p-4 rounded-2xl cursor-pointer group flex flex-col justify-between space-y-3">
            <div class="flex items-start justify-between">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl shadow-inner" style="background: ${color}20; border: 1px solid ${color}40;">
                        ${area.icon || '🎯'}
                    </div>
                    <div>
                        <h4 class="text-sm font-bold text-white group-hover:text-cyan-300 transition-all flex items-center space-x-1.5">
                            <span>${area.name}</span>
                        </h4>
                        <p class="text-[11px] text-gray-400 truncate max-w-[180px]">${area.description || 'Área estratégica'}</p>
                    </div>
                </div>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold" style="background: ${color}20; color: ${color}; border: 1px solid ${color}40;">
                    ${health}% SAÚDE
                </span>
            </div>

            <div class="pt-2 border-t border-gray-800/80 flex items-center justify-between text-xs text-gray-400">
                <div class="flex items-center space-x-1.5">
                    <span class="text-sm">${managerAvatar}</span>
                    <span class="text-[11px]"><strong class="text-gray-300">${managerName}</strong> (Gestor)</span>
                </div>
                <span class="text-[11px] text-indigo-400 font-semibold group-hover:translate-x-0.5 transition-transform flex items-center space-x-0.5">
                    <span>${agentCount} agentes</span>
                    <span>&rarr;</span>
                </span>
            </div>
        </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

// ----------------- MOTOR GRÁFICO DO RADAR ORBITAL (CANVAS 2D) -----------------

let radarState = {
    canvas: null,
    ctx: null,
    width: 840,
    height: 580,
    cx: 420,
    cy: 290,
    coreRadius: 72,
    satellites: [],
    rotation: 0
};

function initOrbitalRadar() {
    const canvas = document.getElementById('orbital-radar-canvas');
    if (!canvas) return;

    radarState.canvas = canvas;
    const ctx = canvas.getContext('2d');
    radarState.ctx = ctx;

    const dpr = window.devicePixelRatio || 1;
    const containerW = canvas.parentElement ? canvas.parentElement.clientWidth : 840;
    const displayWidth = Math.min(840, Math.max(600, containerW));
    const displayHeight = 580;

    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;

    radarState.width = displayWidth;
    radarState.height = displayHeight;
    radarState.cx = displayWidth / 2;
    radarState.cy = displayHeight / 2;

    canvas.onmousemove = onRadarMouseMove;
    canvas.onmouseleave = onRadarMouseLeave;
    canvas.onclick = onRadarClick;

    if (!radarAnimFrame) {
        animateOrbitalRadar();
    }
}

function animateOrbitalRadar() {
    radarState.rotation += 0.003;
    drawOrbitalRadar();
    radarAnimFrame = requestAnimationFrame(animateOrbitalRadar);
}

function drawOrbitalRadar() {
    const { ctx, width, height, cx, cy, coreRadius, rotation } = radarState;
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // 1. Grade circular e teia orbital
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    [95, 120, 145, 170, 195].forEach(r => {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
    });

    // Guias em cruz sutil
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.08)';
    ctx.beginPath();
    ctx.moveTo(cx - 240, cy);
    ctx.lineTo(cx + 240, cy);
    ctx.moveTo(cx, cy - 240);
    ctx.lineTo(cx, cy + 240);
    ctx.stroke();

    const n = areasList.length || 6;
    const angleStep = (Math.PI * 2) / n;
    const baseOffset = -Math.PI / 2;
    const satellites = [];

    // 2. Setores Radiais com Segmentos de LED Concêntricos
    areasList.forEach((area, i) => {
        const isHovered = (radarHoveredIndex === i);
        const startAngle = baseOffset + i * angleStep + 0.04;
        const endAngle = startAngle + angleStep - 0.08;
        const midAngle = (startAngle + endAngle) / 2;
        const areaColor = area.color || '#06b6d4';
        const health = area.health_score || 90;

        // 5 faixas concêntricas de LED
        const totalTracks = 5;
        const litTracks = Math.max(1, Math.min(totalTracks, Math.round((health / 100) * totalTracks)));

        for (let t = 0; t < totalTracks; t++) {
            const rIn = 85 + t * 21;
            const rOut = rIn + 14;
            const isLit = t < litTracks;

            ctx.beginPath();
            ctx.arc(cx, cy, rOut, startAngle, endAngle);
            ctx.arc(cx, cy, rIn, endAngle, startAngle, true);
            ctx.closePath();

            if (isLit) {
                if (isHovered) {
                    ctx.fillStyle = areaColor;
                    ctx.shadowColor = areaColor;
                    ctx.shadowBlur = 14;
                } else {
                    ctx.fillStyle = areaColor + 'cc';
                    ctx.shadowBlur = 0;
                }
            } else {
                ctx.fillStyle = 'rgba(255, 255, 255, 0.06)';
                ctx.shadowBlur = 0;
            }
            ctx.fill();
        }
        ctx.shadowBlur = 0;

        // Linha divisória radial
        ctx.strokeStyle = isHovered ? areaColor : 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.beginPath();
        ctx.moveTo(cx + 80 * Math.cos(startAngle - 0.02), cy + 80 * Math.sin(startAngle - 0.02));
        ctx.lineTo(cx + 195 * Math.cos(startAngle - 0.02), cy + 195 * Math.sin(startAngle - 0.02));
        ctx.stroke();

        // Linhas de guia aos Satélites
        const lineStartR = 192;
        const lineElbowR = 230;
        const pStart = { x: cx + lineStartR * Math.cos(midAngle), y: cy + lineStartR * Math.sin(midAngle) };
        const pElbow = { x: cx + lineElbowR * Math.cos(midAngle), y: cy + lineElbowR * Math.sin(midAngle) };

        const isRightSide = Math.cos(midAngle) >= 0;
        const cardW = 164;
        const cardH = 46;
        const cardX = isRightSide ? pElbow.x + 10 : pElbow.x - cardW - 10;
        const cardY = pElbow.y - cardH / 2;

        ctx.strokeStyle = isHovered ? areaColor : 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = isHovered ? 1.5 : 1;
        ctx.beginPath();
        ctx.moveTo(pStart.x, pStart.y);
        ctx.lineTo(pElbow.x, pElbow.y);
        ctx.lineTo(isRightSide ? cardX : cardX + cardW, pElbow.y);
        ctx.stroke();

        // Ponto de conexão
        ctx.fillStyle = isHovered ? areaColor : '#fff';
        ctx.beginPath();
        ctx.arc(pStart.x, pStart.y, isHovered ? 3.5 : 2.5, 0, Math.PI * 2);
        ctx.fill();

        satellites.push({
            index: i,
            area: area,
            bounds: { x: cardX, y: cardY, w: cardW, h: cardH },
            startAngle,
            endAngle
        });

        // Desenha o Satélite
        drawSatelliteCard(ctx, area, cardX, cardY, cardW, cardH, isHovered);
    });

    radarState.satellites = satellites;

    // 3. Núcleo Central (94 SAÚDE / VITALIDADE SISTÊMICA)
    drawRadarCentralCore(ctx, cx, cy, coreRadius, rotation);

    ctx.restore();
}

function drawRadarCentralCore(ctx, cx, cy, r, rotation) {
    // Anel externo tracejado e pulsante
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rotation);
    ctx.strokeStyle = 'rgba(52, 211, 153, 0.4)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 6]);
    ctx.beginPath();
    ctx.arc(0, 0, r + 6, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // Círculo central com gradiente
    const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, r);
    grad.addColorStop(0, '#131b26');
    grad.addColorStop(1, '#090d14');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();

    // Borda do núcleo
    ctx.strokeStyle = 'rgba(52, 211, 153, 0.6)';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#10b981';
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.shadowBlur = 0;

    let avgHealth = 94;
    if (areasList.length > 0) {
        const sum = areasList.reduce((acc, a) => acc + (a.health_score || 90), 0);
        avgHealth = Math.round(sum / areasList.length);
    }

    // Número grande central
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#34d399';
    ctx.font = '800 36px "JetBrains Mono", sans-serif';
    ctx.fillText(`${avgHealth}`, cx, cy - 8);

    // Label abaixo do número
    ctx.fillStyle = '#94a3b8';
    ctx.font = '700 9px "JetBrains Mono", sans-serif';
    ctx.fillText('SAÚDE GERAL', cx, cy + 18);
}

function drawSatelliteCard(ctx, area, x, y, w, h, isHovered) {
    const color = area.color || '#06b6d4';
    const radius = 10;

    // Fundo do card
    ctx.fillStyle = isHovered ? 'rgba(20, 27, 39, 0.96)' : 'rgba(12, 16, 23, 0.9)';
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, radius);
    ctx.fill();

    // Borda
    ctx.strokeStyle = isHovered ? color : 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = isHovered ? 1.5 : 1;
    if (isHovered) {
        ctx.shadowColor = color;
        ctx.shadowBlur = 10;
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    // Título
    ctx.fillStyle = isHovered ? '#ffffff' : '#e2e8f0';
    ctx.font = '700 11px Inter, sans-serif';
    const nameStr = `${area.icon || '🎯'} ${(area.name || '').slice(0, 16)}`;
    ctx.fillText(nameStr, x + 8, y + 8);

    // Subtítulo
    const mgrName = area.manager ? area.manager.name : 'Sem Gestor';
    const subCount = (area.subagent_ids ? area.subagent_ids.length : 0) + (area.manager_agent_id ? 1 : 0);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '500 9px Inter, sans-serif';
    ctx.fillText(`${mgrName} • ${subCount} Agentes`, x + 8, y + 25);

    // Score de Saúde
    const scoreStr = `${area.health_score || 90}%`;
    ctx.font = '700 10px "JetBrains Mono", sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'right';
    ctx.fillText(scoreStr, x + w - 8, y + 8);
}

function onRadarMouseMove(e) {
    if (!radarState.canvas) return;
    const rect = radarState.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    let foundIndex = -1;

    // 1. Testa Satélites
    for (const sat of radarState.satellites) {
        const b = sat.bounds;
        if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) {
            foundIndex = sat.index;
            break;
        }
    }

    // 2. Testa Setores Radiais
    if (foundIndex === -1) {
        const dx = mx - radarState.cx;
        const dy = my - radarState.cy;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist >= 80 && dist <= 205) {
            let angle = Math.atan2(dy, dx);
            if (angle < -Math.PI / 2) angle += Math.PI * 2;

            for (const sat of radarState.satellites) {
                let sA = sat.startAngle;
                let eA = sat.endAngle;
                if (sA < -Math.PI / 2) sA += Math.PI * 2;
                if (eA < -Math.PI / 2) eA += Math.PI * 2;

                if (angle >= sA && angle <= eA) {
                    foundIndex = sat.index;
                    break;
                }
            }
        }
    }

    if (radarHoveredIndex !== foundIndex) {
        radarHoveredIndex = foundIndex;
        radarState.canvas.style.cursor = foundIndex >= 0 ? 'pointer' : 'default';
    }
}

function onRadarMouseLeave() {
    radarHoveredIndex = -1;
    if (radarState.canvas) radarState.canvas.style.cursor = 'default';
}

function onRadarClick(e) {
    if (radarHoveredIndex >= 0 && areasList[radarHoveredIndex]) {
        openConstellationForArea(areasList[radarHoveredIndex].id);
    }
}

// ----------------- DRILL-DOWN: PAINEL DETALHADO DA ÁREA -----------------

// ----------------- DRILL-DOWN: PAINEL DETALHADO DA ÁREA & CONSTELAÇÃO -----------------

let currentAreaSubTab = 'constellation'; // 'constellation' | 'cards'
let areaGraphRawData = { nodes: [], links: [] };
let areaGraphSimNodes = [];
let areaGraphSimLinks = [];
let areaGraphFilterType = 'all';
let areaGraphCanvas = null;
let areaGraphCtx = null;
let areaGraphAnimFrame = null;
let areaGraphPanX = 0;
let areaGraphPanY = 0;
let areaGraphZoom = 1.0;
let areaGraphIsDragging = false;
let areaGraphDraggedNode = null;
let areaGraphHoveredNode = null;
let areaGraphSelectedNode = null;
let areaGraphDragStartX = 0;
let areaGraphDragStartY = 0;

async function drillDownArea(areaId) {
    currentSelectedAreaId = areaId;
    const orbitalView = document.getElementById('orbital-cockpit-view');
    const gridView = document.getElementById('all-specialists-view');
    const detailPanel = document.getElementById('area-detail-panel');

    if (orbitalView) orbitalView.classList.add('hidden');
    if (gridView) gridView.classList.add('hidden');
    if (detailPanel) detailPanel.classList.remove('hidden');

    try {
        const res = await fetch(`/api/areas/${areaId}`);
        if (!res.ok) return;
        const area = await res.json();

        const color = area.color || '#06b6d4';
        document.getElementById('detail-area-icon').innerText = area.icon || '🎯';
        document.getElementById('detail-area-name').innerText = area.name;
        document.getElementById('detail-area-title-large').innerText = area.name;
        document.getElementById('detail-area-desc').innerText = area.description || 'Domínio estratégico da vida.';
        document.getElementById('detail-area-health-val').innerText = area.health_score || 90;

        const totalAgents = (area.subagents ? area.subagents.length : 0) + (area.manager ? 1 : 0);
        document.getElementById('detail-area-agents-count').innerText = `${totalAgents} Agente(s) Cadastrado(s)`;

        const badge = document.getElementById('detail-area-badge');
        if (badge) {
            badge.style.background = `${color}25`;
            badge.style.color = color;
            badge.style.borderColor = `${color}50`;
        }

        renderAreaManagerCard(area);
        renderAreaSubagentsGrid(area);
        renderAreaSkillsList(area);

        // Abre na aba da Constelação Estelar por padrão
        switchAreaDetailSubTab('constellation');
        await loadAreaConstellation(areaId);

        if (window.lucide) lucide.createIcons();
    } catch (e) {
        console.error('Erro ao abrir detalhes da área:', e);
    }
}

function switchAreaDetailSubTab(subTab) {
    currentAreaSubTab = subTab;
    const viewConstellation = document.getElementById('area-subview-constellation');
    const viewCards = document.getElementById('area-subview-cards');
    const btnConstellation = document.getElementById('btn-area-tab-constellation');
    const btnCards = document.getElementById('btn-area-tab-cards');

    if (subTab === 'constellation') {
        if (viewConstellation) viewConstellation.classList.remove('hidden');
        if (viewCards) viewCards.classList.add('hidden');
        if (btnConstellation) {
            btnConstellation.className = 'flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all bg-indigo-600 text-white shadow';
        }
        if (btnCards) {
            btnCards.className = 'flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-gray-400 hover:text-white transition-all';
        }
        setTimeout(() => {
            initAreaConstellationCanvas();
        }, 50);
    } else {
        if (viewConstellation) viewConstellation.classList.add('hidden');
        if (viewCards) viewCards.classList.remove('hidden');
        if (btnConstellation) {
            btnConstellation.className = 'flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-gray-400 hover:text-white transition-all';
        }
        if (btnCards) {
            btnCards.className = 'flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all bg-indigo-600 text-white shadow';
        }
    }
    if (window.lucide) lucide.createIcons();
}

async function loadAreaConstellation(areaId) {
    try {
        const res = await fetch(`/api/areas/${areaId}/graph`);
        if (!res.ok) return;
        const data = await res.json();
        areaGraphRawData = data;

        const nodes = data.nodes || [];
        const links = data.links || [];
        const agents = nodes.filter(n => n.type === 'agent');
        const courses = nodes.filter(n => n.type === 'course');
        const lessons = nodes.filter(n => n.type === 'lesson');
        const topics = nodes.filter(n => n.type === 'topic');

        const badge = document.getElementById('area-graph-nodes-count');
        if (badge) {
            badge.innerText = `${agents.length} Agente(s) • ${courses.length} Curso(s) • ${lessons.length} Aula(s) • ${topics.length} Habilidades`;
        }

        const agentCount = agents.length || 1;

        areaGraphSimNodes = nodes.map((n) => {
            let x = 0, y = 0;
            if (n.type === 'area_hub') {
                x = 0;
                y = 0;
            } else if (n.type === 'agent') {
                const aIdx = agents.indexOf(n);
                const angle = (aIdx / agentCount) * Math.PI * 2 - Math.PI / 2;
                x = Math.cos(angle) * 115;
                y = Math.sin(angle) * 115;
            } else if (n.type === 'course') {
                const angle = Math.random() * Math.PI * 2;
                x = Math.cos(angle) * (180 + Math.random() * 30);
                y = Math.sin(angle) * (180 + Math.random() * 30);
            } else if (n.type === 'lesson') {
                const angle = Math.random() * Math.PI * 2;
                x = Math.cos(angle) * (230 + Math.random() * 45);
                y = Math.sin(angle) * (230 + Math.random() * 45);
            } else if (n.type === 'topic') {
                const angle = Math.random() * Math.PI * 2;
                x = Math.cos(angle) * (165 + Math.random() * 40);
                y = Math.sin(angle) * (165 + Math.random() * 40);
            } else {
                x = (Math.random() - 0.5) * 200;
                y = (Math.random() - 0.5) * 200;
            }

            return {
                ...n,
                x,
                y,
                vx: 0,
                vy: 0,
                radius: n.size || 10
            };
        });

        const nodeMap = new Map(areaGraphSimNodes.map(n => [n.id, n]));
        areaGraphSimLinks = links.map(l => ({
            source: nodeMap.get(l.source),
            target: nodeMap.get(l.target),
            distance: l.distance || 65,
            color: l.color || 'rgba(148, 163, 184, 0.3)',
            width: l.width || 1
        })).filter(l => l.source && l.target);

        initAreaConstellationCanvas();

    } catch (e) {
        console.error('Erro ao carregar constelação da área:', e);
    }
}

function initAreaConstellationCanvas() {
    const canvas = document.getElementById('area-constellation-canvas');
    if (!canvas) return;

    areaGraphCanvas = canvas;
    areaGraphCtx = canvas.getContext('2d');

    const dpr = window.devicePixelRatio || 1;
    const parentW = canvas.parentElement ? canvas.parentElement.clientWidth : 860;
    const displayWidth = Math.max(600, parentW);
    const displayHeight = 540;

    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;

    canvas.onmousedown = onAreaGraphMouseDown;
    window.onmousemove = onAreaGraphMouseMove;
    window.onmouseup = onAreaGraphMouseUp;
    canvas.onwheel = onAreaGraphWheel;
    canvas.onclick = onAreaGraphClick;

    if (!areaGraphAnimFrame) {
        animateAreaConstellation();
    }
}

function animateAreaConstellation() {
    simulateAreaGraphPhysics();
    drawAreaConstellation();
    areaGraphAnimFrame = requestAnimationFrame(animateAreaConstellation);
}

function simulateAreaGraphPhysics() {
    const nodes = areaGraphSimNodes;
    const links = areaGraphSimLinks;
    if (!nodes || nodes.length === 0) return;

    // 1. Repulsão de nós
    for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const distSq = dx * dx + dy * dy + 80;
            const dist = Math.sqrt(distSq);
            const repForce = ((a.radius + b.radius) * 110) / distSq;
            const fx = (dx / dist) * repForce;
            const fy = (dy / dist) * repForce;

            if (a.type !== 'area_hub') {
                a.vx -= fx;
                a.vy -= fy;
            }
            if (b.type !== 'area_hub') {
                b.vx += fx;
                b.vy += fy;
            }
        }
    }

    // 2. Molas elásticas de atração
    for (let i = 0; i < links.length; i++) {
        const l = links[i];
        const a = l.source;
        const b = l.target;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const displacement = dist - l.distance;
        const springK = (b.type === 'lesson') ? 0.055 : 0.035;
        const springForce = displacement * springK;

        const fx = (dx / dist) * springForce;
        const fy = (dy / dist) * springForce;

        if (a.type !== 'area_hub') {
            a.vx += fx;
            a.vy += fy;
        }
        if (b.type !== 'area_hub') {
            b.vx -= fx;
            b.vy -= fy;
        }
    }

    // 3. Gravidade central e amortecimento
    for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        if (n.type === 'area_hub') {
            n.vx = 0;
            n.vy = 0;
            if (n !== areaGraphDraggedNode) {
                n.x = 0;
                n.y = 0;
            }
            continue;
        }

        n.vx -= n.x * 0.0006;
        n.vy -= n.y * 0.0006;
        n.vx *= 0.86;
        n.vy *= 0.86;

        if (n !== areaGraphDraggedNode) {
            n.x += n.vx;
            n.y += n.vy;
        }
    }
}

function drawAreaConstellation() {
    const canvas = areaGraphCanvas;
    const ctx = areaGraphCtx;
    if (!canvas || !ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;

    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    ctx.translate(width / 2 + areaGraphPanX, height / 2 + areaGraphPanY);
    ctx.scale(areaGraphZoom, areaGraphZoom);

    // Órbitas de fundo sutis em volta do Sol da Área
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    [115, 180, 240, 290].forEach(r => {
        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.stroke();
    });

    const nodes = areaGraphSimNodes;
    const links = areaGraphSimLinks;

    // 1. Desenha Links
    for (let i = 0; i < links.length; i++) {
        const l = links[i];
        ctx.beginPath();
        ctx.moveTo(l.source.x, l.source.y);
        ctx.lineTo(l.target.x, l.target.y);
        ctx.strokeStyle = l.color;
        ctx.lineWidth = l.width || 1;
        ctx.stroke();
    }

    // 2. Desenha Nós
    for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        const isHovered = (n === areaGraphHoveredNode);
        const isSelected = (n === areaGraphSelectedNode);

        ctx.save();
        ctx.shadowBlur = (n.type === 'area_hub' || n.type === 'agent' || isHovered) ? 16 : 6;
        ctx.shadowColor = n.color || '#06b6d4';

        // Nó Central da Área (Super Hub)
        if (n.type === 'area_hub') {
            // Anel pulsante
            const pulse = (Math.sin(Date.now() / 300) + 1) * 3;
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius + 6 + pulse, 0, Math.PI * 2);
            ctx.strokeStyle = n.color + '55';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Esfera central
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
            ctx.fillStyle = n.color;
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2.5;
            ctx.stroke();

            // Emoji do Ícone
            ctx.shadowBlur = 0;
            ctx.font = '20px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(n.icon || '🎯', n.x, n.y);

            // Label
            ctx.font = 'bold 12px Inter, sans-serif';
            ctx.fillStyle = '#ffffff';
            ctx.textBaseline = 'top';
            ctx.fillText(n.label, n.x, n.y + n.radius + 6);
        } else if (n.type === 'agent') {
            // Agente (Planeta)
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
            ctx.fillStyle = n.is_manager ? '#f59e0b' : n.color;
            ctx.fill();
            ctx.strokeStyle = n.is_manager ? '#fbbf24' : '#ffffff';
            ctx.lineWidth = n.is_manager ? 2.5 : 1.5;
            ctx.stroke();

            // Avatar
            ctx.shadowBlur = 0;
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(n.avatar || '👨‍💻', n.x, n.y);

            // Nome e Cargo
            ctx.font = 'bold 10px monospace';
            ctx.fillStyle = '#ffffff';
            ctx.textBaseline = 'top';
            ctx.fillText(`${n.is_manager ? '👑 ' : ''}${n.label}`, n.x, n.y + n.radius + 4);
        } else if (n.type === 'course') {
            // Curso (Assunto maior)
            ctx.beginPath();
            ctx.arc(n.x, n.y, 35, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(129, 140, 248, 0.25)';
            ctx.setLineDash([3, 4]);
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
            ctx.fillStyle = n.color || '#818cf8';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.shadowBlur = 0;
            ctx.font = 'bold 9px monospace';
            ctx.fillStyle = '#c7d2fe';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            const shortTitle = n.label.length > 18 ? n.label.slice(0, 16) + '...' : n.label;
            ctx.fillText(shortTitle, n.x, n.y + n.radius + 3);
        } else if (n.type === 'lesson') {
            // Aula Estudada (Bolinha de conhecimento verde esmeralda)
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
            ctx.fillStyle = n.color || '#22c55e';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = isHovered ? 2 : 1;
            ctx.stroke();

            // Ponto de brilho interno
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(n.x - 2, n.y - 2, 1.5, 0, Math.PI * 2);
            ctx.fill();

            if (isHovered || isSelected || areaGraphZoom > 1.3) {
                ctx.shadowBlur = 0;
                ctx.font = '9px monospace';
                ctx.fillStyle = '#86efac';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                const shortTitle = n.label.length > 20 ? n.label.slice(0, 18) + '...' : n.label;
                ctx.fillText(shortTitle, n.x, n.y + n.radius + 2);
            }
        } else if (n.type === 'topic') {
            // Habilidade / Tópico
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
            ctx.fillStyle = n.color || '#38bdf8';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1;
            ctx.stroke();

            if (isHovered || isSelected || areaGraphZoom > 1.2) {
                ctx.shadowBlur = 0;
                ctx.font = '9px monospace';
                ctx.fillStyle = '#7dd3fc';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(`#${n.label}`, n.x, n.y + n.radius + 2);
            }
        }
        ctx.restore();
    }

    ctx.restore();
}

function onAreaGraphMouseDown(e) {
    if (!areaGraphCanvas) return;
    const rect = areaGraphCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const dpr = window.devicePixelRatio || 1;
    const width = areaGraphCanvas.width / dpr;
    const height = areaGraphCanvas.height / dpr;

    const worldX = (mx - (width / 2 + areaGraphPanX)) / areaGraphZoom;
    const worldY = (my - (height / 2 + areaGraphPanY)) / areaGraphZoom;

    // Procura nó sob o cursor
    let clicked = null;
    for (let i = areaGraphSimNodes.length - 1; i >= 0; i--) {
        const n = areaGraphSimNodes[i];
        const dx = worldX - n.x;
        const dy = worldY - n.y;
        if (dx * dx + dy * dy <= (n.radius + 5) * (n.radius + 5)) {
            clicked = n;
            break;
        }
    }

    if (clicked) {
        areaGraphDraggedNode = clicked;
        areaGraphSelectedNode = clicked;
        updateAreaNodeInspector(clicked);
    } else {
        areaGraphIsDragging = true;
        areaGraphDragStartX = mx - areaGraphPanX;
        areaGraphDragStartY = my - areaGraphPanY;
        if (areaGraphCanvas) areaGraphCanvas.classList.add('cursor-grabbing');
    }
}

function onAreaGraphMouseMove(e) {
    if (!areaGraphCanvas) return;
    const rect = areaGraphCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const dpr = window.devicePixelRatio || 1;
    const width = areaGraphCanvas.width / dpr;
    const height = areaGraphCanvas.height / dpr;

    if (areaGraphDraggedNode) {
        areaGraphDraggedNode.x = (mx - (width / 2 + areaGraphPanX)) / areaGraphZoom;
        areaGraphDraggedNode.y = (my - (height / 2 + areaGraphPanY)) / areaGraphZoom;
        return;
    }

    if (areaGraphIsDragging) {
        areaGraphPanX = mx - areaGraphDragStartX;
        areaGraphPanY = my - areaGraphDragStartY;
        return;
    }

    const worldX = (mx - (width / 2 + areaGraphPanX)) / areaGraphZoom;
    const worldY = (my - (height / 2 + areaGraphPanY)) / areaGraphZoom;

    let hovered = null;
    for (let i = areaGraphSimNodes.length - 1; i >= 0; i--) {
        const n = areaGraphSimNodes[i];
        const dx = worldX - n.x;
        const dy = worldY - n.y;
        if (dx * dx + dy * dy <= (n.radius + 5) * (n.radius + 5)) {
            hovered = n;
            break;
        }
    }

    if (areaGraphHoveredNode !== hovered) {
        areaGraphHoveredNode = hovered;
        if (hovered) {
            updateAreaNodeInspector(hovered);
        }
    }
}

function onAreaGraphMouseUp() {
    areaGraphDraggedNode = null;
    areaGraphIsDragging = false;
    if (areaGraphCanvas) areaGraphCanvas.classList.remove('cursor-grabbing');
}

function onAreaGraphWheel(e) {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    areaGraphZoom = Math.min(3.0, Math.max(0.4, areaGraphZoom * zoomFactor));
}

function onAreaGraphClick(e) {
    if (areaGraphHoveredNode) {
        updateAreaNodeInspector(areaGraphHoveredNode);
    }
}

function resetAreaGraphView() {
    areaGraphPanX = 0;
    areaGraphPanY = 0;
    areaGraphZoom = 1.0;
}

function onAreaGraphFilterChange(val) {
    areaGraphFilterType = val;
}

function updateAreaNodeInspector(node) {
    const box = document.getElementById('area-node-inspector-box');
    if (!box || !node) return;

    box.classList.remove('hidden');
    const avatarEl = document.getElementById('inspector-node-avatar');
    const typeEl = document.getElementById('inspector-node-type');
    const titleEl = document.getElementById('inspector-node-title');
    const descEl = document.getElementById('inspector-node-desc');
    const extraEl = document.getElementById('inspector-node-extra');

    if (node.type === 'area_hub') {
        avatarEl.innerText = node.icon || '🎯';
        typeEl.innerText = 'DOMÍNIO CENTRAL';
        typeEl.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300';
        titleEl.innerText = node.label;
        descEl.innerText = `Saúde Geral: ${node.health}% • ${node.agents_count || 0} Agentes Cadastrados`;
        extraEl.innerHTML = `<span>Sol Central da Constelação</span><span class="text-cyan-400">Hub Estratégico</span>`;
    } else if (node.type === 'agent') {
        avatarEl.innerText = node.avatar || '👨‍💻';
        typeEl.innerText = node.is_manager ? 'GESTOR EXECUTIVO' : 'ESPECIALISTA TÉCNICO';
        typeEl.className = node.is_manager 
            ? 'px-1.5 py-0.2 rounded text-[10px] font-mono font-bold badge-gestor' 
            : 'px-1.5 py-0.2 rounded text-[10px] font-mono font-bold badge-tecnico';
        titleEl.innerText = node.label;
        descEl.innerText = `${node.role} • ${node.hours}h estudadas`;
        extraEl.innerHTML = `
            <span>${node.videos_count} aulas assistidas</span>
            <button onclick="openAgentSpecModal('${node.id}')" class="text-indigo-400 hover:underline">Ver Spec &rarr;</button>
        `;
    } else if (node.type === 'course') {
        avatarEl.innerText = '📁';
        typeEl.innerText = 'CURSO / ASSUNTO';
        typeEl.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-purple-500/20 text-purple-300';
        titleEl.innerText = node.label;
        descEl.innerText = `${node.lessons_count} aula(s) indexadas`;
        extraEl.innerHTML = `<span>Base de Conhecimento</span><span class="text-purple-300">Concluído</span>`;
    } else if (node.type === 'lesson') {
        avatarEl.innerText = '🟢';
        typeEl.innerText = 'AULA ESTUDADA';
        typeEl.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300';
        titleEl.innerText = node.label;
        const mins = Math.round((node.duration_seconds || 0) / 60);
        descEl.innerText = `Absorvida e compreendida pelo especialista (${mins > 0 ? mins + ' min' : 'Concluída'})`;
        extraEl.innerHTML = `<span>Status: Estudo Concluído</span><span class="text-emerald-400">✓ Aprendida</span>`;
    } else if (node.type === 'topic') {
        avatarEl.innerText = '🔷';
        typeEl.innerText = 'HABILIDADE';
        typeEl.className = 'px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-sky-500/20 text-sky-300';
        titleEl.innerText = `#${node.label}`;
        descEl.innerText = `Competência prática dominada pelo agente`;
        extraEl.innerHTML = `<span>Skill Ativa</span><span class="text-sky-300">Disponível no Oráculo</span>`;
    }
}

function backToOrbitalView() {

    const orbitalView = document.getElementById('orbital-cockpit-view');
    const detailPanel = document.getElementById('area-detail-panel');
    if (detailPanel) detailPanel.classList.add('hidden');
    if (orbitalView) orbitalView.classList.remove('hidden');
    initOrbitalRadar();
}

// ----------------- CRUD DE ÁREAS DA VIDA (MODAL) -----------------

function updateAreaManagerSelect() {
    const select = document.getElementById('area-form-manager');
    if (!select) return;
    const currentVal = select.value;
    select.innerHTML = `<option value="">-- Sem Gestor Atribuído --</option>` +
        agentsList.map(a => `<option value="${a.id}">${a.avatar || '👨‍💻'} ${a.name} (${a.role})</option>`).join('');
    if (currentVal) select.value = currentVal;
}

function openNewAreaModal() {
    const modal = document.getElementById('area-crud-modal');
    if (!modal) return;
    document.getElementById('area-crud-modal-title').innerText = 'Nova Área da Vida';
    document.getElementById('area-form-mode').value = 'create';
    document.getElementById('area-form-id').value = '';
    document.getElementById('area-form-name').value = '';
    document.getElementById('area-form-icon').value = '🎯';
    document.getElementById('area-form-color').value = '#06b6d4';
    document.getElementById('area-form-color-label').innerText = '#06b6d4';
    document.getElementById('area-form-desc').value = '';
    document.getElementById('area-form-health').value = '90';
    updateAreaManagerSelect();
    modal.classList.remove('hidden');
}

function openEditCurrentAreaModal() {
    if (currentSelectedAreaId) {
        openEditAreaModal(currentSelectedAreaId);
    }
}

function openEditAreaModal(areaId) {
    const area = areasList.find(a => a.id === areaId);
    if (!area) return;
    const modal = document.getElementById('area-crud-modal');
    if (!modal) return;

    document.getElementById('area-crud-modal-title').innerText = 'Editar Área da Vida';
    document.getElementById('area-form-mode').value = 'edit';
    document.getElementById('area-form-id').value = area.id;
    document.getElementById('area-form-name').value = area.name;
    document.getElementById('area-form-icon').value = area.icon || '🎯';
    document.getElementById('area-form-color').value = area.color || '#06b6d4';
    document.getElementById('area-form-color-label').innerText = area.color || '#06b6d4';
    document.getElementById('area-form-desc').value = area.description || '';
    document.getElementById('area-form-health').value = area.health_score || 90;
    updateAreaManagerSelect();
    document.getElementById('area-form-manager').value = area.manager_agent_id || '';

    modal.classList.remove('hidden');
}

function closeAreaCrudModal() {
    const modal = document.getElementById('area-crud-modal');
    if (modal) modal.classList.add('hidden');
}

async function submitAreaForm() {
    const mode = document.getElementById('area-form-mode').value;
    const id = document.getElementById('area-form-id').value;
    const name = document.getElementById('area-form-name').value.trim();
    if (!name) {
        alert('Por favor digite o nome da área.');
        return;
    }

    const icon = document.getElementById('area-form-icon').value.trim() || '🎯';
    const color = document.getElementById('area-form-color').value || '#06b6d4';
    const description = document.getElementById('area-form-desc').value.trim();
    const manager_agent_id = document.getElementById('area-form-manager').value || null;
    const health_score = parseInt(document.getElementById('area-form-health').value) || 90;

    let targetId = id;
    if (mode === 'create') {
        const cleanSlug = name.toLowerCase()
            .normalize("NFD")
            .replace(/[̀-ͯ]/g, "")
            .replace(/[^a-z0-9]/g, '_');
        targetId = `area_${cleanSlug}_${Date.now().toString().slice(-4)}`;
    }

    const payload = {
        id: targetId,
        name,
        icon,
        color,
        description,
        manager_agent_id,
        health_score
    };

    try {
        const url = mode === 'create' ? '/api/areas' : `/api/areas/${targetId}`;
        const method = mode === 'create' ? 'POST' : 'PUT';
        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Erro ao salvar área: ${err.detail || res.statusText}`);
            return;
        }

        closeAreaCrudModal();
        await loadAgents();
        await loadAreas();

        if (currentSelectedAreaId === targetId) {
            await drillDownArea(targetId);
        }
    } catch (e) {
        console.error('Erro ao submeter área:', e);
        alert(`Erro de conexão: ${e.message}`);
    }
}

async function deleteCurrentArea() {
    if (!currentSelectedAreaId) return;
    if (!confirm('Tem certeza que deseja excluir esta área? Os agentes permanecerão ativos, apenas desvinculados.')) return;

    try {
        const res = await fetch(`/api/areas/${currentSelectedAreaId}`, { method: 'DELETE' });
        if (!res.ok) {
            alert('Erro ao excluir área');
            return;
        }
        await loadAgents();
        await loadAreas();
        backToOrbitalView();
    } catch (e) {
        console.error('Erro ao excluir área:', e);
    }
}

function openNewAgentForCurrentAreaModal() {
    openNewAgentModal();
}

// ----------------- MODAL DE ESPECIFICAÇÃO DO AGENTE (agent.md & skill.md) -----------------

async function openAgentSpecModal(agentId) {
    try {
        const res = await fetch(`/api/agents/${agentId}/spec`);
        if (!res.ok) return;
        currentSpecData = await res.json();
        currentSpecTab = 'agent';

        const agent = currentSpecData.agent || {};
        const area = currentSpecData.area || {};

        document.getElementById('spec-modal-avatar').innerText = agent.avatar || '👨‍💻';
        document.getElementById('spec-modal-name').innerText = agent.name || 'Agente';

        const isGestor = agent.agent_type === 'gestor';
        const badgeEl = document.getElementById('spec-modal-role-badge');
        if (badgeEl) {
            badgeEl.innerText = isGestor ? 'GESTOR EXECUTIVO' : 'ESPECIALISTA TÉCNICO';
            badgeEl.className = isGestor 
                ? 'px-2 py-0.5 rounded-full text-[10px] font-bold badge-gestor'
                : 'px-2 py-0.5 rounded-full text-[10px] font-bold badge-tecnico';
        }

        document.getElementById('spec-modal-subtitle').innerText = `${agent.role} • ${area.name || 'Sem Área'}`;

        renderCurrentSpecContent();

        const modal = document.getElementById('agent-spec-modal');
        if (modal) modal.classList.remove('hidden');
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        console.error('Erro ao carregar especificação do agente:', e);
    }
}

function closeAgentSpecModal() {
    const modal = document.getElementById('agent-spec-modal');
    if (modal) modal.classList.add('hidden');
}

function switchSpecTab(tab) {
    currentSpecTab = tab;
    const btnAgent = document.getElementById('spec-tab-btn-agent');
    const btnSkills = document.getElementById('spec-tab-btn-skills');

    if (tab === 'agent') {
        if (btnAgent) btnAgent.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition-all';
        if (btnSkills) btnSkills.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white transition-all';
    } else {
        if (btnAgent) btnAgent.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white transition-all';
        if (btnSkills) btnSkills.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition-all';
    }
    renderCurrentSpecContent();
}

function renderCurrentSpecContent() {
    const pre = document.getElementById('spec-content-pre');
    if (!pre || !currentSpecData) return;

    if (currentSpecTab === 'agent') {
        pre.innerText = currentSpecData.agent_md || 'Nenhum agent.md disponível';
    } else {
        const skills = currentSpecData.skills || [];
        if (skills.length === 0) {
            pre.innerText = '# Nenhuma skill.md gerada ainda para este agente.';
        } else {
            pre.innerText = skills.map((s, idx) => `<!-- ================= SKILL ${idx + 1}: ${s.name.toUpperCase()} ================= -->\n\n${s.skill_md}`).join('\n\n\n');
        }
    }
}

function copyCurrentSpecContent() {
    const pre = document.getElementById('spec-content-pre');
    if (!pre) return;
    navigator.clipboard.writeText(pre.innerText).then(() => {
        const label = document.getElementById('copy-spec-btn-label');
        if (label) {
            label.innerText = 'Copiado!';
            setTimeout(() => { label.innerText = 'Copiar Conteúdo'; }, 2000);
        }
    });
}

function startOracleMeetingWithAgent(agentId) {
    switchTab('oracle');
    setTimeout(() => {
        const modeSelect = document.getElementById('chat-mode-select');
        if (modeSelect) {
            modeSelect.value = agentId;
        }
        const promptInput = document.getElementById('chat-prompt-input');
        if (promptInput) {
            promptInput.value = 'Olá, vamos alinhar os projetos e prioridades estratégicas da nossa área.';
            promptInput.focus();
        }
    }, 100);
}

// ----------------- MODAL: CONTRATAR NOVO AGENTE -----------------

function openNewAgentModal(preselectedAreaId = null) {
    const modal = document.getElementById('new-agent-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    // Popula o select de área com as áreas disponíveis
    const areaSelect = document.getElementById('agent-area-select');
    if (areaSelect) {
        areaSelect.innerHTML = `<option value="">-- Sem Área Definida --</option>` +
            areasList.map(ar => `<option value="${ar.id}">${ar.icon || '🎯'} ${ar.name}</option>`).join('');
        if (preselectedAreaId) {
            areaSelect.value = preselectedAreaId;
        } else if (currentSelectedAreaId) {
            areaSelect.value = currentSelectedAreaId;
        }
    }

    if (window.lucide) lucide.createIcons();
    setTimeout(() => {
        document.getElementById('agent-name-input')?.focus();
    }, 100);
}

function closeNewAgentModal() {
    const modal = document.getElementById('new-agent-modal');
    if (modal) {
        modal.classList.remove('flex');
        modal.classList.add('hidden');
    }
    const form = document.getElementById('new-agent-form');
    if (form) form.reset();
}

async function submitNewAgent(e) {
    if (e && e.preventDefault) e.preventDefault();
    const btn = document.getElementById('btn-confirm-hire');
    const nameInput = document.getElementById('agent-name-input');
    const roleInput = document.getElementById('agent-role-input');

    const name = nameInput ? nameInput.value.trim() : '';
    const role = roleInput ? roleInput.value.trim() : '';
    if (!name) {
        alert('Por favor digite o nome do agente.');
        if (nameInput) nameInput.focus();
        return;
    }
    if (!role) {
        alert('Por favor digite o cargo/especialidade do agente.');
        if (roleInput) roleInput.focus();
        return;
    }

    const customAvatar = document.getElementById('agent-avatar-custom')?.value.trim();
    const selectAvatar = document.getElementById('agent-avatar-select')?.value;
    const avatar = customAvatar || selectAvatar || '👨‍💻';
    const topicsRaw = document.getElementById('agent-topics-input')?.value.trim() || '';
    const initial_topics = topicsRaw ? topicsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];
    const area_id = document.getElementById('agent-area-select')?.value || null;
    const agent_type = document.getElementById('agent-type-select')?.value || 'tecnico';

    // Normaliza acentuação e gera slug limpo
    const cleanSlug = name.toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]/g, '_');
    const id = `agent_${cleanSlug}_${Date.now().toString().slice(-4)}`;

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="animate-spin inline-block mr-1">⏳</span> Contratando...';
    }

    try {
        const res = await fetch('/api/agents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, name, role, avatar, area_id, agent_type, initial_topics })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro ao processar requisição' }));
            alert(`Erro ao contratar: ${err.detail || res.statusText}`);
            return;
        }
        closeNewAgentModal();
        await loadAgents();
        await loadAreas();

        if (currentSelectedAreaId && area_id === currentSelectedAreaId) {
            await drillDownArea(currentSelectedAreaId);
        }

        alert(`🎉 Agente ${name} contratado com sucesso!`);
    } catch (err) {
        alert(`Erro ao contratar agente: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = 'Confirmar Contratação';
        }
    }
}

// ----------------- FICHA DETALHADA DO AGENTE -----------------

async function openAgentDetailModal(agentId) {
    try {
        const res = await fetch(`/api/agents/${agentId}`);
        if (!res.ok) return;
        const agent = await res.json();
        currentActiveAgentDetail = agent;

        document.getElementById('detail-agent-avatar').innerText = agent.avatar || '👨‍💻';
        document.getElementById('detail-agent-name').innerText = agent.name;
        document.getElementById('detail-agent-role').innerText = agent.role;
        document.getElementById('detail-agent-hours').innerText = `${agent.total_hours_studied}h`;
        document.getElementById('detail-hours-input').value = agent.total_hours_studied;

        const sen = agent.seniority || {};
        const badgeElem = document.getElementById('detail-agent-rank-badge');
        badgeElem.innerText = `${sen.badge || ''} ${sen.rank || 'Estagiário'}`;

        let rankBadgeClass = 'badge-estagiario';
        if (sen.rank === 'Júnior') rankBadgeClass = 'badge-junior';
        if (sen.rank === 'Pleno') rankBadgeClass = 'badge-pleno';
        if (sen.rank === 'Sênior') rankBadgeClass = 'badge-senior';
        if (sen.rank === 'Arquiteto Mestre') rankBadgeClass = 'badge-mestre';
        badgeElem.className = `text-xs px-2.5 py-0.5 rounded-md font-semibold ${rankBadgeClass}`;

        // Renderiza Cursos & Aulas
        renderAgentCoursesList(agent.sources || []);

        // Renderiza Chips de Tópicos
        renderAgentTopicsChips(agent.topics_mastered || []);

        const modal = document.getElementById('agent-detail-modal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        console.error('Erro ao abrir detalhe do agente:', e);
    }
}

function closeAgentDetailModal() {
    const modal = document.getElementById('agent-detail-modal');
    if (modal) {
        modal.classList.remove('flex');
        modal.classList.add('hidden');
    }
    currentActiveAgentDetail = null;
}

function renderAgentCoursesList(sources) {
    const container = document.getElementById('detail-agent-courses-list');
    if (!sources || !sources.length) {
        container.innerHTML = `
            <div class="p-6 bg-[#16161a] rounded-2xl border border-[#27272a] text-center space-y-2">
                <div class="text-2xl">📚</div>
                <p class="text-xs font-medium text-gray-300">Nenhum curso estudado ainda por este especialista.</p>
                <p class="text-[11px] text-gray-500">Acesse a aba <strong>Sala de Estudos</strong>, selecione os canais do Telegram e mande este especialista estudar para ganhar horas e senioridade!</p>
            </div>`;
        return;
    }

    container.innerHTML = sources.map(s => {
        const lessons = s.lessons || [];
        const lastStudied = s.last_studied_at ? new Date(s.last_studied_at).toLocaleDateString('pt-BR') : '';
        return `
        <div class="p-4 bg-[#18181b] rounded-2xl border border-[#2e2e34] space-y-3 shadow-sm hover:border-purple-500/40 transition-all">
            <div class="flex items-start justify-between gap-3">
                <div class="flex items-center space-x-3">
                    <div class="w-9 h-9 rounded-xl bg-purple-900/30 text-purple-300 flex items-center justify-center text-base border border-purple-500/30 flex-shrink-0">
                        🎓
                    </div>
                    <div>
                        <h5 class="font-bold text-white text-xs">${s.group_name}</h5>
                        <p class="text-[10px] text-gray-400 font-mono mt-0.5">
                            ${s.hours_studied}h dominadas • ${s.videos_count} ${s.videos_count === 1 ? 'aula' : 'aulas'} absorvidas ${lastStudied ? '• ' + lastStudied : ''}
                        </p>
                    </div>
                </div>
                <span class="obsidian-tag obsidian-tag-green flex-shrink-0">#concluído</span>
            </div>

            ${lessons.length ? `
            <div class="space-y-1.5 pt-2 border-t border-[#27272a]">
                <span class="text-[10px] font-mono text-gray-400 uppercase tracking-wider">Aulas Absorvidas no Acervo:</span>
                ${lessons.map(l => {
                    const durMin = l.duration_seconds ? Math.round(l.duration_seconds / 60) : Math.round(l.duration_hours * 60);
                    const topicsList = l.topics && l.topics.length ? l.topics : [];
                    return `
                    <div class="p-2.5 rounded-xl bg-[#121214] border border-[#242428] space-y-1.5 text-xs">
                        <div class="flex items-center justify-between">
                            <span class="font-medium text-gray-200 truncate pr-2 flex items-center space-x-1.5">
                                <span class="text-emerald-400">✓</span>
                                <span title="${l.title}">${l.title}</span>
                            </span>
                            <span class="text-[10px] font-mono text-purple-300 flex-shrink-0 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-500/20">
                                ⏱️ ${durMin > 0 ? durMin + ' min' : l.duration_hours + 'h'}
                            </span>
                        </div>
                        ${topicsList.length ? `
                        <div class="flex flex-wrap gap-1 pt-1">
                            ${topicsList.map(t => `<span class="px-1.5 py-0.5 rounded bg-[#202024] text-[9px] text-gray-400 border border-[#2d2d32] font-mono">#${t}</span>`).join('')}
                        </div>` : ''}
                    </div>
                    `;
                }).join('')}
            </div>` : ''}
        </div>
        `;
    }).join('');
}

function renderAgentTopicsChips(topics) {
    const container = document.getElementById('detail-agent-topics-chips');
    if (!topics.length) {
        container.innerHTML = `<span class="text-xs text-gray-500 py-1">Nenhum tópico cadastrado. Adicione suas habilidades e padrões abaixo.</span>`;
        return;
    }

    container.innerHTML = topics.map((t, idx) => `
        <span class="inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-gray-800 text-xs font-medium text-gray-200 border border-gray-700">
            <span>${t}</span>
            <button onclick="removeAgentTopic(${idx})" class="text-gray-400 hover:text-rose-400 transition-all">&times;</button>
        </span>
    `).join('');
}

async function addAgentTopic() {
    if (!currentActiveAgentDetail) return;
    const input = document.getElementById('detail-new-topic-input');
    const newTopic = input.value.trim();
    if (!newTopic) return;

    const topics = currentActiveAgentDetail.topics_mastered || [];
    if (!topics.includes(newTopic)) {
        topics.push(newTopic);
    }
    input.value = '';

    await saveAgentTopicsToServer(topics);
}

async function removeAgentTopic(idx) {
    if (!currentActiveAgentDetail) return;
    const topics = currentActiveAgentDetail.topics_mastered || [];
    topics.splice(idx, 1);
    await saveAgentTopicsToServer(topics);
}

async function saveAgentTopicsToServer(topics) {
    try {
        const res = await fetch(`/api/agents/${currentActiveAgentDetail.id}/topics`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topics })
        });
        if (res.ok) {
            currentActiveAgentDetail.topics_mastered = topics;
            renderAgentTopicsChips(topics);
            loadAgents();
        }
    } catch (e) {
        alert('Erro ao salvar tópicos: ' + e.message);
    }
}

async function saveAgentHours() {
    if (!currentActiveAgentDetail) return;
    const hours = parseFloat(document.getElementById('detail-hours-input').value);
    if (isNaN(hours) || hours < 0) return;

    try {
        const res = await fetch(`/api/agents/${currentActiveAgentDetail.id}/hours`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hours })
        });
        if (res.ok) {
            document.getElementById('detail-agent-hours').innerText = `${hours}h`;
            await loadAgents();
            openAgentDetailModal(currentActiveAgentDetail.id);
        }
    } catch (e) {
        alert('Erro ao atualizar horas: ' + e.message);
    }
}

// ----------------- TAB 2: TREINAMENTO POR CANAIS INTEIROS (TELEGRAM) -----------------

function toggleMultiAgentMode() {
    isMultiAgentBatchMode = !isMultiAgentBatchMode;
    renderBatchAgentChips();
    updateBatchCounters();
}

function updateYamlTierDisplay() {
    const tier = document.querySelector('input[name="batch-tier"]:checked')?.value || 'audio_only';
    const el = document.getElementById('yaml-target-tier');
    if (el) {
        if (tier === 'audio_only') {
            el.innerText = 'audio_only (90% economia)';
            el.className = 'text-emerald-400 font-semibold';
        } else {
            el.innerText = 'multimodal_ocr (visão computacional)';
            el.className = 'text-purple-400 font-semibold';
        }
    }
}

function renderBatchAgentChips() {
    const container = document.getElementById('batch-agents-chips-container');
    if (!container) return;

    if (!agentsList || agentsList.length === 0) {
        container.innerHTML = `<span class="text-xs text-gray-500 py-1 px-2 font-mono">#nenhum-agente-cadastrado</span>`;
        return;
    }

    // Se nenhum agente estiver selecionado, seleciona o primeiro por padrão
    if (selectedBatchAgentIds.size === 0 && agentsList.length > 0) {
        if (currentChannelAgentFilter !== 'all') {
            selectedBatchAgentIds.add(currentChannelAgentFilter);
        } else {
            selectedBatchAgentIds.add(agentsList[0].id);
        }
    }

    // 1. Chip Visão Geral (Todos)
    const isAllSelected = (currentChannelAgentFilter === 'all');
    let html = `
        <button type="button" onclick="selectBatchAgent('all')"
            class="px-2.5 py-1 rounded-lg text-xs font-mono border flex items-center space-x-1.5 transition-all cursor-pointer ${
                isAllSelected 
                    ? 'bg-purple-600 text-white font-semibold border-purple-400 shadow-md shadow-purple-600/20' 
                    : 'bg-[#18181c] text-gray-400 hover:text-white hover:bg-[#222228] border-[#2c2c32]'
            }">
            <span>🌐</span>
            <span>#todos</span>
            ${isAllSelected ? `<span class="text-[10px] ml-1">✓</span>` : ''}
        </button>
    `;

    // 2. Chips individuais de cada especialista estilo Obsidian
    html += agentsList.map(a => {
        const isAgentFilterActive = (currentChannelAgentFilter === a.id);
        const isBatchSelected = selectedBatchAgentIds.has(a.id);
        const isSelected = isMultiAgentBatchMode ? isBatchSelected : isAgentFilterActive;

        const activeClass = isSelected
            ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold border-purple-400 shadow-md shadow-purple-600/25 ring-1 ring-purple-400/50'
            : 'bg-[#18181c] text-gray-400 hover:text-white hover:bg-[#222228] border-[#2c2c32]';

        const slug = a.name.toLowerCase().replace(/\s+/g, '-');
        return `
            <button type="button" onclick="selectBatchAgent('${a.id}')"
                class="px-2.5 py-1 rounded-lg text-xs font-mono border flex items-center space-x-1.5 transition-all cursor-pointer ${activeClass}">
                <span>${a.avatar || '👨‍💻'}</span>
                <span>#${slug}</span>
                ${isSelected 
                    ? `<span class="text-[10px] ml-1">✓</span>` 
                    : `<span class="w-1.5 h-1.5 rounded-full bg-[#383842]"></span>`
                }
            </button>
        `;
    }).join('');

    container.innerHTML = html;
    updateBatchAgentModeBadge();
}

function setChannelViewMode(mode) {
    currentChannelViewMode = mode;
    const btnAll = document.getElementById('btn-view-all-courses');
    const btnStudied = document.getElementById('btn-view-studied-courses');
    if (btnAll && btnStudied) {
        if (mode === 'all') {
            btnAll.className = 'px-2.5 py-1 rounded-lg text-white bg-purple-600 font-medium transition-all cursor-pointer';
            btnStudied.className = 'px-2.5 py-1 rounded-lg text-gray-400 hover:text-white transition-all cursor-pointer';
        } else {
            btnStudied.className = 'px-2.5 py-1 rounded-lg text-white bg-purple-600 font-medium transition-all cursor-pointer';
            btnAll.className = 'px-2.5 py-1 rounded-lg text-gray-400 hover:text-white transition-all cursor-pointer';
        }
    }
    renderChannelsGrid();
}

function selectBatchAgent(agentId) {
    if (agentId === 'all') {
        currentChannelAgentFilter = 'all';
    } else {
        if (isMultiAgentBatchMode) {
            // Em modo multi-agente, alterna no conjunto
            if (selectedBatchAgentIds.has(agentId)) {
                if (selectedBatchAgentIds.size > 1) {
                    selectedBatchAgentIds.delete(agentId);
                }
            } else {
                selectedBatchAgentIds.add(agentId);
            }
            if (selectedBatchAgentIds.size === 1) {
                currentChannelAgentFilter = Array.from(selectedBatchAgentIds)[0];
            } else {
                currentChannelAgentFilter = 'all';
            }
        } else {
            // Modo foco único (8x load balancer): foco direto neste especialista!
            selectedBatchAgentIds.clear();
            selectedBatchAgentIds.add(agentId);
            currentChannelAgentFilter = agentId;
        }
    }

    const select = document.getElementById('channels-agent-filter');
    if (select) select.value = currentChannelAgentFilter;
    updateChannelFilterBadge();

    // Atualiza o bloco YAML de Frontmatter
    const yamlAgentEl = document.getElementById('yaml-target-agent');
    if (yamlAgentEl) {
        if (isMultiAgentBatchMode) {
            yamlAgentEl.innerText = `[[Multi-Agente (${selectedBatchAgentIds.size} Especialistas)]]`;
        } else if (currentChannelAgentFilter === 'all') {
            yamlAgentEl.innerText = '[[Todos os Especialistas]]';
        } else {
            const ag = agentsList.find(a => a.id === currentChannelAgentFilter);
            yamlAgentEl.innerText = ag ? `[[${ag.name}]]` : '[[Especialista]]';
        }
    }
    updateYamlTierDisplay();

    renderBatchAgentChips();
    updateBatchCounters();
    renderChannelsGrid();
}

// Alias para compatibilidade
const toggleBatchAgent = selectBatchAgent;

function updateBatchAgentModeBadge() {
    const badge = document.getElementById('batch-agent-mode-badge');
    const toggleBtn = document.getElementById('btn-toggle-multi-agent');
    if (!badge) return;

    if (!isMultiAgentBatchMode && selectedBatchAgentIds.size === 1) {
        const singleId = Array.from(selectedBatchAgentIds)[0];
        const agent = agentsList.find(a => a.id === singleId);
        const name = agent ? agent.name : '1 Especialista';
        badge.innerHTML = `⚡ Load Balancer 8x Ativo (${name})`;
        badge.className = 'obsidian-tag obsidian-tag-amber flex items-center space-x-1';
        badge.title = 'Todas as 8 filas paralelas e chaves de API focarão neste especialista para velocidade máxima';
        if (toggleBtn) toggleBtn.innerText = '👥 Mudar p/ Grupo';
        badge.innerHTML = `👥 Multi-Agente (${selectedBatchAgentIds.size} Especialistas)`;
        badge.className = 'obsidian-tag obsidian-tag-purple flex items-center space-x-1';
        badge.title = 'As 8 filas de processamento serão distribuídas entre os especialistas selecionados';
        if (toggleBtn) toggleBtn.innerText = '⚡ Mudar p/ 1 Especialista';
    }
}

function updateChannelAgentFilterSelect() {
    const select = document.getElementById('channels-agent-filter');
    if (!select) return;
    const currentVal = currentChannelAgentFilter;
    let html = `<option value="all">🌐 Todos os Especialistas (Visão Geral)</option>`;
    agentsList.forEach(a => {
        html += `<option value="${a.id}">${a.avatar || '👨‍💻'} Apenas cursos de ${a.name}</option>`;
    });
    select.innerHTML = html;
    if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
        select.value = currentVal;
    } else {
        select.value = 'all';
    }
}

function updateChannelFilterBadge() {
    const badge = document.getElementById('channels-filter-badge');
    if (badge) {
        if (currentChannelAgentFilter === 'all') {
            badge.innerText = '🌐 Visão Geral';
            badge.className = 'px-2 py-0.5 rounded-full bg-indigo-500/20 text-[11px] text-indigo-300 font-medium';
        } else {
            const agent = agentsList.find(a => a.id === currentChannelAgentFilter);
            badge.innerText = agent ? `👤 Progresso de ${agent.name}` : 'Especialista';
            badge.className = 'px-2 py-0.5 rounded-full bg-purple-500/20 text-[11px] text-purple-300 font-medium';
        }
    }
}

function onChannelAgentFilterChange() {
    const select = document.getElementById('channels-agent-filter');
    const val = select ? select.value : 'all';
    selectBatchAgent(val);
}

async function loadTelegramGroupsSummary() {
    const container = document.getElementById('channels-batch-grid');
    const modalList = document.getElementById('modal-channels-list');
    
    if (container) {
        renderBatchAgentChips();
        updateChannelAgentFilterSelect();
        container.innerHTML = `
            <div class="col-span-full py-12 text-center text-gray-400 flex items-center justify-center space-x-2">
                <i data-lucide="loader-2" class="w-5 h-5 animate-spin text-indigo-400"></i>
                <span class="text-xs">Mapeando canais e aulas na pasta 'Estudos'...</span>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
    }

    if (modalList && (!groupsSummaryList || !groupsSummaryList.length)) {
        modalList.innerHTML = `
            <div class="py-6 text-center text-gray-400 text-xs flex items-center justify-center space-x-2">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-purple-400"></i>
                <span>Conectando ao Telegram e listando canais de estudo...</span>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch('/api/telegram/groups/summary');
        if (!res.ok) throw new Error('Falha ao obter canais do Telegram');
        groupsSummaryList = await res.json();
        
        if (container) {
            renderChannelsGrid();
            updateBatchCounters();
        }
        if (typeof renderModalChannelsList === 'function') {
            renderModalChannelsList();
        }
    } catch (e) {
        console.error('Erro ao buscar canais do Telegram:', e);
        if (container) {
            container.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400 text-xs">Erro ao buscar canais: ${e.message}</div>`;
        }
        if (modalList) {
            modalList.innerHTML = `<div class="p-3 text-center text-rose-400 text-xs">Erro ao buscar canais do Telegram: ${e.message}</div>`;
        }
    }
}

function renderChannelsGrid() {
    const container = document.getElementById('channels-batch-grid');
    if (!container) return;

    if (!groupsSummaryList.length) {
        container.innerHTML = `<div class="p-8 text-center text-gray-500 text-xs font-mono">Cofre vazio: nenhum canal encontrado na pasta 'Estudos' do Telegram.</div>`;
        return;
    }

    // Filtragem por especialista selecionado vs visão geral (todos)
    let filterAgent = null;
    if (currentChannelAgentFilter !== 'all') {
        filterAgent = agentsList.find(a => a.id === currentChannelAgentFilter);
    }

    // Atualiza o painel visual de conhecimento do agente no lado direito do Dual-Pane
    renderAgentKnowledgeVault(filterAgent);

    let displayList = [...groupsSummaryList];

    // Se um especialista estiver selecionado, ordena colocando no topo os cursos que ele JÁ dominou ([x] #dominado)
    if (filterAgent) {
        displayList.sort((a, b) => {
            const aBrk = (a.agents_studied && a.agents_studied[filterAgent.id]) || 
                         (a.agents_studied && Object.values(a.agents_studied).find(it => it.agent_name === filterAgent.name)) || { studied_count: 0 };
            const bBrk = (b.agents_studied && b.agents_studied[filterAgent.id]) || 
                         (b.agents_studied && Object.values(b.agents_studied).find(it => it.agent_name === filterAgent.name)) || { studied_count: 0 };
            return (bBrk.studied_count || 0) - (aBrk.studied_count || 0);
        });
    }

    if (filterAgent && currentChannelViewMode === 'studied_only') {
        displayList = displayList.filter(g => {
            const brk = (g.agents_studied && g.agents_studied[filterAgent.id]) || 
                        (g.agents_studied && Object.values(g.agents_studied).find(it => it.agent_name === filterAgent.name));
            return brk && brk.studied_count > 0;
        });
    } else if (!filterAgent && currentChannelViewMode === 'studied_only') {
        displayList = displayList.filter(g => (g.studied_videos > 0) || (g.studied_agents_list && g.studied_agents_list.length > 0));
    }

    if (!displayList.length && currentChannelViewMode === 'studied_only') {
        const titleText = filterAgent ? `[[${filterAgent.name}]] ainda não absorveu nenhum canal` : 'Nenhum curso concluído no Vault ainda';
        const descText = filterAgent 
            ? `Alterne para <strong>"Todos"</strong> para ver todo o acervo do cofre e aloque este especialista para estudar.`
            : `Alterne para <strong>"Todos"</strong> para ver todas as pastas de cursos disponíveis no cofre.`;

        container.innerHTML = `
            <div class="p-6 rounded-xl bg-[#141417] border border-[#27272a] text-center space-y-2.5 font-mono">
                <div class="text-2xl">${filterAgent ? (filterAgent.avatar || '👨‍💻') : '📂'}</div>
                <h4 class="text-xs font-bold text-white">${titleText}</h4>
                <p class="text-[11px] text-gray-400">${descText}</p>
                <button onclick="setChannelViewMode('all')" 
                    class="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-all shadow-sm cursor-pointer">
                    Ver Todos os Cursos (${groupsSummaryList.length})
                </button>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    container.innerHTML = displayList.map(g => {
        const isSelected = selectedGroupIds.has(g.id);
        const total = g.total_videos || 0;
        const studied = g.studied_videos || 0;
        const pending = g.pending_videos || 0;
        const safeTitle = (g.title || 'Canal').replace(/'/g, "\\'");

        // 1. MODO ESPECIALISTA SELECIONADO: Mostra PORCENTAGENS ESPECÍFICAS deste agente e marcação [x] ou [ ]
        if (filterAgent) {
            const brk = (g.agents_studied && g.agents_studied[filterAgent.id]) || 
                        (g.agents_studied && Object.values(g.agents_studied).find(it => it.agent_name === filterAgent.name)) ||
                        { studied_count: 0, percent: 0 };
            const agentCount = brk.studied_count || 0;
            const agentPct = total > 0 ? Math.round((agentCount / total) * 100) : 0;
            const agentPending = Math.max(0, total - agentCount);
            const hoursEst = g.duration_hours > 0 && total > 0 ? ((g.duration_hours * agentCount) / total).toFixed(1) : '0';
            const isFullyMastered = (agentPct === 100 && total > 0);
            const isPartiallyMastered = (agentCount > 0 && !isFullyMastered);

            return `
            <div onclick="toggleChannelSelection(event, ${g.id})" 
                class="obsidian-note-card ${isSelected ? 'selected' : ''} p-3 rounded-xl flex flex-col justify-between space-y-2.5 cursor-pointer relative group">
                
                <!-- Top Header: Checkbox + Título da Nota + Tag de Status [x] ou [ ] -->
                <div class="flex items-start justify-between gap-2">
                    <div class="flex items-center space-x-2.5 min-w-0">
                        <div class="w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 transition-all ${
                            isSelected ? 'bg-purple-600 border-purple-400 text-white' : 'border-[#383842] bg-[#141416] text-transparent'
                        }">
                            <i data-lucide="check" class="w-3.5 h-3.5 ${isSelected ? 'block' : 'opacity-0'}"></i>
                        </div>
                        <div class="min-w-0">
                            <h4 class="text-xs font-semibold text-white truncate font-mono group-hover:text-purple-300 transition-colors" title="${g.title}">
                                📄 ${g.title}
                            </h4>
                            <div class="text-[10px] text-gray-500 font-mono mt-0.5">
                                <span>${g.duration_hours > 0 ? `⏱️ ~${g.duration_hours}h` : ''}</span>
                                <span>${g.size_gb > 0 ? ` • 💾 ${g.size_gb} GB` : ''}</span>
                                <span> • ${total} aulas</span>
                            </div>
                        </div>
                    </div>

                    <!-- Badge de Domínio do Especialista: [x] #dominado ou [ ] #pendente -->
                    <div>
                        ${isFullyMastered 
                            ? `<span class="obsidian-tag obsidian-tag-green flex items-center space-x-1 flex-shrink-0">
                                 <span>[x]</span><span>#dominado</span>
                               </span>`
                            : (isPartiallyMastered 
                                ? `<span class="obsidian-tag obsidian-tag-purple flex items-center space-x-1 flex-shrink-0">
                                     <span>⚡</span><span>${agentPct}%</span>
                                   </span>`
                                : `<span class="obsidian-tag obsidian-tag-amber flex items-center space-x-1 flex-shrink-0">
                                     <span>[ ]</span><span>#pendente</span>
                                   </span>`
                              )
                        }
                    </div>
                </div>

                <!-- Barra de Progresso Fina de ${filterAgent.name} -->
                <div class="space-y-1 pt-1 border-t border-[#242428]">
                    <div class="flex items-center justify-between text-[10px] font-mono">
                        <span class="text-gray-400">Progresso de ${filterAgent.name}:</span>
                        <span class="font-bold ${isFullyMastered ? 'text-emerald-400' : (isPartiallyMastered ? 'text-purple-300' : 'text-gray-500')}">
                            ${agentCount > 0 ? `${agentPct}% (${agentCount}/${total} aulas dominadas)` : `0 aulas estudadas`}
                        </span>
                    </div>
                    <div class="w-full bg-[#121214] rounded-full h-1 overflow-hidden border border-[#222226]">
                        <div class="${isFullyMastered ? 'bg-emerald-500' : (isPartiallyMastered ? 'bg-purple-500' : 'bg-transparent')} h-1 rounded-full transition-all duration-300" style="width: ${agentPct}%"></div>
                    </div>
                </div>

                <!-- Bottom Actions & Metadados do Vault -->
                <div class="flex items-center justify-between pt-1 border-t border-[#222226] text-[10px] font-mono">
                    <span class="text-gray-400">
                        ${agentCount > 0 ? `~${hoursEst}h absorvidas` : `${agentPending} aulas pendentes`}
                    </span>

                    <button onclick="openChannelInspectModal(event, ${g.id}, '${safeTitle}')" 
                        class="px-2 py-0.5 rounded-md bg-[#222226] hover:bg-[#2b2b32] text-[10px] font-mono text-gray-300 hover:text-white border border-[#2f2f36] flex items-center space-x-1 transition-all cursor-pointer" title="Inspecionar aulas deste canal">
                        <i data-lucide="eye" class="w-3 h-3"></i>
                        <span>Aulas</span>
                    </button>
                </div>
            </div>
            `;
        }

        // 2. MODO DEFAULT (VISÃO GERAL): Mostra cobertura geral de todos os especialistas
        const pct = total > 0 ? Math.round((studied / total) * 100) : 0;
        const isMasteredGeneral = (studied === total && total > 0);

        let studiedAgentsBadges = '';
        if (g.studied_agents_list && g.studied_agents_list.length > 0) {
            studiedAgentsBadges = g.studied_agents_list.map(name => 
                `<span class="px-1.5 py-0.2 rounded bg-purple-950/40 text-purple-300 text-[9px] font-mono border border-purple-500/20">👤 ${name}</span>`
            ).join(' ');
        }

        return `
        <div onclick="toggleChannelSelection(event, ${g.id})" 
            class="obsidian-note-card ${isSelected ? 'selected' : ''} p-3 rounded-xl flex flex-col justify-between space-y-2.5 cursor-pointer relative group">
            
            <!-- Top Header & Checkbox -->
            <div class="flex items-start justify-between gap-2">
                <div class="flex items-center space-x-2.5 min-w-0">
                    <div class="w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 transition-all ${
                        isSelected ? 'bg-purple-600 border-purple-400 text-white' : 'border-[#383842] bg-[#141416] text-transparent'
                    }">
                        <i data-lucide="check" class="w-3.5 h-3.5 ${isSelected ? 'block' : 'opacity-0'}"></i>
                    </div>
                    <div class="min-w-0">
                        <h4 class="text-xs font-semibold text-white truncate font-mono group-hover:text-purple-300 transition-colors" title="${g.title}">
                            📂 ${g.title}
                        </h4>
                        <div class="text-[10px] text-gray-500 font-mono mt-0.5">
                            <span>${g.duration_hours > 0 ? `⏱️ ~${g.duration_hours}h` : ''}</span>
                            <span>${g.size_gb > 0 ? ` • 💾 ${g.size_gb} GB` : ''}</span>
                            <span> • ${total} aulas</span>
                        </div>
                    </div>
                </div>

                <div>
                    ${isMasteredGeneral 
                        ? `<span class="obsidian-tag obsidian-tag-green flex items-center space-x-1 flex-shrink-0">
                             <span>[x]</span><span>#dominado</span>
                           </span>`
                        : (studied > 0 
                            ? `<span class="obsidian-tag obsidian-tag-purple flex items-center space-x-1 flex-shrink-0">
                                 <span>#parcial</span>
                               </span>`
                            : `<span class="obsidian-tag obsidian-tag-amber flex items-center space-x-1 flex-shrink-0">
                                 <span>[ ]</span><span>#pendente</span>
                               </span>`
                          )
                    }
                </div>
            </div>

            <!-- Barra de Progresso Geral -->
            <div class="space-y-1 pt-1 border-t border-[#242428]">
                <div class="flex items-center justify-between text-[10px] font-mono">
                    <span class="text-gray-400">Progresso Geral:</span>
                    <span class="font-bold ${isMasteredGeneral ? 'text-emerald-400' : 'text-purple-300'}">${pct}% (${studied}/${total} aulas)</span>
                </div>
                <div class="w-full bg-[#121214] rounded-full h-1 overflow-hidden border border-[#222226]">
                    <div class="bg-gradient-to-r from-purple-500 to-emerald-500 h-1 rounded-full transition-all duration-300" style="width: ${pct}%"></div>
                </div>
            </div>

            <!-- Especialistas que já estudaram -->
            ${studiedAgentsBadges ? `
            <div class="flex flex-wrap items-center gap-1 pt-0.5">
                <span class="text-[9px] text-gray-500 font-mono">Absorvido por:</span>
                ${studiedAgentsBadges}
            </div>` : ''}

            <!-- Bottom Actions -->
            <div class="flex items-center justify-between pt-1 border-t border-[#222226] text-[10px] font-mono">
                <span class="text-amber-400">${pending > 0 ? `${pending} aulas pendentes` : '✓ 100% Estudado'}</span>

                <button onclick="openChannelInspectModal(event, ${g.id}, '${safeTitle}')" 
                    class="px-2 py-0.5 rounded-md bg-[#222226] hover:bg-[#2b2b32] text-[10px] font-mono text-gray-300 hover:text-white border border-[#2f2f36] flex items-center space-x-1 transition-all cursor-pointer" title="Inspecionar aulas deste canal">
                    <i data-lucide="eye" class="w-3 h-3"></i>
                    <span>Aulas</span>
                </button>
            </div>
        </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

function renderAgentKnowledgeVault(filterAgent) {
    const container = document.getElementById('obsidian-agent-knowledge-vault');
    if (!container) return;

    if (!filterAgent) {
        // Visão Geral: Panorama do Cofre e Todos os Agentes
        const totalLessonsStudied = agentsList.reduce((acc, a) => acc + (a.total_videos_studied || 0), 0);
        const totalHoursStudied = agentsList.reduce((acc, a) => acc + (a.total_hours_studied || 0), 0).toFixed(1);
        const allMasteredTopics = Array.from(new Set(agentsList.flatMap(a => a.topics_mastered || [])));

        container.innerHTML = `
            <div class="space-y-2.5">
                <div class="flex items-center justify-between pb-1 border-b border-[#242428]">
                    <div class="flex items-center space-x-2 text-xs font-mono text-gray-300 font-semibold">
                        <span>🌐</span>
                        <span>Acervo Global do Cofre</span>
                    </div>
                    <span class="obsidian-tag obsidian-tag-purple font-mono">${agentsList.length} agentes • ${totalLessonsStudied} aulas • ${totalHoursStudied}h</span>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    ${agentsList.map(a => {
                        const cCount = a.sources ? a.sources.length : 0;
                        return `
                        <div onclick="selectBatchAgent('${a.id}')" class="p-2.5 rounded-xl bg-[#141417] border border-[#27272a] hover:border-purple-500/50 cursor-pointer space-y-1.5 transition-all">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-bold text-white flex items-center space-x-1.5 font-mono">
                                    <span>${a.avatar || '👨‍💻'}</span>
                                    <span>[[${a.name}]]</span>
                                </span>
                                <span class="obsidian-tag ${cCount > 0 ? 'obsidian-tag-green' : 'obsidian-tag-amber'} font-mono">${cCount > 0 ? `[x] ${cCount} cursos` : '[ ] #novo'}</span>
                            </div>
                            <div class="flex items-center justify-between text-[10px] font-mono text-gray-400">
                                <span>${a.total_videos_studied || 0} aulas</span>
                                <span>${a.total_hours_studied || 0}h dominadas</span>
                            </div>
                        </div>
                        `;
                    }).join('')}
                </div>

                ${allMasteredTopics.length ? `
                <div class="space-y-1 pt-1">
                    <span class="text-[10px] font-mono uppercase tracking-wider text-gray-500">Conceitos Mapeados no Cofre:</span>
                    <div class="flex flex-wrap gap-1">
                        ${allMasteredTopics.slice(0, 10).map(t => `<span class="px-1.5 py-0.5 rounded bg-[#18181c] text-[10px] font-mono text-gray-400 border border-[#27272a]">#${t}</span>`).join('')}
                        ${allMasteredTopics.length > 10 ? `<span class="text-[10px] font-mono text-purple-400 self-center">+${allMasteredTopics.length - 10} tópicos</span>` : ''}
                    </div>
                </div>` : ''}
            </div>
        `;
        return;
    }

    // Modo Especialista Específico (ex: Bruno, Jim Kwik, Jordan)
    const sources = filterAgent.sources || [];
    const topics = filterAgent.topics_mastered || [];

    container.innerHTML = `
        <div class="space-y-2.5">
            <div class="flex items-center justify-between pb-1 border-b border-[#242428]">
                <div class="flex items-center space-x-2 text-xs font-mono text-gray-300 font-semibold">
                    <span>${filterAgent.avatar || '👨‍💻'}</span>
                    <span>Conhecimento Dominado por [[${filterAgent.name}]]</span>
                </div>
                <span class="obsidian-tag ${sources.length > 0 ? 'obsidian-tag-green' : 'obsidian-tag-amber'} font-mono">
                    ${sources.length > 0 ? `[x] ${sources.length} cursos dominados` : '[ ] Nenhum curso iniciado'}
                </span>
            </div>

            ${sources.length > 0 ? `
            <div class="space-y-2 max-h-52 overflow-y-auto pr-1">
                ${sources.map(s => {
                    const lCount = s.lessons ? s.lessons.length : (s.videos_count || 0);
                    const lHours = s.hours_studied || 0;
                    return `
                    <div class="p-2.5 rounded-xl bg-[#141417] border border-purple-500/30 space-y-1.5">
                        <div class="flex items-start justify-between gap-2">
                            <div class="min-w-0">
                                <h5 class="text-xs font-bold text-white truncate font-mono">🎓 ${s.group_name}</h5>
                                <p class="text-[10px] font-mono text-purple-300/80 mt-0.5">
                                    ⏱️ ${lHours}h absorvidas • ${lCount} ${lCount === 1 ? 'aula' : 'aulas'}
                                </p>
                            </div>
                            <span class="obsidian-tag obsidian-tag-green flex items-center space-x-1 flex-shrink-0">
                                <span>[x]</span><span>#dominado</span>
                            </span>
                        </div>

                        ${s.lessons && s.lessons.length ? `
                        <div class="space-y-1 pt-1 border-t border-[#222226]">
                            ${s.lessons.map(l => `
                                <div class="flex items-center justify-between text-[10px] font-mono text-gray-300 py-0.5 px-1.5 rounded bg-[#0e0e11]">
                                    <span class="truncate pr-2 text-emerald-400">✓ ${l.title}</span>
                                    <span class="text-purple-400 flex-shrink-0">${l.duration_hours}h</span>
                                </div>
                            `).join('')}
                        </div>` : ''}
                    </div>
                    `;
                }).join('')}
            </div>` : `
            <div class="p-3.5 rounded-xl bg-[#121214] border border-[#27272a] text-xs space-y-1 font-mono">
                <p class="text-gray-300 font-semibold flex items-center space-x-1.5">
                    <span>⚠️</span>
                    <span>[[${filterAgent.name}]] ainda não possui campos estudados no Vault.</span>
                </p>
                <p class="text-[11px] text-gray-400">
                    Marque os canais ao lado com <span class="text-amber-400 font-bold">[ ] #pendente</span> e inicie o estudo abaixo com <strong>Load Balancer 8x</strong> para carregar o especialista!
                </p>
            </div>
            `}

            ${topics.length ? `
            <div class="space-y-1 pt-1 border-t border-[#242428]">
                <span class="text-[10px] font-mono uppercase tracking-wider text-gray-400">Tópicos & Padrões que [[${filterAgent.name}]] Domina:</span>
                <div class="flex flex-wrap gap-1">
                    ${topics.map(t => `<span class="px-2 py-0.5 rounded bg-[#16161a] text-[10px] font-mono text-purple-300 border border-purple-500/20">#${t}</span>`).join('')}
                </div>
            </div>` : ''}
        </div>
    `;

    if (window.lucide) lucide.createIcons();
}

// ----------------- EXPORTAR AGENTE COMO SKILL DO ANTIGRAVITY -----------------

async function exportCurrentAgentSkill() {
    if (!currentActiveAgentDetail) return;
    await exportAgentSkillById(currentActiveAgentDetail.id, currentActiveAgentDetail.name);
}

async function exportAgentSkillById(agentId, agentName) {
    const btn = document.getElementById('btn-detail-export-skill');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="animate-spin mr-1">⏳</span> Exportando...';
    }

    try {
        const res = await fetch(`/api/agents/${agentId}/export-skill`, {
            method: 'POST'
        });
        const data = await res.json();
        if (!res.ok) {
            alert(`Erro ao exportar skill: ${data.detail || 'Falha na exportação'}`);
            return;
        }

        alert(`🚀 Skill Exportada com Sucesso!\n\nA Skill "${data.skill_name}" foi instalada no Antigravity em:\n${data.skill_path}\n\nO Antigravity já carregará as diretrizes, padrões e códigos deste especialista durante suas sessões de programação!`);
    } catch (e) {
        alert(`Erro ao exportar skill: ${e.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="sparkles" class="w-3.5 h-3.5 mr-1"></i><span>Exportar Skill Antigravity</span>';
            if (window.lucide) lucide.createIcons();
        }
    }
}

function toggleChannelSelection(e, groupId) {
    if (selectedGroupIds.has(groupId)) {
        selectedGroupIds.delete(groupId);
    } else {
        selectedGroupIds.add(groupId);
    }
    updateBatchCounters();
    renderChannelsGrid();
}

function toggleSelectAllChannels() {
    const btn = document.getElementById('btn-select-all');
    if (selectedGroupIds.size === groupsSummaryList.length) {
        selectedGroupIds.clear();
        if (btn) btn.innerText = 'Selecionar Todos';
    } else {
        groupsSummaryList.forEach(g => selectedGroupIds.add(g.id));
        if (btn) btn.innerText = 'Desmarcar Todos';
    }
    updateBatchCounters();
    renderChannelsGrid();
}

function updateBatchCounters() {
    const countEl = document.getElementById('batch-selection-count');
    const pendEl = document.getElementById('batch-pending-count');
    const btnStart = document.getElementById('btn-start-batch');
    const btnSelectAll = document.getElementById('btn-select-all');

    const selectedCount = selectedGroupIds.size;
    const totalPending = groupsSummaryList
        .filter(g => selectedGroupIds.has(g.id))
        .reduce((acc, g) => acc + (g.pending_videos || 0), 0);

    if (countEl) countEl.innerText = `${selectedCount} ${selectedCount === 1 ? 'canal selecionado' : 'canais selecionados'}`;
    if (pendEl) pendEl.innerText = `${totalPending} ${totalPending === 1 ? 'aula pendente' : 'aulas pendentes no total'}`;
    
    if (btnStart) {
        if (selectedBatchAgentIds.size === 1) {
            const singleId = Array.from(selectedBatchAgentIds)[0];
            const agent = agentsList.find(a => a.id === singleId);
            const agentName = agent ? agent.name : 'Especialista';
            btnStart.innerHTML = `<i data-lucide="zap" class="w-4 h-4"></i><span>Estudar com Load Balancer 8x (${totalPending} aulas • ${agentName})</span>`;
        } else {
            btnStart.innerHTML = `<i data-lucide="users" class="w-4 h-4"></i><span>Estudar em Grupo (${selectedBatchAgentIds.size} Especialistas • ${totalPending} aulas)</span>`;
        }
    }

    if (btnSelectAll && groupsSummaryList.length > 0) {
        btnSelectAll.innerText = selectedCount === groupsSummaryList.length ? 'Desmarcar Todos' : 'Selecionar Todos';
    }
    if (window.lucide) lucide.createIcons();
}

async function startBatchStudy() {
    if (!selectedGroupIds.size) {
        alert('Por favor selecione ao menos um canal para iniciar o estudo.');
        return;
    }

    const agentIdsArray = Array.from(selectedBatchAgentIds);
    if (!agentIdsArray.length) {
        alert('Por favor selecione ao menos um especialista.');
        return;
    }

    const tier = document.querySelector('input[name="batch-tier"]:checked')?.value || 'audio_only';
    const groupIdsArray = Array.from(selectedGroupIds);

    const btn = document.getElementById('btn-start-batch');
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Enfileirando canais...</span>`;
    if (window.lucide) lucide.createIcons();

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(new Error('A requisição de escaneamento do canal excedeu o limite de 3 minutos. O canal pode ter muitas mensagens.')), 180000);

        const res = await fetch('/api/study/groups/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_ids: agentIdsArray,
                agent_id: agentIdsArray[0],
                group_ids: groupIdsArray,
                tier: tier,
                only_pending: true
            }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Falha ao enfileirar canais');

        alert(data.message || 'Canais enfileirados com sucesso!');

        // Limpa a seleção de canais para liberar a interface para o próximo especialista imediatamente!
        selectedGroupIds.clear();
        updateBatchCounters();
        renderChannelsGrid();

        await loadStudyQueue();
        startStudyPolling();
    } catch (e) {
        if (e.name === 'AbortError' || e.message?.includes('aborted')) {
            alert('A operação demorou mais do que o esperado para escanear todas as mensagens do Telegram (tempo limite de 3 min). Verifique se as aulas já estão sendo enfileiradas no monitor.');
        } else {
            alert(`Erro ao iniciar estudo em lote: ${e.message}`);
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
        if (window.lucide) lucide.createIcons();
    }
}

// ----------------- MODAL DE INSPEÇÃO RÁPIDA DE AULAS DO CANAL -----------------

async function openChannelInspectModal(e, groupId, groupTitle) {
    if (e) e.stopPropagation();

    document.getElementById('inspect-modal-title').innerText = groupTitle;
    document.getElementById('inspect-modal-subtitle').innerText = 'Carregando lista de aulas...';
    
    const list = document.getElementById('inspect-modal-videos-list');
    list.innerHTML = `<div class="text-center py-8 text-gray-400"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400"></i>Listando aulas...</div>`;
    document.getElementById('channel-inspect-modal').classList.remove('hidden');
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch(`/api/telegram/groups/${groupId}/videos`);
        const videos = await res.json();

        document.getElementById('inspect-modal-subtitle').innerText = `${videos.length} aulas encontradas neste curso`;

        if (!videos.length) {
            list.innerHTML = `<div class="text-center py-8 text-gray-500 text-xs">Nenhum vídeo encontrado neste canal.</div>`;
            return;
        }

        list.innerHTML = videos.map(v => {
            const isPdf = v.media_type === 'pdf' || (v.file_name && v.file_name.toLowerCase().endsWith('.pdf'));
            const durMin = Math.round(v.duration_seconds / 60);
            const sizeMb = (v.file_size_bytes / (1024 * 1024)).toFixed(1);
            const icon = v.is_studied ? '✅' : (isPdf ? '📄' : '📹');
            return `
            <div class="p-3 rounded-xl bg-gray-950/80 border ${v.is_studied ? 'border-emerald-500/20' : 'border-gray-800'} flex items-center justify-between text-xs">
                <div class="flex items-center space-x-3 min-w-0 pr-2">
                    <span class="text-base">${icon}</span>
                    <div class="min-w-0">
                        <div class="flex items-center space-x-2">
                            <p class="font-medium text-white truncate" title="${v.file_name}">${v.file_name}</p>
                            ${isPdf ? '<span class="px-1.5 py-0.2 rounded bg-purple-500/15 text-purple-300 text-[9px] border border-purple-500/30 font-mono shrink-0">PDF OCR</span>' : ''}
                        </div>
                        <div class="flex items-center space-x-2 text-[10px] text-gray-400 mt-0.5">
                            ${durMin > 0 ? `<span>⏱️ ${durMin} min</span> • ` : ''}
                            <span>💾 ${sizeMb} MB</span>
                        </div>
                    </div>
                </div>
                <div class="shrink-0 ml-2">
                    ${v.is_studied 
                        ? `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold border border-emerald-500/30">Estudada</span>`
                        : `<span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 text-[10px] font-semibold border border-amber-500/30">Pendente</span>`
                    }
                </div>
            </div>
            `;
        }).join('');
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        list.innerHTML = `<div class="text-center py-8 text-rose-400 text-xs">Erro: ${err.message}</div>`;
    }
}

function closeChannelInspectModal() {
    const modal = document.getElementById('channel-inspect-modal');
    if (modal) modal.classList.add('hidden');
}

// ----------------- GERENCIAMENTO DA FILA DE ESTUDOS -----------------

async function loadStudyQueue() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 6000);
        const res = await fetch('/api/study/queue', { signal: controller.signal });
        clearTimeout(timeoutId);
        if (!res.ok) return;
        const state = await res.json();

        // 1. Badge count & ETA Display
        const badge = document.getElementById('queue-badge-count');
        if (badge) badge.innerText = `${state.queue_count} na fila`;

        const etaText = state.estimated_time_text || '0m';
        const etaHeaderVal = document.getElementById('study-eta-value');
        if (etaHeaderVal) etaHeaderVal.innerText = etaText;
        const drawerEta = document.getElementById('drawer-eta-time');
        if (drawerEta) drawerEta.innerText = etaText;

        // Salva estado global da fila para renderização reativa da gaveta
        window._lastStudyQueueState = state;

        // Atualiza contadores numéricos nas abas da gaveta da fila
        const drawerQueue = document.getElementById('drawer-queue-count');
        if (drawerQueue) drawerQueue.innerText = state.queue_count || 0;
        const drawerComp = document.getElementById('drawer-completed-count');
        if (drawerComp) drawerComp.innerText = state.completed_count || 0;
        const drawerErr = document.getElementById('drawer-errors-count');
        if (drawerErr) drawerErr.innerText = state.error_count || 0;
        const drawerStatus = document.getElementById('drawer-workers-status');
        if (drawerStatus) drawerStatus.innerText = state.is_busy ? `${state.active_count} workers ativos` : 'Ocioso';

        // Atualiza botão de Pausar / Retomar Fila no cabeçalho
        const pauseBtn = document.getElementById('btn-header-pause-queue');
        const pauseText = document.getElementById('text-header-pause');
        const pauseIcon = document.getElementById('icon-header-pause');
        if (pauseBtn && pauseText) {
            if (state.safety_paused) {
                pauseText.innerText = 'Retomar Fila (Pausada)';
                pauseBtn.className = 'text-xs text-emerald-300 hover:text-white px-3.5 py-2.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 flex items-center space-x-1.5 transition-all cursor-pointer shadow-sm animate-pulse';
                if (pauseIcon) pauseIcon.setAttribute('data-lucide', 'play-circle');
            } else {
                pauseText.innerText = 'Pausar Fila';
                pauseBtn.className = 'text-xs text-amber-400 hover:text-white px-3.5 py-2.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 flex items-center space-x-1.5 transition-all cursor-pointer shadow-sm';
                if (pauseIcon) pauseIcon.setAttribute('data-lucide', 'pause-circle');
            }
        }

        // Botão de Retomar Estudos Interrompidos
        const headerResumeBtn = document.getElementById('btn-header-resume');
        if (headerResumeBtn) {
            if (state.can_resume) {
                headerResumeBtn.classList.remove('hidden');
            } else {
                headerResumeBtn.classList.add('hidden');
            }
        }

        // Se o estado de execução mudou (iniciou ou terminou), atualiza a lista de agentes reativamente
        if (window._lastStudyBusyState !== state.is_busy) {
            window._lastStudyBusyState = state.is_busy;
            loadAgents();
            if (typeof loadKnowledgeGraph === 'function') loadKnowledgeGraph();
        }

        // 2. Active Box & Drawer Workers Grid (Multi-Worker Paralelo)
        const activeBox = document.getElementById('queue-active-box');
        const banner = document.getElementById('study-banner');
        const drawerGrid = document.getElementById('drawer-workers-grid');

        const activeList = (state.active_items && state.active_items.length > 0)
            ? state.active_items
            : (state.active_item ? [state.active_item] : []);

        // Renderiza no drawer moderno da Sala de Estudos
        if (drawerGrid) {
            if (activeList.length > 0) {
                drawerGrid.innerHTML = activeList.map((act, i) => `
                    <div class="p-2.5 rounded-xl bg-[#171b26] border border-[#272b38] flex flex-col justify-between space-y-1.5 shadow-sm text-xs">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-1.5 truncate">
                                <span class="text-xs">👤</span>
                                <span class="font-bold text-white text-[11px] truncate">${act.agent_name || 'Especialista'}</span>
                            </div>
                            <span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[9px] font-mono">#${i + 1}</span>
                        </div>
                        <p class="text-[10px] text-gray-300 font-mono truncate" title="${act.file_name}">${act.file_name}</p>
                        <div class="space-y-1">
                            <div class="flex items-center justify-between text-[9px] font-mono text-gray-400">
                                <span class="truncate flex-1 pr-1 text-gray-300" title="${act.current_step_text || 'Processando...'}">${act.current_step_text || 'Processando...'}</span>
                                <span class="text-indigo-300 font-bold flex-shrink-0">${act.progress_pct}%</span>
                            </div>
                            <div class="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                                <div class="h-1.5 rounded-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-300" style="width: ${act.progress_pct}%"></div>
                            </div>
                        </div>
                    </div>
                `).join('');
            } else {
                drawerGrid.innerHTML = `<div class="col-span-1 sm:col-span-2 md:col-span-4 py-4 text-center text-xs font-mono text-gray-500">Nenhum worker ativo no momento. Inicie uma jornada de estudos pelo botão acima.</div>`;
            }
        }

        if (state.is_busy && activeList.length > 0) {
            const uniqueAgentIds = new Set(activeList.map(it => it.agent_id));
            const isSingleAgentParallel = uniqueAgentIds.size === 1 && activeList.length > 1;

            if (activeBox) {
                activeBox.classList.remove('hidden');
                activeBox.innerHTML = activeList.map((act, i) => `
                    <div class="p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
                        <div class="flex items-center space-x-3 min-w-0">
                            <div class="w-8 h-8 rounded-lg bg-indigo-600/30 text-indigo-400 flex items-center justify-center animate-spin flex-shrink-0">
                                <i data-lucide="loader-2" class="w-4 h-4"></i>
                            </div>
                            <div class="min-w-0">
                                <div class="text-xs font-bold text-white flex items-center space-x-2">
                                    <span class="truncate max-w-xs sm:max-w-md" title="${act.file_name || 'Aula'}">${act.file_name || 'Aula'}</span>
                                    <span class="px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 text-[10px] font-semibold flex-shrink-0">👤 ${act.agent_name || 'Especialista'}</span>
                                    ${activeList.length > 1 ? `<span class="px-1.5 py-0.5 rounded ${isSingleAgentParallel ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-purple-500/20 text-purple-300'} text-[9px] font-mono">Slot #${i + 1} ${isSingleAgentParallel ? '⚡ Load Balancer' : ''}</span>` : ''}
                                </div>
                                <p class="text-[11px] text-indigo-300/80 truncate">${act.current_step_text || 'Processando...'}</p>
                            </div>
                        </div>
                        <div class="w-48 flex items-center space-x-3 flex-shrink-0">
                            <div class="flex-1 bg-gray-800 rounded-full h-1.5 overflow-hidden">
                                <div class="h-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300" style="width: ${act.progress_pct}%"></div>
                            </div>
                            <span class="text-xs font-bold text-indigo-300">${act.progress_pct}%</span>
                        </div>
                    </div>
                `).join('');
                if (window.lucide) lucide.createIcons();
            }
            if (banner) {
                banner.classList.remove('hidden');
                if (activeList.length === 1) {
                    const act = activeList[0];
                    document.getElementById('study-banner-title').innerText = `${act.agent_name} estudando: ${act.file_name || 'Aula'}`;
                    document.getElementById('study-banner-status').innerText = act.current_step_text || 'Processando...';
                    document.getElementById('study-banner-pct').innerText = `${act.progress_pct}%`;
                    document.getElementById('study-banner-bar').style.width = `${act.progress_pct}%`;
                } else if (isSingleAgentParallel) {
                    const act = activeList[0];
                    const avgPct = Math.round(activeList.reduce((acc, it) => acc + (it.progress_pct || 0), 0) / activeList.length);
                    document.getElementById('study-banner-title').innerText = `⚡ Load Balancer Ativo: ${act.agent_name} estudando com ${activeList.length} workers em paralelo!`;
                    document.getElementById('study-banner-status').innerText = `${activeList.length} aulas sendo absorvidas simultaneamente com aceleração total via chaves de API independentes`;
                    document.getElementById('study-banner-pct').innerText = `${avgPct}%`;
                    document.getElementById('study-banner-bar').style.width = `${avgPct}%`;
                } else {
                    const avgPct = Math.round(activeList.reduce((acc, it) => acc + (it.progress_pct || 0), 0) / activeList.length);
                    const names = Array.from(new Set(activeList.map(a => a.agent_name))).join(', ');
                    document.getElementById('study-banner-title').innerText = `${activeList.length} Slots Ativos: Especialistas em Paralelo (${names})`;
                    document.getElementById('study-banner-status').innerText = `${activeList.length} aulas sendo absorvidas simultaneamente via chaves de API independentes`;
                    document.getElementById('study-banner-pct').innerText = `${avgPct}%`;
                    document.getElementById('study-banner-bar').style.width = `${avgPct}%`;
                }
            }
        } else {
            if (activeBox) {
                activeBox.classList.add('hidden');
                activeBox.innerHTML = '';
            }
            if (banner) banner.classList.add('hidden');
        }

        // 3. Renderiza a tabela da Gaveta de Estudos
        renderStudyQueueTable();

        // 4. Controles de Retomada de Estudos Interrompidos
        const resumeContainer = document.getElementById('resume-study-container');
        const resumeHeaderBtn = document.getElementById('btn-header-resume');
        const resumeLabel = document.getElementById('btn-resume-label');
        const headerResumeLabel = document.getElementById('header-resume-label');

        const hasInterrupted = state.can_resume || (state.error_count && state.error_count > 0);
        if (hasInterrupted && !state.is_busy) {
            if (resumeContainer) resumeContainer.classList.remove('hidden');
            if (resumeHeaderBtn) resumeHeaderBtn.classList.remove('hidden');
            const countStr = (state.interrupted_count || state.error_count) 
                ? ` (${state.interrupted_count || state.error_count} aulas)` 
                : '';
            if (resumeLabel) resumeLabel.innerText = `▶️ Retomar Estudos de Onde Parou${countStr}`;
            if (headerResumeLabel) headerResumeLabel.innerText = `Retomar Estudos${countStr}`;
        } else {
            if (resumeContainer) resumeContainer.classList.add('hidden');
            if (resumeHeaderBtn) resumeHeaderBtn.classList.add('hidden');
        }
    } catch (e) {
        console.error('Erro ao carregar fila:', e);
    }
}

async function resumeInterruptedStudy() {
    const btn = document.getElementById('btn-resume-study');
    const headerBtn = document.getElementById('btn-header-resume');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-amber-400"></i><span>Retomando conexão e estudos...</span>`;
    }
    if (headerBtn) {
        headerBtn.disabled = true;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/study/queue/resume', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            alert(`✅ ${data.message || 'Estudos retomados de onde pararam!'}`);
            await loadStudyQueue();
            await loadAgents();
        } else {
            alert(`❌ ${data.detail || 'Não foi possível retomar os estudos.'}`);
        }
    } catch (e) {
        alert(`Erro de conexão ao retomar: ${e.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="play-circle" class="w-4 h-4 text-amber-400"></i><span id="btn-resume-label">▶️ Retomar Estudos de Onde Parou</span>`;
        }
        if (headerBtn) headerBtn.disabled = false;
        if (window.lucide) lucide.createIcons();
    }
}

async function deleteQueueItem(itemId) {
    try {
        const res = await fetch(`/api/study/queue/${itemId}`, { method: 'DELETE' });
        if (res.ok) {
            await loadStudyQueue();
        }
    } catch (e) {
        console.error('Erro ao remover item:', e);
    }
}

async function clearFinishedQueue() {
    try {
        await fetch('/api/study/queue/clear', { method: 'POST' });
        await loadStudyQueue();
    } catch (e) {
        console.error('Erro ao limpar fila:', e);
    }
}

function startStudyPolling() {
    if (studyPollingInterval) clearInterval(studyPollingInterval);
    checkActiveStudyStatus();
    studyPollingInterval = setInterval(checkActiveStudyStatus, 2500);
}

async function checkActiveStudyStatus() {
    try {
        await loadStudyQueue();
        await loadTokenStats();

        // Atualiza agentes e canais se houver processamento
        const hasActiveOrQueued = document.getElementById('queue-active-box') && !document.getElementById('queue-active-box').classList.contains('hidden');
        if (hasActiveOrQueued && currentTab === 'study') {
            loadAgents();
        }
    } catch (e) {
        console.error('Erro no polling:', e);
    }
}

// ----------------- TAB 3: SALA DO ORÁCULO (MESA REDONDA & 1-ON-1) -----------------

function updateChatModeSelect() {
    const select = document.getElementById('chat-mode-select');
    if (!select) return;

    const currentVal = select.value;
    let html = `<option value="debate">🔮 Mesa Redonda (Oráculo convoca especialistas)</option>`;
    agentsList.forEach(a => {
        html += `<option value="${a.id}">${a.avatar || '👨‍💻'} Falar direto com ${a.name} (${a.role})</option>`;
    });
    select.innerHTML = html;
    if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
        select.value = currentVal;
    }
    onChatModeChange();
}

function onChatModeChange() {
    const mode = document.getElementById('chat-mode-select').value;
    const title = document.getElementById('chat-header-title');
    const subtitle = document.getElementById('chat-header-subtitle');
    const avatar = document.getElementById('chat-header-avatar');

    if (mode === 'debate') {
        avatar.innerText = '🔮';
        title.innerText = 'Mesa Redonda Multi-Agente';
        subtitle.innerText = 'Especialistas debatem e interagem entre si';
    } else {
        const agent = agentsList.find(a => a.id === mode);
        if (agent) {
            avatar.innerText = agent.avatar || '👨‍💻';
            title.innerText = `Conversa Direta com ${agent.name}`;
            subtitle.innerText = `${agent.role} • Consulta exclusiva às suas fontes`;
        }
    }
}

async function loadKnowledgeSources() {
    const list = document.getElementById('knowledge-sources-list');
    if (!list) return;

    try {
        const res = await fetch('/api/knowledge');
        const knowledge = await res.json();

        document.getElementById('sources-count').innerText = `${knowledge.length} aulas`;

        if (!knowledge.length) {
            list.innerHTML = `<div class="text-xs text-gray-500 py-6 text-center">Nenhuma aula estudada ainda. Mande os agentes estudarem na Sala de Estudos!</div>`;
            return;
        }

        list.innerHTML = knowledge.map(k => `
            <div class="p-3 bg-gray-950/60 rounded-xl border border-gray-800/80 space-y-1.5">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">${k.group_name}</span>
                    <span class="text-[10px] text-gray-500">${k.duration_minutes > 0 ? k.duration_minutes + ' min' : k.segments_count + ' trechos'}</span>
                </div>
                <h4 class="text-xs font-semibold text-white truncate" title="${k.title}">${k.title}</h4>
                <p class="text-[11px] text-gray-400 line-clamp-2">${k.summary}</p>
            </div>
        `).join('');
    } catch (e) {
        console.error('Erro ao buscar fontes:', e);
    }
}

async function sendChatMessage(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    if (!query) return;

    const messagesContainer = document.getElementById('chat-messages');
    const modeSelect = document.getElementById('chat-mode-select').value;
    const isDebate = modeSelect === 'debate';
    const targetAgentId = isDebate ? null : modeSelect;

    // 1. Mensagem do Usuário
    messagesContainer.innerHTML += `
        <div class="flex items-start justify-end space-x-3">
            <div class="bg-indigo-600 text-white rounded-2xl p-3.5 max-w-[85%] text-sm shadow-md">
                ${query}
            </div>
            <div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">Você</div>
        </div>
    `;

    input.value = '';
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // 2. Loading
    const loadingId = `loading-${Date.now()}`;
    const loadingText = isDebate 
        ? 'O Oráculo está convocando os especialistas para o debate...' 
        : 'Consultando o especialista...';

    messagesContainer.innerHTML += `
        <div id="${loadingId}" class="flex items-start space-x-3">
            <div class="w-8 h-8 rounded-full bg-indigo-600/30 flex items-center justify-center text-sm flex-shrink-0">🔮</div>
            <div class="bg-gray-800/80 rounded-2xl p-3.5 max-w-[85%] border border-gray-700/50 flex items-center space-x-2 text-xs text-gray-400">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-indigo-400"></i>
                <span>${loadingText}</span>
            </div>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
        const res = await fetch('/api/oracle/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                query: query,
                mode: isDebate ? 'debate' : 'single',
                agent_id: targetAgentId
            })
        });

        if (!res.ok) {
            let errorMsg = `Erro no servidor (${res.status})`;
            try {
                const errData = await res.json();
                if (errData && errData.detail) errorMsg = errData.detail;
            } catch (_) {
                const textErr = await res.text().catch(() => '');
                if (textErr) errorMsg = textErr;
            }
            throw new Error(errorMsg);
        }

        const data = await res.json();

        document.getElementById(loadingId)?.remove();

        if (data.mode === 'debate' && data.debate && data.debate.length) {
            // Renderiza o debate multi-agente
            let debateHtml = `
            <div class="space-y-3 max-w-[95%]">
                <div class="text-xs font-semibold text-purple-400 uppercase tracking-wider flex items-center space-x-1 mb-2">
                    <i data-lucide="messages-square" class="w-3.5 h-3.5"></i>
                    <span>Mesa Redonda Multi-Agente</span>
                </div>
            `;

            data.debate.forEach(turn => {
                const isOracle = turn.speaker === 'Oráculo';
                const cardBg = isOracle ? 'bg-purple-950/30 border-purple-500/30' : 'bg-gray-800/90 border-gray-700/60';
                debateHtml += `
                <div class="flex items-start space-x-3">
                    <div class="w-8 h-8 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center text-sm flex-shrink-0">
                        ${turn.avatar || '💬'}
                    </div>
                    <div class="rounded-2xl p-3.5 ${cardBg} border text-sm text-gray-200 flex-1 space-y-1">
                        <div class="flex items-center space-x-2 mb-1">
                            <span class="font-bold text-xs ${isOracle ? 'text-purple-300' : 'text-indigo-300'}">${turn.speaker}</span>
                            <span class="text-[10px] text-gray-400">${turn.role || ''}</span>
                        </div>
                        <div class="text-xs leading-relaxed text-gray-200 markdown-body">${renderMarkdown(turn.text)}</div>
                    </div>
                </div>
                `;
            });

            if (data.final_summary) {
                debateHtml += `
                <div class="p-3.5 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-200 space-y-1 mt-2">
                    <div class="font-bold text-indigo-300 flex items-center space-x-1.5">
                        <span>🔮</span>
                        <span>Conclusão do Oráculo:</span>
                    </div>
                    <div class="markdown-body mt-1 text-gray-200">${renderMarkdown(data.final_summary)}</div>
                </div>
                `;
            }

            debateHtml += `</div>`;
            messagesContainer.innerHTML += debateHtml;

        } else {
            // Renderiza resposta individual
            const speakerName = data.speaker || 'Oráculo';
            const speakerAvatar = data.avatar || '🔮';
            const speakerRole = data.role || '';

            messagesContainer.innerHTML += `
                <div class="flex items-start space-x-3">
                    <div class="w-8 h-8 rounded-full bg-indigo-600/30 flex items-center justify-center text-sm flex-shrink-0">
                        ${speakerAvatar}
                    </div>
                    <div class="bg-gray-800/80 rounded-2xl p-4 max-w-[85%] border border-gray-700/50 text-sm text-gray-100 space-y-3">
                        <div class="flex items-center space-x-2 border-b border-gray-700/50 pb-2">
                            <span class="font-bold text-xs text-indigo-300">${speakerName}</span>
                            <span class="text-[10px] text-gray-400">${speakerRole}</span>
                        </div>
                        <div class="text-xs leading-relaxed text-gray-200 markdown-body">${renderMarkdown(data.answer || '')}</div>
                        ${data.citations && data.citations.length ? `
                        <div class="pt-2 border-t border-gray-700/60 text-xs text-gray-400 space-y-1">
                            <span class="font-semibold text-indigo-400">Fontes Citadas:</span>
                            ${data.citations.map(c => `<div>📌 <strong>${c.title}</strong> (${c.timestamps.join(', ')})</div>`).join('')}
                        </div>` : ''}
                    </div>
                </div>
            `;
        }

        renderCodeSnippets(data.extracted_codes || []);
        if (window.lucide) lucide.createIcons();
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

    } catch (err) {
        document.getElementById(loadingId)?.remove();
        messagesContainer.innerHTML += `
            <div class="flex items-start space-x-3">
                <div class="w-8 h-8 rounded-full bg-rose-600/30 flex items-center justify-center text-sm">⚠️</div>
                <div class="bg-rose-950/40 rounded-2xl p-3.5 max-w-[85%] border border-rose-500/30 text-xs text-rose-300">
                    Erro na consulta: ${err.message}
                </div>
            </div>
        `;
    }
}

function renderCodeSnippets(codes) {
    const panel = document.getElementById('code-snippets-panel');
    if (!panel) return;

    if (!codes.length) {
        panel.innerHTML = `<div class="text-center py-12 text-gray-500 text-xs">Nenhum bloco de código específico nesta resposta.</div>`;
        return;
    }

    panel.innerHTML = codes.map((c, idx) => `
        <div class="bg-gray-950 rounded-xl border border-gray-800 overflow-hidden text-xs">
            <div class="bg-gray-900 px-3 py-1.5 flex items-center justify-between border-b border-gray-800">
                <span class="font-mono text-indigo-400">${c.language || 'code'} • [${c.timestamp || '00:00'}]</span>
                <button onclick="copyCode(this, ${idx})" class="text-gray-400 hover:text-white flex items-center space-x-1">
                    <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                    <span>Copiar</span>
                </button>
            </div>
            <pre class="p-3 text-gray-200 overflow-x-auto font-mono text-[11px] leading-relaxed"><code id="code-block-${idx}">${c.code}</code></pre>
            ${c.description ? `<div class="px-3 py-1.5 bg-gray-900/50 text-[11px] text-gray-400 border-t border-gray-800/60">${c.description}</div>` : ''}
        </div>
    `).join('');

    if (window.lucide) lucide.createIcons();
}

function copyCode(btn, idx) {
    const code = document.getElementById(`code-block-${idx}`)?.innerText;
    if (code) {
        navigator.clipboard.writeText(code);
        btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i><span class="text-emerald-400">Copiado!</span>`;
        if (window.lucide) lucide.createIcons();
        setTimeout(() => {
            btn.innerHTML = `<i data-lucide="copy" class="w-3.5 h-3.5"></i><span>Copiar</span>`;
            if (window.lucide) lucide.createIcons();
        }, 2000);
    }
}

// =========================================================================
// OBSIDIAN GRAPH VIEW: CANVAS FORCE-DIRECTED SIMULATION & KNOWLEDGE VAULT
// =========================================================================

let graphRawData = { nodes: [], links: [] };
let graphSimNodes = [];
let graphSimLinks = [];
let graphCanvas = null;
let graphCtx = null;
let graphAnimFrame = null;
let graphSimAlpha = 1.0;
let cachedKnowledgeGraphData = null;


let graphZoom = 1.0;
let graphPanX = 0;
let graphPanY = 0;
let isGraphPanning = false;
let panStartX = 0;
let panStartY = 0;

let graphDraggedNode = null;
let graphHoveredNode = null;
let graphSelectedNode = null;
let graphFilterType = 'all';
let graphSearchQuery = '';
let isDrawerMinimized = false;


// =========================================================================
// QUADRO DE FUNCIONÁRIOS (CRUD CORPORATIVO & EDITOR DE SKILL.MD)
// =========================================================================

function renderEmployeesTable() {
    const tbody = document.getElementById('crud-employees-table-body');
    if (!tbody) return;

    const query = (document.getElementById('crud-search-input')?.value || '').toLowerCase();
    const areaFilter = document.getElementById('crud-filter-area')?.value || 'all';
    const hierarchyFilter = document.getElementById('crud-filter-hierarchy')?.value || 'all';

    const filtered = agentsList.filter(a => {
        if (query) {
            const matchName = a.name.toLowerCase().includes(query);
            const matchRole = (a.role || '').toLowerCase().includes(query);
            const matchTopics = (a.topics_mastered || []).some(t => t.toLowerCase().includes(query));
            if (!matchName && !matchRole && !matchTopics) return false;
        }
        if (areaFilter !== 'all' && a.area_id !== areaFilter) return false;
        if (hierarchyFilter !== 'all' && a.agent_type !== hierarchyFilter) return false;
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-gray-500 font-mono text-xs">Nenhum funcionário encontrado com os filtros atuais.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(a => {
        const area = areasList.find(ar => ar.id === a.area_id);
        const areaColor = area?.color || '#6366f1';
        const areaName = area?.name || 'Sem Área';
        const areaIcon = area?.icon || '📁';
        const isGestor = a.agent_type === 'gestor';
        const sen = a.seniority || {};

        const statusBadge = a.status === 'estudando'
            ? `<span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center space-x-1 w-fit"><span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span><span>Estudando</span></span>`
            : `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1 w-fit"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span>Ativo</span></span>`;

        return `
            <tr class="hover:bg-gray-900/60 transition-colors group">
                <td class="py-3 px-4">
                    <div class="flex items-center space-x-3">
                        <div class="w-9 h-9 rounded-xl bg-gray-900 border border-gray-800 flex items-center justify-center text-lg flex-shrink-0 group-hover:border-indigo-500/50 transition-all">
                            ${a.avatar || '👨‍💻'}
                        </div>
                        <div>
                            <div class="font-bold text-white text-xs flex items-center space-x-1.5">
                                <span>${a.name}</span>
                            </div>
                            <div class="text-[10px] font-mono text-gray-500">${a.id}</div>
                        </div>
                    </div>
                </td>
                <td class="py-3 px-4 text-gray-300 font-medium">${a.role || 'Especialista'}</td>
                <td class="py-3 px-4">
                    <span class="px-2.5 py-1 rounded-lg text-[11px] font-medium inline-flex items-center space-x-1.5" style="background: ${areaColor}15; color: ${areaColor}; border: 1px solid ${areaColor}35;">
                        <span>${areaIcon}</span>
                        <span>${areaName}</span>
                    </span>
                </td>
                <td class="py-3 px-4">
                    ${isGestor
                        ? `<span class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 inline-flex items-center space-x-1"><span>👑</span><span>Gestor Executivo</span></span>`
                        : `<span class="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 inline-flex items-center space-x-1"><span>⚡</span><span>Especialista Técnico</span></span>`
                    }
                </td>
                <td class="py-3 px-4 font-mono">
                    <div class="text-white font-bold">${a.total_hours_studied || 0}h</div>
                    <div class="text-[10px] text-gray-400">${sen.rank || 'Estagiário'}</div>
                </td>
                <td class="py-3 px-4">
                    ${statusBadge}
                </td>
                <td class="py-3 px-4 text-right">
                    <div class="flex items-center justify-end space-x-1.5">
                        <button onclick="openEmployeeEditModal('${a.id}', 'cadastral')" title="Editar Cadastro" class="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border border-gray-700 transition-all">
                            <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
                        </button>
                        <button onclick="openEmployeeEditModal('${a.id}', 'skill')" title="Ver e Editar skill.md" class="px-2.5 py-1 rounded-lg bg-purple-500/15 hover:bg-purple-500/25 text-purple-300 border border-purple-500/30 text-[11px] font-mono transition-all flex items-center space-x-1">
                            <i data-lucide="zap" class="w-3 h-3 text-purple-400"></i>
                            <span>skill.md</span>
                        </button>
                        <button onclick="openEmployeeEditModal('${a.id}', 'agent')" title="Ver agent.md" class="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border border-gray-700 transition-all">
                            <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
                        </button>
                        <button onclick="confirmDeleteEmployee('${a.id}')" title="Demitir / Excluir" class="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 transition-all">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

function onCrudSearchInput(val) {
    renderEmployeesTable();
}

function onCrudFilterChange() {
    renderEmployeesTable();
}

let currentEmployeeEditingId = null;

async function openEmployeeEditModal(agentId, initialTab = 'cadastral') {
    currentEmployeeEditingId = agentId;
    const modal = document.getElementById('employee-edit-modal');
    if (!modal) return;

    try {
        const [resAgent, resSpec] = await Promise.all([
            fetch(`/api/agents/${agentId}`),
            fetch(`/api/agents/${agentId}/spec`)
        ]);

        if (!resAgent.ok) return;
        const agent = await resAgent.json();
        const spec = resSpec.ok ? await resSpec.json() : {};

        document.getElementById('emp-edit-agent-id').value = agent.id;
        document.getElementById('emp-edit-modal-name').innerText = agent.name;
        document.getElementById('emp-edit-id-label').innerText = `ID: ${agent.id}`;
        document.getElementById('emp-edit-avatar-badge').innerText = agent.avatar || '👨‍💻';
        
        const typeBadge = document.getElementById('emp-edit-type-badge');
        if (typeBadge) {
            typeBadge.innerText = agent.agent_type === 'gestor' ? 'GESTOR EXECUTIVO' : 'ESPECIALISTA TÉCNICO';
            typeBadge.className = agent.agent_type === 'gestor' 
                ? 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30'
                : 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
        }

        // Form Fields
        document.getElementById('emp-edit-name-input').value = agent.name || '';
        document.getElementById('emp-edit-role-input').value = agent.role || '';
        document.getElementById('emp-edit-avatar-input').value = agent.avatar || '👨‍💻';
        document.getElementById('emp-edit-area-select').value = agent.area_id || '';
        document.getElementById('emp-edit-type-select').value = agent.agent_type || 'tecnico';
        document.getElementById('emp-edit-status-select').value = agent.status || 'ativo';
        document.getElementById('emp-edit-hours-input').value = agent.total_hours_studied || 0;
        document.getElementById('emp-edit-topics-textarea').value = (agent.topics_mastered || []).join(', ');

        // Markdown Editors
        document.getElementById('emp-edit-skill-md-editor').value = spec.skill_md || '';
        document.getElementById('emp-edit-agent-md-editor').value = spec.agent_md || '';

        document.getElementById('emp-edit-feedback-msg').innerText = '';

        switchEmployeeEditTab(initialTab);
        modal.classList.remove('hidden');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Erro ao abrir edição de funcionário:', err);
    }
}

function switchEmployeeEditTab(tab) {
    const btnCad = document.getElementById('emp-tab-btn-cadastral');
    const btnSkill = document.getElementById('emp-tab-btn-skill');
    const btnAgent = document.getElementById('emp-tab-btn-agent');

    const paneCad = document.getElementById('emp-subtab-cadastral');
    const paneSkill = document.getElementById('emp-subtab-skill');
    const paneAgent = document.getElementById('emp-subtab-agent');

    const activeClass = 'px-3.5 py-1.5 rounded-lg font-semibold bg-indigo-600 text-white transition-all';
    const inactiveClass = 'px-3.5 py-1.5 rounded-lg font-semibold text-gray-400 hover:text-white transition-all';

    if (btnCad) btnCad.className = (tab === 'cadastral') ? activeClass : inactiveClass;
    if (btnSkill) btnSkill.className = (tab === 'skill') ? activeClass : inactiveClass;
    if (btnAgent) btnAgent.className = (tab === 'agent') ? activeClass : inactiveClass;

    if (paneCad) paneCad.classList.toggle('hidden', tab !== 'cadastral');
    if (paneSkill) paneSkill.classList.toggle('hidden', tab !== 'skill');
    if (paneAgent) paneAgent.classList.toggle('hidden', tab !== 'agent');
}

function closeEmployeeEditModal() {
    const modal = document.getElementById('employee-edit-modal');
    if (modal) modal.classList.add('hidden');
}

async function saveEmployeeFullForm() {
    if (!currentEmployeeEditingId) return;
    const feedback = document.getElementById('emp-edit-feedback-msg');
    const saveBtn = document.getElementById('btn-save-employee-modal');

    const name = document.getElementById('emp-edit-name-input').value.trim();
    const role = document.getElementById('emp-edit-role-input').value.trim();
    const avatar = document.getElementById('emp-edit-avatar-input').value.trim() || '👨‍💻';
    const area_id = document.getElementById('emp-edit-area-select').value;
    const agent_type = document.getElementById('emp-edit-type-select').value;
    const status = document.getElementById('emp-edit-status-select').value;
    const hours = parseFloat(document.getElementById('emp-edit-hours-input').value) || 0;
    const topicsRaw = document.getElementById('emp-edit-topics-textarea').value;
    const topics_mastered = topicsRaw.split(',').map(t => t.trim()).filter(Boolean);

    const skill_md = document.getElementById('emp-edit-skill-md-editor').value;
    const agent_md = document.getElementById('emp-edit-agent-md-editor').value;

    try {
        if (saveBtn) saveBtn.disabled = true;
        if (feedback) feedback.innerText = 'Salvando...';

        const res1 = await fetch(`/api/agents/${currentEmployeeEditingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name, role, avatar, area_id, agent_type, status,
                total_hours_studied: hours,
                topics_mastered
            })
        });

        const res2 = await fetch(`/api/agents/${currentEmployeeEditingId}/spec`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                skill_md,
                agent_md
            })
        });

        if (res1.ok && res2.ok) {
            if (feedback) feedback.innerText = '✓ Alterações salvas com sucesso!';
            await loadAgents();
            await loadAreas();
            renderEmployeesTable();
            setTimeout(() => {
                closeEmployeeEditModal();
            }, 700);
        } else {
            if (feedback) feedback.innerText = 'Erro ao salvar alterações.';
        }
    } catch (e) {
        console.error('Erro ao salvar funcionário:', e);
        if (feedback) feedback.innerText = 'Erro de comunicação com o servidor.';
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

async function confirmDeleteEmployee(agentId) {
    const agent = agentsList.find(a => a.id === agentId);
    const name = agent ? agent.name : agentId;
    if (!confirm(`Deseja realmente excluir o agente "${name}"?\nEsta ação removerá o perfil, suas skills operacionais e o desvinculará de áreas.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/agents/${agentId}`, { method: 'DELETE' });
        if (res.ok) {
            await loadAgents();
            await loadAreas();
            renderEmployeesTable();
            loadKnowledgeGraph();
        } else {
            const err = await res.json().catch(() => ({}));
            alert(`Erro ao excluir agente: ${err.detail || 'Falha no servidor'}`);
        }
    } catch (e) {
        console.error('Erro ao excluir agente:', e);
        alert('Erro ao excluir agente. Verifique sua conexão.');
    }
}

async function deleteCurrentAgentFromDetail() {
    if (!currentActiveAgentDetail) return;
    const agentId = typeof currentActiveAgentDetail === 'object' ? currentActiveAgentDetail.id : currentActiveAgentDetail;
    closeAgentDetailModal();
    await confirmDeleteEmployee(agentId);
}

async function deleteCurrentEmployeeFromModal() {
    if (!currentEmployeeEditingId) return;
    const agentId = currentEmployeeEditingId;
    closeEmployeeEditModal();
    await confirmDeleteEmployee(agentId);
}

function initObsidianGraph() {
    graphCanvas = document.getElementById('obsidian-graph-canvas');
    if (!graphCanvas) return;
    graphCtx = graphCanvas.getContext('2d');

    window.removeEventListener('resize', resizeGraphCanvas);
    window.addEventListener('resize', resizeGraphCanvas);
    resizeGraphCanvas();

    // Eventos de Interatividade
    graphCanvas.onmousedown = onGraphMouseDown;
    window.onmousemove = onGraphMouseMove;
    window.onmouseup = onGraphMouseUp;
    graphCanvas.onwheel = onGraphWheel;
    graphCanvas.onclick = onGraphClick;

    if (!graphAnimFrame) {
        graphAnimFrame = requestAnimationFrame(graphRenderStep);
    }
}

function resizeGraphCanvas() {
    if (!graphCanvas || !graphCtx) return;
    const parent = graphCanvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    graphCanvas.width = rect.width * dpr;
    graphCanvas.height = rect.height * dpr;
    graphCanvas.style.width = `${rect.width}px`;
    graphCanvas.style.height = `${rect.height}px`;
}

async function loadKnowledgeGraph() {
    initObsidianGraph();
    try {
        const res = await fetch('/api/knowledge/graph');
        if (!res.ok) return;
        graphRawData = await res.json();

        const badge = document.getElementById('vault-nodes-count-badge');
        if (badge) badge.innerText = `${graphRawData.nodes.length} nós`;

        const prevNodeMap = new Map(graphSimNodes.map(n => [n.id, n]));
        const agentCount = graphRawData.nodes.filter(n => n.type === 'agent').length || 1;
        let agentIdx = 0;

        graphSimNodes = graphRawData.nodes.map(n => {
            const prev = prevNodeMap.get(n.id);
            if (prev) {
                return {
                    ...n,
                    x: prev.x,
                    y: prev.y,
                    vx: prev.vx,
                    vy: prev.vy,
                    radius: n.size || 8
                };
            }

            let initX = 0;
            let initY = 0;
            if (n.type === 'agent') {
                const angle = (agentIdx / agentCount) * Math.PI * 2;
                initX = Math.cos(angle) * 120;
                initY = Math.sin(angle) * 120;
                agentIdx++;
            } else if (n.type === 'course') {
                const angle = Math.random() * Math.PI * 2;
                initX = Math.cos(angle) * (200 + Math.random() * 40);
                initY = Math.sin(angle) * (200 + Math.random() * 40);
            } else if (n.type === 'lesson') {
                const parent = n.course_id ? prevNodeMap.get(n.course_id) : null;
                const angle = Math.random() * Math.PI * 2;
                const dist = 28 + Math.random() * 20;
                if (parent) {
                    initX = parent.x + Math.cos(angle) * dist;
                    initY = parent.y + Math.sin(angle) * dist;
                } else {
                    initX = Math.cos(angle) * (200 + Math.random() * 40);
                    initY = Math.sin(angle) * (200 + Math.random() * 40);
                }
            } else {
                const angle = Math.random() * Math.PI * 2;
                initX = Math.cos(angle) * (160 + Math.random() * 60);
                initY = Math.sin(angle) * (160 + Math.random() * 60);
            }

            return {
                ...n,
                x: initX,
                y: initY,
                vx: 0,
                vy: 0,
                radius: n.size || 8
            };
        });

        const nodeMap = new Map(graphSimNodes.map(n => [n.id, n]));
        graphSimLinks = graphRawData.links.map(l => ({
            source: nodeMap.get(l.source),
            target: nodeMap.get(l.target),
            distance: l.distance || 50,
            color: l.color || 'rgba(100, 116, 139, 0.25)'
        })).filter(l => l.source && l.target);

        renderVaultTree();

    } catch (err) {
        console.error('Erro ao carregar grafo de conhecimento:', err);
    }
}

let vaultSearchQuery = '';

function onVaultSearchInput(val) {
    vaultSearchQuery = (val || '').trim().toLowerCase();
    renderVaultTree();
}

function renderVaultTree() {
    const agentsContainer = document.getElementById('tree-agents-list');
    const coursesContainer = document.getElementById('tree-courses-list');
    const topicsContainer = document.getElementById('tree-topics-list');

    const areaFilter = currentConstellationAreaFilter || 'all';

    // 1. Filtragem estrita por Área
    let agents = graphSimNodes.filter(n => n.type === 'agent');
    let courses = graphSimNodes.filter(n => n.type === 'course');
    let topics = graphSimNodes.filter(n => n.type === 'topic');

    if (areaFilter !== 'all') {
        agents = agents.filter(n => n.area_id === areaFilter);
        const areaAgentIds = new Set(agents.map(n => n.id));
        courses = courses.filter(n => n.area_id === areaFilter || (n.agent_id && areaAgentIds.has(n.agent_id)));
        topics = topics.filter(n => n.area_id === areaFilter || (n.agent_id && areaAgentIds.has(n.agent_id)));
    }

    // 2. Filtragem estrita por Busca
    if (vaultSearchQuery) {
        agents = agents.filter(n => (n.label || '').toLowerCase().includes(vaultSearchQuery) || (n.role || '').toLowerCase().includes(vaultSearchQuery));
        courses = courses.filter(n => (n.label || '').toLowerCase().includes(vaultSearchQuery));
        topics = topics.filter(n => (n.label || '').toLowerCase().includes(vaultSearchQuery));
    }

    const totalNodesCount = agents.length + courses.length + topics.length;
    const badge = document.getElementById('vault-nodes-count-badge');
    if (badge) badge.innerText = `${totalNodesCount} nós`;

    if (document.getElementById('tree-agents-count')) document.getElementById('tree-agents-count').innerText = agents.length;
    if (document.getElementById('tree-courses-count')) document.getElementById('tree-courses-count').innerText = courses.length;
    if (document.getElementById('tree-topics-count')) document.getElementById('tree-topics-count').innerText = topics.length;

    if (agentsContainer) {
        agentsContainer.innerHTML = agents.length ? agents.map(a => `
            <div onclick="focusGraphNode('${a.id}')" class="p-1.5 rounded-lg hover:bg-gray-800/80 cursor-pointer flex items-center justify-between group transition-all">
                <div class="flex items-center space-x-2 truncate">
                    <span class="text-sm">${a.avatar || '🤖'}</span>
                    <span class="font-bold text-gray-200 group-hover:text-purple-300 truncate">${a.label}</span>
                </div>
                <span class="text-[10px] text-gray-500">${a.hours || 0}h</span>
            </div>
        `).join('') : `<div class="text-gray-500 text-[10px] py-1 pl-2">Nenhum agente neste filtro.</div>`;
    }

    if (coursesContainer) {
        coursesContainer.innerHTML = courses.length ? courses.map(c => `
            <div onclick="focusGraphNode('${c.id}')" class="p-1.5 rounded-lg hover:bg-gray-800/80 cursor-pointer flex items-center justify-between group transition-all">
                <div class="flex items-center space-x-2 truncate">
                    <span class="text-indigo-400">📁</span>
                    <span class="text-gray-300 group-hover:text-indigo-300 truncate">${c.label}</span>
                </div>
                <span class="text-[10px] text-gray-500 font-mono">${c.lessons_count || 0}</span>
            </div>
        `).join('') : `<div class="text-gray-500 text-[10px] py-1 pl-2">Nenhum curso indexado nesta área.</div>`;
    }

    if (topicsContainer) {
        topicsContainer.innerHTML = topics.length ? topics.map(t => `
            <span onclick="focusGraphNode('${t.id}')" class="obsidian-tag obsidian-tag-purple cursor-pointer hover:border-purple-400 transition-all">
                #${t.label}
            </span>
        `).join('') : `<div class="text-gray-500 text-[10px] pl-2">Nenhuma habilidade nesta área.</div>`;
    }
}

function graphRenderStep() {
    if (!graphCanvas || !graphCtx) {
        graphAnimFrame = requestAnimationFrame(graphRenderStep);
        return;
    }

    const dpr = window.devicePixelRatio || 1;
    const width = graphCanvas.width / dpr;
    const height = graphCanvas.height / dpr;

    if (width <= 0 || height <= 0) {
        graphAnimFrame = requestAnimationFrame(graphRenderStep);
        return;
    }

    const nodes = graphSimNodes;
    const links = graphSimLinks;

    // Física acelerada com Alpha Decay de estabilização imediata
    if (graphSimAlpha > 0.003) {
        for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const distSq = dx * dx + dy * dy + 80;
            const dist = Math.sqrt(distSq);
            const repForce = ((a.radius + b.radius) * 120) / distSq;
            const fx = (dx / dist) * repForce;
            const fy = (dy / dist) * repForce;

            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
        }
    }

    // Física: Atração por links
    for (let i = 0; i < links.length; i++) {
        const l = links[i];
        const a = l.source;
        const b = l.target;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const displacement = dist - l.distance;
        const springK = (l.target.type === 'lesson' || l.source.type === 'lesson') ? 0.055 : 0.035;
        const springForce = displacement * springK;

        const fx = (dx / dist) * springForce;
        const fy = (dy / dist) * springForce;

        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
    }

    // Gravidade central e atrito
    for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        n.vx -= n.x * 0.0006;
        n.vy -= n.y * 0.0006;
        n.vx *= 0.86;
        n.vy *= 0.86;

        if (n !== graphDraggedNode) {
            n.x += n.vx * graphSimAlpha;
            n.y += n.vy * graphSimAlpha;
        }
    }
    graphSimAlpha *= 0.985;
    }

    // Renderização
    graphCtx.save();
    graphCtx.setTransform(1, 0, 0, 1, 0, 0);
    graphCtx.scale(dpr, dpr);
    graphCtx.clearRect(0, 0, width, height);

    graphCtx.translate(width / 2 + graphPanX, height / 2 + graphPanY);
    graphCtx.scale(graphZoom, graphZoom);

    const connectedNodeIds = new Set();
    if (graphSelectedNode) {
        connectedNodeIds.add(graphSelectedNode.id);
        links.forEach(l => {
            if (l.source.id === graphSelectedNode.id) connectedNodeIds.add(l.target.id);
            if (l.target.id === graphSelectedNode.id) connectedNodeIds.add(l.source.id);
        });
    }

    // Identifica nós que pertencem à área ativa
    let activeAreaNodeIds = null;
    if (currentConstellationAreaFilter && currentConstellationAreaFilter !== 'all') {
        activeAreaNodeIds = new Set();
        nodes.forEach(n => {
            if (n.type === 'agent' && n.area_id === currentConstellationAreaFilter) {
                activeAreaNodeIds.add(n.id);
            }
        });
        links.forEach(l => {
            if (activeAreaNodeIds.has(l.source.id)) activeAreaNodeIds.add(l.target.id);
            if (activeAreaNodeIds.has(l.target.id)) activeAreaNodeIds.add(l.source.id);
        });
        links.forEach(l => {
            if (activeAreaNodeIds.has(l.source.id)) activeAreaNodeIds.add(l.target.id);
            if (activeAreaNodeIds.has(l.target.id)) activeAreaNodeIds.add(l.source.id);
        });
    }

    // Links
    for (let i = 0; i < links.length; i++) {
        const l = links[i];
        if (activeAreaNodeIds && (!activeAreaNodeIds.has(l.source.id) || !activeAreaNodeIds.has(l.target.id))) {
            continue; // Oculta links fora da área ativa
        }
        const isConnected = !graphSelectedNode || (connectedNodeIds.has(l.source.id) && connectedNodeIds.has(l.target.id));
        
        graphCtx.beginPath();
        graphCtx.moveTo(l.source.x, l.source.y);
        graphCtx.lineTo(l.target.x, l.target.y);
        graphCtx.strokeStyle = isConnected ? l.color : 'rgba(75, 85, 99, 0.08)';
        graphCtx.lineWidth = isConnected ? 1.4 : 0.6;
        graphCtx.stroke();
    }

    // Nós
    for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        if (activeAreaNodeIds && !activeAreaNodeIds.has(n.id)) {
            continue; // Oculta nós de outras áreas quando filtrado!
        }
        const matchesType = (graphFilterType === 'all') || (n.type === graphFilterType);
        const matchesSearch = !graphSearchQuery || n.label.toLowerCase().includes(graphSearchQuery.toLowerCase());
        const isDimmed = (graphSelectedNode && !connectedNodeIds.has(n.id)) || !matchesType || !matchesSearch;

        graphCtx.save();
        graphCtx.globalAlpha = isDimmed ? 0.2 : 1.0;

        if (!isDimmed) {
            graphCtx.shadowBlur = n.type === 'agent' ? 16 : (n.status === 'processing' ? 12 : 6);
            graphCtx.shadowColor = n.color || '#8b5cf6';
        }

        // Halo orbital para o assunto maior (curso)
        if (n.type === 'course' && !isDimmed) {
            graphCtx.save();
            graphCtx.beginPath();
            graphCtx.arc(n.x, n.y, 45, 0, Math.PI * 2);
            graphCtx.strokeStyle = 'rgba(129, 140, 248, 0.25)';
            graphCtx.setLineDash([3, 4]);
            graphCtx.lineWidth = 1;
            graphCtx.stroke();
            graphCtx.fillStyle = 'rgba(99, 102, 241, 0.03)';
            graphCtx.fill();
            graphCtx.restore();
        }

        // Anel pulsante para aulas ativas
        if (n.status === 'processing') {
            const pulse = (Math.sin(Date.now() / 250) + 1) * 2.5;
            graphCtx.beginPath();
            graphCtx.arc(n.x, n.y, n.radius + 3 + pulse, 0, Math.PI * 2);
            graphCtx.strokeStyle = 'rgba(245, 158, 11, 0.8)';
            graphCtx.lineWidth = 1.5;
            graphCtx.stroke();
        }

        graphCtx.beginPath();
        graphCtx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        graphCtx.fillStyle = n.color || '#94a3b8';
        graphCtx.fill();
        graphCtx.lineWidth = (n === graphSelectedNode || n === graphHoveredNode) ? 2.5 : 1;
        graphCtx.strokeStyle = (n === graphSelectedNode || n === graphHoveredNode) ? '#ffffff' : (n.color || 'rgba(255, 255, 255, 0.4)');
        graphCtx.stroke();

        const showLabel = (n.type === 'agent') || (n.type === 'course') || (n.type === 'topic') || (graphZoom > 1.3) || (n === graphHoveredNode) || (n === graphSelectedNode);
        if (showLabel && !isDimmed) {
            graphCtx.shadowBlur = 0;
            graphCtx.font = n.type === 'agent' ? 'bold 11px monospace' : (n.type === 'course' ? 'bold 10px monospace' : '9px monospace');
            graphCtx.fillStyle = '#f1f5f9';
            graphCtx.textAlign = 'center';
            graphCtx.textBaseline = 'top';

            if (n.avatar && n.type === 'agent') {
                graphCtx.font = '13px sans-serif';
                graphCtx.textBaseline = 'middle';
                graphCtx.fillText(n.avatar, n.x, n.y);
                graphCtx.font = 'bold 11px monospace';
                graphCtx.textBaseline = 'top';
                graphCtx.fillText(n.label, n.x, n.y + n.radius + 3);
            } else {
                const displayLabel = n.label.length > 22 ? n.label.substring(0, 20) + '...' : n.label;
                graphCtx.fillText(displayLabel, n.x, n.y + n.radius + 3);
            }
        }

        graphCtx.restore();
    }

    graphCtx.restore();
    graphAnimFrame = requestAnimationFrame(graphRenderStep);
}

function getGraphWorldCoords(e) {
    if (!graphCanvas) return { x: 0, y: 0 };
    const rect = graphCanvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = graphCanvas.width / dpr;
    const height = graphCanvas.height / dpr;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const worldX = (mouseX - (width / 2 + graphPanX)) / graphZoom;
    const worldY = (mouseY - (height / 2 + graphPanY)) / graphZoom;

    return { x: worldX, y: worldY };
}

function findNodeAt(worldX, worldY) {
    for (let i = graphSimNodes.length - 1; i >= 0; i--) {
        const n = graphSimNodes[i];
        const dx = n.x - worldX;
        const dy = n.y - worldY;
        const hitRadius = (n.radius + 6);
        if (dx * dx + dy * dy <= hitRadius * hitRadius) {
            return n;
        }
    }
    return null;
}

function onGraphMouseDown(e) {
    const coords = getGraphWorldCoords(e);
    const hitNode = findNodeAt(coords.x, coords.y);

    if (hitNode) {
        graphDraggedNode = hitNode;
        graphCanvas.classList.add('cursor-grabbing');
    } else {
        isGraphPanning = true;
        panStartX = e.clientX - graphPanX;
        panStartY = e.clientY - graphPanY;
        graphCanvas.classList.add('cursor-grabbing');
    }
}

function onGraphMouseMove(e) {
    if (graphDraggedNode) {
        const coords = getGraphWorldCoords(e);
        graphDraggedNode.x = coords.x;
        graphDraggedNode.y = coords.y;
        graphDraggedNode.vx = 0;
        graphDraggedNode.vy = 0;
        return;
    }

    if (isGraphPanning) {
        graphPanX = e.clientX - panStartX;
        graphPanY = e.clientY - panStartY;
        return;
    }

    const coords = getGraphWorldCoords(e);
    const hitNode = findNodeAt(coords.x, coords.y);
    graphHoveredNode = hitNode;

    const tooltip = document.getElementById('graph-tooltip');
    if (hitNode && tooltip && graphCanvas) {
        const rect = graphCanvas.getBoundingClientRect();
        tooltip.style.left = `${e.clientX - rect.left + 14}px`;
        tooltip.style.top = `${e.clientY - rect.top + 14}px`;
        tooltip.classList.remove('hidden');

        let typeBadge = '';
        if (hitNode.type === 'agent') typeBadge = '<span class="obsidian-tag obsidian-tag-green">#especialista</span>';
        else if (hitNode.type === 'course') typeBadge = '<span class="obsidian-tag obsidian-tag-purple">#curso</span>';
        else if (hitNode.type === 'lesson') {
            const sc = hitNode.status === 'completed' ? 'obsidian-tag-green' : (hitNode.status === 'processing' ? 'obsidian-tag-amber' : 'obsidian-tag-purple');
            typeBadge = `<span class="obsidian-tag ${sc}">#${hitNode.status || 'aula'}</span>`;
        } else if (hitNode.type === 'topic') typeBadge = '<span class="obsidian-tag obsidian-tag-blue">#habilidade</span>';

        tooltip.innerHTML = `
            <div class="flex items-center space-x-2">
                <span class="font-bold text-white truncate max-w-[200px]">${hitNode.label}</span>
                ${typeBadge}
            </div>
            ${hitNode.role ? `<div class="text-[10px] text-gray-400">${hitNode.role} • ${hitNode.hours || 0}h estudadas</div>` : ''}
            ${hitNode.progress_pct ? `<div class="text-[10px] text-amber-300 font-mono">Progresso: ${hitNode.progress_pct}%</div>` : ''}
            ${hitNode.lessons_count ? `<div class="text-[10px] text-indigo-300 font-mono">${hitNode.lessons_count} aulas associadas</div>` : ''}
        `;
    } else if (tooltip) {
        tooltip.classList.add('hidden');
    }
}

function onGraphMouseUp() {
    graphDraggedNode = null;
    isGraphPanning = false;
    if (graphCanvas) graphCanvas.classList.remove('cursor-grabbing');
}

function onGraphWheel(e) {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.88;
    graphZoom = Math.max(0.25, Math.min(4.0, graphZoom * factor));
}

function onGraphClick(e) {
    const coords = getGraphWorldCoords(e);
    const hitNode = findNodeAt(coords.x, coords.y);
    graphSelectedNode = hitNode;

    const detailsCard = document.getElementById('tree-node-details-card');
    if (hitNode && detailsCard) {
        detailsCard.classList.remove('hidden');
        document.getElementById('node-detail-title').innerText = hitNode.label;
        document.getElementById('node-detail-type').innerText = `#${hitNode.type}`;
        
        let desc = '';
        if (hitNode.type === 'agent') desc = `${hitNode.role || 'Especialista'}. Acumula ${hitNode.hours || 0} horas de estudo.`;
        else if (hitNode.type === 'course') desc = `Curso indexado no cofre com ${hitNode.lessons_count || 0} aulas catalogadas.`;
        else if (hitNode.type === 'lesson') desc = `Aula individual. Status: ${hitNode.status || 'pendente'}.`;
        else if (hitNode.type === 'topic') desc = `Habilidade e padrão dominado extraído das aulas.`;
        document.getElementById('node-detail-desc').innerText = desc;

        const linksEl = document.getElementById('node-detail-links');
        const connected = graphSimLinks
            .filter(l => l.source.id === hitNode.id || l.target.id === hitNode.id)
            .map(l => l.source.id === hitNode.id ? l.target.label : l.source.label);
        
        linksEl.innerHTML = connected.length
            ? `<div class="font-semibold text-purple-300">Conexões (${connected.length}):</div>` + connected.slice(0, 5).map(c => `<div>• [[${c}]]</div>`).join('')
            : '<div class="text-gray-500">Nenhuma conexão direta encontrada.</div>';

    } else if (detailsCard) {
        detailsCard.classList.add('hidden');
    }
}

function focusGraphNode(nodeId) {
    const target = graphSimNodes.find(n => n.id === nodeId);
    if (!target) return;
    graphSelectedNode = target;
    graphPanX = -target.x * graphZoom;
    graphPanY = -target.y * graphZoom;
    graphZoom = 1.3;

    onGraphClick({ clientX: 0, clientY: 0 });
}

function setGraphFilter(type) {
    graphFilterType = type;
    ['all', 'agent', 'course', 'lesson', 'topic'].forEach(t => {
        const btn = document.getElementById(`gfilter-${t}`);
        if (!btn) return;
        if (t === type) {
            btn.className = 'px-2.5 py-1 rounded-lg text-[11px] font-mono text-white bg-purple-600 font-semibold transition-all';
        } else {
            btn.className = 'px-2 py-1 rounded-lg text-[11px] font-mono text-gray-400 hover:text-white transition-all';
        }
    });
}

function onVaultSearchInput(val) {
    graphSearchQuery = (val || '').trim();
}

function zoomGraph(factor) {
    graphZoom = Math.max(0.25, Math.min(4.0, graphZoom * factor));
}

function resetGraphView() {
    graphZoom = 1.0;
    graphPanX = 0;
    graphPanY = 0;
    graphSelectedNode = null;
    const detailsCard = document.getElementById('tree-node-details-card');
    if (detailsCard) detailsCard.classList.add('hidden');
}

function toggleStudyDrawer() {
    isDrawerMinimized = !isDrawerMinimized;
    const grid = document.getElementById('drawer-workers-grid');
    const btn = document.getElementById('btn-toggle-drawer');
    const compact = document.getElementById('drawer-queue-compact');

    if (isDrawerMinimized) {
        if (grid) grid.classList.add('hidden');
        if (compact) compact.classList.add('hidden');
        if (btn) btn.innerHTML = '▲ Expandir Gaveta';
    } else {
        if (grid) grid.classList.remove('hidden');
        if (compact) compact.classList.remove('hidden');
        if (btn) btn.innerHTML = '▼ Recolher Gaveta';
    }
}

// =========================================================================
// MODAL DE NOVA JORNADA DE ESTUDOS
// =========================================================================


// =========================================================================
// GOOGLE DRIVE COMPARTILHADO: GERENCIAMENTO, STATUS & ENFILEIRAMENTO
// =========================================================================

let currentStudySourceMode = 'drive'; // 'drive' ou 'telegram'
let driveConnectionStatus = null;
let driveTreeData = null;
let allDriveCoursesCached = [];

function switchModalStudySource(mode) {
    currentStudySourceMode = mode;
    const btnDrive = document.getElementById('modal-tab-btn-drive');
    const btnTg = document.getElementById('modal-tab-btn-telegram');
    const paneDrive = document.getElementById('modal-pane-drive');
    const paneTg = document.getElementById('modal-pane-telegram');

    const activeClass = 'px-3 py-1 rounded-lg text-xs font-semibold bg-purple-600 text-white flex items-center space-x-1.5 transition-all shadow';
    const inactiveClass = 'px-3 py-1 rounded-lg text-xs font-semibold text-gray-400 hover:text-white flex items-center space-x-1.5 transition-all';

    if (btnDrive) btnDrive.className = (mode === 'drive') ? activeClass : inactiveClass;
    if (btnTg) btnTg.className = (mode === 'telegram') ? activeClass : inactiveClass;

    if (paneDrive) paneDrive.classList.toggle('hidden', mode !== 'drive');
    if (paneTg) paneTg.classList.toggle('hidden', mode !== 'telegram');

    if (mode === 'drive') {
        loadDriveStatusAndTree();
    } else {
        if (typeof renderModalChannelsList === 'function') renderModalChannelsList();
        loadTelegramGroupsSummary();
        updateModalSelectedCount();
    }
}

async function loadDriveStatusAndTree() {
    const statusContainer = document.getElementById('drive-status-container');
    const coursesList = document.getElementById('drive-courses-list');
    if (!statusContainer) return;

    statusContainer.innerHTML = `
        <div class="py-4 text-center text-gray-400 text-xs flex items-center justify-center space-x-2">
            <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-purple-400"></i>
            <span>Verificando conexão com o Google Drive...</span>
        </div>
    `;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/drive/status');
        driveConnectionStatus = await res.json();

        if (!driveConnectionStatus.accessible) {
            // Exibe formulário amigável de configuração
            renderDriveSetupBox(statusContainer, driveConnectionStatus);
            const driveHeader = document.getElementById('drive-courses-header');
            if (driveHeader) driveHeader.classList.add('hidden');
            if (coursesList) coursesList.classList.add('hidden');
            return;
        }

        // Renderiza card de conexão ativa com o seletor e input de link do Drive SEMPRE visíveis e fáceis de editar
        statusContainer.innerHTML = `
            <div class="space-y-3">
                <div class="p-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-between">
                    <div class="flex items-center space-x-2.5 min-w-0">
                        <div class="w-8 h-8 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 flex items-center justify-center text-sm font-bold flex-shrink-0">
                            ✓
                        </div>
                        <div class="min-w-0">
                            <div class="text-xs font-bold text-white flex items-center space-x-1.5">
                                <span>Pasta Atual Conectada:</span>
                                <span class="text-emerald-300 font-mono truncate">${driveConnectionStatus.root_folder_name || 'Conectada'}</span>
                                <span class="obsidian-tag obsidian-tag-green text-[9px]">#drive-ativo</span>
                            </div>
                            <div class="text-[10px] text-gray-400 font-mono truncate max-w-sm">
                                ID: ${driveConnectionStatus.root_folder_id || '-'} • ${driveConnectionStatus.user_email || driveConnectionStatus.service_account_email || 'Conectado'}
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2">
                        <button type="button" onclick="disconnectGoogleDrive()" class="px-2.5 py-1 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-semibold transition-all">
                            Desconectar
                        </button>
                        <button type="button" onclick="loadDriveStatusAndTree()" class="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-all text-xs flex items-center space-x-1" title="Atualizar">
                            <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </div>

                <!-- Formulário Direto para Trocar a Pasta / Link do Drive -->
                <div class="p-3.5 rounded-2xl border border-blue-500/30 bg-[#0e131f] space-y-2.5">
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold text-blue-300 flex items-center space-x-1.5">
                            <span>📁</span>
                            <span>Trocar Pasta ou Link do Google Drive:</span>
                        </span>
                        <span class="text-[10px] text-gray-400 font-mono">Cole qualquer link ou ID abaixo</span>
                    </div>

                    <div class="space-y-1">
                        <label class="block text-[10px] font-mono text-gray-400 uppercase font-semibold">1. Selecionar das pastas compartilhadas comigo:</label>
                        <select id="drive-shared-folders-select" onchange="onSharedFolderSelected(this.value)" class="w-full bg-[#121620] border border-blue-500/30 rounded-xl px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-blue-400">
                            <option value="">-- Carregando pastas compartilhadas... --</option>
                        </select>
                    </div>

                    <div class="space-y-1">
                        <label class="block text-[10px] font-mono text-gray-400 uppercase font-semibold">2. Ou cole o Link ou ID de qualquer outra pasta do Drive:</label>
                        <div class="flex items-center space-x-2">
                            <input type="text" id="drive-setup-folder-id" placeholder="Cole o link aqui: https://drive.google.com/drive/folders/..." 
                                class="flex-1 bg-[#121620] border border-blue-500/30 rounded-xl px-3 py-2 text-xs text-white font-mono placeholder-gray-500 focus:outline-none focus:border-blue-400"
                                value="${driveConnectionStatus.root_folder_id || ''}">
                            <button type="button" onclick="saveDriveQuickConfig()" id="btn-save-drive-config" class="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl text-xs transition-all shadow flex items-center space-x-1.5 flex-shrink-0">
                                <i data-lucide="save" class="w-3.5 h-3.5"></i>
                                <span>Salvar & Carregar Pasta</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        populateSharedFoldersSelect(driveConnectionStatus.root_folder_id);

        // Carrega e renderiza as pastas/cursos
        await loadDriveTree(coursesList);

    } catch (err) {
        statusContainer.innerHTML = `<div class="p-3 rounded-xl bg-rose-500/10 text-rose-300 border border-rose-500/30 text-xs">Erro ao verificar Drive: ${err.message}</div>`;
    } finally {
        if (window.lucide) lucide.createIcons();
    }
}

function toggleDriveChangeFolderPanel() {
    const panel = document.getElementById('drive-change-folder-panel');
    if (panel) {
        panel.classList.toggle('hidden');
        if (window.lucide) lucide.createIcons();
    }
}

function renderDriveSetupBox(container, status) {
    const isConnected = status.is_configured || status.has_oauth_token;
    
    let authSection = '';
    if (isConnected) {
        const email = status.user_email || status.service_account_email || 'Usuário Conectado';
        authSection = `
            <div class="flex items-center justify-between bg-emerald-950/40 border border-emerald-500/30 p-3 rounded-xl mb-3">
                <div class="flex items-center space-x-2 text-emerald-300 text-xs">
                    <span>✅</span>
                    <span>Conectado como: <strong>${email}</strong></span>
                </div>
                <button type="button" onclick="disconnectGoogleDrive()" class="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/40 text-rose-300 border border-rose-500/50 rounded-lg text-xs font-semibold transition-all">
                    Desconectar
                </button>
            </div>
        `;
    } else {
        authSection = `
            <div class="bg-black/40 border border-blue-500/20 p-4 rounded-xl mb-3 flex flex-col items-center justify-center space-y-3">
                <p class="text-xs text-gray-300 text-center">Conecte sua conta do Google para acessar as pastas do Drive.</p>
                <button type="button" onclick="window.location.href='/auth/google/login'" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl text-xs transition-all shadow-lg flex items-center justify-center space-x-2 w-full max-w-xs">
                    <span>Login com Google</span>
                </button>
            </div>
        `;
    }

    container.innerHTML = `
        <div class="p-4 rounded-2xl border border-blue-500/30 bg-blue-500/10 space-y-3">
            <div class="flex items-start justify-between mb-2">
                <div class="flex items-center space-x-2 text-blue-300 font-bold text-xs">
                    <span>☁️</span>
                    <span>Autenticação Google Drive</span>
                </div>
            </div>
            
            ${authSection}
            
            ${status.error ? `<div class="text-[10px] text-rose-300/90 font-mono bg-rose-950/40 p-2 rounded-lg border border-rose-500/20 mb-3">${status.error}</div>` : ''}

            <div class="space-y-3">
                ${isConnected ? `
                <div class="space-y-1">
                    <label class="block text-[10px] font-mono text-blue-300 uppercase font-bold">1. Escolha uma pasta compartilhada com você:</label>
                    <select id="drive-shared-folders-select" onchange="onSharedFolderSelected(this.value)" class="w-full bg-[#121620] border border-blue-500/30 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-blue-400">
                        <option value="">-- Carregando pastas compartilhadas... --</option>
                    </select>
                </div>
                ` : ''}

                <div class="space-y-1">
                    <label class="block text-[10px] font-mono text-gray-400 uppercase font-bold">Link ou ID da Pasta Raiz:</label>
                    <input type="text" id="drive-setup-folder-id" placeholder="Ex: https://drive.google.com/drive/folders/..." 
                        class="w-full bg-[#121620] border border-blue-500/30 rounded-xl px-3 py-1.5 text-xs text-white font-mono placeholder-gray-500 focus:outline-none focus:border-blue-400"
                        value="${status.root_folder_id || ''}">
                </div>
                
                <div class="flex items-center space-x-2 pt-1">
                    <button type="button" onclick="saveDriveQuickConfig()" id="btn-save-drive-config" class="flex-1 py-2 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 text-white font-bold rounded-xl text-xs transition-all shadow flex items-center justify-center space-x-1.5">
                        <i data-lucide="save" class="w-3.5 h-3.5"></i>
                        <span>Salvar Pasta Raiz</span>
                    </button>
                    <button type="button" onclick="loadDriveStatusAndTree()" class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-xl text-xs font-semibold transition-all">
                        Atualizar
                    </button>
                </div>
            </div>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
    if (isConnected) {
        populateSharedFoldersSelect(status.root_folder_id);
    }
}

function onSharedFolderSelected(val) {
    if (!val) return;
    const folderInput = document.getElementById('drive-setup-folder-id');
    if (folderInput) {
        folderInput.value = val;
    }
}

async function populateSharedFoldersSelect(currentSelectedId) {
    const select = document.getElementById('drive-shared-folders-select');
    if (!select) return;
    try {
        const res = await fetch('/api/drive/shared-with-me');
        const data = await res.json();
        const folders = data.shared_folders || [];
        if (!folders.length) {
            select.innerHTML = '<option value="">Nenhuma pasta compartilhada encontrada</option>';
            return;
        }
        let html = '<option value="">-- Selecione uma pasta compartilhada (' + folders.length + ' encontradas) --</option>';
        folders.forEach(f => {
            const isSel = (f.id === currentSelectedId) ? 'selected' : '';
            html += `<option value="${f.id}" ${isSel}>${f.name} (${f.owner || 'compartilhada'})</option>`;
        });
        select.innerHTML = html;
        if (currentSelectedId) {
            select.value = currentSelectedId;
        }
    } catch (e) {
        select.innerHTML = '<option value="">Erro ao carregar compartilhados</option>';
    }
}

async function disconnectGoogleDrive() {
    try {
        await fetch('/auth/google/disconnect', { method: 'POST' });
        loadDriveStatusAndTree();
    } catch (e) {
        console.error(e);
    }
}

async function saveDriveQuickConfig() {
    const folderInput = document.getElementById('drive-setup-folder-id');
    const jsonInput = document.getElementById('drive-setup-json');
    const btn = document.getElementById('btn-save-drive-config');

    const folder_id = folderInput ? folderInput.value.trim() : '';
    const service_account_json = jsonInput ? jsonInput.value.trim() : '';

    if (!folder_id && !service_account_json) {
        alert('Por favor, informe a URL/ID da pasta compartilhada ou cole o JSON de credenciais.');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Salvando e testando...</span>`;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch('/api/drive/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_id: folder_id || null,
                service_account_json: service_account_json || null
            })
        });

        let data;
        try {
            data = await res.json();
        } catch (e) {
            const rawText = await res.text().catch(() => '');
            throw new Error(rawText || `Erro HTTP ${res.status}`);
        }

        if (!res.ok) throw new Error(data.detail || data.message || 'Falha ao salvar configuração');

        const folderName = data.status?.root_folder_name || folder_id;
        alert(`✅ Pasta raiz do Google Drive configurada com sucesso!\n📁 ${folderName}`);
        await loadDriveStatusAndTree();
    } catch (err) {
        alert(`Erro ao salvar pasta raiz: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="save" class="w-3.5 h-3.5"></i><span>Salvar Pasta Raiz</span>`;
            if (window.lucide) lucide.createIcons();
        }
    }
}

async function loadDriveTree(container) {
    if (!container) return;
    const header = document.getElementById('drive-courses-header');
    if (header) header.classList.add('hidden');

    container.innerHTML = `
        <div class="py-4 text-center text-gray-400 text-xs flex items-center justify-center space-x-2">
            <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-purple-400"></i>
            <span>Mapeando cursos e aulas no Drive...</span>
        </div>
    `;
    container.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/drive/tree');
        const data = await res.json();
        driveTreeData = data;

        const tree = data.tree || [];
        if (!tree.length) {
            container.innerHTML = `<div class="text-center py-6 text-gray-400 text-xs">Nenhum curso ou vídeo encontrado na pasta raiz compartilhada.</div>`;
            return;
        }

        // Achata os cursos para renderizar no modal
        let allCourses = [];
        tree.forEach(node => {
            if (node.type === 'area') {
                (node.courses || []).forEach(c => {
                    allCourses.push({ ...c, areaName: node.name });
                });
            } else if (node.type === 'course') {
                allCourses.push({ ...node, areaName: 'Geral' });
            }
        });

        if (!allCourses.length) {
            container.innerHTML = `<div class="text-center py-6 text-gray-400 text-xs">Nenhum curso com vídeos encontrado nas subpastas.</div>`;
            return;
        }

        allDriveCoursesCached = allCourses;
        if (header) {
            header.classList.remove('hidden');
            const searchInput = document.getElementById('modal-drive-search');
            if (searchInput) searchInput.value = '';
            const btn = document.getElementById('modal-btn-select-all-drive');
            if (btn) btn.innerText = 'Selecionar Todos os Módulos';
        }

        renderDriveCoursesHtmlList(container, allCourses);
        updateModalSelectedCount();

    } catch (err) {
        container.innerHTML = `<div class="p-3 rounded-xl bg-rose-500/10 text-rose-300 text-xs">Erro ao mapear árvore do Drive: ${err.message}</div>`;
    } finally {
        if (window.lucide) lucide.createIcons();
    }
}

function renderDriveCoursesHtmlList(container, courses) {
    if (!courses || !courses.length) {
        container.innerHTML = `<div class="text-center py-6 text-gray-500 text-xs">Nenhum curso ou módulo encontrado com este filtro.</div>`;
        return;
    }

    container.innerHTML = courses.map((c, cIdx) => {
        const themes = c.themes || [];
        const directVideos = c.direct_videos || [];
        const directSupport = c.direct_support_files || [];
        const isLazy = c.lazy || (!themes.length && !directVideos.length && !directSupport.length);
        const detailsId = `drive-course-details-${cIdx}`;
        const safeCourseName = (c.name || '').replace(/'/g, "\\'");

        let themesHtml = '';
        if (themes.length > 0) {
            themesHtml = renderDriveThemesHtml(themes);
        } else if (directVideos.length > 0 || directSupport.length > 0) {
            themesHtml = renderDriveDirectContentsHtml(directVideos, directSupport);
        }

        return `
            <div class="rounded-xl border border-[#232733] bg-[#151923] hover:border-purple-500/30 transition-all overflow-hidden">
                <div class="p-3 flex items-center justify-between cursor-pointer group" onclick="toggleDriveCourseAccordion('${detailsId}', '${c.id}', '${safeCourseName}', event)">
                    <div class="flex items-center space-x-3 min-w-0">
                        <input type="checkbox" name="modal-drive-course-cb" value="${c.id}" data-coursename="${c.name}" class="rounded text-purple-600 bg-gray-900 border-gray-700" onclick="event.stopPropagation()" onchange="updateModalSelectedCount()">
                        <div class="min-w-0">
                            <div class="font-bold text-white group-hover:text-purple-300 truncate flex items-center space-x-1.5 text-xs">
                                <span>📁</span>
                                <span>${c.name}</span>
                            </div>
                            <div id="subtitle-${detailsId}" class="text-[10px] text-gray-400 font-mono">
                                ${isLazy ? `${c.areaName} • Toque para ver módulos, aulas e arquivos de apoio` : `${c.areaName} • ${themes.length} temas/módulos • ${c.support_files_count || 0} arquivos de apoio • ${c.total_size_mb} MB`}
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center space-x-3 flex-shrink-0">
                        <div id="badges-${detailsId}" class="text-right font-mono">
                            ${isLazy ? `
                                <div class="text-[11px] text-purple-400 font-semibold">Ver detalhes</div>
                            ` : `
                                <div class="text-[11px] text-purple-300 font-bold">${c.videos_count} aulas</div>
                                <div class="text-[10px] ${c.pending_count > 0 ? 'text-amber-400' : 'text-emerald-400'}">
                                    ${c.pending_count > 0 ? `${c.pending_count} pendentes` : '100% estudado'}
                                </div>
                            `}
                        </div>
                        <button type="button" class="text-gray-400 hover:text-white p-1 rounded-lg text-xs" title="Ver temas e arquivos">
                            <span id="icon-${detailsId}">▼</span>
                        </button>
                    </div>
                </div>
                <div id="${detailsId}" data-loaded="${isLazy ? 'false' : 'true'}" class="hidden p-3 pt-0 border-t border-gray-800/60 space-y-2 mt-2">
                    ${themesHtml || '<div class="text-gray-500 text-xs py-2">Carregando temas...</div>'}
                </div>
            </div>
        `;
    }).join('');
}

function onModalDriveSearch(query) {
    const container = document.getElementById('drive-courses-list');
    if (!container || !allDriveCoursesCached) return;
    const q = (query || '').trim().toLowerCase();
    const filtered = allDriveCoursesCached.filter(c => 
        !q || (c.name || '').toLowerCase().includes(q) || (c.areaName || '').toLowerCase().includes(q)
    );
    renderDriveCoursesHtmlList(container, filtered);
    updateModalSelectedCount();
    if (window.lucide) lucide.createIcons();
}

function renderDriveThemesHtml(themes) {
    return themes.map(t => {
        const vidsHtml = (t.videos || []).map(v => `
            <div class="flex items-center justify-between py-1 px-2 rounded bg-black/20 text-[11px]">
                <span class="truncate text-gray-300 flex items-center space-x-1.5">
                    <span>🎬</span>
                    <span title="${v.name}">${v.name}</span>
                </span>
                <div class="flex items-center space-x-2 text-[10px] font-mono flex-shrink-0">
                    <span class="text-gray-500">${v.size_mb} MB</span>
                    <span class="${v.is_studied ? 'text-emerald-400 font-bold' : 'text-amber-400'}">${v.is_studied ? '✓ Concluído' : 'Pendente'}</span>
                </div>
            </div>
        `).join('');

        const suppHtml = (t.support_files || []).map(s => `
            <span class="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-500/30 text-[10px] text-purple-300 font-mono" title="${s.name} (${s.size_mb} MB)">
                <span>📎</span>
                <span class="truncate max-w-[140px]">${s.name}</span>
            </span>
        `).join('');

        return `
            <div class="p-2.5 rounded-xl border border-gray-800/80 bg-gray-950/60 space-y-1.5">
                <div class="flex items-center justify-between text-xs">
                    <span class="font-bold text-gray-200 flex items-center space-x-1.5">
                        <span>📑</span>
                        <span>${t.name}</span>
                    </span>
                    <span class="text-[10px] font-mono text-purple-300">${t.videos_count} aulas • ${t.support_files_count} arquivos</span>
                </div>
                ${suppHtml ? `<div class="flex flex-wrap gap-1 pt-1">${suppHtml}</div>` : ''}
                <div class="space-y-1 pt-1 max-h-32 overflow-y-auto">
                    ${vidsHtml || '<span class="text-gray-500 text-[10px]">Nenhum vídeo neste tema</span>'}
                </div>
            </div>
        `;
    }).join('');
}

function renderDriveDirectContentsHtml(directVideos, directSupport) {
    const vidsHtml = directVideos.map(v => `
        <div class="flex items-center justify-between py-1 px-2 rounded bg-black/20 text-[11px]">
            <span class="truncate text-gray-300">🎬 ${v.name}</span>
            <span class="text-[10px] font-mono ${v.is_studied ? 'text-emerald-400' : 'text-amber-400'}">${v.is_studied ? '✓ Concluído' : 'Pendente'}</span>
        </div>
    `).join('');
    const suppHtml = directSupport.map(s => `
        <span class="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-500/30 text-[10px] text-purple-300 font-mono">
            <span>📎</span>
            <span class="truncate max-w-[140px]">${s.name}</span>
        </span>
    `).join('');

    return `
        <div class="p-2 rounded-xl bg-gray-950/60 space-y-1.5">
            ${suppHtml ? `<div class="flex flex-wrap gap-1">${suppHtml}</div>` : ''}
            <div class="space-y-1 max-h-32 overflow-y-auto">${vidsHtml}</div>
        </div>
    `;
}

async function toggleDriveCourseAccordion(detailsId, folderId, courseName, event) {
    const el = document.getElementById(detailsId);
    const icon = document.getElementById(`icon-${detailsId}`);
    if (!el) return;

    const isHidden = el.classList.toggle('hidden');
    if (icon) icon.innerText = isHidden ? '▼' : '▲';

    if (!isHidden && el.dataset.loaded !== 'true' && folderId) {
        el.innerHTML = `
            <div class="py-3 text-center text-gray-400 text-xs flex items-center justify-center space-x-2">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-purple-400"></i>
                <span>Mapeando módulos, aulas e materiais de apoio...</span>
            </div>
        `;
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch(`/api/drive/course-details?folder_id=${folderId}&course_name=${encodeURIComponent(courseName)}`);
            const data = await res.json();
            el.dataset.loaded = 'true';

            const themes = data.themes || [];
            const directVideos = data.direct_videos || [];
            const directSupport = data.direct_support_files || [];

            let themesHtml = '';
            if (themes.length > 0) {
                themesHtml = renderDriveThemesHtml(themes);
            } else if (directVideos.length > 0 || directSupport.length > 0) {
                themesHtml = renderDriveDirectContentsHtml(directVideos, directSupport);
            } else {
                themesHtml = '<div class="text-gray-500 text-xs py-2">Nenhum vídeo ou arquivo encontrado neste curso.</div>';
            }
            el.innerHTML = themesHtml;

            const subTitle = document.getElementById(`subtitle-${detailsId}`);
            if (subTitle) {
                subTitle.innerText = `${data.area_name || 'Geral'} • ${themes.length} temas/módulos • ${data.support_files_count || 0} arquivos de apoio • ${data.total_size_mb} MB`;
            }
            const badges = document.getElementById(`badges-${detailsId}`);
            if (badges) {
                badges.innerHTML = `
                    <div class="text-[11px] text-purple-300 font-bold">${data.videos_count} aulas</div>
                    <div class="text-[10px] ${data.pending_count > 0 ? 'text-amber-400' : 'text-emerald-400'}">
                        ${data.pending_count > 0 ? `${data.pending_count} pendentes` : '100% estudado'}
                    </div>
                `;
            }
        } catch (err) {
            el.innerHTML = `<div class="text-rose-400 text-xs py-2">Erro ao carregar detalhes: ${err.message}</div>`;
        } finally {
            if (window.lucide) lucide.createIcons();
        }
    }
}

async function openNewStudyModal() {
    const modal = document.getElementById('new-study-modal');
    if (!modal) return;

    if (!agentsList.length) await loadAgents();
    if (!groupsSummaryList.length) await loadTelegramGroupsSummary();

    const agentGrid = document.getElementById('modal-agent-selection-grid');
    if (agentGrid) {
        agentGrid.innerHTML = agentsList.map((a, idx) => `
            <label class="p-3 rounded-2xl border ${idx === 0 ? 'border-purple-500/60 bg-purple-500/10' : 'border-[#272b38] bg-[#161a24]'} hover:border-purple-500/40 cursor-pointer flex items-center space-x-3 transition-all">
                <input type="radio" name="modal-selected-agent" value="${a.id}" ${idx === 0 ? 'checked' : ''} class="text-purple-500 focus:ring-0">
                <div class="text-xl flex-shrink-0">${a.avatar || '🤖'}</div>
                <div class="min-w-0">
                    <div class="font-bold text-white text-xs truncate">${a.name}</div>
                    <div class="text-[10px] text-gray-400 truncate">${a.role}</div>
                </div>
            </label>
        `).join('');
    }

    renderModalChannelsList();

    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

function closeNewStudyModal() {
    const modal = document.getElementById('new-study-modal');
    if (modal) modal.classList.add('hidden');
}

function renderModalChannelsList(filterText = '') {
    const list = document.getElementById('modal-channels-list');
    if (!list) return;

    const filtered = groupsSummaryList.filter(g => 
        !filterText || (g.title || '').toLowerCase().includes(filterText.toLowerCase())
    );

    if (!filtered.length) {
        list.innerHTML = `<div class="text-center py-6 text-gray-500 text-xs">Nenhum canal encontrado.</div>`;
        return;
    }

    list.innerHTML = filtered.map(g => `
        <label class="p-2.5 rounded-xl border border-[#232733] bg-[#151923] hover:border-purple-500/30 flex items-center justify-between cursor-pointer text-xs">
            <div class="flex items-center space-x-2.5 min-w-0">
                <input type="checkbox" name="modal-channel-cb" value="${g.id}" class="rounded text-purple-600 bg-gray-900 border-gray-700" onchange="updateModalSelectedCount()">
                <span class="truncate text-gray-200 font-medium">${g.title}</span>
            </div>
            <span class="text-[10px] text-gray-400 font-mono px-2 py-0.5 rounded-md bg-gray-800">${g.total_videos || 0} aulas</span>
        </label>
    `).join('');

    updateModalSelectedCount();
}

function onModalChannelSearch(query) {
    renderModalChannelsList(query);
}

function toggleModalSelectAllChannels() {
    const checkboxes = document.querySelectorAll('input[name="modal-channel-cb"]');
    const anyUnchecked = Array.from(checkboxes).some(cb => !cb.checked);
    checkboxes.forEach(cb => cb.checked = anyUnchecked);
    
    const btn = document.getElementById('modal-btn-select-all');
    if (btn) btn.innerText = anyUnchecked ? 'Desmarcar Todos' : 'Selecionar Todos';
    updateModalSelectedCount();
}

function toggleModalSelectAllDriveCourses() {
    const checkboxes = document.querySelectorAll('input[name="modal-drive-course-cb"]');
    if (!checkboxes.length) return;
    const anyUnchecked = Array.from(checkboxes).some(cb => !cb.checked);
    checkboxes.forEach(cb => cb.checked = anyUnchecked);
    
    const btn = document.getElementById('modal-btn-select-all-drive');
    if (btn) btn.innerText = anyUnchecked ? 'Desmarcar Todos' : 'Selecionar Todos os Módulos';
    updateModalSelectedCount();
}

function updateModalSelectedCount() {
    const summary = document.getElementById('modal-summary-selected');
    if (!summary) return;

    if (currentStudySourceMode === 'drive') {
        const checked = document.querySelectorAll('input[name="modal-drive-course-cb"]:checked');
        summary.innerText = `${checked.length} módulo(s)/curso(s) do Google Drive selecionado(s)`;
        const btn = document.getElementById('modal-btn-select-all-drive');
        const checkboxes = document.querySelectorAll('input[name="modal-drive-course-cb"]');
        if (btn && checkboxes.length > 0) {
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            btn.innerText = allChecked ? 'Desmarcar Todos' : 'Selecionar Todos os Módulos';
        }
    } else {
        const checked = document.querySelectorAll('input[name="modal-channel-cb"]:checked');
        summary.innerText = `${checked.length} canal(is) do Telegram selecionado(s)`;
        const btn = document.getElementById('modal-btn-select-all');
        const checkboxes = document.querySelectorAll('input[name="modal-channel-cb"]');
        if (btn && checkboxes.length > 0) {
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            btn.innerText = allChecked ? 'Desmarcar Todos' : 'Selecionar Todos';
        }
    }
}

async function startStudyFromModal() {
    const agentRadio = document.querySelector('input[name="modal-selected-agent"]:checked');
    if (!agentRadio) {
        alert('Por favor, selecione um especialista.');
        return;
    }
    const agentId = agentRadio.value;

    const tierRadio = document.querySelector('input[name="modal-tier"]:checked');
    const tier = tierRadio ? tierRadio.value : 'audio_only';
    const onlyPending = document.getElementById('modal-only-pending')?.checked ?? true;

    const btn = document.getElementById('btn-modal-start-study');
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Enfileirando...</span>`;
    if (window.lucide) lucide.createIcons();

    try {
        if (currentStudySourceMode === 'drive') {
            const checkedDriveCourses = Array.from(document.querySelectorAll('input[name="modal-drive-course-cb"]:checked'));
            if (!checkedDriveCourses.length) {
                alert('Por favor, selecione ao menos um curso do Google Drive na lista abaixo.');
                btn.disabled = false;
                btn.innerHTML = origHtml;
                return;
            }

            let totalEnqueued = 0;
            for (const cb of checkedDriveCourses) {
                const folderId = cb.value;
                const courseName = cb.dataset.coursename || 'Curso Drive';
                const res = await fetch('/api/drive/enqueue-course', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        agent_id: agentId,
                        folder_id: folderId,
                        course_name: courseName,
                        tier: tier,
                        only_pending: onlyPending
                    })
                });
                let data;
                try {
                    data = await res.json();
                } catch(e) {
                    const raw = await res.text().catch(() => '');
                    throw new Error(raw || `Erro HTTP ${res.status}`);
                }
                if (!res.ok) throw new Error(data.detail || `Erro ao enfileirar curso ${courseName}`);
                totalEnqueued += (data.count || 0);
            }

            if (totalEnqueued === 0) {
                alert('Todas as aulas dos cursos selecionados já foram concluídas por este especialista!\n(Dica: se quiser reprocessar, desmarque a opção "Apenas aulas pendentes")');
            } else {
                alert(`🚀 ${totalEnqueued} aula(s) do Google Drive adicionadas à esteira de processamento!`);
            }
        } else {
            const checkedBoxes = Array.from(document.querySelectorAll('input[name="modal-channel-cb"]:checked'));
            if (!checkedBoxes.length) {
                alert('Por favor, selecione ao menos um canal do Telegram para estudar.');
                btn.disabled = false;
                btn.innerHTML = origHtml;
                return;
            }
            const groupIds = checkedBoxes.map(cb => parseInt(cb.value));

            const res = await fetch('/api/study/groups/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_ids: [agentId],
                    agent_id: agentId,
                    group_ids: groupIds,
                    tier: tier,
                    only_pending: onlyPending
                })
            });
            let data;
            try {
                data = await res.json();
            } catch(e) {
                const raw = await res.text().catch(() => '');
                throw new Error(raw || `Erro HTTP ${res.status}`);
            }
            if (!res.ok) throw new Error(data.detail || 'Falha ao iniciar estudos pelo Telegram');

            if (data.count === 0) {
                alert('Todas as aulas dos canais selecionados já foram concluídas por este especialista!\n(Dica: para forçar reprocessamento, desmarque "Apenas aulas pendentes")');
            } else {
                alert(`🚀 ${data.message || `${data.count} aulas do Telegram adicionadas à esteira de estudos!`}`);
            }
        }

        closeNewStudyModal();
        if (typeof switchTab === 'function') switchTab('study');
        if (typeof loadStudyQueue === 'function') await loadStudyQueue();
        if (typeof loadKnowledgeGraph === 'function') await loadKnowledgeGraph();

    } catch (err) {
        alert(`Erro ao iniciar estudos: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
        if (window.lucide) lucide.createIcons();
    }
}



let currentStudyQueueTab = 'queued'; // 'queued', 'completed', 'errors'
let isStudyDrawerCollapsed = false;

function setQueueTab(tab) {
    currentStudyQueueTab = tab;
    const tabs = [
        { id: 'queued', activeClass: 'bg-purple-600 text-white shadow-sm' },
        { id: 'completed', activeClass: 'bg-emerald-600 text-white shadow-sm' },
        { id: 'errors', activeClass: 'bg-rose-600 text-white shadow-sm' }
    ];
    tabs.forEach(t => {
        const btn = document.getElementById(`qtab-${t.id}`);
        if (!btn) return;
        if (t.id === tab) {
            btn.className = `px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all ${t.activeClass} flex items-center space-x-1.5 cursor-pointer`;
        } else {
            btn.className = 'px-2.5 py-1 rounded-lg text-[11px] text-gray-400 hover:text-white transition-all flex items-center space-x-1.5 cursor-pointer';
        }
    });
    renderStudyQueueTable();
}

function toggleStudyDrawerCollapse() {
    isStudyDrawerCollapsed = !isStudyDrawerCollapsed;
    const wrapper = document.getElementById('study-drawer-table-wrapper');
    const textEl = document.getElementById('text-drawer-collapse');
    const iconEl = document.getElementById('icon-drawer-collapse');
    if (wrapper) {
        if (isStudyDrawerCollapsed) {
            wrapper.classList.add('hidden');
            if (textEl) textEl.innerText = 'Expandir Gaveta';
            if (iconEl) iconEl.style.transform = 'rotate(180deg)';
        } else {
            wrapper.classList.remove('hidden');
            if (textEl) textEl.innerText = 'Recolher Gaveta';
            if (iconEl) iconEl.style.transform = 'rotate(0deg)';
        }
    }
}

async function togglePauseStudyQueue() {
    try {
        const isCurrentlyPaused = window._lastStudyQueueState?.safety_paused || false;
        const newBudget = isCurrentlyPaused ? 0 : 1;
        const res = await fetch('/api/tokens/budget', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ daily_budget: newBudget })
        });
        if (res.ok) {
            await loadStudyQueue();
            await loadTokenStats();
        }
    } catch (err) {
        console.error('Erro ao alternar pausa da fila:', err);
    }
}

function renderStudyQueueTable() {
    const tbody = document.getElementById('study-queue-table-body');
    if (!tbody) return;

    const state = window._lastStudyQueueState;
    if (!state) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500 font-mono text-xs">Carregando itens da fila...</td></tr>`;
        return;
    }

    let itemsToRender = [];
    if (currentStudyQueueTab === 'queued') {
        itemsToRender = state.queued_items || [];
    } else if (currentStudyQueueTab === 'completed') {
        itemsToRender = state.completed_items || [];
    } else if (currentStudyQueueTab === 'errors') {
        itemsToRender = state.error_items || [];
    }

    if (!itemsToRender.length) {
        let emptyMsg = "Nenhuma aula aguardando na fila no momento.";
        if (currentStudyQueueTab === 'completed') emptyMsg = "Nenhuma aula concluída nesta sessão ainda.";
        if (currentStudyQueueTab === 'errors') emptyMsg = "Nenhum erro registrado na fila. Tudo operando com perfeição!";
        tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500 font-mono text-xs">${emptyMsg}</td></tr>`;
        return;
    }

    tbody.innerHTML = itemsToRender.map((it, idx) => {
        const isPdf = (it.file_name && it.file_name.toLowerCase().endsWith('.pdf'));
        const icon = isPdf ? '📄' : '📹';
        const typeBadge = isPdf 
            ? '<span class="px-1.5 py-0.2 rounded bg-purple-500/15 text-purple-300 text-[9px] border border-purple-500/30 font-mono shrink-0">PDF OCR</span>' 
            : '<span class="px-1.5 py-0.2 rounded bg-cyan-500/15 text-cyan-300 text-[9px] border border-cyan-500/30 font-mono shrink-0">Vídeo</span>';
        
        const tierBadge = it.tier === 'audio_only'
            ? '<span class="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[10px]">🟢 Econômico</span>'
            : '<span class="px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-[10px]">🔵 OCR Profundo</span>';

        let statusBadge = '';
        let actionBtn = '';

        if (currentStudyQueueTab === 'queued') {
            statusBadge = `<span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center space-x-1.5 w-fit">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
                <span>Na Fila (#${idx + 1})</span>
            </span>`;
            actionBtn = `<button onclick="deleteQueueItem('${it.id}')" class="text-gray-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-500/10 transition-all cursor-pointer" title="Remover da fila">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>`;
        } else if (currentStudyQueueTab === 'completed') {
            statusBadge = `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1 w-fit">
                <span>✓ Concluída</span>
            </span>`;
            actionBtn = `<span class="text-emerald-400/60 text-[10px]">Absorvida</span>`;
        } else if (currentStudyQueueTab === 'errors') {
            const rawErr = it.error_message || 'Erro desconhecido';
            const cleanErr = rawErr.length > 55 ? rawErr.substring(0, 52) + '...' : rawErr;
            const fullEscapedErr = rawErr.replace(/"/g, '&quot;');
            statusBadge = `<div class="flex flex-col gap-1">
                <span class="px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center space-x-1 w-fit">
                    <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                    <span>Falha no Processamento</span>
                </span>
                <span class="text-[10px] text-rose-400/80 font-mono truncate max-w-xs" title="${fullEscapedErr}">
                    ${cleanErr}
                </span>
            </div>`;
            actionBtn = `<div class="flex items-center justify-end space-x-2">
                <button onclick="resumeInterruptedStudy()" class="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[10px] font-semibold transition-all cursor-pointer" title="Retomar estudo desta e outras aulas com erro">
                    Retomar
                </button>
                <button onclick="deleteQueueItem('${it.id}')" class="text-gray-500 hover:text-rose-400 p-1 rounded hover:bg-rose-500/10 transition-all cursor-pointer" title="Remover aula com erro">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>
            </div>`;
        }

        return `
            <tr class="hover:bg-gray-900/60 transition-colors">
                <td class="py-2.5 px-4 font-semibold text-white max-w-[280px]">
                    <div class="flex items-center space-x-2 min-w-0">
                        <span class="text-sm shrink-0">${icon}</span>
                        <span class="truncate" title="${it.file_name}">${it.file_name}</span>
                        ${typeBadge}
                    </div>
                </td>
                <td class="py-2.5 px-4 text-purple-300 font-medium truncate max-w-[180px]" title="${it.group_name || ''}">${it.group_name || 'Curso'}</td>
                <td class="py-2.5 px-4 text-indigo-300 truncate max-w-[150px]">👤 ${it.agent_name || 'Especialista'}</td>
                <td class="py-2.5 px-4">${tierBadge}</td>
                <td class="py-2.5 px-4">${statusBadge}</td>
                <td class="py-2.5 px-4 text-right">${actionBtn}</td>
            </tr>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}


// =========================================================================
// ORQUESTRADOR DE PROJETOS & HARNESS DE EXECUÇÃO MULTI-AGENTE
// =========================================================================

let currentProjectsList = [];
let currentDocumentsList = [];
let activeViewingDocument = null;

async function loadProjects() {
    const grid = document.getElementById('projects-grid');
    if (!grid) return;
    grid.innerHTML = `<div class="py-12 text-center text-gray-500 text-xs flex items-center justify-center space-x-2">
        <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-indigo-400"></i>
        <span>Carregando projetos da equipe...</span>
    </div>`;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/projects');
        currentProjectsList = await res.json();

        if (!currentProjectsList.length) {
            grid.innerHTML = `
                <div class="p-8 rounded-3xl border border-[#232733] bg-[#121620] text-center space-y-3">
                    <div class="text-3xl">🚀</div>
                    <div class="text-sm font-bold text-white">Nenhum projeto em andamento</div>
                    <p class="text-xs text-gray-400 max-w-md mx-auto">
                        Crie seu primeiro projeto para que os Gestores de Área decomponham o objetivo e deleguem para os técnicos executarem!
                    </p>
                    <button onclick="openNewProjectModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow transition-all">
                        Criar Meu Primeiro Projeto
                    </button>
                </div>
            `;
            return;
        }

        grid.innerHTML = currentProjectsList.map(proj => {
            const tasks = proj.tasks || [];
            const docs = proj.documents || [];
            const doneTasks = tasks.filter(t => t.status === 'done').length;
            const progressPct = tasks.length ? Math.round((doneTasks / tasks.length) * 100) : 0;

            let statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-gray-500/20 text-gray-300 border border-gray-500/30">Rascunho</span>`;
            if (proj.status === 'planning') {
                statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">Planejando Tarefas</span>`;
            } else if (proj.status === 'in_progress') {
                statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Em Execução</span>`;
            } else if (proj.status === 'completed') {
                statusBadge = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">✓ Concluído</span>`;
            }

            return `
                <div class="spotlight-card project-card rounded-3xl p-6 space-y-5 shadow-md">
                    <div class="flex flex-col md:flex-row md:items-start justify-between gap-3">
                        <div class="space-y-1 min-w-0">
                            <div class="flex items-center space-x-2">
                                ${statusBadge}
                                <span class="text-[11px] font-mono text-gray-400">• Área: <strong class="text-indigo-300">${proj.area_name || 'Geral'}</strong></span>
                                <span class="text-[11px] font-mono text-gray-400">• Gestor: <strong class="text-purple-300">${proj.manager_agent_name || 'Gestor'}</strong></span>
                            </div>
                            <h3 class="text-base font-bold text-white truncate">${proj.title}</h3>
                            <p class="text-xs text-gray-300 leading-relaxed max-w-3xl">${proj.description}</p>
                        </div>

                        <div class="flex items-center space-x-2 flex-shrink-0">
                            ${!tasks.length ? `
                                <button onclick="planProjectWithManager('${proj.id}')" class="px-3.5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-gray-950 font-bold text-xs flex items-center space-x-1.5 transition-all shadow">
                                    <span>🤖</span>
                                    <span>Decompor com Gestor</span>
                                </button>
                            ` : `
                                <button onclick="executeAllProjectTasks('${proj.id}')" class="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center space-x-1.5 transition-all shadow">
                                    <i data-lucide="play" class="w-3.5 h-3.5"></i>
                                    <span>Executar Fila</span>
                                </button>
                            `}
                            <button onclick="deleteProject('${proj.id}')" class="p-2 rounded-xl bg-gray-800 hover:bg-rose-900/40 text-gray-400 hover:text-rose-300 transition-all text-xs" title="Excluir Projeto">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>

                    <div class="space-y-1.5">
                        <div class="flex justify-between text-[11px] font-mono text-gray-400">
                            <span>Progresso do Projeto: <strong>${doneTasks}/${tasks.length} tarefas</strong> concluídas</span>
                            <span>${progressPct}%</span>
                        </div>
                        <div class="w-full bg-[#1e2332] rounded-full h-2 overflow-hidden">
                            <div class="bg-gradient-to-r from-indigo-500 to-emerald-500 h-2 rounded-full transition-all duration-500" style="width: ${progressPct}%"></div>
                        </div>
                    </div>

                    <div class="space-y-2 pt-2 border-t border-[#232733]/60">
                        <div class="text-[11px] font-mono uppercase text-gray-400 font-bold flex items-center justify-between">
                            <span>Tarefas Atribuídas aos Especialistas:</span>
                            <span class="text-[10px] text-gray-500">${tasks.length} etapa(s)</span>
                        </div>

                        <div class="grid grid-cols-1 gap-2">
                            ${tasks.map((t, idx) => {
                                let taskBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-gray-800 text-gray-400 font-mono">Pendente</span>`;
                                if (t.status === 'in_progress') {
                                    taskBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-indigo-500/20 text-indigo-300 font-mono animate-pulse">⚡ Em Execução</span>`;
                                } else if (t.status === 'done') {
                                    taskBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 font-mono">✓ Concluído</span>`;
                                } else if (t.status === 'failed') {
                                    taskBadge = `<span class="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 font-mono">Falhou</span>`;
                                }

                                return `
                                    <div class="p-3 rounded-2xl bg-[#10131c] border border-[#202534] flex flex-col md:flex-row md:items-center justify-between gap-2.5">
                                        <div class="space-y-0.5 min-w-0">
                                            <div class="flex items-center space-x-2">
                                                <span class="font-mono text-xs text-indigo-400 font-bold">${idx + 1}.</span>
                                                <span class="text-xs font-bold text-white truncate">${t.title}</span>
                                                ${taskBadge}
                                            </div>
                                            <div class="text-[11px] text-gray-400 truncate max-w-2xl">
                                                👤 Técnico: <strong class="text-gray-300">${t.assigned_agent_name || 'Especialista'}</strong> • ${t.instruction}
                                            </div>
                                            ${t.result_summary ? `<div class="text-[10px] text-emerald-400 font-mono mt-1">Resultado: ${t.result_summary}</div>` : ''}
                                        </div>

                                        <div class="flex items-center space-x-2 flex-shrink-0">
                                            ${t.harness_type === 'antigravity_ide' ? `
                                                <span class="px-2 py-1 rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-mono font-bold flex items-center space-x-1">
                                                    <span>💻</span><span>Antigravity IDE</span>
                                                </span>
                                                <button onclick="copyHandoffPrompt('${t.id}')" class="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold flex items-center space-x-1 shadow-md shadow-purple-600/30 transition-all" title="Copiar comando pronto para executar no Antigravity IDE">
                                                    <i data-lucide="terminal" class="w-3.5 h-3.5"></i>
                                                    <span>Executar na IDE</span>
                                                </button>
                                            ` : `
                                                ${t.status !== 'done' ? `
                                                    <button onclick="executeSingleTask('${t.id}')" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center space-x-1 shadow transition-all">
                                                        <i data-lucide="play" class="w-3 h-3"></i>
                                                        <span>Executar</span>
                                                    </button>
                                                ` : `
                                                    <span class="text-xs text-emerald-400 font-bold">✓ Entregue</span>
                                                `}
                                            `}
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>

                    ${docs.length ? `
                        <div class="pt-2 border-t border-[#232733]/60 space-y-2">
                            <div class="text-[11px] font-mono uppercase text-purple-300 font-bold flex items-center space-x-1.5">
                                <span>📄</span>
                                <span>Entregas Geradas por este Projeto (${docs.length}):</span>
                            </div>
                            <div class="flex flex-wrap gap-2">
                                ${docs.map(d => `
                                    <button onclick="openDocumentModalById('${d.id}')" class="px-3 py-1.5 rounded-xl bg-purple-600/10 hover:bg-purple-600/20 border border-purple-500/30 text-purple-200 text-xs font-mono flex items-center space-x-2 transition-all">
                                        <span>📝</span>
                                        <span class="font-bold truncate max-w-xs">${d.title}</span>
                                        <span class="text-[10px] text-purple-400 font-normal">(${d.created_by_agent_name})</span>
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

    } catch (err) {
        grid.innerHTML = `<div class="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">Erro ao carregar projetos: ${err.message}</div>`;
    } finally {
        if (window.lucide) lucide.createIcons();
    }
}

function openNewProjectModal() {
    const modal = document.getElementById('modal-new-project');
    if (!modal) return;

    const areaSelect = document.getElementById('new-proj-area');
    if (areaSelect && window.areasList) {
        areaSelect.innerHTML = window.areasList.map(a => `
            <option value="${a.id}">${a.name} (${a.domain_key})</option>
        `).join('');
        if (window.areasList.length) {
            onProjectAreaChange(window.areasList[0].id);
        }
    }

    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

function closeNewProjectModal() {
    const modal = document.getElementById('modal-new-project');
    if (modal) modal.classList.add('hidden');
}

function onProjectAreaChange(areaId) {
    const managerSelect = document.getElementById('new-proj-manager');
    if (!managerSelect) return;

    const allAgents = window.agentsList || [];
    const areaManagers = allAgents.filter(a => a.area_id === areaId && a.agent_type === 'gestor');
    const fallbackManagers = allAgents.filter(a => a.agent_type === 'gestor');

    const listToUse = areaManagers.length ? areaManagers : (fallbackManagers.length ? fallbackManagers : allAgents);
    managerSelect.innerHTML = listToUse.map(m => `
        <option value="${m.id}">${m.name} (${m.role})</option>
    `).join('');
}

async function submitNewProject() {
    const title = document.getElementById('new-proj-title')?.value.trim();
    const area_id = document.getElementById('new-proj-area')?.value;
    const manager_agent_id = document.getElementById('new-proj-manager')?.value;
    const description = document.getElementById('new-proj-description')?.value.trim();

    if (!title || !description) {
        alert('Por favor, informe o título e o objetivo do projeto.');
        return;
    }

    const btn = document.getElementById('btn-submit-new-project');
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'Criando projeto...';

    try {
        const res = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                area_id,
                manager_agent_id
            })
        });
        const proj = await res.json();
        if (!res.ok) throw new Error(proj.detail || 'Falha ao criar projeto');

        closeNewProjectModal();
        await loadProjects();

        // Dispara planejamento com o gestor
        planProjectWithManager(proj.id);

    } catch (err) {
        alert(`Erro: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
    }
}

async function planProjectWithManager(projectId) {
    const card = document.querySelector(`[onclick*="planProjectWithManager('${projectId}')"]`);
    if (card) card.innerHTML = '<span>🤖 Gestor planejando...</span>';

    try {
        const res = await fetch(`/api/projects/${projectId}/plan`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Falha ao planejar');
        await loadProjects();
    } catch (err) {
        alert(`Erro ao planejar com gestor: ${err.message}`);
    }
}

async function executeSingleTask(taskId) {
    const btn = document.querySelector(`[onclick*="executeSingleTask('${taskId}')"]`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Executando...</span>`;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch(`/api/tasks/${taskId}/execute`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Falha na execução');
        await loadProjects();
        await loadDocuments();
    } catch (err) {
        alert(`Erro na execução do agente: ${err.message}`);
        await loadProjects();
    }
}

async function executeAllProjectTasks(projectId) {
    try {
        const res = await fetch(`/api/projects/${projectId}/execute`, { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Execução iniciada em background!');
        setTimeout(loadProjects, 1500);
    } catch (err) {
        alert(`Erro: ${err.message}`);
    }
}

async function deleteProject(projectId) {
    if (!confirm('Deseja realmente excluir este projeto e todas as suas tarefas e documentos?')) return;
    try {
        await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
        await loadProjects();
        await loadDocuments();
    } catch (err) {
        alert(`Erro: ${err.message}`);
    }
}

async function loadDocuments() {
    const grid = document.getElementById('documents-grid');
    if (!grid) return;
    grid.innerHTML = `<div class="col-span-full py-12 text-center text-gray-500 text-xs flex items-center justify-center space-x-2">
        <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-purple-400"></i>
        <span>Carregando cofre de documentos...</span>
    </div>`;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/documents');
        currentDocumentsList = await res.json();

        if (!currentDocumentsList.length) {
            grid.innerHTML = `
                <div class="col-span-full p-8 rounded-3xl border border-[#232733] bg-[#121620] text-center space-y-2">
                    <div class="text-3xl">📄</div>
                    <div class="text-sm font-bold text-white">Nenhum documento gerado ainda</div>
                    <p class="text-xs text-gray-400 max-w-md mx-auto">
                        Conforme os agentes executarem suas tarefas nos projetos, todos os roteiros, códigos e relatórios serão salvos aqui automaticamente!
                    </p>
                </div>
            `;
            return;
        }

        grid.innerHTML = currentDocumentsList.map(doc => {
            const dateStr = new Date(doc.created_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
            let typeBadge = `<span class="px-2 py-0.5 rounded text-[9px] bg-purple-500/20 text-purple-300 font-mono">${doc.doc_type}</span>`;

            return `
                <div class="spotlight-card doc-card p-5 rounded-3xl flex flex-col justify-between space-y-4 shadow-lg group">
                    <div class="space-y-2">
                        <div class="flex items-center justify-between">
                            ${typeBadge}
                            <span class="text-[10px] font-mono text-gray-500">${dateStr}</span>
                        </div>
                        <h4 class="text-sm font-bold text-white group-hover:text-purple-300 transition-colors leading-snug line-clamp-2">${doc.title}</h4>
                        <p class="text-xs text-gray-400 font-mono line-clamp-3 leading-relaxed bg-[#0d1017] p-2.5 rounded-xl border border-[#1e2332]">
                            ${doc.content.replace(/[#*`]/g, '').slice(0, 150)}...
                        </p>
                    </div>

                    <div class="pt-3 border-t border-[#232733]/60 flex items-center justify-between">
                        <div class="text-[11px] text-gray-400 flex items-center space-x-1.5">
                            <span>👤</span>
                            <span class="font-bold text-gray-300">${doc.created_by_agent_name}</span>
                        </div>
                        <div class="flex items-center space-x-1.5">
                            <button onclick="openDocumentModalById('${doc.id}')" class="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow transition-all flex items-center space-x-1">
                                <i data-lucide="eye" class="w-3.5 h-3.5"></i>
                                <span>Abrir</span>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        grid.innerHTML = `<div class="col-span-full p-6 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">Erro ao carregar documentos: ${err.message}</div>`;
    } finally {
        if (window.lucide) lucide.createIcons();
    }
}

function openDocumentModalById(docId) {
    const doc = currentDocumentsList.find(d => d.id === docId) || 
                currentProjectsList.flatMap(p => p.documents || []).find(d => d.id === docId);
    if (!doc) return;

    activeViewingDocument = doc;
    const modal = document.getElementById('modal-view-document');
    if (!modal) return;

    document.getElementById('doc-modal-title').innerText = doc.title;
    document.getElementById('doc-modal-meta').innerText = `Autor: ${doc.created_by_agent_name} • Tipo: ${doc.doc_type} • Versão ${doc.version}`;
    document.getElementById('doc-modal-content').innerText = doc.content;

    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

function closeDocumentModal() {
    const modal = document.getElementById('modal-view-document');
    if (modal) modal.classList.add('hidden');
}

function downloadCurrentDocument() {
    if (!activeViewingDocument) return;
    const blob = new Blob([activeViewingDocument.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeViewingDocument.title.replace(/[^a-zA-Z0-9_-]/g, '_')}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}


// ----------------- UNIVERSAL PROMPT BAR & ANTIGRAVITY HANDOFF -----------------

function setUniversalPromptText(text) {
    const input = document.getElementById('universal-prompt-input');
    if (input) {
        input.value = text;
        input.focus();
    }
}

async function submitUniversalPrompt() {
    const input = document.getElementById('universal-prompt-input');
    const prompt = input?.value.trim();
    if (!prompt) {
        alert('Por favor, digite o objetivo ou tarefa que deseja orquestrar.');
        return;
    }

    const btn = document.getElementById('btn-universal-submit');
    const feedback = document.getElementById('universal-prompt-feedback');
    const feedbackText = document.getElementById('universal-prompt-feedback-text');

    btn.disabled = true;
    btn.classList.add('opacity-50');
    if (feedback) {
        feedback.classList.remove('hidden');
        feedbackText.innerText = 'Orquestrador analisando objetivo... Selecionando Gestor e Especialistas...';
    }

    try {
        const res = await fetch('/api/projects/auto-dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt, auto_execute: false })
        });
        const project = await res.json();
        if (!res.ok) throw new Error(project.detail || 'Falha ao orquestrar projeto');

        if (feedbackText) {
            feedbackText.innerText = `✓ Projeto "${project.title}" criado com ${project.tasks?.length || 0} tarefas! Redirecionando...`;
        }

        input.value = '';
        setTimeout(() => {
            if (feedback) feedback.classList.add('hidden');
            switchTab('projects');
        }, 1200);

    } catch (err) {
        alert(`Erro na orquestração: ${err.message}`);
        if (feedback) feedback.classList.add('hidden');
    } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50');
    }
}

function copyHandoffPrompt(taskId) {
    const task = currentProjectsList.flatMap(p => p.tasks || []).find(t => t.id === taskId);
    if (!task || !task.ide_handoff_prompt) {
        alert('Prompt para IDE não disponível para esta tarefa.');
        return;
    }

    navigator.clipboard.writeText(task.ide_handoff_prompt).then(() => {
        alert('⚡ Comando para Antigravity IDE copiado para sua área de transferência!\n\nCole no chat do Antigravity para que o agente execute as alterações de código diretamente no seu workspace.');
    }).catch(err => {
        prompt('Copie o comando abaixo e cole no Antigravity:', task.ide_handoff_prompt);
    });
}

// ----------------- SINCRONIZAÇÃO DE GESTORES & ESPECIALISTAS -----------------

async function triggerManagersSync() {
    const btn = document.getElementById('btn-sync-managers');
    const icon = document.getElementById('icon-sync-managers');
    if (!btn) return;
    
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.classList.add('opacity-75');
    if (icon) icon.classList.add('animate-spin');
    
    try {
        const res = await fetch('/api/managers/sync', { method: 'POST' });
        const data = await res.json();
        
        if (res.ok) {
            btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i><span class="text-emerald-300 font-bold">${data.total_managers_synced || 0} Gestores Sincronizados!</span>`;
            if (window.lucide) lucide.createIcons();
            
            // Recarrega visualizações de áreas e agentes se as funções existirem
            if (typeof loadQuickAreasGrid === 'function') loadQuickAreasGrid();
            if (typeof loadAllAgentsCorporate === 'function') loadAllAgentsCorporate();
            if (typeof loadAreas === 'function') loadAreas();
            
            setTimeout(() => {
                btn.disabled = false;
                btn.classList.remove('opacity-75');
                btn.innerHTML = originalHtml;
                if (window.lucide) lucide.createIcons();
            }, 3000);
        } else {
            alert('Erro ao sincronizar gestores: ' + (data.detail || 'Falha na requisição'));
            btn.disabled = false;
            btn.classList.remove('opacity-75');
            btn.innerHTML = originalHtml;
            if (window.lucide) lucide.createIcons();
        }
    } catch (e) {
        console.error(e);
        alert('Erro ao sincronizar gestores: ' + e.message);
        btn.disabled = false;
        btn.classList.remove('opacity-75');
        btn.innerHTML = originalHtml;
        if (window.lucide) lucide.createIcons();
    }
}

// ================= AWWWARDS SPOTLIGHT MOUSE TRACKER (GPU-OPTIMIZED) =================
(function initAwwwardsMouseTracker() {
    let ticking = false;
    document.addEventListener('mousemove', (e) => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                const targetCards = document.querySelectorAll('.spotlight-card, .manager-executive-card, .area-quick-card');
                const winH = window.innerHeight;
                for (let i = 0; i < targetCards.length; i++) {
                    const card = targetCards[i];
                    const rect = card.getBoundingClientRect();
                    // Only update elements visible on screen for peak efficiency
                    if (rect.bottom >= 0 && rect.top <= winH) {
                        const x = e.clientX - rect.left;
                        const y = e.clientY - rect.top;
                        card.style.setProperty('--mouse-x', `${x}px`);
                        card.style.setProperty('--mouse-y', `${y}px`);
                    }
                }
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
})();


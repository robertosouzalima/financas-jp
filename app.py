<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Finanças 18</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <style>
        :root {
            --bg-main: #07090E;
            --card-bg: rgba(21, 26, 38, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent-blue: #00D4FF;
            --accent-purple: #A855F7;
            --accent-gold: #F59E0B;
            --accent-green: #10B981;
            --text-primary: #FFFFFF;
            --text-secondary: #9CA3AF;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, blinkmacsystemfont, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-primary);
            padding: 20px 16px 120px 16px;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Top Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-top: env(safe-area-inset-top, 10px);
        }

        .header h1 {
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .header p {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .badge-pro {
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(139, 92, 246, 0.2));
            border: 1px solid rgba(56, 189, 248, 0.4);
            color: #38BDF8;
            font-size: 11px;
            font-weight: 800;
            padding: 5px 12px;
            border-radius: 20px;
        }

        /* Balance Cards Grid */
        .grid-cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 20px;
        }

        .bank-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            transition: transform 0.2s ease, opacity 0.3s ease;
        }

        .bank-card:active {
            transform: scale(0.98);
        }

        .card-label {
            font-size: 10px;
            font-weight: 700;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .card-value {
            font-size: 22px;
            font-weight: 800;
            margin-top: 6px;
            letter-spacing: -0.5px;
        }

        .card-blue { border-top: 3px solid var(--accent-blue); }
        .card-purple { border-top: 3px solid var(--accent-purple); }
        .card-gold { border-top: 3px solid var(--accent-gold); }
        .card-green { border-top: 3px solid var(--accent-green); }

        /* Meta Progress */
        .progress-box {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            padding: 14px 16px;
            margin-bottom: 24px;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .progress-bar-bg {
            background: rgba(255, 255, 255, 0.08);
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #8B5CF6, #38BDF8);
            border-radius: 4px;
            transition: width 0.5s ease;
        }

        /* Sections & Views */
        .view-section {
            display: none;
            animation: fadeIn 0.25s ease-in-out;
        }

        .view-section.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Form Components */
        .form-group {
            margin-bottom: 16px;
        }

        label {
            display: block;
            font-size: 12px;
            font-weight: 700;
            color: var(--text-secondary);
            margin-bottom: 6px;
            text-transform: uppercase;
        }

        input, select {
            width: 100%;
            background: rgba(18, 24, 38, 0.8);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 14px;
            color: #FFF;
            font-size: 15px;
            font-weight: 600;
            outline: none;
        }

        input:focus, select:focus {
            border-color: var(--accent-purple);
        }

        .btn-primary {
            width: 100%;
            background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
            color: #FFF;
            border: none;
            border-radius: 16px;
            height: 54px;
            font-size: 16px;
            font-weight: 800;
            box-shadow: 0 8px 20px rgba(139, 92, 246, 0.35);
            cursor: pointer;
            transition: transform 0.1s ease;
        }

        .btn-primary:active {
            transform: scale(0.97);
        }

        /* Dynamic Feedback Card */
        .alert-card {
            background: rgba(15, 23, 42, 0.9);
            border-radius: 16px;
            padding: 16px;
            margin-top: 16px;
            border: 1.5px solid var(--accent-purple);
        }

        .alert-card h4 { font-size: 14px; font-weight: 800; margin-bottom: 4px; }
        .alert-card p { font-size: 13px; color: #E2E8F0; line-height: 1.4; }

        /* iOS 18 Liquid Glass Floating Tab Bar (Exata da imagem!) */
        .floating-tab-bar {
            position: fixed;
            bottom: max(20px, env(safe-area-inset-bottom, 20px));
            left: 50%;
            transform: translateX(-50%);
            width: calc(100% - 32px);
            max-width: 420px;
            height: 64px;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(25px) saturate(180%);
            -webkit-backdrop-filter: blur(25px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 35px;
            display: flex;
            align-items: center;
            justify-content: space-around;
            padding: 0 8px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.3);
            z-index: 9999;
        }

        .tab-item {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex: 1;
            height: 48px;
            border-radius: 24px;
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            font-size: 10px;
            font-weight: 700;
            transition: color 0.2s ease;
            cursor: pointer;
        }

        .tab-item svg {
            width: 20px;
            height: 20px;
            margin-bottom: 2px;
            fill: currentColor;
        }

        .tab-item.active {
            color: #FFFFFF;
            background: rgba(0, 0, 0, 0.7);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        /* History Table */
        .history-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .history-item {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 12px 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .history-type { font-size: 13px; font-weight: 700; }
        .history-date { font-size: 11px; color: var(--text-secondary); }
        .history-val { font-size: 14px; font-weight: 800; }
    </style>
</head>
<body>

    <!-- Header -->
    <div class="header">
        <div>
            <h1>Finanças 18</h1>
            <p>Seu Assistente de Patrimônio</p>
        </div>
        <div class="badge-pro">PRO 💎</div>
    </div>

    <!-- Cards de Saldo Dinâmicos -->
    <div class="grid-cards" id="cardsGrid">
        <!-- Renderizado dinamicamente via JS -->
    </div>

    <!-- Barra de Progresso Meta -->
    <div class="progress-box">
        <div class="progress-header">
            <span>Meta R$ 62.000,00</span>
            <span id="progresoTexto">0%</span>
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="progresoBarra" style="width: 0%;"></div>
        </div>
    </div>

    <!-- ABAS / TELAS DO APP -->

    <!-- ABA 1: INÍCIO / RESUMO -->
    <div id="viewHome" class="view-section active">
        <div class="alert-card" style="border-color: var(--accent-blue);">
            <h4 style="color: var(--accent-blue);">⚡ Painel de Controle</h4>
            <p>Acompanhe seu saldo livre em conta e os aportes das Caixinhas em tempo real.</p>
        </div>
    </div>

    <!-- ABA 2: LANÇAR -->
    <div id="viewLancamento" class="view-section">
        <div class="form-group">
            <label>Tipo de Operação</label>
            <select id="selectOperacao" onchange="atualizarFormulario()">
                <option value="receber">📥 Recebi Dinheiro</option>
                <option value="guardar">🔒 Guardar na Caixinha</option>
                <option value="resgatar">🔓 Resgatar da Caixinha</option>
                <option value="gastar">💸 Gastei Dinheiro</option>
            </select>
        </div>

        <div class="form-group" id="groupCaixinha" style="display: none;">
            <label id="labelCaixinha">Caixinha</label>
            <select id="selectCaixinha">
                <option value="futuro">Caixinha Futuro (100% CDI)</option>
                <option value="sonho">Caixinha Sonho (RDB)</option>
            </select>
        </div>

        <div class="form-group">
            <label>Valor (R$)</label>
            <input type="number" id="inputValor" placeholder="50.00" value="50.00">
        </div>

        <div class="form-group">
            <label>Descrição</label>
            <input type="text" id="inputDescricao" placeholder="Ex: Mesada, Sorvete, Resgate">
        </div>

        <button class="btn-primary" onclick="processarOperacao()">🚀 Confirmar Operação</button>

        <div id="feedbackContainer"></div>
    </div>

    <!-- ABA 3: ONDE INVESTIR -->
    <div id="viewInvestir" class="view-section">
        <div id="recomencacaoBox"></div>
    </div>

    <!-- ABA 4: EXTRATO -->
    <div id="viewExtrato" class="view-section">
        <div class="history-list" id="historicoLista">
            <!-- Transações dinâmicas -->
        </div>
    </div>

    <!-- ABA 5: PROJEÇÃO METAS -->
    <div id="viewProjecao" class="view-section">
        <h3 style="font-size: 16px; margin-bottom: 12px;">Evolução Estimada até os 18 Anos</h3>
        <div id="projecaoLista"></div>
    </div>

    <!-- LIQUID GLASS FLOATING TAB BAR (Estilo iOS 18 da Imagem!) -->
    <nav class="floating-tab-bar">
        <div class="tab-item active" onclick="trocarAba('Home', this)">
            <svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
            <span>Início</span>
        </div>
        <div class="tab-item" onclick="trocarAba('Lancamento', this)">
            <svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
            <span>Lançar</span>
        </div>
        <div class="tab-item" onclick="trocarAba('Investir', this)">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 16h-2v-2h2v2zm0-4h-2V7h2v7z"/></svg>
            <span>Guia</span>
        </div>
        <div class="tab-item" onclick="trocarAba('Extrato', this)">
            <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
            <span>Extrato</span>
        </div>
        <div class="tab-item" onclick="trocarAba('Projecao', this)">
            <svg viewBox="0 0 24 24"><path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>
            <span>Projeção</span>
        </div>
    </nav>

    <script>
        // Dados Iniciais do Usuário
        let dados = JSON.parse(localStorage.getItem('financas_18')) || {
            saldo_conta: 100.00,
            caixinha_futuro: 966.55,
            caixinha_sonho: 971.85,
            transacoes: [
                { data: '2026-10-03', tipo: 'Entrada', valor: 445.00, cat: 'Mesada Extra' },
                { data: '2026-10-03', tipo: 'Entrada', valor: 100.00, cat: 'Mesada Livre' },
                { data: '2026-10-03', tipo: 'Aporte', valor: 966.55, cat: 'Caixinha Futuro' }
            ]
        };

        function salvarDados() {
            localStorage.setItem('financas_18', JSON.stringify(dados));
            renderizarApp();
        }

        function renderizarApp() {
            const grid = document.getElementById('cardsGrid');
            grid.innerHTML = '';

            const patrimonioTotal = dados.saldo_conta + dados.caixinha_futuro + dados.caixinha_sonho;

            // Renderiza apenas as Caixinhas com saldo > 0
            grid.innerHTML += `
                <div class="bank-card card-blue">
                    <div class="card-label">💳 Saldo Livre</div>
                    <div class="card-value">R$ ${dados.saldo_conta.toFixed(2)}</div>
                </div>
            `;

            if (dados.caixinha_futuro > 0) {
                grid.innerHTML += `
                    <div class="bank-card card-purple">
                        <div class="card-label">🚀 Caixinha Futuro</div>
                        <div class="card-value">R$ ${dados.caixinha_futuro.toFixed(2)}</div>
                    </div>
                `;
            }

            if (dados.caixinha_sonho > 0) {
                grid.innerHTML += `
                    <div class="bank-card card-gold">
                        <div class="card-label">🔒 Caixinha Sonho</div>
                        <div class="card-value">R$ ${dados.caixinha_sonho.toFixed(2)}</div>
                    </div>
                `;
            }

            grid.innerHTML += `
                <div class="bank-card card-green">
                    <div class="card-label">🌟 Patrimônio</div>
                    <div class="card-value">R$ ${patrimonioTotal.toFixed(2)}</div>
                </div>
            `;

            // Progresso Meta 62k
            const pct = Math.min((patrimonioTotal / 62000) * 100, 100).toFixed(1);
            document.getElementById('progresoTexto').innerText = `${pct}%`;
            document.getElementById('progresoBarra').style.width = `${pct}%`;

            // Guia Onde Investir
            const box = document.getElementById('recomencacaoBox');
            if (dados.saldo_conta > 100) {
                const excesso = (dados.saldo_conta - 100).toFixed(2);
                box.innerHTML = `
                    <div class="alert-card" style="border-color: var(--accent-green);">
                        <h4 style="color: var(--accent-green);">🎯 HORA DE INVESTIR!</h4>
                        <p>Você tem R$ ${dados.saldo_conta.toFixed(2)} livres. Como sua reserva do mês é R$ 100,00:</p>
                        <br>
                        <p style="color: var(--accent-blue); font-weight: 700;">👉 Transfira R$ ${excesso} para a Caixinha Futuro (100% CDI) no Nubank.</p>
                    </div>
                `;
            } else {
                box.innerHTML = `
                    <div class="alert-card" style="border-color: var(--accent-blue);">
                        <h4 style="color: var(--accent-blue);">✅ CONTA EQUILIBRADA</h4>
                        <p>Seus R$ 100,00 estão garantidos para os gastos do mês. O restante já está rendendo nas Caixinhas!</p>
                    </div>
                `;
            }

            // Extrato
            const hist = document.getElementById('historicoLista');
            hist.innerHTML = '';
            dados.transacoes.slice().reverse().forEach(t => {
                hist.innerHTML += `
                    <div class="history-item">
                        <div>
                            <div class="history-type">${t.tipo} - ${t.cat}</div>
                            <div class="history-date">${t.data}</div>
                        </div>
                        <div class="history-val" style="color: ${t.tipo === 'Entrada' || t.tipo === 'Resgate' ? '#10B981' : '#F43F5E'}">
                            ${t.tipo === 'Entrada' || t.tipo === 'Resgate' ? '+' : '-'} R$ ${t.valor.toFixed(2)}
                        </div>
                    </div>
                `;
            });

            // Projeção
            const projList = document.getElementById('projecaoLista');
            projList.innerHTML = '';
            let ac = patrimonioTotal;
            for (let ano = 2026; ano <= 2032; ano++) {
                if (ano > 2026) ac = (ac + (600 * 12)) * 1.095;
                const p = Math.min((ac / 62000) * 100, 100);
                projList.innerHTML += `
                    <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 12px; margin-bottom: 8px;">
                        <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700; margin-bottom:6px;">
                            <span>Ano ${ano}</span>
                            <span style="color: var(--accent-green);">R$ ${ac.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                        </div>
                        <div style="background: rgba(255,255,255,0.08); height:6px; border-radius:3px;">
                            <div style="background: var(--accent-purple); width:${p}%; height:100%; border-radius:3px;"></div>
                        </div>
                    </div>
                `;
            }
        }

        function trocarAba(nomeAba, el) {
            document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
            document.getElementById(`view${nomeAba}`).classList.add('active');
            el.classList.add('active');
        }

        function atualizarFormulario() {
            const op = document.getElementById('selectOperacao').value;
            const group = document.getElementById('groupCaixinha');
            group.style.display = (op === 'guardar' || op === 'resgatar') ? 'block' : 'none';
        }

        function processarOperacao() {
            const op = document.getElementById('selectOperacao').value;
            const val = parseFloat(document.getElementById('inputValor').value);
            const desc = document.getElementById('inputDescricao').value || 'Movimentação';
            const cx = document.getElementById('selectCaixinha').value;
            const hoje = new Date().toISOString().split('T')[0];
            const feedback = document.getElementById('feedbackContainer');

            if (isNaN(val) || val <= 0) return alert('Digite um valor válido');

            if (op === 'receber') {
                dados.saldo_conta += val;
                dados.transacoes.push({ data: hoje, tipo: 'Entrada', valor: val, cat: desc });
                confetti({ particleCount: 80, spread: 60, origin: { y: 0.8 } });
                feedback.innerHTML = `
                    <div class="alert-card" style="border-color: var(--accent-green);">
                        <h4 style="color: var(--accent-green);">🎉 VALOR RECEBIDO!</h4>
                        <p>👉 Vá no Nubank e guarde o excedente dos R$ 100 na Caixinha Futuro!</p>
                    </div>
                `;
            } else if (op === 'guardar') {
                if (val > dados.saldo_conta) return alert('Saldo Livre insuficiente!');
                dados.saldo_conta -= val;
                if (cx === 'futuro') dados.caixinha_futuro += val;
                else dados.caixinha_sonho += val;
                dados.transacoes.push({ data: hoje, tipo: 'Aporte', valor: val, cat: `Caixinha ${cx}` });
                feedback.innerHTML = `
                    <div class="alert-card" style="border-color: var(--accent-purple);">
                        <h4 style="color: var(--accent-purple);">🔒 APORTE REGISTRADO!</h4>
                        <p>👉 Abra o Nubank e mova R$ ${val.toFixed(2)} para a Caixinha selecionada.</p>
                    </div>
                `;
            } else if (op === 'resgatar') {
                let disp = cx === 'futuro' ? dados.caixinha_futuro : dados.caixinha_sonho;
                if (val > disp) return alert('Saldo indisponível nesta Caixinha!');
                if (cx === 'futuro') dados.caixinha_futuro -= val;
                else dados.caixinha_sonho -= val;
                dados.saldo_conta += val;
                dados.transacoes.push({ data: hoje, tipo: 'Resgate', valor: val, cat: `Caixinha ${cx}` });
                feedback.innerHTML = `
                    <div class="alert-card" style="border-color: var(--accent-gold);">
                        <h4 style="color: var(--accent-gold);">🔓 RESGATE REGISTRADO!</h4>
                        <p>👉 Vá no Nubank e resgate R$ ${val.toFixed(2)} da Caixinha para sua Conta.</p>
                    </div>
                `;
            } else if (op === 'gastar') {
                dados.saldo_conta -= val;
                dados.transacoes.push({ data: hoje, tipo: 'Saída', valor: val, cat: desc });
                feedback.innerHTML = `
                    <div class="alert-card" style="border-color: #F43F5E;">
                        <h4 style="color: #F43F5E;">💸 GASTO REGISTRADO</h4>
                        <p>R$ ${val.toFixed(2)} descontados do seu Saldo Livre.</p>
                    </div>
                `;
            }

            salvarDados();
        }

        // Inicialização
        renderizarApp();
    </script>
</body>
</html>

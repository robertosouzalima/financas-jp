import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO BASE
# ==========================================
st.set_page_config(
    page_title="Finanças 18",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================
# 2. INJEÇÃO DE CSS (O SEGREDO DO LIQUID GLASS)
# ==========================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background-color: #05070A !important; /* Fundo super escuro (Modo Noturno Real) */
        color: #F3F4F6;
    }

    /* Oculta barras e menus do Streamlit */
    header, #MainMenu, footer, .stDeployButton { visibility: hidden !important; display: none !important; }

    /* Espaço extra no rodapé para a barra flutuante não tampar o conteúdo */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 7rem !important; 
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* ========================================================
       A MÁGICA: BARRA FLUTUANTE LIQUID GLASS NO RODAPÉ (iOS 18)
       ======================================================== */
    [data-baseweb="tab-list"] {
        position: fixed !important;
        bottom: 25px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 999999 !important;
        background: rgba(30, 35, 45, 0.65) !important;
        backdrop-filter: blur(25px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(25px) saturate(200%) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 40px !important;
        padding: 6px !important;
        box-shadow: 0 20px 45px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255,255,255,0.2) !important;
        display: flex !important;
        width: 90% !important;
        max-width: 400px !important;
        justify-content: space-between !important;
        gap: 2px !important;
    }

    /* Remove linha e fundo feio do Streamlit nas abas */
    [data-baseweb="tab-border"], [data-baseweb="tab-highlight"] { display: none !important; }

    /* Estilo de cada botão da barra */
    [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 30px !important;
        color: #8B94A5 !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        padding: 10px 14px !important;
        border: none !important;
        transition: all 0.3s ease !important;
        margin: 0 !important;
        flex: 1 !important;
        text-align: center !important;
    }

    /* Aba Ativa (A pílula preta sólida dentro do vidro) */
    [aria-selected="true"] {
        background: rgba(0, 0, 0, 0.85) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
    }

    /* ========================================================
       CARDS NEUMÓRFICOS (ESTILO BANCO)
       ======================================================== */
    .premium-card {
        background: linear-gradient(150deg, #131722 0%, #0B0D14 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 22px;
        padding: 18px;
        margin-bottom: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    }
    
    .c-blue { border-top: 3px solid #00D4FF; }
    .c-purple { border-top: 3px solid #A855F7; }
    .c-gold { border-top: 3px solid #F59E0B; }
    .c-green { border-top: 3px solid #10B981; }

    .c-label { font-size: 10px; color: #9CA3AF; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px; }
    .c-val { font-size: 26px; color: #FFFFFF; font-weight: 800; margin-top: 4px; letter-spacing: -0.5px; }

    /* ========================================================
       BOTÕES DE ESCOLHA (RÁDIOS) EM LIQUID GLASS
       ======================================================== */
    div[role="radiogroup"] {
        background: rgba(255,255,255,0.04);
        border-radius: 18px;
        padding: 6px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    label[data-baseweb="radio"] {
        background: transparent;
        padding: 14px 16px;
        border-radius: 14px;
        margin: 0;
        transition: 0.2s;
    }
    /* Esconde a bolinha padrão do rádio */
    div[data-baseweb="radio"] div:first-child { display: none !important; }
    div[data-baseweb="radio"] div:last-child { margin-left: 0 !important; font-weight: 700; font-size: 15px; color: #9CA3AF; }
    
    /* Quando selecionado */
    label[data-baseweb="radio"]:has(input:checked) {
        background: #1E2532;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }
    label[data-baseweb="radio"]:has(input:checked) div:last-child {
        color: #FFFFFF;
    }

    /* Botão Principal */
    .stButton>button {
        width: 100%;
        border-radius: 18px;
        height: 58px;
        font-weight: 800;
        font-size: 16px;
        background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
        color: #FFFFFF;
        border: none;
        box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4);
        transition: all 0.15s;
    }
    .stButton>button:active { transform: scale(0.96); }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 3. GERENCIADOR DE DADOS
# ==========================================
ARQUIVO_DADOS = "dados_financas.json"
DADOS_INICIAIS = {
    "saldo_conta": 100.00,
    "caixinha_futuro": 966.55,
    "caixinha_sonho": 971.85,
    "transacoes": []
}

def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return DADOS_INICIAIS
    return DADOS_INICIAIS

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

dados = carregar_dados()

# ==========================================
# 4. CABEÇALHO DO APLICATIVO
# ==========================================
st.markdown(
    """
    <div style="margin-bottom: 20px;">
        <h2 style="margin:0; font-weight: 800; font-size: 24px; color: #FFF;">Finanças 18</h2>
        <p style="margin:0; color: #6B7280; font-size: 13px;">Gestão de Patrimônio PRO 💎</p>
    </div>
    """, unsafe_allow_html=True
)

patrimonio_total = dados["saldo_conta"] + dados["caixinha_futuro"] + dados["caixinha_sonho"]

# ==========================================
# 5. AS 4 ABAS (Que agora são a barra de baixo!)
# ==========================================
aba_painel, aba_lancar, aba_guia, aba_extrato = st.tabs(
    ["Painel", "Lançar", "Aportes", "Extrato"]
)

# ------------------------------------------
# ABA 1: PAINEL (Cards dinâmicos que somem)
# ------------------------------------------
with aba_painel:
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(f"""
        <div class="premium-card c-blue">
            <div class="c-label">💳 Saldo Livre</div>
            <div class="c-val">R$ {dados['saldo_conta']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="premium-card c-green">
            <div class="c-label">🌟 Patrimônio</div>
            <div class="c-val">R$ {patrimonio_total:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Lógica Dinâmica: Só renderiza as Caixinhas se tiver dinheiro nelas!
    c3, c4 = st.columns(2)
    
    if dados["caixinha_futuro"] > 0:
        with c3:
            st.markdown(f"""
            <div class="premium-card c-purple">
                <div class="c-label">🚀 C. Futuro</div>
                <div class="c-val">R$ {dados['caixinha_futuro']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
            
    if dados["caixinha_sonho"] > 0:
        with c4:
            st.markdown(f"""
            <div class="premium-card c-gold">
                <div class="c-label">🔒 C. Sonho</div>
                <div class="c-val">R$ {dados['caixinha_sonho']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

    progresso = min(patrimonio_total / 62000.0, 1.0)
    st.write(f"🎯 **Meta (R$ 62k):** `{progresso * 100:.2f}%` atingido")
    st.progress(progresso)

# ------------------------------------------
# ABA 2: LANÇAR (Com resgate dinâmico)
# ------------------------------------------
with aba_lancar:
    st.markdown("<h4 style='margin-bottom:10px;'>Nova Operação</h4>", unsafe_allow_html=True)

    opcao = st.radio(
        "Ação",
        ["📥 Recebi Dinheiro", "🔒 Guardar na Caixinha", "🔓 Resgatar da Caixinha", "💸 Gastei Dinheiro"],
        label_visibility="collapsed"
    )

    if opcao == "🔒 Guardar na Caixinha":
        caixinha_alvo = st.selectbox("Qual Caixinha?", ["Futuro", "Sonho"])
    elif opcao == "🔓 Resgatar da Caixinha":
        opcoes_resgate = []
        if dados["caixinha_futuro"] > 0: opcoes_resgate.append("Futuro")
        if dados["caixinha_sonho"] > 0: opcoes_resgate.append("Sonho")
        
        if not opcoes_resgate:
            st.warning("⚠️ Você não tem dinheiro nas Caixinhas para resgatar.")
            caixinha_alvo = None
        else:
            caixinha_alvo = st.selectbox("De onde quer resgatar?", opcoes_resgate)

    valor = st.number_input("Valor (R$):", min_value=1.00, step=10.00, value=50.00)
    desc = st.text_input("Descrição:", placeholder="Ex: Mesada, Lanche, Resgate")

    if st.button("🚀 Confirmar"):
        data = str(pd.Timestamp.now().strftime("%Y-%m-%d"))

        if opcao == "📥 Recebi Dinheiro":
            dados["saldo_conta"] += valor
            dados["transacoes"].append({"Data": data, "Tipo": "Entrada", "Valor": valor, "Categoria": desc or "Recebimento"})
            st.success(f"R$ {valor:.2f} adicionados à conta!")
            st.balloons()

        elif opcao == "🔒 Guardar na Caixinha":
            if valor > dados["saldo_conta"]:
                st.error("⚠️ Saldo da conta insuficiente para guardar isso tudo.")
            else:
                dados["saldo_conta"] -= valor
                if caixinha_alvo == "Futuro": dados["caixinha_futuro"] += valor
                else: dados["caixinha_sonho"] += valor
                dados["transacoes"].append({"Data": data, "Tipo": "Aporte", "Valor": valor, "Categoria": f"Para {caixinha_alvo}"})
                st.success(f"R$ {valor:.2f} guardados com sucesso!")
                st.snow()

        elif opcao == "🔓 Resgatar da Caixinha":
            if caixinha_alvo:
                saldo_disponivel = dados["caixinha_futuro"] if caixinha_alvo == "Futuro" else dados["caixinha_sonho"]
                if valor > saldo_disponivel:
                    st.error(f"⚠️ A Caixinha {caixinha_alvo} só tem R$ {saldo_disponivel:.2f}.")
                else:
                    if caixinha_alvo == "Futuro": dados["caixinha_futuro"] -= valor
                    else: dados["caixinha_sonho"] -= valor
                    dados["saldo_conta"] += valor
                    dados["transacoes"].append({"Data": data, "Tipo": "Resgate", "Valor": valor, "Categoria": f"De {caixinha_alvo}"})
                    st.success(f"R$ {valor:.2f} resgatados de volta para a conta!")

        elif opcao == "💸 Gastei Dinheiro":
            dados["saldo_conta"] -= valor
            dados["transacoes"].append({"Data": data, "Tipo": "Saída", "Valor": valor, "Categoria": desc or "Gasto"})
            st.warning(f"R$ {valor:.2f} descontados da conta.")

        salvar_dados(dados)
        time.sleep(1)
        st.rerun()

# ------------------------------------------
# ABA 3: APORTES E DICAS
# ------------------------------------------
with aba_guia:
    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.markdown(f"""
        <div style="background: #0B1A15; padding: 20px; border-radius: 18px; border: 1px solid #10B981;">
            <h4 style="color: #10B981; margin:0;">🎯 HORA DE INVESTIR!</h4>
            <p style="color: #A0AAB8; font-size: 14px; margin-top: 10px;">
                Sua reserva do mês é R$ 100,00 e você tem R$ {dados['saldo_conta']:.2f}.
            </p>
            <p style="color: #38BDF8; font-size: 16px; font-weight: 700;">👉 Transfira R$ {excesso:.2f} para a Caixinha "Futuro" no app do Nubank.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background: #0A1322; padding: 20px; border-radius: 18px; border: 1px solid #38BDF8;">
            <h4 style="color: #38BDF8; margin:0;">✅ CONTA BALANCEADA!</h4>
            <p style="color: #A0AAB8; font-size: 14px; margin-top: 10px;">
                Você tem R$ {dados['saldo_conta']:.2f} livres. O resto está rendendo!
            </p>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------
# ABA 4: EXTRATO
# ------------------------------------------
with aba_extrato:
    st.markdown("<h4 style='margin-bottom:10px;'>Seu Histórico</h4>", unsafe_allow_html=True)
    if len(dados["transacoes"]) > 0:
        for t in reversed(dados["transacoes"]):
            cor = "#10B981" if t["Tipo"] in ["Entrada", "Resgate"] else "#F43F5E"
            sinal = "+" if t["Tipo"] in ["Entrada", "Resgate"] else "-"
            st.markdown(f"""
            <div style="background: #11151E; padding: 14px; border-radius: 14px; margin-bottom: 8px; border: 1px solid #1E2532; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 13px; font-weight: 700; color: #FFF;">{t['Tipo']}</div>
                    <div style="font-size: 11px; color: #8B94A5;">{t['Categoria']} • {t['Data']}</div>
                </div>
                <div style="font-size: 16px; font-weight: 800; color: {cor};">{sinal} R$ {t['Valor']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("Nenhuma movimentação.")

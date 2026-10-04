import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Projeto 18 Anos",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================
# 2. DESIGN PREMIUM & LIQUID GLASS BAR
# ==========================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
        background-color: #0B0E14 !important;
        color: #F3F4F6;
    }

    header, #MainMenu, footer, .stDeployButton { visibility: hidden !important; display: none !important; }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 6.5rem !important; 
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* BARRA FLUTUANTE (LIQUID GLASS iOS 18) */
    [data-baseweb="tab-list"] {
        position: fixed !important;
        bottom: 25px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 999999 !important;
        background: rgba(20, 25, 35, 0.75) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 40px !important;
        padding: 6px !important;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6) !important;
        display: flex !important;
        width: 95% !important;
        max-width: 450px !important;
        gap: 2px !important;
    }

    [data-baseweb="tab-border"], [data-baseweb="tab-highlight"] { display: none !important; }

    [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 30px !important;
        color: #8B94A5 !important;
        font-weight: 700 !important;
        font-size: 11px !important;
        padding: 12px 4px !important;
        border: none !important;
        margin: 0 !important;
        flex: 1 !important;
        text-align: center !important;
        transition: all 0.2s ease !important;
    }

    [aria-selected="true"] {
        background: rgba(255, 255, 255, 0.12) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
    }

    /* CARDS PRINCIPAIS */
    .fin-card {
        background: linear-gradient(145deg, #151A22 0%, #0D1016 100%);
        border: 1px solid #1E2532;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.3);
    }
    
    .c-blue { border-top: 3px solid #00D4FF; }
    .c-purple { border-top: 3px solid #A855F7; }
    .c-gold { border-top: 3px solid #F59E0B; }
    .c-green { border-top: 3px solid #10B981; }

    .c-title { font-size: 11px; color: #9CA3AF; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .c-val { font-size: 24px; color: #FFFFFF; font-weight: 800; margin-top: 4px; }

    /* LISTA DE TRANSAÇÕES (Substitui as tabelas feias) */
    .list-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #12161F;
        border: 1px solid #1E2532;
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 8px;
    }
    .list-left { display: flex; flex-direction: column; }
    .list-title { font-size: 14px; font-weight: 700; color: #FFFFFF; }
    .list-sub { font-size: 11px; color: #8B94A5; margin-top: 4px; }
    .val-pos { font-size: 15px; font-weight: 800; color: #10B981; }
    .val-neg { font-size: 15px; font-weight: 800; color: #F43F5E; }
    .val-neu { font-size: 15px; font-weight: 800; color: #38BDF8; }

    .stButton>button {
        width: 100%;
        border-radius: 14px;
        height: 52px;
        font-weight: 700;
        font-size: 16px;
        background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
        color: #FFFFFF;
        border: none;
        box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
        transition: all 0.15s;
    }
    .stButton>button:active { transform: scale(0.97); }
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
    "transacoes": [
        {"Data": "03/10/2026", "Tipo": "Aporte", "Origem": "Sistema", "Valor": 966.55, "Categoria": "Saldo Inicial", "Conta": "Caixinha Futuro"},
        {"Data": "03/10/2026", "Tipo": "Aporte", "Origem": "Sistema", "Valor": 971.85, "Categoria": "Saldo Inicial", "Conta": "Caixinha Sonho"}
    ]
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
if "transacoes" not in dados:
    dados["transacoes"] = []

patrimonio_total = dados["saldo_conta"] + dados["caixinha_futuro"] + dados["caixinha_sonho"]

# ==========================================
# 4. CABEÇALHO
# ==========================================
st.markdown(
    """
    <div style="margin-bottom: 16px;">
        <h2 style="margin:0; font-weight: 800; font-size: 24px; color: #FFF;">Finanças 18</h2>
        <p style="margin:0; color: #9CA3AF; font-size: 13px;">Seu controle financeiro profissional</p>
    </div>
    """, unsafe_allow_html=True
)

# ==========================================
# 5. ABAS
# ==========================================
aba_painel, aba_lancar, aba_investir, aba_extrato, aba_projecao = st.tabs(
    ["Painel", "Lançar", "Investir", "Extrato", "Projeção"]
)

# ------------------------------------------
# ABA 1: PAINEL DE CONTROLE
# ------------------------------------------
with aba_painel:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="fin-card c-blue">
            <div class="c-title">💳 Saldo Livre</div>
            <div class="c-val">R$ {dados['saldo_conta']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="fin-card c-green">
            <div class="c-title">🌟 Patrimônio</div>
            <div class="c-val">R$ {patrimonio_total:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    if dados["caixinha_futuro"] > 0:
        with col3:
            st.markdown(f"""
            <div class="fin-card c-purple">
                <div class="c-title">🚀 C. Futuro</div>
                <div class="c-val">R$ {dados['caixinha_futuro']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
            
    if dados["caixinha_sonho"] > 0:
        with col4:
            st.markdown(f"""
            <div class="fin-card c-gold">
                <div class="c-title">🔒 C. Sonho</div>
                <div class="c-val">R$ {dados['caixinha_sonho']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

    progresso = min(patrimonio_total / 62000.0, 1.0)
    st.write(f"🎯 **Meta (R$ 62.000,00):** `{progresso * 100:.2f}%` atingido")
    st.progress(progresso)

# ------------------------------------------
# ABA 2: LANÇAMENTOS
# ------------------------------------------
with aba_lancar:
    st.subheader("Nova Operação")

    opcao = st.radio(
        "Selecione o tipo:",
        ["📥 Recebi Dinheiro", "🔒 Guardar na Caixinha", "🔓 Resgatar da Caixinha", "💸 Gastei Dinheiro"],
        horizontal=False
    )

    if opcao == "🔒 Guardar na Caixinha":
        caixinha_alvo = st.selectbox("Qual Caixinha quer alimentar?", ["Futuro", "Sonho"])
    elif opcao == "🔓 Resgatar da Caixinha":
        opcoes_resgate = []
        if dados["caixinha_futuro"] > 0: opcoes_resgate.append("Futuro")
        if dados["caixinha_sonho"] > 0: opcoes_resgate.append("Sonho")
        
        if not opcoes_resgate:
            st.warning("⚠️ Nenhuma Caixinha possui saldo para resgate.")
            caixinha_alvo = None
        else:
            caixinha_alvo = st.selectbox("De qual Caixinha quer resgatar?", opcoes_resgate)

    valor = st.number_input("Valor da operação (R$):", min_value=1.00, step=10.00, value=50.00)
    desc = st.text_input("Descrição / Categoria:", placeholder="Ex: Mesada, Uber, Resgate")

    if st.button("🚀 Confirmar Lançamento"):
        data = str(pd.Timestamp.now().strftime("%d/%m/%Y"))

        if opcao == "📥 Recebi Dinheiro":
            dados["saldo_conta"] += valor
            dados["transacoes"].append({"Data": data, "Tipo": "Entrada", "Valor": valor, "Categoria": desc or "Recebimento", "Conta": "Saldo Livre"})
            st.success(f"R$ {valor:.2f} adicionados com sucesso!")

        elif opcao == "🔒 Guardar na Caixinha":
            if valor > dados["saldo_conta"]:
                st.error("⚠️ Seu Saldo Livre é insuficiente para guardar este valor.")
            else:
                dados["saldo_conta"] -= valor
                if caixinha_alvo == "Futuro": dados["caixinha_futuro"] += valor
                else: dados["caixinha_sonho"] += valor
                dados["transacoes"].append({"Data": data, "Tipo": "Aporte", "Valor": valor, "Categoria": desc or "Aporte", "Conta": f"Caixinha {caixinha_alvo}"})
                st.success(f"R$ {valor:.2f} guardados na Caixinha {caixinha_alvo}!")
                st.snow()

        elif opcao == "🔓 Resgatar da Caixinha":
            if caixinha_alvo:
                saldo_disponivel = dados["caixinha_futuro"] if caixinha_alvo == "Futuro" else dados["caixinha_sonho"]
                if valor > saldo_disponivel:
                    st.error(f"⚠️ A Caixinha {caixinha_alvo} possui apenas R$ {saldo_disponivel:.2f}.")
                else:
                    if caixinha_alvo == "Futuro": dados["caixinha_futuro"] -= valor
                    else: dados["caixinha_sonho"] -= valor
                    dados["saldo_conta"] += valor
                    dados["transacoes"].append({"Data": data, "Tipo": "Resgate", "Valor": valor, "Categoria": desc or "Resgate", "Conta": f"Da C. {caixinha_alvo}"})
                    st.success(f"R$ {valor:.2f} resgatados para o Saldo Livre!")

        elif opcao == "💸 Gastei Dinheiro":
            dados["saldo_conta"] -= valor
            dados["transacoes"].append({"Data": data, "Tipo": "Saída", "Valor": valor, "Categoria": desc or "Gasto Pessoal", "Conta": "Saldo Livre"})
            st.warning(f"R$ {valor:.2f} descontados do seu saldo.")

        salvar_dados(dados)
        time.sleep(1)
        st.rerun()

# ------------------------------------------
# ABA 3: INVESTIR
# ------------------------------------------
with aba_investir:
    st.subheader("Onde Investir Agora")
    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.success(f"**Ação Recomendada:** Transfira **R$ {excesso:.2f}** para a Caixinha Futuro (100% CDI).")
        st.info("Sua reserva mensal de R$ 100,00 será mantida no Saldo Livre para gastos diários.")
    else:
        st.info("Sua conta está equilibrada! Você não possui saldo excedente para investir neste momento.")

# ------------------------------------------
# ABA 4: EXTRATO (NOVO DESIGN DE LISTA NATIVA)
# ------------------------------------------
with aba_extrato:
    st.subheader("Movimentações")
    
    if len(dados["transacoes"]) > 0:
        for t in reversed(dados["transacoes"]):
            # Define cor e sinal da transação
            if t["Tipo"] in ["Entrada", "Resgate"]:
                classe_cor = "val-pos"
                sinal = "+"
            elif t["Tipo"] == "Saída":
                classe_cor = "val-neg"
                sinal = "-"
            else:
                classe_cor = "val-neu"
                sinal = ""

            # Renderiza um "cartão" de lista para cada transação
            st.markdown(f"""
            <div class="list-row">
                <div class="list-left">
                    <span class="list-title">{t['Categoria']}</span>
                    <span class="list-sub">{t['Tipo']} • {t['Conta']} • {t['Data']}</span>
                </div>
                <div class="{classe_cor}">{sinal} R$ {t['Valor']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("Nenhuma movimentação registrada.")

# ------------------------------------------
# ABA 5: PROJEÇÃO (NOVO DESIGN EM LISTA)
# ------------------------------------------
with aba_projecao:
    st.subheader("Projeção aos 18 Anos")
    st.caption("Aportes de R$ 600/mês a 100% do CDI")

    anos = [2026, 2027, 2028, 2029, 2030, 2031, 2032]
    valores = [patrimonio_total]
    atual = patrimonio_total

    for i in range(1, len(anos)):
        atual = (atual + (600 * 12)) * 1.095
        valores.append(atual)

    # Gráfico Area
    df_projecao = pd.DataFrame({"Ano": anos, "Patrimônio": valores})
    st.area_chart(df_projecao.set_index("Ano"))

    st.markdown("<br><b>Detalhamento Anual</b>", unsafe_allow_html=True)

    # Tabela Substituída por Lista Nativa
    for ano, valor in zip(anos, valores):
        st.markdown(f"""
        <div class="list-row">
            <div class="list-left">
                <span class="list-title">Acumulado em {ano}</span>
            </div>
            <div class="val-neu">R$ {valor:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

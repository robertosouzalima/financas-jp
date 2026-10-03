import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. DESIGN PROFISSIONAL & ESTILO APP NATIVO
# ==========================================
st.set_page_config(
    page_title="Finanças 18",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Injeção de CSS para transformar em App de Celular Premium
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    * { font-family: 'Inter', sans-serif !important; }

    /* Fundo Dark Profundo */
    .stApp { background-color: #0B0E14; }
    
    /* Ocultar elementos nativos de site do Streamlit */
    #MainMenu, footer, header { visibility: hidden; display: none !important; }

    /* Layout responsivo para celular sem scroll lateral */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* Cartões Neon Fintech */
    .card-base {
        background: linear-gradient(135deg, #151922 0%, #0F1218 100%);
        padding: 16px;
        border-radius: 18px;
        margin-bottom: 10px;
        border: 1px solid #1F2633;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .card-saldo { border-left: 5px solid #00D4FF; }
    .card-futuro { border-left: 5px solid #A855F7; }
    .card-sonho { border-left: 5px solid #F59E0B; }
    .card-total { border-left: 5px solid #10B981; }

    .titulo-card { 
        font-size: 11px; 
        color: #9CA3AF; 
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 0.8px; 
    }
    .valor-card { 
        font-size: 24px; 
        font-weight: 800; 
        color: #FFFFFF; 
        margin-top: 4px; 
    }
    
    /* Botões Dinâmicos Estilo App */
    .stButton>button {
        width: 100%;
        border-radius: 16px;
        height: 54px;
        font-weight: 800;
        font-size: 16px;
        background: linear-gradient(90deg, #8B5CF6 0%, #6D28D9 100%);
        color: #FFFFFF;
        border: none;
        box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4);
        transition: all 0.2s ease;
    }

    /* Ajuste de Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #11151F;
        padding: 6px;
        border-radius: 14px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        color: #9CA3AF;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1F2937 !important;
        color: #FFFFFF !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

ARQUIVO_DADOS = "dados_financas.json"

# ==========================================
# 2. GERENCIAMENTO DE DADOS
# ==========================================
DADOS_INICIAIS = {
    "saldo_conta": 100.00,
    "caixinha_futuro": 966.55,
    "caixinha_sonho": 971.85,
    "transacoes": [
        {
            "Data": "2026-10-03",
            "Tipo": "Entrada",
            "Origem": "Pai (Pix)",
            "Valor": 445.00,
            "Categoria": "Mesada Extra",
        },
        {
            "Data": "2026-10-03",
            "Tipo": "Entrada",
            "Origem": "Mãe (Pix)",
            "Valor": 100.00,
            "Categoria": "Mesada Livre",
        },
        {
            "Data": "2026-10-03",
            "Tipo": "Aporte",
            "Origem": "Caixinha Futuro",
            "Valor": 966.55,
            "Categoria": "Investimento 100% CDI",
        },
    ],
}


def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return DADOS_INICIAIS
    else:
        salvar_dados(DADOS_INICIAIS)
        return DADOS_INICIAIS


def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)


dados = carregar_dados()

# ==========================================
# 3. CABEÇALHO PRINCIPAL DO APP
# ==========================================
st.title("⚡ Projeto 18 Anos")
st.caption("Seu assistente financeiro pessoal de alta performance")

patrimonio_total = (
    dados["saldo_conta"]
    + dados["caixinha_futuro"]
    + dados["caixinha_sonho"]
)

# Grid 2x2 para telas de celular
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    st.markdown(
        f"""<div class="card-base card-saldo">
            <div class="titulo-card">💳 Saldo Livre</div>
            <div class="valor-card">R$ {dados['saldo_conta']:.2f}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""<div class="card-base card-futuro">
            <div class="titulo-card">🚀 Caixinha Futuro</div>
            <div class="valor-card">R$ {dados['caixinha_futuro']:.2f}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""<div class="card-base card-sonho">
            <div class="titulo-card">🔒 Caixinha Sonho</div>
            <div class="valor-card">R$ {dados['caixinha_sonho']:.2f}</div>
        </div>""",
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""<div class="card-base card-total">
            <div class="titulo-card">🌟 Patrimônio Total</div>
            <div class="valor-card">R$ {patrimonio_total:.2f}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# Progresso da Meta
progresso_meta = min(patrimonio_total / 62000.0, 1.0)
st.write(
    f"🎯 **Progresso Meta (R$ 62.000):** `{progresso_meta * 100:.2f}%` atingido"
)
st.progress(progresso_meta)
st.divider()

# ==========================================
# 4. NAVEGAÇÃO POR ABAS
# ==========================================
aba_lancamento, aba_guia, aba_extrato, aba_projecao = st.tabs(
    ["➕ Lançar", "📍 Investir", "📑 Extrato", "📈 Projeção"]
)

# ------------------------------------------
# ABA 1: LANÇAR MOVIMENTAÇÕES
# ------------------------------------------
with aba_lancamento:
    st.subheader("Registrar Valor")

    opcao = st.radio(
        "Selecione a ação:",
        ["💸 Gastei Dinheiro", "📥 Recebi Dinheiro", "🔒 Guardei na Caixinha"],
        horizontal=True,
    )

    valor_input = st.number_input(
        "Valor da operação (R$):", min_value=1.00, step=5.00, value=50.00
    )
    descricao_input = st.text_input(
        "Descrição:", placeholder="Ex: Mesada, Sorvete, Jogo"
    )

    if st.button("🚀 Confirmar Lançamento"):
        data_hoje = str(pd.Timestamp.now().strftime("%Y-%m-%d"))

        if opcao == "📥 Recebi Dinheiro":
            dados["saldo_conta"] += valor_input
            dados["transacoes"].append(
                {
                    "Data": data_hoje,
                    "Tipo": "Entrada",
                    "Origem": "Conta",
                    "Valor": valor_input,
                    "Categoria": descricao_input or "Recebimento",
                }
            )
            salvar_dados(dados)
            st.balloons()
            st.success(f"R$ {valor_input:.2f} adicionados ao seu Saldo Livre!")

        elif opcao == "🔒 Guardei na Caixinha":
            if valor_input > dados["saldo_conta"]:
                st.error("⚠️ Saldo em conta insuficiente para este aporte!")
            else:
                dados["saldo_conta"] -= valor_input
                dados["caixinha_futuro"] += valor_input
                dados["transacoes"].append(
                    {
                        "Data": data_hoje,
                        "Tipo": "Aporte",
                        "Origem": "Caixinha Futuro",
                        "Valor": valor_input,
                        "Categoria": descricao_input or "Aporte Caixinha",
                    }
                )
                salvar_dados(dados)
                st.snow()
                st.success(
                    f"R$ {valor_input:.2f} investidos na Caixinha Futuro!"
                )

        elif opcao == "💸 Gastei Dinheiro":
            dados["saldo_conta"] -= valor_input
            dados["transacoes"].append(
                {
                    "Data": data_hoje,
                    "Tipo": "Saída",
                    "Origem": "Conta",
                    "Valor": valor_input,
                    "Categoria": descricao_input or "Gasto Pessoal",
                }
            )
            salvar_dados(dados)
            st.warning(f"Gasto de R$ {valor_input:.2f} registrado.")

        time.sleep(1)
        st.rerun()

# ------------------------------------------
# ABA 2: ONDE INVESTIR (LIMPO E INTELIGENTE)
# ------------------------------------------
with aba_guia:
    st.subheader("🤖 Recomendação do Seu Assistente")

    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.markdown(
            f"""
            <div style="background-color: #111827; padding: 20px; border-radius: 16px; border: 2px solid #10B981;">
                <h4 style="color: #10B981; margin:0;">🎯 HORA DE INVESTIR!</h4>
                <p style="color: #F3F4F6; font-size: 15px; margin-top: 10px;">
                    Você está com <b>R$ {dados['saldo_conta']:.2f}</b> no saldo livre. Como sua reserva do mês é de R$ 100,00, você pode investir o restante!
                </p>
                <hr style="border-color: #1F2937;">
                <p style="color: #38BDF8; font-size: 16px; font-weight: bold; margin: 0;">
                    👉 Abra o app do Nubank e transfira R$ {excesso:.2f} para a Caixinha "Futuro" (100% CDI).
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    elif dados["saldo_conta"] == 100.00:
        st.markdown(
            """
            <div style="background-color: #111827; padding: 20px; border-radius: 16px; border: 2px solid #38BDF8;">
                <h4 style="color: #38BDF8; margin:0;">✅ CONTA TOTALMENTE EQUILIBRADA!</h4>
                <p style="color: #F3F4F6; font-size: 15px; margin-top: 10px;">
                    Seus R$ 100,00 estão garantidos no Saldo Livre para seus gastos do mês.
                </p>
                <hr style="border-color: #1F2937;">
                <p style="color: #9CA3AF; font-size: 14px; margin: 0;">
                    Todo o restante do seu dinheiro já está trabalhando para você nas Caixinhas!
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            f"Você tem R$ {dados['saldo_conta']:.2f} no Saldo Livre. Lembre-se de completar os R$ 100,00 na próxima entrada!"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📌 Mapeamento das Suas Contas:")
    st.write(
        "• **Saldo em Conta:** Manter R$ 100,00 livres para lanches e gastos do mês."
    )
    st.write(
        "• **Caixinha 'Futuro' (100% CDI):** Caixinha principal de resgate diário. Guarde todos os aportes novos aqui."
    )
    st.write(
        "• **Caixinha 'Sonho' (RDB):** Mantida até Novembro/2026. Quando vencer, consolide tudo na Caixinha Futuro."
    )

# ------------------------------------------
# ABA 3: EXTRATO
# ------------------------------------------
with aba_extrato:
    st.subheader("Histórico do Seu Dinheiro")
    if len(dados["transacoes"]) > 0:
        df = pd.DataFrame(dados["transacoes"])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ------------------------------------------
# ABA 4: PROJEÇÃO 18 ANOS
# ------------------------------------------
with aba_projecao:
    st.subheader("Evolução Esperada Até os 18 Anos")

    anos = list(range(2026, 2033))
    valores = [patrimonio_total]
    acumulado = patrimonio_total

    for idx in range(1, len(anos)):
        acumulado = (acumulado + (600 * 12)) * 1.095
        valores.append(acumulado)

    df_proj = pd.DataFrame(
        {"Ano": anos, "Patrimônio Estimado (R$)": valores}
    )
    st.area_chart(df_proj.set_index("Ano"))

    st.success(
        f"🚀 **Estimativa aos 18 Anos (2032):** ~R$ {valores[-1]:,.2f}"
    )

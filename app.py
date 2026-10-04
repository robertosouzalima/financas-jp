import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA & DESIGN PREMIUM
# ==========================================
st.set_page_config(
    page_title="Finanças 18",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS Profissional Estilo Fintech
st.markdown(
    """
    <style>
    /* Fundo Escuro Moderno */
    .stApp { background-color: #0D0F12; }
    
    /* Esconder elementos padrão da interface Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Espaçamento Mobile Perfeito */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* Cards Estilo Neumorphism / Fintech */
    .card-base {
        background: linear-gradient(145deg, #161A22, #111319);
        padding: 18px;
        border-radius: 16px;
        margin-bottom: 12px;
        border: 1px solid #222732;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .card-saldo { border-left: 5px solid #00D4FF; }
    .card-futuro { border-left: 5px solid #8A05BE; }
    .card-sonho { border-left: 5px solid #FF9900; }
    .card-total { border-left: 5px solid #00E676; }

    .titulo-card { 
        font-size: 11px; 
        color: #8B949E; 
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 1px; 
    }
    .valor-card { 
        font-size: 26px; 
        font-weight: 800; 
        color: #FFFFFF; 
        margin-top: 6px; 
        letter-spacing: -0.5px;
    }
    
    /* Botões Modernos e Arredondados */
    .stButton>button {
        width: 100%;
        border-radius: 14px;
        height: 52px;
        font-weight: 700;
        font-size: 16px;
        background: linear-gradient(90deg, #8A05BE 0%, #5B0382 100%);
        color: white;
        border: none;
        box-shadow: 0 4px 12px rgba(138, 5, 190, 0.3);
    }
    </style>
""",
    unsafe_allow_html=True,
)

ARQUIVO_DADOS = "dados_financas.json"

# ==========================================
# 2. DADOS INICIAIS
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
            "Categoria": "Aporte Extra",
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
# 3. CABEÇALHO DO DASHBOARD
# ==========================================
st.title("⚡ Projeto 18 Anos")
st.caption("O teu gestor financeiro pessoal")

patrimonio_total = (
    dados["saldo_conta"]
    + dados["caixinha_futuro"]
    + dados["caixinha_sonho"]
)

# Grelha de Saldos 2x2 para Telemóvel
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
            <div class="titulo-card">🌟 Património Total</div>
            <div class="valor-card">R$ {patrimonio_total:.2f}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# Barra de Progresso Visual
progresso_meta = min(patrimonio_total / 62000.0, 1.0)
st.write(
    f"🎯 **Meta R$ 62.000,00:** `{progresso_meta * 100:.2f}%` concluído"
)
st.progress(progresso_meta)
st.divider()

# ==========================================
# 4. ABAS DE NAVEGAÇÃO
# ==========================================
aba_lancamento, aba_guia, aba_extrato, aba_projecao = st.tabs(
    ["➕ Lançar", "📍 Onde Investir", "📑 Extrato", "📈 Projeção"]
)

# ------------------------------------------
# ABA 1: LANÇAMENTOS
# ------------------------------------------
with aba_lancamento:
    st.subheader("Nova Movimentação")

    opcao = st.radio(
        "Operação:",
        ["💸 Gastei Dinheiro", "📥 Recebi Dinheiro", "🔒 Guardei na Caixinha"],
        horizontal=True,
    )

    valor_input = st.number_input(
        "Valor (R$):", min_value=1.00, step=5.00, value=50.00
    )
    descricao_input = st.text_input(
        "Descrição:", placeholder="Ex: Lanche, Mesada, Jogo"
    )

    if st.button("🚀 Confirmar e Salvar"):
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
            st.success(
                f"R$ {valor_input:.2f} adicionados ao seu Saldo Livre na Conta!"
            )

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
                    f"R$ {valor_input:.2f} transferidos para a Caixinha Futuro!"
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
# ABA 2: ONDE INVESTIR (LIMPO E SEM MARCAÇÕES)
# ------------------------------------------
with aba_guia:
    st.subheader("🤖 Recomendação de Investimento")

    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.markdown(
            f"""
            <div style="background-color: #161A22; padding: 18px; border-radius: 14px; border: 2px solid #00E676;">
                <h4 style="color: #00E676; margin:0;">🎯 HORA DE INVESTIR!</h4>
                <p style="color: #FFFFFF; font-size: 15px; margin-top: 8px;">
                    Tens <b>R$ {dados['saldo_conta']:.2f}</b> na conta. Como a tua reserva do mês é de R$ 100,00, podes guardar o restante!
                </p>
                <hr style="border-color: #222732;">
                <p style="color: #00D4FF; font-size: 16px; font-weight: bold;">
                    👉 Abre o app do Nubank e transfere R$ {excesso:.2f} para a Caixinha "Futuro" (100% CDI).
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    elif dados["saldo_conta"] == 100.00:
        st.markdown(
            """
            <div style="background-color: #161A22; padding: 18px; border-radius: 14px; border: 2px solid #00D4FF;">
                <h4 style="color: #00D4FF; margin:0;">✅ CONTA PERFEITA!</h4>
                <p style="color: #FFFFFF; font-size: 15px; margin-top: 8px;">
                    Os teus R$ 100,00 estão exatamente no Saldo Livre para gastares no mês.
                </p>
                <hr style="border-color: #222732;">
                <p style="color: #8B949E; font-size: 14px;">
                    Todo o restante do teu dinheiro já está a render 100% do CDI nas Caixinhas!
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            f"Tens R$ {dados['saldo_conta']:.2f} livres na conta. Lembra-te de repor para os R$ 100,00 na próxima mesada!"
        )

    st.markdown("---")
    st.markdown("### 📌 Mapeamento do teu Dinheiro:")
    st.markdown(
        """
    * **Saldo em Conta:** Manter R$ 100,00 livres para lanches e pequenos gastos do mês[span_0](start_span)[span_0](end_span).
    * **Caixinha 'Futuro' (100% CDI):** Caixinha principal de resgate diário[span_1](start_span)[span_1](end_span)[span_2](start_span)[span_2](end_span). Todos os novos aportes vão para aqui[span_3](start_span)[span_3](end_span)[span_4](start_span)[span_4](end_span)!
    * **Caixinha 'Sonho' (RDB):** Guardada até Novembro/2026[span_5](start_span)[span_5](end_span)[span_6](start_span)[span_6](end_span). Quando vencer, transfere tudo para a Caixinha Futuro[span_7](start_span)[span_7](end_span).
    """
    )

# ------------------------------------------
# ABA 3: EXTRATO
# ------------------------------------------
with aba_extrato:
    st.subheader("Histórico do Teu Dinheiro")
    if len(dados["transacoes"]) > 0:
        df = pd.DataFrame(dados["transacoes"])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ------------------------------------------
# ABA 4: PROJEÇÃO 18 ANOS
# ------------------------------------------
with aba_projecao:
    st.subheader("Projeção do Teu Património")

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
        f"🚀 **Projeção para os 18 Anos (2032):** ~R$ {valores[-1]:,.2f}"
    )

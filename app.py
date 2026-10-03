import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA & RESPONSIVIDADE MOBILE
# ==========================================
st.set_page_config(
    page_title="Projeto 18 Anos - Finanças",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Estilo CSS customizado para transformar a página num App de Telemóvel Nativo
st.markdown(
    """
    <style>
    /* Fundo Dark Profissional */
    .stApp { background-color: #0E1117; }
    
    /* Adaptação de Margens para Telemóveis */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* Cards Visualmente Marcantes */
    .card-base {
        background-color: #1E232A;
        padding: 16px;
        border-radius: 14px;
        margin-bottom: 12px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
    }
    .card-saldo { border-left: 6px solid #00D4FF; }
    .card-futuro { border-left: 6px solid #8A05BE; }
    .card-sonho { border-left: 6px solid #FF9900; }
    .card-total { border-left: 6px solid #00E676; }

    .titulo-card { font-size: 12px; color: #A0AAB8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    .valor-card { font-size: 24px; font-weight: 800; color: #FFFFFF; margin-top: 4px; }
    
    /* Botões Grandes para Toque Fácil no Ecrã */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 50px;
        font-weight: bold;
        font-size: 16px;
        background: linear-gradient(90deg, #8A05BE 0%, #6D029B 100%);
        color: white;
        border: none;
    }
    </style>
""",
    unsafe_allow_html=True,
)

ARQUIVO_DADOS = "dados_financas.json"

# ==========================================
# 2. DADOS INICIAIS CONSOLIDADO DO SEU PATRIMÓNIO
# ==========================================
DADOS_INICIAIS = {
    "saldo_conta": 100.00,  # Seus R$ 100,00 livres na conta!
    "caixinha_futuro": 966.55,  # Caixinha Resgate Diário 100% CDI
    "caixinha_sonho": 971.85,  # Caixinha RDB Vence em Nov/2026
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
# 3. PAINEL DE CONTROLE MOBILE (CABEÇALHO)
# ==========================================
st.title("⚡ Projeto 18 Anos")
st.caption("Assistente Inteligente de Finanças Exclusivo")

patrimonio_total = (
    dados["saldo_conta"]
    + dados["caixinha_futuro"]
    + dados["caixinha_sonho"]
)

# Layout em Grelha Adaptável para Telemóvel
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    st.markdown(
        f"""<div class="card-base card-saldo">
            <div class="titulo-card">💳 Saldo LIVRE</div>
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

# Barra de Progresso Rumo aos R$ 62.000
progresso_meta = min(patrimonio_total / 62000.0, 1.0)
st.write(
    f"🎯 **Meta 18 Anos (R$ 62k):** `{progresso_meta * 100:.2f}%` concluído"
)
st.progress(progresso_meta)
st.divider()

# ==========================================
# 4. ABAS NAVEGÁVEIS DO APLICATIVO
# ==========================================
aba_lancamento, aba_guia, aba_extrato, aba_projecao = st.tabs(
    [
        "➕ Lançar",
        "📍 Onde Investir",
        "📑 Extrato",
        "📈 Projeção",
    ]
)

# ------------------------------------------
# ABA 1: REGISTRO DE MOVIMENTAÇÃO
# ------------------------------------------
with aba_lancamento:
    st.subheader("Registrar Movimentação")

    opcao = st.radio(
        "Selecione a Operação:",
        ["💸 Gastei Dinheiro", "📥 Recebi Dinheiro", "🔒 Guardei na Caixinha"],
        horizontal=True,
    )

    valor_input = st.number_input(
        "Valor (R$):", min_value=1.00, step=5.00, value=50.00
    )
    descricao_input = st.text_input(
        "Descrição / Origem:", placeholder="Ex: Mesada, Lanche, Presente"
    )

    if st.button("🚀 Confirmar e Salvar"):
        data_hoje = str(pd.Timestamp.now().strftime("%Y-%m-%d"))

        with st.spinner("A processar e a atualizar os saldos..."):
            time.sleep(0.5)

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
                    f"Boa! R$ {valor_input:.2f} transferidos para a Caixinha Futuro!"
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
            st.warning(f"Gasto de R$ {valor_input:.2f} registado.")

        time.sleep(1.5)
        st.rerun()

# ------------------------------------------
# ABA 2: GUIA INTELIGENTE - ONDE COLOCAR O DINHEIRO
# ------------------------------------------
with aba_guia:
    st.subheader("🤖 Assistente de Destinação do Dinheiro")

    st.info(f"💡 **Seu Saldo Livre Atual:** R$ {dados['saldo_conta']:.2f}")

    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.markdown(
            f"""
            <div style="background-color: #1E232A; padding: 18px; border-radius: 12px; border: 2px solid #00E676;">
                <h4 style="color: #00E676; margin:0;">🎯 INSTRUÇÃO DE APORTE IMEDIATO:</h4>
                <p style="color: #FFFFFF; font-size: 15px; margin-top: 8px;">
                    Tens <b>R$ {dados['saldo_conta']:.2f}</b> na conta, que é mais do que os R$ 100,00 de reserva diária!
                </p>
                <hr style="border-color: #333;">
                <p style="color: #00D4FF; font-size: 16px; font-weight: bold;">
                    👉 Abre o Nubank e transfere R$ {excesso:.2f} para a Caixinha "Futuro" (100% CDI).
                </p>
                <p style="color: #A0AAB8; font-size: 13px;">
                    Assim manténs R$ 100,00 exatos no Saldo Livre e colocas o restante a render juros diários!
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    elif dados["saldo_conta"] == 100.00:
        st.markdown(
            """
            <div style="background-color: #1E232A; padding: 18px; border-radius: 12px; border: 2px solid #00D4FF;">
                <h4 style="color: #00D4FF; margin:0;">✅ CONTA PERFEITAMENTE BALANCEADA!</h4>
                <p style="color: #FFFFFF; font-size: 15px; margin-top: 8px;">
                    Seus <b>R$ 100,00</b> estão corretos no Saldo Livre para uso mensal!
                </p>
                <hr style="border-color: #333;">
                <p style="color: #E0E0E0; font-size: 14px;">
                    📌 Todo o restante do seu patrimônio (R$ 1.938,40) já está a render 100% do CDI nas Caixinhas.
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
    st.markdown("### 📌 Mapeamento do seu Dinheiro no Nubank:")
    st.markdown(
        """
    - **Saldo em Conta:** Deixar exatamente **R$ 100,00** para lanches e gastos do mês[span_0](start_span)[span_0](end_span).
    - **Caixinha 'Futuro' (100% CDI):** Caixinha principal de Resgate Diário[span_1](start_span)[span_1](end_span)[span_2](start_span)[span_2](end_span). Depositar todas as mesadas e extras aqui[span_3](start_span)[span_3](end_span)[span_4](start_span)[span_4](end_span)!
    - **Caixinha 'Sonho de consumo' (RDB):** Deixar quieta até **Novembro/2026**[span_5](start_span)[span_5](end_span)[span_6](start_span)[span_6](end_span). Quando vencer, mover tudo para a Caixinha Futuro[span_7](start_span)[span_7](end_span)!
    """
    )

# ------------------------------------------
# ABA 3: EXTRATO COMPLETO
# ------------------------------------------
with aba_extrato:
    st.subheader("Histórico do Seu Dinheiro")
    if len(dados["transacoes"]) > 0:
        df = pd.DataFrame(dados["transacoes"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.write("Nenhuma transação registrada ainda.")

# ------------------------------------------
# ABA 4: PROJEÇÃO INTERATIVA ATE OS 18 ANOS
# ------------------------------------------
with aba_projecao:
    st.subheader("Evolução do Património aos 18 Anos")
    st.caption(
        "Simulação com base na consolidação de Novembro/2026 + R$ 600/mês"
    )

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
        f"🚀 **Projeção para Outubro/2032 (18 Anos):** ~R$ {valores[-1]:,.2f}"
    )

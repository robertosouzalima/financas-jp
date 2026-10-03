import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. ESTILIZAÇÃO NATIVA DE BANCO DIGITAL (DARK LUXURY)
# ==========================================
st.set_page_config(
    page_title="Finanças 18",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background-color: #080A0E !important;
        color: #F3F4F6;
    }

    /* Oculta elementos nativos de site */
    #MainMenu, footer, header, .stDeployButton { visibility: hidden !important; display: none !important; }

    /* Ajuste Mobile */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
    }

    /* Cards Neumórficos */
    .bank-card {
        background: linear-gradient(160deg, #121620 0%, #0A0C10 100%);
        border: 1px solid #1E2638;
        border-radius: 20px;
        padding: 16px 18px;
        margin-bottom: 12px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6);
    }
    
    .card-accent-blue { border-top: 3px solid #00D4FF; }
    .card-accent-purple { border-top: 3px solid #A855F7; }
    .card-accent-gold { border-top: 3px solid #F59E0B; }
    .card-accent-green { border-top: 3px solid #10B981; }

    .card-label {
        font-size: 10px;
        font-weight: 700;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }
    
    .card-value {
        font-size: 25px;
        font-weight: 800;
        color: #FFFFFF;
        margin-top: 4px;
        letter-spacing: -0.5px;
    }

    /* Botão Principal */
    .stButton>button {
        width: 100%;
        border-radius: 16px;
        height: 56px;
        font-weight: 800;
        font-size: 16px;
        background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
        color: #FFFFFF;
        border: none;
        box-shadow: 0 8px 20px rgba(139, 92, 246, 0.35);
        transition: all 0.15s ease-in-out;
    }

    .stButton>button:active {
        transform: scale(0.98);
    }

    /* Abas Customizadas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #0F131D;
        padding: 6px;
        border-radius: 16px;
        border: 1px solid #1A202C;
    }

    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 12px;
        color: #9CA3AF;
        font-weight: 700;
        font-size: 13px;
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
# 2. BASE DE DADOS E DADOS INICIAIS
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

# Garantir que chaves existam caso venham de versões antigas
if "caixinha_futuro" not in dados:
    dados["caixinha_futuro"] = 0.0
if "caixinha_sonho" not in dados:
    dados["caixinha_sonho"] = 0.0

# ==========================================
# 3. PAINEL PRINCIPAL COM CARDS DINÂMICOS
# ==========================================
st.markdown(
    """
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div>
            <h2 style="margin:0; font-weight: 800; font-size: 22px; color: #FFF;">Finanças 18</h2>
            <p style="margin:0; color: #6B7280; font-size: 12px;">Seu Assistente de Patrimônio</p>
        </div>
        <div style="background-color: #1E293B; padding: 6px 12px; border-radius: 20px; border: 1px solid #334155; font-size: 11px; font-weight: 700; color: #38BDF8;">
            PRO 💎
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

patrimonio_total = (
    dados["saldo_conta"]
    + dados["caixinha_futuro"]
    + dados["caixinha_sonho"]
)

# Renderização Dinâmica: Monta a lista de cards ativos
cards_ativos = []

cards_ativos.append(
    f"""<div class="bank-card card-accent-blue">
        <div class="card-label">💳 Saldo Livre</div>
        <div class="card-value">R$ {dados['saldo_conta']:.2f}</div>
    </div>"""
)

if dados["caixinha_futuro"] > 0:
    cards_ativos.append(
        f"""<div class="bank-card card-accent-purple">
            <div class="card-label">🚀 Caixinha Futuro</div>
            <div class="card-value">R$ {dados['caixinha_futuro']:.2f}</div>
        </div>"""
    )

if dados["caixinha_sonho"] > 0:
    cards_ativos.append(
        f"""<div class="bank-card card-accent-gold">
            <div class="card-label">🔒 Caixinha Sonho</div>
            <div class="card-value">R$ {dados['caixinha_sonho']:.2f}</div>
        </div>"""
    )

cards_ativos.append(
    f"""<div class="bank-card card-accent-green">
        <div class="card-label">🌟 Patrimônio</div>
        <div class="card-value">R$ {patrimonio_total:.2f}</div>
    </div>"""
)

# Exibe os cards organizados em 2 colunas dinamicamente
for i in range(0, len(cards_ativos), 2):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(cards_ativos[i], unsafe_allow_html=True)
    if i + 1 < len(cards_ativos):
        with c2:
            st.markdown(cards_ativos[i + 1], unsafe_allow_html=True)

# Barra de Progresso Real
progresso = min(patrimonio_total / 62000.0, 1.0)
st.write(
    f"🎯 **Progresso da Meta (R$ 62.000):** `{progresso * 100:.2f}%` atingido"
)
st.progress(progresso)
st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. OPERAÇÕES E NAVEGAÇÃO
# ==========================================
aba_lancamento, aba_guia, aba_extrato, aba_projecao = st.tabs(
    ["➕ Lançar", "📍 Investir", "📑 Extrato", "📈 Meta 18"]
)

# ABA 1: LANÇAMENTOS DINÂMICOS COM RESGATE
with aba_lancamento:
    st.subheader("Nova Operação")

    opcao = st.radio(
        "Selecione a ação:",
        [
            "💸 Gastei Dinheiro",
            "📥 Recebi Dinheiro",
            "🔒 Guardar na Caixinha",
            "🔓 Resgatar da Caixinha",
        ],
        horizontal=True,
    )

    # Formulário adaptativo dependendo da escolha
    if opcao == "🔒 Guardar na Caixinha":
        caixinha_destino = st.selectbox(
            "Qual Caixinha quer alimentar?",
            ["Caixinha Futuro", "Caixinha Sonho"],
        )
    elif opcao == "🔓 Resgatar da Caixinha":
        caixinhas_disponiveis = []
        if dados["caixinha_futuro"] > 0:
            caixinhas_disponiveis.append("Caixinha Futuro")
        if dados["caixinha_sonho"] > 0:
            caixinhas_disponiveis.append("Caixinha Sonho")

        if not caixinhas_disponiveis:
            st.warning("⚠️ Você não possui saldo em nenhuma Caixinha para resgatar.")
            caixinha_origem = None
        else:
            caixinha_origem = st.selectbox(
                "De qual Caixinha quer resgatar?", caixinhas_disponiveis
            )

    valor_input = st.number_input(
        "Valor (R$):", min_value=1.00, step=5.00, value=50.00
    )
    descricao_input = st.text_input(
        "Descrição / Motivo:", placeholder="Ex: Mesada, Sorvete, Resgate urgente"
    )

    if st.button("🚀 Confirmar Operação"):
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
            st.session_state["ultima_acao"] = (
                f"receber|{valor_input}|{dados['saldo_conta']}"
            )
            st.balloons()

        elif opcao == "🔒 Guardar na Caixinha":
            if valor_input > dados["saldo_conta"]:
                st.error("⚠️ Saldo Livre na conta insuficiente para investir esse valor!")
            else:
                dados["saldo_conta"] -= valor_input
                if caixinha_destino == "Caixinha Futuro":
                    dados["caixinha_futuro"] += valor_input
                else:
                    dados["caixinha_sonho"] += valor_input

                dados["transacoes"].append(
                    {
                        "Data": data_hoje,
                        "Tipo": "Aporte",
                        "Origem": caixinha_destino,
                        "Valor": valor_input,
                        "Categoria": descricao_input or "Investimento",
                    }
                )
                salvar_dados(dados)
                st.session_state["ultima_acao"] = (
                    f"guardar|{valor_input}|{caixinha_destino}"
                )
                st.snow()

        elif opcao == "🔓 Resgatar da Caixinha":
            if caixinha_origem is None:
                st.error("Nenhuma Caixinha disponível.")
            else:
                saldo_disponivel = (
                    dados["caixinha_futuro"]
                    if caixinha_origem == "Caixinha Futuro"
                    else dados["caixinha_sonho"]
                )
                if valor_input > saldo_disponivel:
                    st.error(
                        f"⚠️ Valor maior do que o disponível na {caixinha_origem} (R$ {saldo_disponivel:.2f})."
                    )
                else:
                    if caixinha_origem == "Caixinha Futuro":
                        dados["caixinha_futuro"] -= valor_input
                    else:
                        dados["caixinha_sonho"] -= valor_input

                    dados["saldo_conta"] += valor_input
                    dados["transacoes"].append(
                        {
                            "Data": data_hoje,
                            "Tipo": "Resgate",
                            "Origem": caixinha_origem,
                            "Valor": valor_input,
                            "Categoria": descricao_input or "Resgate de investimento",
                        }
                    )
                    salvar_dados(dados)
                    st.session_state["ultima_acao"] = (
                        f"resgatar|{valor_input}|{caixinha_origem}"
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
            st.session_state["ultima_acao"] = f"gastar|{valor_input}"

        time.sleep(0.5)
        st.rerun()

    # Exibe caixa de instruções personalizada após a última ação
    if "ultima_acao" in st.session_state:
        partes = st.session_state["ultima_acao"].split("|")
        tipo_acao = partes[0]

        if tipo_acao == "receber":
            v, saldo_atual = float(partes[1]), float(partes[2])
            excesso = max(0.0, saldo_atual - 100.0)
            st.markdown(
                f"""
                <div style="background-color: #0F172A; padding: 18px; border-radius: 16px; border: 2px solid #10B981; margin-top: 15px;">
                    <h4 style="color: #10B981; margin:0;">🎉 DINHEIRO RECEBIDO! (+R$ {v:.2f})</h4>
                    <p style="color: #E2E8F0; font-size: 14px; margin-top: 8px;">
                        Passo 1: Mantenha R$ 100,00 na conta para seus gastos.<br>
                        👉 <b>Passo 2 (Ação no Nubank):</b> Transfira R$ {excesso:.2f} para a Caixinha "Futuro" para rende 100% do CDI!
                    </p>
                </div>
            """,
                unsafe_allow_html=True,
            )

        elif tipo_acao == "guardar":
            v, dest = float(partes[1]), partes[2]
            st.markdown(
                f"""
                <div style="background-color: #0F172A; padding: 18px; border-radius: 16px; border: 2px solid #8B5CF6; margin-top: 15px;">
                    <h4 style="color: #A855F7; margin:0;">🔒 INVESTIMENTO REGISTRADO!</h4>
                    <p style="color: #E2E8F0; font-size: 14px; margin-top: 8px;">
                        👉 <b>Ação no Nubank:</b> Abra o app do Nubank, acesse as Caixinhas e guarde <b>R$ {v:.2f}</b> na <b>{dest}</b>.
                    </p>
                </div>
            """,
                unsafe_allow_html=True,
            )

        elif tipo_acao == "resgatar":
            v, orig = float(partes[1]), partes[2]
            st.markdown(
                f"""
                <div style="background-color: #0F172A; padding: 18px; border-radius: 16px; border: 2px solid #F59E0B; margin-top: 15px;">
                    <h4 style="color: #F59E0B; margin:0;">🔓 RESGATE REGISTRADO!</h4>
                    <p style="color: #E2E8F0; font-size: 14px; margin-top: 8px;">
                        👉 <b>Ação no Nubank:</b> Abra o app do Nubank, vá na <b>{orig}</b> e clique em <b>Resgatar R$ {v:.2f}</b> para seu Saldo Livre.
                    </p>
                </div>
            """,
                unsafe_allow_html=True,
            )

        elif tipo_acao == "gastar":
            v = float(partes[1])
            st.warning(f"💸 Gasto de R$ {v:.2f} descontado do seu Saldo Livre em Conta.")

# ABA 2: GUIA DE INVESTIMENTO DINÂMICO
with aba_guia:
    st.subheader("🤖 Recomendação de Aporte")

    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.markdown(
            f"""
            <div style="background-color: #0F172A; padding: 20px; border-radius: 18px; border: 2px solid #10B981;">
                <h4 style="color: #10B981; margin:0; font-weight: 800;">🎯 HORA DE APORTAR!</h4>
                <p style="color: #E2E8F0; font-size: 14px; margin-top: 8px;">
                    Seu saldo livre está em <b>R$ {dados['saldo_conta']:.2f}</b>. Como sua reserva do mês é de R$ 100,00, invista a diferença!
                </p>
                <hr style="border-color: #1E293B; margin: 12px 0;">
                <p style="color: #38BDF8; font-size: 15px; font-weight: 700; margin: 0;">
                    👉 Transfira R$ {excesso:.2f} para a Caixinha "Futuro" (100% CDI) no app do Nubank.
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    elif dados["saldo_conta"] == 100.00:
        st.markdown(
            """
            <div style="background-color: #0F172A; padding: 20px; border-radius: 18px; border: 2px solid #38BDF8;">
                <h4 style="color: #38BDF8; margin:0; font-weight: 800;">✅ CONTA BALANCEADA!</h4>
                <p style="color: #E2E8F0; font-size: 14px; margin-top: 8px;">
                    Seus R$ 100,00 estão garantidos no Saldo Livre para seus gastos do mês.
                </p>
                <hr style="border-color: #1E293B; margin: 12px 0;">
                <p style="color: #94A3B8; font-size: 13px; margin: 0;">
                    Todo o restante do seu patrimônio já está rendendo 100% do CDI nas Caixinhas.
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            f"Seu saldo livre está em R$ {dados['saldo_conta']:.2f}. Complete para R$ 100,00 na próxima entrada!"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📌 Estrutura do Seu Plano:")
    st.write("• **Saldo em Conta:** Manter R$ 100,00 para lanches e saídas do mês.")
    st.write(
        "• **Caixinha 'Futuro' (100% CDI):** Guardar todas as mesadas e valores acumulados."
    )
    if dados["caixinha_sonho"] > 0:
        st.write(
            "• **Caixinha 'Sonho' (RDB):** Manter até Novembro/2026 e consolidar tudo na Caixinha Futuro no vencimento."
        )

# ABA 3: EXTRATO COMPLETO
with aba_extrato:
    st.subheader("Histórico do Seu Dinheiro")
    if len(dados["transacoes"]) > 0:
        df = pd.DataFrame(dados["transacoes"])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ABA 4: PROJEÇÃO LIMPA
with aba_projecao:
    st.subheader("📈 Projeção do Patrimônio")
    st.caption("Simulação baseada nos aportes de R$ 600/mês + 100% do CDI acumulado")

    anos = [2026, 2027, 2028, 2029, 2030, 2031, 2032]
    valores = [patrimonio_total]
    acumulado = patrimonio_total

    for idx in range(1, len(anos)):
        acumulado = (acumulado + (600 * 12)) * 1.095
        valores.append(acumulado)

    for ano, val in zip(anos, valores):
        pct = min(val / 62000.0, 1.0)
        st.markdown(
            f"""
            <div style="background-color: #0F172A; padding: 12px 16px; border-radius: 12px; margin-bottom: 8px; border: 1px solid #1E293B;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #94A3B8; font-weight: 700;">Ano {ano}</span>
                    <span style="color: #10B981; font-weight: 800;">R$ {val:,.2f}</span>
                </div>
                <div style="background-color: #1E293B; height: 6px; border-radius: 3px; overflow: hidden;">
                    <div style="background-color: #8B5CF6; width: {pct * 100}%; height: 100%;"></div>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    st.success(f"🚀 **Estimativa Final aos 18 Anos (2032):** ~R$ {valores[-1]:,.2f}")

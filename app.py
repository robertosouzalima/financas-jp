import json
import os
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO E ESTADO DA SESSÃO
# ==========================================
st.set_page_config(page_title="Finanças 18", page_icon="🏦", layout="wide", initial_sidebar_state="collapsed")

if "tema" not in st.session_state:
    st.session_state["tema"] = "Escuro"
if "modo_pais" not in st.session_state:
    st.session_state["modo_pais"] = False

# ==========================================
# 2. SISTEMA DE CORES (CLARO / ESCURO)
# ==========================================
temas = {
    "Escuro": {
        "bg": "#09090B", "card": "#18181B", "text": "#F9FAFB", "sub": "#A1A1AA", 
        "border": "#27272A", "glass": "rgba(24, 24, 27, 0.8)", "glass_text": "#A1A1AA",
        "glass_active": "#FAFAFA", "glass_active_bg": "#27272A"
    },
    "Claro": {
        "bg": "#F3F4F6", "card": "#FFFFFF", "text": "#111827", "sub": "#6B7280", 
        "border": "#E5E7EB", "glass": "rgba(255, 255, 255, 0.8)", "glass_text": "#6B7280",
        "glass_active": "#111827", "glass_active_bg": "#E5E7EB"
    }
}
t = temas[st.session_state["tema"]]

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; background-color: {t['bg']} !important; color: {t['text']} !important; }}
    header, #MainMenu, footer, .stDeployButton {{ visibility: hidden !important; display: none !important; }}
    .block-container {{ padding: 1rem 1rem 6.5rem 1rem !important; }}

    /* BARRA FLUTUANTE (LIQUID GLASS) */
    [data-baseweb="tab-list"] {{
        position: fixed !important; bottom: 20px !important; left: 50% !important; transform: translateX(-50%) !important;
        z-index: 999999 !important; background: {t['glass']} !important; backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important; border: 1px solid {t['border']} !important;
        border-radius: 40px !important; padding: 6px !important; box-shadow: 0 10px 30px rgba(0,0,0,0.15) !important;
        display: flex !important; width: 92% !important; max-width: 400px !important; gap: 4px !important;
    }}
    [data-baseweb="tab-border"], [data-baseweb="tab-highlight"] {{ display: none !important; }}
    [data-baseweb="tab"] {{
        background: transparent !important; border-radius: 30px !important; color: {t['glass_text']} !important;
        font-weight: 700 !important; font-size: 11px !important; padding: 12px 0px !important;
        border: none !important; margin: 0 !important; flex: 1 !important; text-align: center !important; transition: 0.2s !important;
    }}
    [aria-selected="true"] {{ background: {t['glass_active_bg']} !important; color: {t['glass_active']} !important; }}

    /* CARDS FINANCEIROS (FLAT & CLEAN) */
    .fin-card {{
        background: {t['card']}; border: 1px solid {t['border']}; border-radius: 16px; padding: 16px; margin-bottom: 12px;
    }}
    .c-title {{ font-size: 11px; color: {t['sub']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
    .c-val {{ font-size: 24px; color: {t['text']}; font-weight: 800; margin-top: 4px; }}
    
    /* CORES SÓLIDAS SIMPLES */
    .c-blue {{ border-left: 4px solid #3B82F6; }}
    .c-purple {{ border-left: 4px solid #8B5CF6; }}
    .c-gold {{ border-left: 4px solid #F59E0B; }}
    .c-green {{ border-left: 4px solid #10B981; }}

    /* LISTA DE EXTRATO NATIVA */
    .list-row {{
        display: flex; justify-content: space-between; align-items: center; background: {t['card']};
        border: 1px solid {t['border']}; border-radius: 12px; padding: 14px; margin-bottom: 8px;
    }}
    .list-title {{ font-size: 14px; font-weight: 700; color: {t['text']}; }}
    .list-sub {{ font-size: 11px; color: {t['sub']}; margin-top: 4px; }}
    .val-pos {{ font-size: 15px; font-weight: 800; color: #10B981; }}
    .val-neg {{ font-size: 15px; font-weight: 800; color: #EF4444; }}

    /* BOTÃO PRINCIPAL */
    .stButton>button {{
        width: 100%; border-radius: 12px; height: 50px; font-weight: 700; font-size: 15px;
        background: #111827; color: #FFFFFF; border: none; transition: 0.2s;
    }}
    .stButton>button:active {{ transform: scale(0.97); }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. DADOS
# ==========================================
ARQUIVO_DADOS = "dados_financas.json"
DADOS_INICIAIS = {
    "saldo_conta": 100.00, "caixinha_futuro": 966.55, "caixinha_sonho": 971.85,
    "transacoes": [
        {"Data": "03/10/2026", "Tipo": "Aporte", "Origem": "Sistema", "Valor": 966.55, "Categoria": "Saldo Inicial", "Conta": "Caixinha Futuro"},
        {"Data": "03/10/2026", "Tipo": "Aporte", "Origem": "Sistema", "Valor": 971.85, "Categoria": "Saldo Inicial", "Conta": "Caixinha Sonho"}
    ]
}

def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f: return json.load(f)
        except: return DADOS_INICIAIS
    return DADOS_INICIAIS

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f: json.dump(dados, f, indent=4, ensure_ascii=False)

dados = carregar_dados()
if "transacoes" not in dados: dados["transacoes"] = []
patrimonio_total = dados["saldo_conta"] + dados["caixinha_futuro"] + dados["caixinha_sonho"]

# ==========================================
# 4. MENU TOPO: CONFIGURAÇÕES & MODO PAIS
# ==========================================
col_titulo, col_config = st.columns([3, 1])
with col_titulo:
    st.markdown(f"<h2 style='margin:0; font-weight:800; font-size:20px;'>🏦 Finanças 18</h2>", unsafe_allow_html=True)
    if st.session_state["modo_pais"]:
        st.markdown(f"<span style='background:#3B82F6; color:#FFF; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:700;'>👀 MODO SUPERVISÃO (PAIS)</span>", unsafe_allow_html=True)

with col_config:
    with st.popover("⚙️ Ajustes"):
        st.markdown("**Tema Visual**")
        novo_tema = st.radio("Escolha o tema:", ["Escuro", "Claro"], index=0 if st.session_state["tema"] == "Escuro" else 1, label_visibility="collapsed")
        if novo_tema != st.session_state["tema"]:
            st.session_state["tema"] = novo_tema
            st.rerun()
            
        st.divider()
        st.markdown("**Acesso dos Pais**")
        if not st.session_state["modo_pais"]:
            senha = st.text_input("Código de Acesso:", type="password")
            if st.button("Entrar"):
                if senha == "1234":
                    st.session_state["modo_pais"] = True
                    st.rerun()
                else:
                    st.error("Código incorreto.")
        else:
            if st.button("Sair do Modo Pais"):
                st.session_state["modo_pais"] = False
                st.rerun()

st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

# ==========================================
# 5. ABAS DA BARRA FLUTUANTE
# ==========================================
if st.session_state["modo_pais"]:
    aba_painel, aba_extrato, aba_projecao = st.tabs(["Painel", "Extrato", "Projeção"])
else:
    aba_painel, aba_lancar, aba_extrato, aba_projecao = st.tabs(["Painel", "Lançar", "Extrato", "Projeção"])

# ------------------------------------------
# ABA 1: PAINEL DE CONTROLE
# ------------------------------------------
with aba_painel:
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"""<div class="fin-card c-blue"><div class="c-title">💳 Saldo Livre</div><div class="c-val">R$ {dados['saldo_conta']:.2f}</div></div>""", unsafe_allow_html=True)
    with c2: st.markdown(f"""<div class="fin-card c-green"><div class="c-title">🌟 Patrimônio</div><div class="c-val">R$ {patrimonio_total:.2f}</div></div>""", unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    if dados["caixinha_futuro"] > 0:
        with c3: st.markdown(f"""<div class="fin-card c-purple"><div class="c-title">🚀 C. Futuro</div><div class="c-val">R$ {dados['caixinha_futuro']:.2f}</div></div>""", unsafe_allow_html=True)
    if dados["caixinha_sonho"] > 0:
        with c4: st.markdown(f"""<div class="fin-card c-gold"><div class="c-title">🔒 C. Sonho</div><div class="c-val">R$ {dados['caixinha_sonho']:.2f}</div></div>""", unsafe_allow_html=True)

    progresso = min(patrimonio_total / 62000.0, 1.0)
    st.write(f"🎯 **Meta R$ 62.000:** `{progresso * 100:.2f}%` atingido")
    st.progress(progresso)

# ------------------------------------------
# ABA 2: LANÇAR (Oculta para os Pais)
# ------------------------------------------
if not st.session_state["modo_pais"]:
    with aba_lancar:
        st.markdown("### Nova Operação")
        opcao = st.selectbox("O que você quer fazer?", [
            "📥 Recebi Dinheiro", 
            "🔒 Guardar na Caixinha", 
            "🔓 Resgatar da Caixinha", 
            "📈 Registrar Rendimento (Juros)", 
            "💸 Gastei Dinheiro"
        ])

        if opcao in ["🔒 Guardar na Caixinha", "📈 Registrar Rendimento (Juros)"]: 
            caixinha_alvo = st.selectbox("Qual Caixinha?", ["Futuro", "Sonho"])
        elif opcao == "🔓 Resgatar da Caixinha":
            opcoes_resgate = []
            if dados["caixinha_futuro"] > 0: opcoes_resgate.append("Futuro")
            if dados["caixinha_sonho"] > 0: opcoes_resgate.append("Sonho")
            if not opcoes_resgate:
                st.warning("⚠️ Nenhuma Caixinha possui saldo.")
                caixinha_alvo = None
            else: caixinha_alvo = st.selectbox("De qual Caixinha?", opcoes_resgate)

        # O rendimento geralmente quebra em centavos, então o step vira R$ 0.10 para facilitar
        passo_valor = 0.10 if opcao == "📈 Registrar Rendimento (Juros)" else 5.00
        valor = st.number_input("Valor (R$):", min_value=0.01, step=passo_valor, value=50.00)
        desc = st.text_input("Descrição:", placeholder="Ex: Rendimento do mês, Mesada, Uber...")

        if st.button("Confirmar Lançamento"):
            data = str(pd.Timestamp.now().strftime("%d/%m/%Y"))
            
            if opcao == "📥 Recebi Dinheiro":
                dados["saldo_conta"] += valor
                dados["transacoes"].append({"Data": data, "Tipo": "Entrada", "Valor": valor, "Categoria": desc or "Recebimento", "Conta": "Conta"})
                st.success("Recebido com sucesso!")
                
            elif opcao == "🔒 Guardar na Caixinha":
                if valor > dados["saldo_conta"]: st.error("Saldo Livre insuficiente.")
                else:
                    dados["saldo_conta"] -= valor
                    if caixinha_alvo == "Futuro": dados["caixinha_futuro"] += valor
                    else: dados["caixinha_sonho"] += valor
                    dados["transacoes"].append({"Data": data, "Tipo": "Aporte", "Valor": valor, "Categoria": desc or "Aporte", "Conta": f"C. {caixinha_alvo}"})
                    st.success("Guardado com sucesso!")
                    
            elif opcao == "🔓 Resgatar da Caixinha":
                if caixinha_alvo:
                    saldo_disp = dados["caixinha_futuro"] if caixinha_alvo == "Futuro" else dados["caixinha_sonho"]
                    if valor > saldo_disp: st.error("Saldo da caixinha insuficiente.")
                    else:
                        if caixinha_alvo == "Futuro": dados["caixinha_futuro"] -= valor
                        else: dados["caixinha_sonho"] -= valor
                        dados["saldo_conta"] += valor
                        dados["transacoes"].append({"Data": data, "Tipo": "Resgate", "Valor": valor, "Categoria": desc or "Resgate", "Conta": f"C. {caixinha_alvo}"})
                        st.success("Resgatado com sucesso!")
                        
            elif opcao == "📈 Registrar Rendimento (Juros)":
                if caixinha_alvo == "Futuro": dados["caixinha_futuro"] += valor
                else: dados["caixinha_sonho"] += valor
                dados["transacoes"].append({"Data": data, "Tipo": "Rendimento", "Valor": valor, "Categoria": desc or "Rendimento CDI", "Conta": f"C. {caixinha_alvo}"})
                st.success(f"Juros registrados na Caixinha {caixinha_alvo}! 🚀")
                
            elif opcao == "💸 Gastei Dinheiro":
                dados["saldo_conta"] -= valor
                dados["transacoes"].append({"Data": data, "Tipo": "Saída", "Valor": valor, "Categoria": desc or "Gasto", "Conta": "Conta"})
                st.warning("Gasto registrado.")
            
            salvar_dados(dados)
            time.sleep(1)
            st.rerun()

# ------------------------------------------
# ABA 3: EXTRATO
# ------------------------------------------
with aba_extrato:
    st.markdown("### Extrato")
    if len(dados["transacoes"]) > 0:
        for t in reversed(dados["transacoes"]):
            # Rendimentos, Entradas e Resgates ficam verde (+). Saídas ficam vermelho (-).
            if t["Tipo"] in ["Entrada", "Resgate", "Rendimento"]: css_val, sinal = "val-pos", "+"
            else: css_val, sinal = "val-neg", "-"
            
            st.markdown(f"""
            <div class="list-row">
                <div style="display: flex; flex-direction: column;">
                    <span class="list-title">{t['Categoria']}</span>
                    <span class="list-sub">{t['Data']} • {t['Tipo']} • {t['Conta']}</span>
                </div>
                <div class="{css_val}">{sinal} R$ {t['Valor']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("Nenhuma movimentação.")

# ------------------------------------------
# ABA 4: PROJEÇÃO
# ------------------------------------------
with aba_projecao:
    st.markdown("### Projeção 18 Anos")
    st.caption("Aportes de R$ 600/mês + 100% CDI")

    anos, valores = [2026, 2027, 2028, 2029, 2030, 2031, 2032], [patrimonio_total]
    atual = patrimonio_total
    for i in range(1, len(anos)):
        atual = (atual + (600 * 12)) * 1.095
        valores.append(atual)

    # Gráfico Nativo
    df_grafico = pd.DataFrame({"Ano": anos, "Patrimônio": valores})
    st.line_chart(df_grafico.set_index("Ano"))

    # Tabela Simples
    df_tabela = df_grafico.copy()
    df_tabela["Patrimônio"] = df_tabela["Patrimônio"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.dataframe(df_tabela, use_container_width=True, hide_index=True)

import json
import os
import random
import time
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAÇÃO E ESTADO DA SESSÃO
# ==========================================
st.set_page_config(page_title="Finanças 18", page_icon="🏦", layout="wide", initial_sidebar_state="collapsed")

if "tema" not in st.session_state:
    st.session_state["tema"] = "Escuro"
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# ==========================================
# 2. SISTEMA DE CORES BLINDADO
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
    
    html, body, [data-testid="stAppViewContainer"], .stApp {{ 
        font-family: 'Inter', sans-serif !important; 
        background-color: {t['bg']} !important; 
        color: {t['text']} !important; 
    }}
    
    header, #MainMenu, footer, .stDeployButton {{ visibility: hidden !important; display: none !important; }}
    .block-container {{ padding: 1rem 1rem 7.5rem 1rem !important; }}

    /* BARRA FLUTUANTE (LIQUID GLASS) */
    [data-baseweb="tab-list"] {{
        position: fixed !important; bottom: 20px !important; left: 50% !important; transform: translateX(-50%) !important;
        z-index: 999999 !important; background: {t['glass']} !important; backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important; border: 1px solid {t['border']} !important;
        border-radius: 40px !important; padding: 6px !important; box-shadow: 0 10px 30px rgba(0,0,0,0.15) !important;
        display: flex !important; width: 92% !important; max-width: 440px !important; gap: 2px !important;
    }}
    [data-baseweb="tab-border"], [data-baseweb="tab-highlight"] {{ display: none !important; }}
    [data-baseweb="tab"] {{
        background: transparent !important; border-radius: 30px !important; color: {t['glass_text']} !important;
        font-weight: 700 !important; font-size: 10px !important; padding: 12px 0px !important;
        border: none !important; margin: 0 !important; flex: 1 !important; text-align: center !important; transition: 0.2s !important;
    }}
    [aria-selected="true"] {{ background: {t['glass_active_bg']} !important; color: {t['glass_active']} !important; }}

    /* CARDS */
    .fin-card {{
        background: {t['card']}; border: 1px solid {t['border']}; border-radius: 16px; padding: 16px; margin-bottom: 12px;
    }}
    .c-title {{ font-size: 11px; color: {t['sub']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
    .c-val {{ font-size: 24px; color: {t['text']}; font-weight: 800; margin-top: 4px; }}
    
    .c-blue {{ border-left: 4px solid #3B82F6; }}
    .c-purple {{ border-left: 4px solid #8B5CF6; }}
    .c-gold {{ border-left: 4px solid #F59E0B; }}
    .c-green {{ border-left: 4px solid #10B981; }}

    /* LISTA DE EXTRATO */
    .list-row {{
        display: flex; justify-content: space-between; align-items: center; background: {t['card']};
        border: 1px solid {t['border']}; border-radius: 12px; padding: 14px; margin-bottom: 8px;
    }}
    .list-title {{ font-size: 14px; font-weight: 700; color: {t['text']}; }}
    .list-sub {{ font-size: 11px; color: {t['sub']}; margin-top: 4px; }}
    
    .val-pos {{ font-size: 15px; font-weight: 800; color: #10B981; }}
    .val-neg {{ font-size: 15px; font-weight: 800; color: #EF4444; }}
    .val-neu {{ font-size: 15px; font-weight: 800; color: #3B82F6; }}

    .stButton>button {{
        width: 100%; border-radius: 12px; height: 50px; font-weight: 700; font-size: 15px;
        background: #111827; color: #FFFFFF; border: none; transition: 0.2s;
    }}
    .stButton>button:active {{ transform: scale(0.97); }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. GERENCIADOR DE DADOS SEGUROS
# ==========================================
ARQUIVO_DADOS = "dados_financas.json"

def gerar_pin_aleatorio():
    return str(random.randint(1000, 9999))

DADOS_INICIAIS = {
    "nome_conta": "Meu Cofre",
    "pin_seguranca": gerar_pin_aleatorio(),
    "saldo_conta": 100.00, 
    "caixinha_futuro": 966.55, 
    "caixinha_sonho": 971.85,
    "recorrencias": {"renda_mensal": 500.00, "gasto_mensal": 0.00},
    "transacoes": []
}

def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f: 
                data = json.load(f)
                if "pin_seguranca" not in data:
                    data["pin_seguranca"] = gerar_pin_aleatorio()
                if "recorrencias" not in data:
                    data["recorrencias"] = {"renda_mensal": 500.00, "gasto_mensal": 0.00}
                return data
        except: 
            return DADOS_INICIAIS
    return DADOS_INICIAIS

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f: 
        json.dump(dados, f, indent=4, ensure_ascii=False)

dados = carregar_dados()
if "transacoes" not in dados: dados["transacoes"] = []

patrimonio_total = dados["saldo_conta"] + dados["caixinha_futuro"] + dados["caixinha_sonho"]

# ==========================================
# 4. MENU TOPO: AJUSTES & PRIVACIDADE TOTAL
# ==========================================
col_titulo, col_config = st.columns([3, 1])
with col_titulo:
    st.markdown(f"<h2 style='margin:0; font-weight:800; font-size:20px;'>🏦 Finanças 18</h2>", unsafe_allow_html=True)
    if st.session_state["autenticado"]:
        st.markdown(f"<span style='background:#10B981; color:#FFF; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:700;'>🔓 MESTRE / PAIS AUTORIZADO</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"<span style='color:#A1A1AA; font-size:12px;'>Modo Seguro Ativo • {dados['nome_conta']}</span>", unsafe_allow_html=True)

with col_config:
    with st.popover("⚙️ Ajustes"):
        st.markdown("**Tema Visual**")
        novo_tema = st.radio("Tema:", ["Escuro", "Claro"], index=0 if st.session_state["tema"] == "Escuro" else 1, label_visibility="collapsed")
        if novo_tema != st.session_state["tema"]:
            st.session_state["tema"] = novo_tema
            st.rerun()
            
        st.divider()
        st.markdown("**Área Restrita (Pais / Auditoria)**")
        
        if not st.session_state["autenticado"]:
            st.caption(f"Dica de PIN gerado p/ este app: `{dados['pin_seguranca']}`")
            senha_digitada = st.text_input("Digite o PIN:", type="password")
            if st.button("Desbloquear Acesso"):
                if senha_digitada == dados["pin_seguranca"]:
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("PIN incorreto.")
        else:
            if st.button("Bloquear / Sair"):
                st.session_state["autenticado"] = False
                st.rerun()

        st.divider()
        st.markdown("**Configurações da Conta**")
        novo_nome = st.text_input("Nome da Conta:", value=dados["nome_conta"])
        novo_pin = st.text_input("Alterar PIN (4 dígitos):", value=dados["pin_seguranca"], type="password")
        
        if st.button("Salvar Alterações"):
            dados["nome_conta"] = novo_nome
            dados["pin_seguranca"] = novo_pin
            salvar_dados(dados)
            st.success("Atualizado com sucesso!")
            time.sleep(0.5)
            st.rerun()

        if st.button("⚠️ Resetar Sistema"):
            salvar_dados(DADOS_INICIAIS)
            st.rerun()

st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

# ==========================================
# 5. ABAS DA BARRA FLUTUANTE (5 ABAS)
# ==========================================
aba_painel, aba_lancar, aba_investir, aba_extrato, aba_projecao = st.tabs(["Painel", "Lançar", "Investir", "Extrato", "Projeção"])

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
# ABA 2: LANÇAR (Com data, horário e programação)
# ------------------------------------------
with aba_lancar:
    st.markdown("### Nova Operação")
    opcao = st.selectbox("O que você quer fazer?", [
        "📥 Recebi Dinheiro", 
        "🔒 Guardar na Caixinha", 
        "🔓 Resgatar da Caixinha", 
        "📈 Registrar Rendimento (Juros)", 
        "💸 Gastei Dinheiro",
        "⚙️ Configurar Renda / Gastos Fixos"
    ])

    if opcao == "⚙️ Configurar Renda / Gastos Fixos":
        st.markdown("#### Programação Recorrente")
        r_mensal = st.number_input("Renda Fixa Mensal (R$):", value=float(dados["recorrencias"]["renda_mensal"]))
        g_mensal = st.number_input("Saída Fixa Mensal (R$):", value=float(dados["recorrencias"]["gasto_mensal"]))
        if st.button("Salvar Programação"):
            dados["recorrencias"]["renda_mensal"] = r_mensal
            dados["recorrencias"]["gasto_mensal"] = g_mensal
            salvar_dados(dados)
            st.success("Planejamento atualizado com sucesso!")
            time.sleep(0.5)
            st.rerun()
    else:
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

        passo_valor = 0.10 if opcao == "📈 Registrar Rendimento (Juros)" else 5.00
        valor = st.number_input("Valor (R$):", min_value=0.01, step=passo_valor, value=50.00)
        desc = st.text_input("Descrição:", placeholder="Ex: Mesada, Uber, Rendimento...")

        if st.button("Confirmar Lançamento"):
            # Data e Horário em tempo real exato
            data_hora = str(pd.Timestamp.now().strftime("%d/%m/%Y às %H:%M"))
            
            if opcao == "📥 Recebi Dinheiro":
                dados["saldo_conta"] += valor
                dados["transacoes"].append({"Data": data_hora, "Tipo": "Entrada", "Valor": valor, "Categoria": desc or "Recebimento", "Conta": "Conta"})
                st.success("Recebido com sucesso!")
                
            elif opcao == "🔒 Guardar na Caixinha":
                if valor > dados["saldo_conta"]: st.error("Saldo Livre insuficiente.")
                else:
                    dados["saldo_conta"] -= valor
                    if caixinha_alvo == "Futuro": dados["caixinha_futuro"] += valor
                    else: dados["caixinha_sonho"] += valor
                    dados["transacoes"].append({"Data": data_hora, "Tipo": "Aporte", "Valor": valor, "Categoria": desc or "Aporte", "Conta": f"C. {caixinha_alvo}"})
                    st.success("Guardado com sucesso!")
                    
            elif opcao == "🔓 Resgatar da Caixinha":
                if caixinha_alvo:
                    saldo_disp = dados["caixinha_futuro"] if caixinha_alvo == "Futuro" else dados["caixinha_sonho"]
                    if valor > saldo_disp: st.error("Saldo da caixinha insuficiente.")
                    else:
                        if caixinha_alvo == "Futuro": dados["caixinha_futuro"] -= valor
                        else: dados["caixinha_sonho"] -= valor
                        dados["saldo_conta"] += valor
                        dados["transacoes"].append({"Data": data_hora, "Tipo": "Resgate", "Valor": valor, "Categoria": desc or "Resgate", "Conta": f"C. {caixinha_alvo}"})
                        st.success("Resgatado com sucesso!")
                        
            elif opcao == "📈 Registrar Rendimento (Juros)":
                if caixinha_alvo == "Futuro": dados["caixinha_futuro"] += valor
                else: dados["caixinha_sonho"] += valor
                dados["transacoes"].append({"Data": data_hora, "Tipo": "Rendimento", "Valor": valor, "Categoria": desc or "Rendimento CDI", "Conta": f"C. {caixinha_alvo}"})
                st.success(f"Juros registrados na Caixinha {caixinha_alvo}!")
                
            elif opcao == "💸 Gastei Dinheiro":
                dados["saldo_conta"] -= valor
                dados["transacoes"].append({"Data": data_hora, "Tipo": "Saída", "Valor": valor, "Categoria": desc or "Gasto", "Conta": "Conta"})
                st.warning("Gasto registrado.")
            
            salvar_dados(dados)
            time.sleep(1)
            st.rerun()

# ------------------------------------------
# ABA 3: SUGESTÕES DE INVESTIMENTO BASEADAS NA REGRA DOS R$ 100
# ------------------------------------------
with aba_investir:
    st.markdown("### 💡 Estratégia Inteligente de Aporte")
    st.caption("Baseada estritamente na sua regra fixa de manter R$ 100,00 livres na conta.")

    # Análise de saldo baseada nos R$ 100 fixos
    if dados["saldo_conta"] > 100.00:
        excesso = dados["saldo_conta"] - 100.00
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10B981; padding: 14px; border-radius: 12px; margin-bottom: 15px;">
            <strong style="color: #10B981;">🚀 Sugestão Imediata:</strong><br>
            Você tem <b>R$ {dados['saldo_conta']:.2f}</b> no saldo livre. Como sua regra obriga manter exatamente <b>R$ 100,00</b>, recomendamos investir o excedente de <b>R$ {excesso:.2f}</b> hoje mesmo!
        </div>
        """, unsafe_allow_html=True)
    elif dados["saldo_conta"] == 100.00:
        st.markdown(f"""
        <div style="background: rgba(59, 130, 246, 0.1); border: 1px solid #3B82F6; padding: 14px; border-radius: 12px; margin-bottom: 15px;">
            <strong style="color: #3B82F6;">✅ Conta Perfeitamente Alinhada:</strong><br>
            Seu saldo livre está cravado em <b>R$ 100,00</b>. Todo o restante do seu dinheiro já está rentabilizando.
        </div>
        """, unsafe_allow_html=True)
    else:
        falta = 100.00 - dados["saldo_conta"]
        st.markdown(f"""
        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid #EF4444; padding: 14px; border-radius: 12px; margin-bottom: 15px;">
            <strong style="color: #EF4444;">⚠️ Atenção ao Saldo:</strong><br>
            Você está abaixo dos R$ 100,00 essenciais (faltam R$ {falta:.2f}). Evite novos aportes até regularizar sua base.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="fin-card">
        <h4 style="margin:0 0 8px 0; font-size:15px; color:#3B82F6;">1. Alocação Diária (100% CDI)</h4>
        <p style="font-size:12px; color:#A1A1AA; margin:0;">
            <b>Onde:</b> Caixinha de Resgate Diário.<br>
            <b>Meta:</b> Abrigar todo o excedente gerado pelas suas receitas programadas (como os R$ 500/mês definidos), garantindo liquidez total.
        </p>
    </div>

    <div class="fin-card">
        <h4 style="margin:0 0 8px 0; font-size:15px; color:#8B5CF6;">2. Renda Fixa de Longo Prazo (RDB)</h4>
        <p style="font-size:12px; color:#A1A1AA; margin:0;">
            <b>Onde:</b> Caixinha Sonho / Prazos longos.<br>
            <b>Meta:</b> Reter valores que você não vai mexer até 2032, potencializando juros compostos sem tentação de resgate antecipado.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------
# ABA 4: EXTRATO
# ------------------------------------------
with aba_extrato:
    st.markdown("### Extrato de Transações")
    if len(dados["transacoes"]) > 0:
        for t in reversed(dados["transacoes"]):
            if t["Tipo"] in ["Entrada", "Rendimento"]:
                css_val, sinal = "val-pos", "+"
            elif t["Tipo"] == "Saída":
                css_val, sinal = "val-neg", "-"
            else: 
                css_val, sinal = "val-neu", ""
            
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
        st.write("Nenhuma movimentação registrada.")

# ------------------------------------------
# ABA 5: PROJEÇÃO COM RECORRÊNCIA CONFIGURADA
# ------------------------------------------
with aba_projecao:
    st.markdown("### Projeção Dinâmica 18 Anos")
    renda_prog = dados["recorrencias"]["renda_mensal"]
    gasto_prog = dados["recorrencias"]["gasto_mensal"]
    aporte_liquido_mensal = max(0, renda_prog - gasto_prog)
    
    st.caption(f"Considerando renda líquida programada de R$ {aporte_liquido_mensal:,.2f}/mês + 100% CDI")

    anos = [2026, 2027, 2028, 2029, 2030, 2031, 2032]
    valores = [patrimonio_total]
    atual = patrimonio_total
    
    for i in range(1, len(anos)):
        # Acumula o valor líquido anual baseado na programação configurada
        atual = (atual + (aporte_liquido_mensal * 12)) * 1.095
        valores.append(atual)

    anos_str = [str(a) for a in anos]
    valores_limpos = [round(v, 2) for v in valores]
    
    df_grafico = pd.DataFrame({"Ano": anos_str, "Patrimônio": valores_limpos})
    st.bar_chart(df_grafico.set_index("Ano"))

    df_tabela = df_grafico.copy()
    df_tabela["Patrimônio"] = df_tabela["Patrimônio"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.dataframe(df_tabela, use_container_width=True, hide_index=True)

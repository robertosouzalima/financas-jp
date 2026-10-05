# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography   (cryptography = verificação do Face ID)
Rodar: streamlit run app.py   |   Deploy: Streamlit Cloud (HTTPS é obrigatório para Face ID)
Conta pré-carregada (dados do Nubank): nome João, senha 5102, PIN dos pais 5102.
Contas novas começam zeradas.
"""
import csv, io, json, random, time, html, hmac, hashlib, base64, secrets, threading, urllib.request, unicodedata
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse
import streamlit as st
import streamlit.components.v1 as components

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding
    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ = None

st.set_page_config(page_title="FUTURE", page_icon="🚀", layout="centered", initial_sidebar_state="collapsed")
CODIGO, PIN_PAIS = "5102", "5102"
try:
    SB_URL, SB_KEY = str(st.secrets["supabase_url"]).rstrip("/"), str(st.secrets["supabase_key"])
except Exception:
    SB_URL = SB_KEY = ""

SEED = "joao"
ARQ = Path(__file__).with_name("future_db.json")
RESERVA = 100.0
CAIXAS = {"futuro": ("Caixinha Futuro", "pur", "Principal · rende 100% do CDI"),
          "sonho": ("Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato")}
TIPOS = {"in": ("📥", "Recebi dinheiro"), "out": ("💸", "Gastei dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Rendimento / juros"), "mov": ("🔁", "Mover entre caixinhas"),
         "del": ("🗑️", "Caixinha zerada")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"], ["Início", "Extrato", "Projeção", "Ideias"]

PALETAS = {
    "Roxo Neón": {"pur": "#b57bff", "blue": "#4aa3ff", "gold": "#f0c24b"},
    "Verde Esmeralda": {"pur": "#3fdc78", "blue": "#38ef7d", "gold": "#f39c12"},
    "Azul Deep": {"pur": "#3a86ff", "blue": "#00f5d4", "gold": "#ff006e"},
    "Ouro Luxo": {"pur": "#f7b801", "blue": "#f18701", "gold": "#ffd166"},
    "Vermelho Carmesim": {"pur": "#ff4d6d", "blue": "#ff758f", "gold": "#ffb3c1"}
}

for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", paleta="Roxo Neón", tab=0, nav=False, dir="R", fx=None, msg=None,
                   tent=0, bloq=0.0, chal=secrets.token_urlsafe(32), fid_done=None).items():
    st.session_state.setdefault(_k, _v)


# ---------------------------------------------------------------- utilidades
def agora():
    return datetime.now(TZ) if TZ else datetime.now()


def brl(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "R$ " + s


def kf(v):
    return f"{v / 1000:.1f}".replace(".", ",") + "k"


def fmt_dt(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")


def chave(n):
    n = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")
    return " ".join(n.lower().split())


def b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mk(txt):
    s = secrets.token_bytes(16)
    return s.hex(), hashlib.pbkdf2_hmac("sha256", txt.encode(), s, 150000).hex()


def confere(txt, s, h):
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", txt.encode(), bytes.fromhex(s), 150000).hex(), h)


def calcular_ano_fim(nasc):
    """Calcula automaticamente o ano em que o usuário completa 18 anos com base na data de nascimento."""
    if not nasc:
        return 2032
    return nasc.year + 18


def nova_conta(nome, senha, pin, nasc=str(date(2014, 1, 1)), seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {"futuro": 0.0, "sonho": 0.0}, "extrato": [], "tema": "dark", "paleta": "Roxo Neón",
         "nasc": nasc, "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:  # dados reais do Nubank: total R$ 2.038,40
        d["livre"], d["caixas"] = 100.00, {"futuro": 966.55, "sonho": 971.85}
        d["cfg"].update(renda=600.0, guardar=500.0)
        d["nasc"] = str(date(2014, 1, 1)) # João completaria 18 anos em 2032
    return {"nome": nome, "s": s, "h": h, "ps": ps, "ph": ph, "fid": {}, "d": d}


def _sb(metodo, path="", corpo=None):
    h = {"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(SB_URL + "/rest/v1/future_db" + path, headers=h, method=metodo,
                                 data=None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode())
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


@st.cache_resource
def db():
    d = None
    if SB_URL:
        try:
            r = json.loads(_sb("GET", "?id=eq.db&select=dados"))
            d = r[0]["dados"] if r else None
        except Exception:
            d = None
    if d is None:
        try:
            d = json.loads(ARQ.read_text("utf-8"))
        except Exception:
            d = {}
    c = d.setdefault("contas", {})
    if "projeto18" in c and SEED not in c:
        c[SEED] = c.pop("projeto18")
        if c[SEED]["nome"] == "Minha Conta" or c[SEED]["nome"] == "João":
            c[SEED]["nome"] = "João"
        c[SEED]["s"], c[SEED]["h"] = mk(CODIGO)
        c[SEED]["ps"], c[SEED]["ph"] = mk(PIN_PAIS)
    if SEED not in c:
        c[SEED] = nova_conta("João", CODIGO, PIN_PAIS, seed=True)
    return d


@st.cache_resource
def trava():
    return threading.Lock()


@st.cache_resource
def sessoes():
    return {}


def salvar():
    with trava():
        try:
            if SB_URL:
                _sb("POST", "", [{"id": "db", "dados": db()}])
            else:
                ARQ.write_text(json.dumps(db(), ensure_ascii=False), "utf-8")
        except Exception:
            st.session_state["warn"] = "⚠️ Não consegui salvar os dados. Verifique a conexão com o banco."


# ------------------------------------------------------------------ visual
def gerar_css():
    p = PALETAS.get(st.session_state.get("paleta", "Roxo Neón"), PALETAS["Roxo Neón"])
    temas = {
        "dark": f":root{{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:#3fdc78;--red:#ff6b62;--glass:rgba(34,34,48,.58)}}",
        "light": f":root{{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:#12843f;--red:#d9342b;--glass:rgba(255,255,255,.68)}}",
    }
    css_base = """
    .stApp{background:var(--bg)!important;color:var(--tx);overflow-x:hidden;font-family:-apple-system,"SF Pro Text",Roboto,system-ui,sans-serif;transition:background 0.3s ease}
    header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
    .block-container{max-width:480px!important;padding:1.2rem 1rem 10rem!important}
    .stApp p,.stApp label,.stApp h1,.stApp li,[data-testid="stDialog"] *{color:var(--tx)}
    .stApp input,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"]{background:var(--c2)!important;color:var(--tx)!important;border-radius:14px!important}
    div[role="dialog"]{background:var(--c1)!important;border-radius:28px!important}
    button[kind="secondary"],[data-testid="stBaseButton-secondary"]{background:var(--c2);border:1px solid var(--ln);border-radius:16px}
    button[kind="secondary"] p,[data-testid="stBaseButton-secondary"] p{color:var(--tx)}
    button[kind="primary"],[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--pur),var(--blue))!important;border:0!important;border-radius:16px!important}
    button[kind="primary"] *,[data-testid="stBaseButton-primary"] *{color:#fff!important}
    [data-testid="stForm"]{border:0;padding:0;background:transparent}
    .hd h1{margin:0;font-size:26px;letter-spacing:-.03em;padding:0}.hd{margin-bottom:16px}
    .login{text-align:center;padding:7vh 0 18px;animation:slR .6s cubic-bezier(.2,.8,.2,1)}
    .login h1{font-size:30px;letter-spacing:-.03em;margin:8px 0 4px;padding:0}.logo{font-size:56px;animation:glow 3s ease-in-out infinite}
    @keyframes glow{50%{transform:scale(1.08);filter:drop-shadow(0 0 18px var(--pur))}}
    .card{background:linear-gradient(145deg,var(--c1),var(--c2));border:1px solid color-mix(in srgb,var(--c,var(--ln)) 50%,transparent);border-radius:26px;padding:18px;box-shadow:9px 9px 22px var(--s1),-5px -5px 16px var(--s2);margin-bottom:16px

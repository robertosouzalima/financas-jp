# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography
Rodar: streamlit run app.py
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
    if seed:
        d["livre"], d["caixas"] = 100.00, {"futuro": 966.55, "sonho": 971.85}
        d["cfg"].update(renda=600.0, guardar=500.0)
        d["nasc"] = str(date(2014, 1, 1))
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
        if c[SEED]["nome"] in ("Minha Conta", "João"):
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
            st.session_state["warn"] = "⚠️ Não consegui salvar os dados."


def gerar_css():
    p = PALETAS.get(st.session_state.get("paleta", "Roxo Neón"), PALETAS["Roxo Neón"])
    is_dark = st.session_state.get("tema", "dark") == "dark"
    
    bg = "#07070b" if is_dark else "#eceef4"
    c1 = "#16161f" if is_dark else "#fff"
    c2 = "#0e0e15" if is_dark else "#f3f4f9"
    tx = "#f4f4f8" if is_dark else "#14141c"
    mu = "#8b8b9a" if is_dark else "#656575"
    ln = "rgba(255,255,255,.09)" if is_dark else "rgba(0,0,0,.09)"
    s1 = "rgba(0,0,0,.6)" if is_dark else "rgba(120,125,150,.3)"
    s2 = "rgba(255,255,255,.04)" if is_dark else "rgba(255,255,255,.95)"
    glass = "rgba(34,34,48,.58)" if is_dark else "rgba(255,255,255,.68)"
    grn = "#3fdc78" if is_dark else "#12843f"
    red = "#ff6b62" if is_dark else "#d9342b"

    return f"""
    :root {{
        --bg: {bg}; --c1: {c1}; --c2: {c2}; --tx: {tx};

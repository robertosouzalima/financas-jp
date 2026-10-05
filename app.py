# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography
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

TIPOS = {"in": ("📥", "Recebi dinheiro"), "out": ("💸", "Gastei dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Rendimento / juros"), "mov": ("🔁", "Mover entre caixinhas"),
         "del": ("🗑️", "Caixinha zerada")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"], ["Início", "Extrato", "Projeção", "Ideias"]

PALETAS = {
    "Padrão": {"pur": "#b57bff", "blue": "#4aa3ff", "gold": "#f0c24b", "grn": "#3fdc78", "red": "#ff6b62"},
    "Neon": {"pur": "#ff00ff", "blue": "#00ffff", "gold": "#ffff00", "grn": "#00ff00", "red": "#ff0000"},
    "Oceano": {"pur": "#3a0ca3", "blue": "#4361ee", "gold": "#4cc9f0", "grn": "#2ec4b6", "red": "#e71d36"},
    "Outono": {"pur": "#6a4c93", "blue": "#1982c4", "gold": "#ffca3a", "grn": "#8ac926", "red": "#ff595e"}
}

for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", paleta="Padrão", tab=0, nav=False, dir="R", fx=None, msg=None,
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

def nova_conta(nome, senha, pin, nasc="2014-01-01", seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {}, "minhas_caixas": {}, "extrato": [], "tema": "dark", "paleta": "Padrão",
         "nasc": nasc, "tutorial": not seed, 
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None, "meta": 10000.0, "reserva": 100.0},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:  
        d["livre"] = 100.00
        d["minhas_caixas"] = {
            "futuro": {"nome": "Caixinha Futuro", "cor": "pur", "desc": "Principal · rende 100% do CDI"},
            "sonho": {"nome": "Caixinha Sonho", "cor": "gold", "desc": "Rende 100% do CDI · resgate imediato"}
        }
        d["caixas"] = {"futuro": 966.55, "sonho": 971.85}
        d["cfg"].update(renda=600.0, guardar=500.0, meta=62000.0, reserva=100.0)
    return {"nome": nome, "s": s, "h": h, "ps": ps, "ph": ph, "fid": {}, "d": d}

def _sb(metodo, path="", corpo=None):
    h = {"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(SB_URL + "/rest/v1/future" + path, headers=h, method=metodo,
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
            pass
    if d is None:
        try:
            d = json.loads(ARQ.read_text("utf-8"))
        except Exception:
            d = {}
    c = d.setdefault("contas", {})
    if "projeto18" in c and SEED not in c:
        c[SEED] = c.pop("projeto18")
        if c[SEED]["nome"] == "Minha Conta":
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
def get_css(tema, paleta_nome):
    p = PALETAS.get(paleta_nome, PALETAS["Padrão"])
    t = {
        "dark": f":root{{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']};--glass:rgba(34,34,48,.58)}}",
        "light": f":root{{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']};--glass:rgba(255,255,255,.68)}}",
    }
    return t.get(tema, t["dark"])

CSS_BASE = """
.stApp{background:var(--bg)!important;color:var(--tx);overflow-x:hidden;font-family:-apple-system,"SF Pro Text",Roboto,system-ui,sans-serif;transition:background .3s}
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

/* Login Centralizado */
.login{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:12vh 0 18px;animation:iosR .6s cubic-bezier(0.32, 0.72, 0, 1)}
.login h1{font-size:36px;letter-spacing:-.04em;margin:12px 0 4px;padding:0;width:100%;text-align:center}
.logo{font-size:56px;animation:glow 3s ease-in-out infinite}
@keyframes glow{50%{transform:scale(1.08);filter:drop-shadow(0 0 18px var(--pur))}}

.card{background:linear-gradient(145deg,var(--c1),var(--c2));border:1px solid color-mix(in srgb,var(--c,var(--ln)) 50%,transparent);border-radius:26px;padding:18px;box-shadow:9px 9px 22px var(--s1),-5px -5px 16px var(--s2);margin-bottom:16px}
.k{color:var(--mu);font-size:13px}.lb{font-size:14px;font-weight:600}.big{font-size:34px;font-weight:700;letter-spacing:-.035em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.pg{height:8px;border-radius:9px;background:var(--ln);overflow:hidden;margin:6px 0}.pg i{display:block;height:100%;border-radius:9px;background:linear-gradient(90deg,var(--blue),var(--grn))}
.as{font-size:15px;border-style:dashed}.sup{background:color-mix(in srgb,var(--gold) 16%,transparent);border:1px solid var(--gold);border-radius:18px;padding:12px 14px;margin-bottom:16px;font-size:14px}
.tx{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--ln)}.tx:last-child{border:0}.tx .g{flex:1;min-width:0}
.ic{width:40px;height:40px;border-radius:14px;background:var(--c2);display:grid;place-items:center;font-size:19px;flex:none;border:1px solid var(--ln)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th{color:var(--mu);font-weight:500;text-align:right;padding:6px 0}td{padding:10px 0;text-align:right;border-top:1px solid var(--ln)}th:first-child,td:first-child{text-align:left}
.bar{fill:var(--grn);opacity:.9}.bt{fill:var(--mu);font-size:10px;text-anchor:middle}.tl{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1.2}
.al{display:flex;justify-content:space-between;align-items:baseline}.al b{font-size:20px}
.st-key-nav,.st-key-bolha{position:fixed;left:16px;bottom:calc(66px + env(safe-area-inset-bottom,0px));z-index:999;width:auto!important}

/* Animação Suave iOS 27 da Navegação */
.st-key-nav{width:min(calc(100vw - 32px),420px)!important;display:flex!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:6px;overflow:hidden;background:var(--glass);backdrop-filter:blur(28px) saturate(180%);-webkit-backdrop-filter:blur(28px) saturate(180%);border:1px solid var(--ln);border-radius:34px;box-shadow:0 14px 40px var(--s1),inset 0 1px 0 rgba(255,255,255,.14);animation:stretch .6s cubic-bezier(0.32, 0.72, 0, 1) forwards}
@keyframes stretch{from{width:58px!important;padding:0;opacity:0}}
.st-key-nav>div{width:auto!important;animation:fi .5s .15s cubic-bezier(0.32, 0.72, 0, 1) both}
@keyframes fi{from{opacity:0;transform:translateX(-16px)}}
.st-key-aba{flex:1!important}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:8px 0;border-radius:26px;cursor:pointer;transition:background .3s}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:10px;line-height:1.3;font-weight:600;text-align:center;word-spacing:100vw;margin:0;opacity:.5

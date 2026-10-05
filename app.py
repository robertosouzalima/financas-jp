# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40)."""
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
         "del": ("🗑️", "Caixinha apagada")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias", "⚙️ Ajustes"], ["Início", "Extrato", "Projeção", "Ideias", "Ajustes da Conta"]

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
    d = {"livre": 0.0, "caixas": {}, "caixas_meta": {}, "extrato": [], "tema": "dark", "paleta": "Padrão",
         "nasc": nasc,
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None, 
                 "meta": 10000.0, "reserva": 100.0, "tutorial": not seed},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:  
        d["livre"] = 100.00
        d["caixas"] = {"futuro": 966.55, "sonho": 971.85}
        d["caixas_meta"] = {
            "futuro": ["Caixinha Futuro", "pur", "Principal · rende 100% do CDI"],
            "sonho": ["Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato"]
        }
        d["cfg"].update(renda=600.0, guardar=500.0, meta=62000.0, reserva=100.0, tutorial=False)
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
            st.session_state["warn"] = "⚠️ Não consegui salvar os dados. Verifique a conexão."

# ------------------------------------------------------------------ visual
def get_css(tema, paleta_nome):
    p = PALETAS.get(paleta_nome, PALETAS["Padrão"])
    t = {
        "dark": f":root{{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']};--glass:rgba(34,34,48,.58)}}",
        "light": f":root{{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']};--glass:rgba(255,255,255,.68)}}",
    }
    return t.get(tema, t["dark"])

CSS_BASE = """
html, body, [data-testid="stApp"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
    background: var(--bg) !important;
    background-color: var(--bg) !important;
    overscroll-behavior-y: none;
    margin: 0;
    padding: 0;
}
.stApp {
    color: var(--tx);
    overflow-x: hidden;
    font-family: -apple-system, "SF Pro Text", Roboto, system-ui, sans-serif;
    transition: background .3s;
}
header[data-testid="stHeader"], #MainMenu, footer { display: none !important; }
.block-container { max-width: 480px !important; padding: 1.2rem 1rem 10rem !important; margin: 0 auto !important; }
.stApp p, .stApp label, .stApp h1, .stApp li, [data-testid="stDialog"] * { color: var(--tx); }
.stApp input, [data-baseweb="select"]>div, [data-baseweb="input"], [data-baseweb="base-input"] { background: var(--c2) !important; color: var(--tx) !important; border-radius: 14px !important; }
div[role="dialog"] { background: var(--c1) !important; border-radius: 28px !important; }
button[kind="secondary"], [data-testid="stBaseButton-secondary"] { background: var(--c2); border: 1px solid var(--ln); border-radius: 16px; }
button[kind="secondary"] p, [data-testid="stBaseButton-secondary"] p { color: var(--tx); }
button[kind="primary"], [data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, var(--pur), var(--blue)) !important; border: 0 !important; border-radius: 16px !important; }
button[kind="primary"] *, [data-testid="stBaseButton-primary"] * { color: #fff !important; }
[data-testid="stForm"] { border: 0; padding: 0; background: transparent; }
.hd h1 { margin: 0; font-size: 26px; letter-spacing: -.03em; padding: 0; }
.hd { margin-bottom: 16px; }

/* LOGIN CENTRALIZADO COM ANIMAÇÃO DO FOGUETE */
.login {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    width: 100%;
    margin: 0 auto;
    padding: 7vh 0 18px;
    animation: slR .6s cubic-bezier(.25, 1, .5, 1);
}
.login h1 {
    font-size: 30px;
    letter-spacing: -.03em;
    margin: 8px 0 4px;
    padding: 0;
    width: 100%;
    text-align: center;
    display: block;
}
.logo {
    font-size: 56px;
    text-align: center;
    line-height: 1;
    display: inline-block;
    animation: rocketAnim 3.5s ease-in-out infinite;
}
@keyframes rocketAnim {
    0% { transform: translateY(0) scale(1) rotate(0deg); filter: drop-shadow(0 0 10px var(--pur)); }
    50% { transform: translateY(-12px) scale(1.08) rotate(-3deg); filter: drop-shadow(0 0 22px var(--blue)); }
    100% { transform: translateY(0) scale(1) rotate(0deg); filter: drop-shadow(0 0 10px var(--pur)); }
}
.login .k {
    width: 100%;
    text-align: center;
    display: block;
}

.card { background: linear-gradient(145deg, var(--c1), var(--c2)); border: 1px solid color-mix(in srgb, var(--c, var(--ln)) 50%, transparent); border-radius: 26px; padding: 18px; box-shadow: 9px 9px 22px var(--s1), -5px -5px 16px var(--s2); margin-bottom: 16px; }
.k { color: var(--mu); font-size: 13px; }
.lb { font-size: 14px; font-weight: 600; }
.big { font-size: 34px; font-weight: 700; letter-spacing: -.035em; margin: 2px 0 8px; font-variant-numeric: tabular-nums; }
.pg { height: 8px; border-radius: 9px; background: var(--ln); overflow: hidden; margin: 6px 0; }
.pg i { display: block; height: 100%; border-radius: 9px; background: linear-gradient(90deg, var(--blue), var(--grn)); }
.as { font-size: 15px; border-style: dashed; }
.sup { background: color-mix(in srgb, var(--gold) 16%, transparent); border: 1px solid var(--gold); border-radius: 18px; padding: 12px 14px; margin-bottom: 16px; font-size: 14px; }
.tx { display: flex; align-items: center; gap: 12px; padding: 13px 0; border-bottom: 1px solid var(--ln); }
.tx:last-child { border: 0; }
.tx .g { flex: 1; min-width: 0; }
.ic { width: 40px; height: 40px; border-radius: 14px; background: var(--c2); display: grid; place-items: center; font-size: 19px; flex: none; border: 1px solid var(--ln); }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th { color: var(--mu); font-weight: 500; text-align: right; padding: 6px 0; }
td { padding: 10px 0; text-align: right; border-top: 1px solid var(--ln); }
th:first-child, td:first-child { text-align: left; }
.bar { fill: var(--grn); opacity: .9; }
.bt { fill: var(--mu); font-size: 10px; text-anchor: middle; }
.tl { stroke: var(--gold); stroke-dasharray: 4 4; stroke-width: 1.2; }
.al { display: flex; justify-content: space-between; align-items: baseline; }
.al b { font-size: 20px; }

.st-key-nav, .st-key-bolha { position: fixed; left: 16px; bottom: calc(66px + env(safe-area-inset-bottom, 0px)); z-index: 999; width: auto !important; }
.st-key-nav { width: min(calc(100vw - 32px), 420px) !important; display: flex !important; flex-direction: row !important; align-items: center; gap: 4px !important; padding: 6px; overflow: hidden; background: var(--glass); backdrop-filter: blur(28px) saturate(180%); -webkit-backdrop-filter: blur(28px) saturate(180%); border: 1px solid var(--ln); border-radius: 34px; box-shadow: 0 14px 40px var(--s1), inset 0 1px 0 rgba(255,255,255,.14); animation: stretch .7s cubic-bezier(.16, 1, .3, 1) forwards; }
@keyframes stretch { from { width: 58px !important; padding: 0; opacity: 0; } }
.st-key-nav>div { width: auto !important; animation: fi .6s .15s cubic-bezier(.16, 1, .3, 1) both; }
@keyframes fi { from { opacity: 0; transform: translateX(-16px); } }
.st-key-aba { flex: 1 !important; }
.st-key-nav [role="radiogroup"] { display: flex; flex-wrap: nowrap; gap: 2px; width: 100%; }
.st-key-nav label { flex: 1; justify-content: center; margin: 0; padding: 8px 0; border-radius: 26px; cursor: pointer; transition: background .3s; }
.st-key-nav label>div:first-child { display: none; }
.st-key-nav label p { font-size: 10px; line-height: 1.3; font-weight: 600; text-align: center; word-spacing: 100vw; margin: 0; opacity: .55; transition: opacity .3s; }
.st-key-nav label p::first-line { font-size: 21px; }
.st-key-nav label:has(input:checked) { background: color-mix(in srgb, var(--pur) 26%, transparent); }
.st-key-nav label:has(input:checked) p { opacity: 1; }
.st-key-b_min button, .st-key-b_plus button, .st-key-bolha button, .st-key-b_tema button, .st-key-b_sair button { border-radius: 50%; padding: 0; background: var(--glass); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid var(--ln); }
.st-key-b_min button { width: 34px; height: 34px; }
.st-key-b_plus button { width: 46px; height: 46px; border: 0; background: linear-gradient(135deg, var(--pur), var(--blue)); }
.st-key-b_plus button p { color: #fff; font-size: 24px; line-height: 1; }
.st-key-bolha { animation: popin .4s cubic-bezier(.2, 1.4, .4, 1); }
.st-key-bolha button { width: 58px; height: 58px; font-size: 24px; box-shadow: 0 10px 30px var(--s1); }
@keyframes popin { from { transform: scale(.4); opacity: 0; } }
.st-key-b_tema, .st-key-b_sair { position: fixed; z-index: 1000; width: auto !important; top: calc(12px + env(safe-area-inset-top, 0px)); }
.st-key-b_tema { right: 66px; }
.st-key-b_sair { right: 14px; }
.st-key-b_tema button, .st-key-b_sair button { width: 44px; height: 44px; font-size: 18px; }
[class*="_fromR"] { animation: slR .6s cubic-bezier(0.25, 1, 0.5, 1) forwards; }
[class*="_fromL"] { animation: slL .6s cubic-bezier(0.25, 1, 0.5, 1) forwards; }
@keyframes slR { from { transform: translateX(50px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes slL { from { transform: translateX(-50px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.fx { position: fixed; inset: 0; pointer-events: none; z-index: 2000; overflow: hidden; }
.fx i { position: absolute; bottom: -50px; font-style: normal; opacity: 0; animation: rise 2.4s ease-out forwards; }
.fx b { position: absolute; left: 50%; top: 36%; font-size: 36px; color: var(--grn); opacity: 0; animation: pop 2.4s ease forwards; text-shadow: 0 4px 24px rgba(0,0,0,.35); }
@keyframes rise { 0% { transform: translateY(0) scale(.6); opacity: 0; } 15% { opacity: 1; } 100% { transform: translateY(-90vh) rotate(25deg) scale(1.1); opacity: 0; } }
@keyframes pop { 0% { opacity: 0; transform: translate(-50%, 30px) scale(.7); } 20% { opacity: 1; transform: translate(-50%, 0) scale(1.05); } 80% { opacity: 1; } 100% { opacity: 0; transform: translate(-50%, -40px); } }
html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp [data-baseweb], div[role="dialog"] p { font-family: Inter, -apple-system, "SF Pro Text", system-ui, sans-serif !important; }
.big, .hd h1, .login h1, .al b, .lb { font-family: "Plus Jakarta Sans", Inter, system-ui, sans-serif !important; }
.big, table, .tx b { font-variant-numeric: tabular-nums; }
@media (prefers-reduced-motion: reduce) { *, ::before, ::after { animation: none !important; transition: none !important; } }
"""
FONTES = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');"
st.markdown("<style>" + FONTES + get_css(st.session_state["tema"], st.session_state["paleta"]) + CSS_BASE + "</style>", unsafe_allow_html=True)

# Garante o preenchimento total do ecrã e remove bordas brancas (PWA / Modo App)
components.html("""
<script>
    const parentDoc = window.parent.document;
    const applyBg = () => {
        parentDoc.body.style.backgroundColor = 'var(--bg)';
        parentDoc.documentElement.style.backgroundColor = 'var(--bg)';
        parentDoc.body.style.margin = '0';
        parentDoc.body.style.padding = '0';
    };
    applyBg();
    setTimeout(applyBg, 100);
    setTimeout(applyBg, 500);
</script>
""", height=0, width=0)

try:
    db()
except Exception:
    st.error("Não consegui conectar ao banco de dados. Atualize a página.")
    st.stop()

# ------------------------------------------------- Face ID (WebAuthn / passkey)
FACEID_HTML = """<!DOCTYPE html><html><body style="margin:0;font-family:-apple-system,system-ui,sans-serif"><button id="b"></button><div id="m"></div><script>
const P=(t,d)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
const e64=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\\+/g,"-").replace(/\\//g,"_").replace(/=+$/,"");
const d64=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")),c=>c.charCodeAt(0));
const B=document.getElementById("b"),M=document.getElementById("m");let A={};
const done=v=>P("streamlit:setComponentValue",{value:Object.assign({n:Date.now()+Math.random()},v),dataType:"json"});
async function reg(){try{
const c=await navigator.credentials.create({publicKey:{challenge:d64(A.chal),rp:{name:"FUTURE",id:location.hostname},user:{id:new TextEncoder().encode(A.user),name:A.user,displayName:A.user},pubKeyCredParams:[{type:"public-key",alg:-7},{type:"public-key",alg:-257}],authenticatorSelection:{authenticatorAttachment:"platform",userVerification:"required"},timeout:60000}});
const r=c.response,L=JSON.parse(localStorage.getItem("future_auth")||"[]").filter(x=>x.id!=c.id);L.push({id:c.id,user:A.user});localStorage.setItem("future_auth",JSON.stringify(L));
done({kind:"reg",id:c.id,pk:e64(r.getPublicKey()),alg:r.getPublicKeyAlgorithm(),cd:e64(r.clientDataJSON)});
}catch(e){M.textContent="Não foi possível ativar ("+e.name+")"}}
async function get(){try{
const L=JSON.parse(localStorage.getItem("future_auth")||"[]");if(!L.length){M.textContent="Ative o Face ID nos Ajustes depois de entrar.";return}
const c=await navigator.credentials.get({publicKey:{challenge:d64(A.chal),rpId:location.hostname,allowCredentials:L.map(x=>({type:"public-key",id:d64(x.id)})),userVerification:"required",timeout:60000}});
const r=c.response,u=(L.find(x=>x.id==c.id)||{}).user;
done({kind:"get",id:c.id,user:u,ad:e64(r.authenticatorData),cd:e64(r.clientDataJSON),sg:e64(r.signature)});
}catch(e){M.textContent="Face ID cancelado."}}
addEventListener("message",ev=>{if(ev.data.type!="streamlit:render")return;A=ev.data.args;const d=A.tema=="dark";
document.body.style.color=d?"#8b8b9a":"#656575";M.style.cssText="font-size:12px;text-align:center;margin-top:6px";
B.style.cssText="width:100%;padding:14px;border-radius:16px;font-size:16px;font-weight:600;cursor:pointer;border:1px solid "+(d?"rgba(255,255,255,.14)":"rgba(0,0,0,.14)")+";background:"+(d?"#16161f":"#fff")+";color:"+(d?"#f4f4f8":"#14141c");
B.textContent=(A.modo=="reg"?"Ativar Face ID neste aparelho":"Entrar com Face ID");B.onclick=A.modo=="reg"?reg:get;P("streamlit:setFrameHeight",{height:88})});
P("streamlit:componentReady",{apiVersion:1});</script></body></html>"""
_cdir = Path(__file__).with_name("_faceid")
try:
    _cdir.mkdir(exist_ok=True)
    (_cdir / "index.html").write_text(FACEID_HTML, "utf-8")
except Exception:
    pass
FACEID = components.declare_component("faceid", path=str(_cdir))

def _cd(p, tipo):
    try:
        cd = json.loads(b64d(p["cd"]))
    except Exception:
        return None
    return cd if cd.get("type") == tipo and cd.get("challenge") == st.session_state["chal"] else None

def fid_registrar(u, p):
    cd = _cd(p, "webauthn.create")
    st.session_state["chal"] = secrets.token_urlsafe(32)
    if cd:
        db()["contas"][u]["fid"][p["id"]] = {"pk": p["pk"], "alg": p["alg"]}
        salvar()
    return bool(cd)

def fid_entrar(p):
    cd = _cd(p, "webauthn.get")
    st.session_state["chal"] = secrets.token_urlsafe(32)
    c = db()["contas"].get(p.get("user") or "")
    cr = c["fid"].get(p.get("id")) if c else None
    if not (cd and cr and HAS_CRYPTO):
        return None
    try:
        ad = b64d(p["ad"])
        host = urlparse(cd["origin"]).hostname or ""
        if ad[:32] != hashlib.sha256(host.encode()).digest() or not (ad[32] & 1 and ad[32] & 4):
            return None
        msg = ad + hashlib.sha256(b64d(p["cd"])).digest()
        pub, sig = serialization.load_der_public_key(b64d(cr["pk"])), b64d(p["sg"])
        if cr["alg"] == -7:
            pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))
        else:
            pub.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
        return p["user"]
    except Exception:
        return None

# ------------------------------------------------------------ login / sessão
def entrar(u, modo):
    tok = secrets.token_urlsafe(16)
    sessoes()[tok] = (u, modo)
    st.query_params["s"] = tok
    d = db()["contas"][u]["d"]
    st.session_state.update(u=u, modo=modo, tela="login", tent=0, tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
    st.rerun()

def _ir(t):
    st.session_state["tela"] = t

def _falha():
    st.session_state["tent"] += 1
    if st.session_state["tent"] >= 5:
        st.session_state.update(bloq=time.time() + 30, tent=0)
    st.error("Dados incorretos.")

def _espera():
    e = st.session_state["bloq"] - time.time()
    if e > 0:
        st.error(f"Muitas tentativas. Aguarde {int(e) + 1}s.")
    return e > 0

def tela_login():
    t = st.session_state["tela"]
    sub = {"login": "INICIAR SESSÃO", "criar": "CRIAR CONTA", "pais": "CONTROLE PARENTAL"}[t]
    st.markdown(f'<div class="login"><div class="logo">🚀</div><h1>FUTURE</h1><div class="k" style="letter-spacing:.2em">{sub}</div></div>', unsafe_allow_html=True)
    
    if t == "login":
        with st.form("f_login"):
            n = st.text_input("Nome", placeholder="Nome da conta", label_visibility="collapsed", max_chars=24)
            p = st.text_input("Senha", type="password", placeholder="Senha", label_visibility="collapsed")
            go = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if go and not _espera():
            c = db()["contas"].get(chave(n))
            if c and confere(p, c["s"], c["h"]):
                entrar(chave(n), "filho")
            else:
                _falha()
        if HAS_CRYPTO:
            r = FACEID(modo="get", chal=st.session_state["chal"], user="", tema=st.session_state["tema"], key="fid_get", default=None)
            if r and r.get("kind") == "get" and r["n"] != st.session_state["fid_done"]:
                st.session_state["fid_done"] = r["n"]
                u = fid_entrar(r)
                if u:
                    entrar(u, "filho")
                st.error("Face ID não reconhecido.")
        st.button("🛡️ Controle parental", key="b_pais", use_container_width=True, on_click=_ir, args=("pais",))
        st.button("Criar conta", key="b_criar", use_container_width=True, on_click=_ir, args=("criar",))
        if not SB_URL:
            st.caption("⚠ Armazenamento temporário: os dados podem ser apagados ao reiniciar.")
        return
        
    if t == "criar":
        with st.form("f_criar"):
            n = st.text_input("Nome da conta", max_chars=24)
            p = st.text_input("Senha (mín. 4 caracteres)", type="password")
            pin = st.text_input("PIN dos pais (4 números)", type="password", max_chars=4)
            nasc = st.date_input("Sua data de nascimento", value=date(2014, 1, 1), min_value=date(1900, 1, 1), max_value=date(2020, 12, 31), format="DD/MM/YYYY")
            go = st.form_submit_button("Criar conta", type="primary", use_container_width=True)
        if go:
            k = chave(n)
            if not 2 <= len(k) <= 24:
                st.error("Use um nome entre 2 e 24 caracteres.")
            elif k in db()["contas"]:
                st.error("Esse nome já existe.")
            elif len(p) < 4:
                st.error("Escolha outra senha (mín. 4 caracteres).")
            elif not (pin.isdigit() and len(pin) == 4):
                st.error("O PIN dos pais precisa ter exatamente 4 números.")
            else:
                db()["contas"][k] = nova_conta(n.strip(), p, pin, nasc=nasc.isoformat())
                salvar()
                entrar(k, "filho")
    else:
        with st.form("f_pais"):
            n = st.text_input("Nome da conta", max_chars=24)
            pin = st.text_input("PIN dos pais", type="password", max_chars=4)
            go = st.form_submit_button("Entrar em supervisão", type="primary", use_container_width=True)
        if go and not _espera():
            c = db()["contas"].get(chave(n))
            if c and confere(pin, c["ps"], c["ph"]):
                entrar(chave(n), "pais")
            else:
                _falha()
    st.button("← Voltar", key="b_volta", use_container_width=True, on_click=_ir, args=("login",))

if not st.session_state["u"]:
    r = sessoes().get(st.query_params.get("s"))
    if r and r[0] in db()["contas"]:
        d = db()["contas"][r[0]]["d"]
        st.session_state.update(u=r[0], modo=r[1], tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
        st.rerun()
if not st.session_state["u"]:
    tela_login()
    st.stop()

U, SUP = st.session_state["u"], st.session_state["modo"] == "pais"
CONTA = db()["contas"][U]
S = CONTA["d"]

# --- MIGRAÇÃO AUTOMÁTICA ---
if "caixas_meta" not in S:
    S["caixas_meta"] = {}
    if "futuro" in S.get("caixas", {}):
        S["caixas_meta"]["futuro"] = ["Caixinha Futuro", "pur", "Principal · rende 100% do CDI"]
    if "sonho" in S.get("caixas", {}):
        S["caixas_meta"]["sonho"] = ["Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato"]
if "tutorial" not in S["cfg"]:
    S["cfg"]["tutorial"] = False
    S["cfg"]["meta"] = 62000.0
    S["cfg"]["reserva"] = 100.0
# -------------------------------------------------------------

# ------------------------------------------------------------ regras de negócio
def total():
    return round(S["livre"] + sum(S.get("caixas", {}).values()), 2)

def reg(t, v, cx, obs, ts=None, dest=None):
    S["extrato"].append({"t": t, "v": round(v, 2), "c": cx, "d": dest, "o": obs, "ts": (ts or agora()).isoformat()})

def fx(valor):
    st.session_state["fx"] = {"txt": "+" + brl(valor), "n": int(time.time() * 1000)}

def fecha(msg=None):
    S["livre"] = round(S["livre"], 2)
    for k in S.get("caixas", {}):
        S["caixas"][k] = round(S["caixas"][k], 2)
    st.session_state["msg"] = msg or "Lançado em " + fmt_dt(S["extrato"][-1]["ts"])
    salvar()

def liberar_sonho():
    sd = S["cfg"].get("sonho_data")
    if sd and agora().date().isoformat() >= sd:
        if "sonho" in S.get("caixas", {}) and "futuro" in S.get("caixas", {}) and S["caixas"]["sonho"] > 0.004:
            mover("sonho", "futuro", S["caixas"]["sonho"], "Sonho liberada → Futuro")
        S["cfg"]["sonho_data"] = None
        salvar()

def aplicar(t, v, cx=None, obs=""):
    v = round(v, 2)
    reserva = S["cfg"].get("reserva", 100.0)
    if v <= 0:
        return "Informe um valor maior que zero."
    cxs = S.get("caixas", {})
    if t == "save":
        if S["livre"] - v < reserva - 1e-9:
            return f"A reserva fixa de {brl(reserva)} está protegida. Você pode guardar até {brl(max(0, S['livre'] - reserva))}."
        S["livre"] -= v
        cxs[cx] += v
    elif t == "take":
        if v > cxs[cx] + 1e-9:
            return f"Essa caixinha tem só {brl(cxs[cx])}."
        cxs[cx] -= v
        S["livre"] += v
    elif t == "yld":
        if cxs[cx] <= 0:
            return "Essa caixinha não tem saldo."
        cxs[cx] += v
    elif t == "out":
        if v > S["livre"] + 1e-9:
            return f"Saldo livre insuficiente ({brl(S['livre'])})."
        S["livre"] -= v
    else:
        S["livre"] += v
    reg(t, v, cx if t in ("save", "take", "yld") else None, obs)
    if t in ("in", "yld"):
        fx(v)
    fecha()
    return ""

def mover(o, d, v, obs=""):
    v = round(v, 2)
    if v <= 0:
        return "Informe um valor maior que zero."
    if v > S.get("caixas", {})[o] + 1e-9:
        nome_origem = S.get("caixas_meta", {}).get(o, ["Caixinha"])[0]
        return f"{nome_origem} tem só {brl(S['caixas'][o])}."
    S["caixas"][o] -= v
    S["caixas"][d] += v
    reg("mov", v, o, obs, dest=d)
    fecha()
    return ""

def excluir_caixinha(cx, resgatar):
    v = S.get("caixas", {})[cx]
    if resgatar:
        S["livre"] += v
        reg("take", v, cx, "Exclusão da caixinha")
    else:
        reg("del", v, cx, "Saldo removido do patrimônio")
    nome_cx = S.get("caixas_meta", {}).get(cx, ["Caixinha"])[0]
    S["caixas"].pop(cx, None)
    S["caixas_meta"].pop(cx, None)
    fecha(f"{nome_cx} excluída")

def creditar_mes():
    h = agora()
    a, m = S["ultimo_credito"].split("-")
    ult, atual = int(a) * 12 + int(m) - 1, h.year * 12 + h.month - 1
    if atual <= ult:
        return
    c = S["cfg"]
    g, n = min(c.get("guardar", 0.0), c.get("renda", 0.0)), 0
    primeira_cx = list(S.get("caixas", {}).keys())[0] if S.get("caixas", {}) else None
    
    for k in range(ult + 1, atual + 1):
        if c.get("renda", 0.0) <= 0 and c.get("gastos", 0.0) <= 0:
            break
        ano, mes = divmod(k, 12)
        ts = datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=TZ)
        
        if c.get("renda", 0.0) > 0:
            S["livre"] += c["renda"]
            reg("in", c["renda"], None, "Mesada/Renda automática", ts)
        
        if c.get("gastos", 0.0) > 0:
            S["livre"] -= c["gastos"]
            reg("out", c["gastos"], None, "Gastos fixos programados", ts)
            
        if g > 0 and primeira_cx:
            S["livre"] -= g
            S["caixas"][primeira_cx] += g
            reg("save", g, primeira_cx, "Aporte automático", ts)
        n += 1
    S["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    if n:
        fx(c.get("renda", 0.0))
        fecha("Transações mensais automáticas realizadas.")
    else:
        salvar()

def projetar():
    c, h = S["cfg"], agora()
    r = (1 + c["cdi"] / 100) ** (1 / 12) - 1
    t = total()
    b = ap = t
    n, linhas = 0, []
    
    try:
        nasc_date = date.fromisoformat(S.get("nasc", "2014-01-01"))
    except:
        nasc_date = date(2014, 1, 1)
        
    ano_fim = nasc_date.year + 18
    meta_val = c.get("meta", 62000.0)
    aporte = max(0, c.get("renda", 0.0) - c.get("gastos", 0.0))
    
    for ano in range(h.year, ano_fim + 1):
        for _ in range(12 - h.month if ano == h.year else 12):
            b = b * (1 + r) + aporte
            ap += aporte
            n += 1
        linhas.append((ano, ap, b - ap, b))
    
    g = (1 + r) ** n
    falta = max(0.0, (meta_val - t * g) / ((g - 1) / r)) if n and r > 0 else max(0.0, (meta_val - t) / n) if n else 0.0
    return linhas, falta, ano_fim, meta_val

def get_csv_proj():
    L, _, _, meta_val = projetar()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Ano", "Investido (R$)", "Juros (R$)", "Total (R$)", "% da meta"])
    for a, p, j, b in L:
        pc = b / meta_val * 100 if meta_val > 0 else 0
        w.writerow([a, f"{p:.2f}".replace(".", ","), f"{j:.2f}".replace(".", ","), f"{b:.2f}".replace(".", ","), f"{pc:.1f}".replace(".", ",") + "%"])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")

def relatorio_html():
    L, _, ano_fim, meta_val = projetar()
    fim = L[-1][3] if L else total()
    p = PALETAS[st.session_state.get("paleta", "Padrão")]
    aporte = S["cfg"].get("renda", 0.0) - S["cfg"].get("gastos", 0.0)
    
    html_out = (
        '<div style="background:#16161f; color:#f4f4f8; padding:30px; border-radius:24px; font-family:sans-serif; width:400px; box-shadow: 0 4px 20px rgba(0,0,0,0.5)">'
        '<div style="text-align:center; padding-bottom:15px;">'
        '<h2 style="color:' + p["pur"] + '; margin:0 0 5px 0">🚀 FUTURE - Projeção de Metas</h2>'
        '<p style="color:#8b8b9a; font-size:14px; margin:0">Conta: ' + html.escape(CONTA["nome"]) + ' | Fim: ' + str(ano_fim) + '</p>'
        '</div>'
        '<div style="background:#0e0e15; padding:20px; border-radius:16px; margin:15px 0; border: 1px solid rgba(255,255,255,0.05);">'
        '<div style="font-size:12px; color:#8b8b9a; text-transform:uppercase;">Patrimônio Projetado</div>'
        '<div style="font-size:32px; font-weight:bold; color:' + p["grn"] + '; margin:5px 0;">' + brl(fim) + '</div>'
        '<div style="font-size:14px; color:' + p["gold"] + ';">Meta alvo: ' + brl(meta_val) + '</div>'
        '</div>'
        '<div style="color:#8b8b9a; font-size:13px; line-height:1.6; padding-left:5px;">'
        '• Ponto de partida inicial: ' + brl(total()) + '<br>'
        '• Aporte líquido programado: ' + brl(aporte) + ' / mês<br>'
        '• Rendimento estimado: ' + str(S["cfg"]["cdi"]) + '% ao ano'
        '</div>'
        '</div>'
    )
    return html_out.encode("utf-8")

def get_csv_extrato():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Data", "Hora", "Tipo", "Caixinha", "Valor (R$)", "Observação"])
    for x in sorted(S["extrato"], key=lambda e: e["ts"]):
        d, obs = datetime.fromisoformat(x["ts"]), x["o"]
        if obs[:1] in ("=", "+", "-", "@"):
            obs = "'" + obs
        w.writerow([d.strftime("%d/%m/%Y"), d.strftime("%H:%M:%S"), TIPOS[x["t"]][1], destino(x), f"{x['v']:.2f}".replace(".", ","), obs])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")

def destino(x):
    s = S.get("caixas_meta", {}).get(x["c"], [""])[0] if x.get("c") else ""
    d = " → " + S.get("caixas_meta", {}).get(x["d"], [""])[0] if x.get("d") else ""
    return s + d

# ------------------------------------------------------------------ telas
def fx_html(d):
    random.seed(d["n"])
    itens = "".join(
        '<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
        % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
           random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return ('<div class="fx">' + itens + '<b>' + d["txt"] + '</b></div>')

def card(cor, tit, val, sub="", extra=""):
    return (
        '<div class="card" style="--c:var(--' + cor + ')">'
        '<div class="lb" style="color:var(--' + cor + ')">' + tit + '</div>'
        '<div class="big">' + val + '</div>' + extra +
        '<div class="k">' + sub + '</div></div>'
    )

def v_tutorial():
    try:
        nasc_date = date.fromisoformat(S.get("nasc", "2014-01-01"))
    except:
        nasc_date = date(2014, 1, 1)
    idade = agora().year - nasc_date.year
    
    if idade >= 18:
        texto_idade = f"Como você já tem {idade} anos, nossa projeção vai ajudá-lo a alavancar seu patrimônio financeiro daqui para frente!"
    else:
        texto_idade = f"Como você tem {idade} anos, vamos focar em fazer o seu dinheiro crescer até a maioridade!"
        
    return f"""
    <div class="card as" style="border-color:var(--pur); background:color-mix(in srgb,var(--pur) 10%,transparent)">
        <b style="color:var(--pur); font-size:16px;">👋 Bem-vindo ao FUTURE, {html.escape(CONTA["nome"])}!</b><br><br>
        Sua nova conta está pronta. {texto_idade}<br><br>
        <b>1. Criar uma Caixinha:</b> Clique no botão <b>＋</b> no menu inferior para <i>Criar Caixinha</i>. É lá que o dinheiro rende todos os meses.<br>
        <b>2. Sua Meta:</b> Vá para a aba ⚙️ <b>Ajustes</b> para definir o valor que deseja acumular e a sua Reserva Fixa.<br>
        <b>3. Gastos Mensais:</b> Muito importante! Vá na aba <b>Ajustes</b> e cadastre os seus <b>gastos mensais</b> e a sua renda para que o controle do que sobra seja calculado com perfeição.<br><br>
        <i>Quando estiver pronto, você pode desmarcar este tutorial nas opções de Ajustes.</i>
    </div>
    """

def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    _, _, ano_fim, meta_val = projetar()
    reserva = c.get("reserva", 100.0)
    pc = min(100, t / meta_val * 100) if meta_val > 0 else 0
    
    out = ""
    if c.get("tutorial", False):
        out += v_tutorial()

    if f > reserva + .005:
        msg = "Você tem <b>" + brl(f - reserva) + "</b> acima da reserva fixa. Consulte a aba de Ideias."
    elif f < reserva - .005:
        msg = "Atenção: faltam <b>" + brl(reserva - f) + "</b> para completar a sua reserva fixa."
    else:
        msg = "Sua reserva fixa está completa. Tudo em ordem."
    
    h = agora()
    prox = f"01/{h.month + 1:02d}/{h.year}" if h.month < 12 else f"01/01/{h.year + 1}"
    mesada = (
        "<br>Próxima entrada (Líquida) programada: " + prox
        if c.get("renda", 0.0) > 0 else "<br>Configure sua renda nos Ajustes."
    )
    
    pct = f"{pc:.1f}".replace(".", ",")
    out += card("grn", "Patrimônio total", brl(t), f"{pct}% da meta de {brl(meta_val)} até {ano_fim}", '<div class="pg"><i style="width:' + str(pc) + '%"></i></div>')
    out += '<div class="card as">💡 ' + msg + '</div>'
    out += card("blue", "Saldo livre", brl(f), "Proteção de reserva de emergência: " + brl(reserva) + mesada)
    
    for k, v in S.get("caixas", {}).items():
        meta_cx = S.get("caixas_meta", {}).get(k, ["Caixinha", "blue", ""])
        out += card(meta_cx[1], meta_cx[0], brl(v), meta_cx[2])
        
    return out

def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k">Nenhum lançamento registrado ainda.</div></div>'
    rows = ""
    for _, x in sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True):
        ic, nome = TIPOS[x["t"]]
        tr, ps = x["t"] in ("save", "take", "mov"), x["t"] in ("in", "yld")
        cor = "blue" if tr else "grn" if ps else "red"
        sg = {"save": "→ ", "take": "← ", "mov": "↔ "}.get(x["t"], "+" if ps else "−")
        det = (destino(x) + " · " if x.get("c") else "") + (html.escape(x["o"]) + " · " if x["o"] else "") + fmt_dt(x["ts"])
        rows += ('<div class="tx"><span class="ic">' + ic + '</span><div class="g"><b>' + nome + '</b><div class="k">' + det + '</div></div>'
                 '<b style="color:var(--' + cor + ')">' + sg + brl(x["v"]) + '</b></div>')
    return '<div class="card" style="padding:6px 16px">' + rows + '</div>'

def svg_barras(L, meta_val):
    W, H = 340, 210
    mx = max([meta_val] + [x[3] for x in L]) * 1.12 if meta_val > 0 else 1000.0
    bw = W / len(L) if len(L) > 0 else W
    ty = H - 24 - meta_val / mx * (H - 44)
    s = (
        '<svg viewBox="0 0 ' + str(W) + ' ' + str(H) + '" style="width:100%;height:auto;touch-action:pan-y">'
        '<line class="tl" x1="0" x2="' + str(W) + '" y1="' + f"{ty:.1f}" + '" y2="' + f"{ty:.1f}" + '"/>'
        '<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="' + f"{ty - 5:.1f}" + '">Meta ' + kf(meta_val) + '</text>'
    )
    for i, (ano, ap, j, b) in enumerate(L):
        h = b / mx * (H - 44)
        x = i * bw + bw * .17
        s += (
            '<rect class="bar" x="' + f"{x:.1f}" + '" y="' + f"{H - 24 - h:.1f}" + '" width="' + f"{bw * .66:.1f}" + '" height="' + f"{h:.1f}" + '" rx="7"/>'
            '<text class="bt" x="' + f"{x + bw * .33:.1f}" + '" y="' + f"{H - 28 - h:.1f}" + '">' + kf(b) + '</text>'
            '<text class="bt" x="' + f"{x + bw * .33:.1f}" + '" y="' + str(H - 7) + '">' + str(ano) + '</text>'
        )
    return s + "</svg>"

def v_proj():
    L, falta, ano_fim, meta_val = projetar()
    if not L:
        return card("grn", "Projeção", brl(total()), "Sem meses restantes na projeção.")
    fim = L[-1][3]
    ok = fim >= meta_val
    sub = (
        "Meta de " + brl(meta_val) + " atingida, com folga de " + brl(fim - meta_val) + "." if ok
        else "Para alcançar " + brl(meta_val) + ", aporte cerca de " + brl(falta) + " por mês."
    )
    tab = '<table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th></tr>'
    for a, p, j, b in L:
        tab += '<tr><td>' + str(a) + '</td><td>' + brl(p) + '</td><td style="color:var(--grn)">' + brl(j) + '</td><td><b>' + brl(b) + '</b></td></tr>'
    tab += '</table>'
    
    cdi = str(S["cfg"].get("cdi", 9.5)).replace(".", ",")
    aporte = S["cfg"].get("renda", 0.0) - S["cfg"].get("gastos", 0.0)
    return (
        card("grn" if ok else "gold", "Projeção até " + str(ano_fim), brl(fim), sub)
        + '<div class="card">' + svg_barras(L, meta_val) + '</div><div class="card">' + tab + '</div>'
        + '<div class="k" style="padding:0 6px">Ponto de partida base: ' + brl(total()) + '. Aporte líquido de ' + brl(aporte) + '/mês · Rendimento simulado a ' + cdi + '% a.a.</div>'
    )

def v_idea():
    reserva = S["cfg"].get("reserva", 100.0)
    ex = round(max(0.0, S["livre"] - reserva), 2)
    opc = [("Reserva de liquidez diária", 1.0 if ex < 50 else .4, "blue", "CDB ou RDB com liquidez diária rendendo aprox. 100% do CDI. Dinheiro disponível para imprevistos."),
           ("RDB de longo prazo", .35, "pur", "Prazos de 2 a 5 anos pagam taxas superiores ao CDI. Excelente para o longo prazo."),
           ("Tesouro IPCA+", .25, "gold", "Rende a inflação mais juros fixos, blindando seu poder de compra.")]
    if ex < 50:
        opc = opc[:1]
    sub = "Sugestão de divisão para esse valor:" if ex else "Seu saldo livre precisa passar de " + brl(reserva + 50) + " para liberar sugestões de longo prazo."
    out = card("blue", "Excedente acima da reserva", brl(ex), sub)
    if ex:
        for nome, p, cor, txt in opc:
            out += (
                '<div class="card" style="--c:var(--' + cor + ')"><div class="al"><span class="lb">' + nome + '</span>'
                '<b style="color:var(--' + cor + ')">' + brl(ex * p) + '</b></div><div class="k">' + str(round(p * 100)) + '% · ' + txt + '</div></div>'
            )
    return out + '<div class="k" style="padding:0 6px">Sugestões educacionais, não constituem recomendação de investimento.</div>'

def v_ajustes():
    c = S["cfg"]
    st.markdown('<div class="card as" style="border:none">Aqui você gerencia as configurações da sua conta, metas, rendas e gastos mensais.</div>', unsafe_allow_html=True)
    with st.form("f_ajustes"):
        nome = st.text_input("Nome da conta", CONTA["nome"], max_chars=24)
        paleta_escolhida = st.selectbox("Cor do aplicativo", list(PALETAS.keys()), index=list(PALETAS.keys()).index(S.get("paleta", "Padrão")))
        tutorial = st.checkbox("Exibir tutorial de início na tela Início", value=c.get("tutorial", False))
        
        st.divider()
        st.caption("🎯 SEUS OBJETIVOS")
        meta = st.number_input("Meta financeira aos 18 anos (R$)", min_value=0.0, value=float(c.get("meta", 10000.0)), step=1000.0, format="%.2f")
        reserva = st.number_input("Tamanho ideal da Reserva Fixa (R$)", min_value=0.0, value=float(c.get("reserva", 100.0)), step=100.0, format="%.2f")
        
        st.divider()
        st.caption("💰 FINANÇAS E GASTOS (ENTRA TODO DIA 1)")
        renda = st.number_input("Renda / Mesada bruta mensal (R$)", min_value=0.0, value=float(c.get("renda", 0.0)), step=50.0, format="%.2f")
        gast = st.number_input("Gastos fixos mensais (R$)", min_value=0.0, value=float(c.get("gastos", 0.0)), step=10.0, format="%.2f")
        guard = st.number_input("Desse valor, guardar automaticamente (R$)", min_value=0.0, value=float(c.get("guardar", 0.0)), step=50.0, format="%.2f")
        cdi = st.number_input("CDI estimado (% ao ano)", min_value=0.0, max_value=100.0, value=float(c.get("cdi", 9.5)), step=0.1, format="%.2f")
        
        if st.form_submit_button("Salvar ajustes", type="primary", use_container_width=True):
            CONTA["nome"] = nome.strip() or CONTA["nome"]
            S["paleta"] = paleta_escolhida
            st.session_state["paleta"] = paleta_escolhida
            S["cfg"].update({"renda": renda, "gastos": gast, "guardar": min(guard, renda), "cdi": cdi, "meta": meta, "reserva": reserva, "tutorial": tutorial})
            fecha("Ajustes salvos com sucesso!")
            st.rerun()
            
    if HAS_CRYPTO:
        st.divider()
        r = FACEID(modo="reg", chal=st.session_state["chal"], user=U, tema=st.session_state["tema"], key="fid_reg", default=None)
        if r and r.get("kind") == "reg" and r["n"] != st.session_state["fid_done"]:
            st.session_state["fid_done"] = r["n"]
            if fid_registrar(U, r):
                st.session_state["msg"] = "Face ID ativado neste aparelho!"
                st.rerun()
            st.error("Falha ao registrar Face ID.")

# ------------------------------------------------------------------ diálogos
def form_op(op):
    cx = cx2 = None
    if op in ("save", "take", "yld", "mov"):
        ops = [k for k in S.get("caixas", {}) if op == "save" or S["caixas"][k] > 0]
        if not ops:
            st.info("Nenhuma caixinha criada ou com saldo.")
            return
        cx = st.selectbox("De" if op == "mov" else "Caixinha", ops, key="c_" + op,
                          format_func=lambda k: S.get("caixas_meta", {}).get(k, ["Caixinha"])[0] + " · " + brl(S["caixas"][k]))
        if op == "mov":
            cx2 = st.selectbox("Para", [k for k in S.get("caixas", {}) if k != cx], key="d_mov", format_func=lambda k: S.get("caixas_meta", {}).get(k, ["Caixinha"])[0])
    v = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=0.10 if op == "yld" else 1.0, format="%.2f", key="v_" + op)
    obs = st.text_input("Observação (opcional)", max_chars=40, key="o_" + op)
    if st.button("Confirmar", type="primary", use_container_width=True, key="ok_" + op):
        e = mover(cx, cx2, v, obs.strip()) if op == "mov" else aplicar(op, v, cx, obs.strip())
        if e:
            st.error(e)
        else:
            st.rerun()

def form_criar_cx():
    st.caption("Organize seu dinheiro criando caixinhas separadas que rendem 100% do CDI.")
    nome = st.text_input("Nome da Caixinha (ex: Viagem)")
    cor = st.selectbox("Cor de Destaque", ["pur", "blue", "gold", "grn", "red"], format_func=lambda c: {"pur":"Roxo","blue":"Azul","gold":"Dourado","grn":"Verde","red":"Vermelho"}[c])
    desc = st.text_input("Descrição (ex: Rende 100% do CDI)")
    if st.button("Criar Caixinha", type="primary", use_container_width=True):
        if not nome.strip():
            st.error("Dê um nome para a caixinha.")
        else:
            k = chave(nome) + secrets.token_hex(2)
            if "caixas" not in S: S["caixas"] = {}
            if "caixas_meta" not in S: S["caixas_meta"] = {}
            S["caixas"][k] = 0.0
            S["caixas_meta"][k] = [nome.strip(), cor, desc.strip()]
            salvar()
            st.rerun()

@st.dialog("Novo lançamento")
def dlg_novo():
    t_tabs = ["💳 Conta", "🐷 Caixinhas", "➕ Criar Caixinha"]
    t1, t2, t3 = st.tabs(t_tabs)
    with t1:
        form_op(st.radio("Conta", ["in", "out"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r1"))
    with t2:
        form_op(st.radio("Caixinhas", ["save", "take", "yld", "mov"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r2"))
    with t3:
        form_criar_cx()

@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():
    ops = [k for k in S.get("caixas", {})]
    if not ops:
        st.info("Nenhuma caixinha para excluir.")
        return
    cx = st.selectbox("Qual caixinha?", ops, format_func=lambda k: S.get("caixas_meta", {}).get(k, ["Caixinha"])[0] + " · " + brl(S["caixas"][k]))
    modo = st.radio("O que fazer com o saldo?", ["Resgatar para o Saldo Livre", "Apenas zerar (sai do patrimônio)"])
    st.caption("Isso excluirá o card da caixinha permanentemente.")
    if st.button("Excluir caixinha", type="primary", use_container_width=True):
        excluir_caixinha(cx, modo.startswith("Resgatar"))
        st.rerun()

@st.dialog("🛡️ Painel dos pais")
def dlg_pais():
    st.caption("Modo supervisão: somente leitura. Aqui você pode redefinir os acessos.")
    senha = st.text_input("Nova senha do filho (mín. 4)", type="password")
    pin = st.text_input("Novo PIN dos pais (4 números)", type="password", max_chars=4)
    if st.button("Salvar", type="primary", use_container_width=True):
        if (senha and len(senha) < 4) or (pin and not (pin.isdigit() and len(pin) == 4)):
            st.error("Senha com 4+ caracteres e PIN com 4 números.")
        else:
            if senha:
                CONTA["s"], CONTA["h"] = mk(senha)
            if pin:
                CONTA["ps"], CONTA["ph"] = mk(pin)
            salvar()
            st.session_state["msg"] = "Acessos atualizados!"
            st.rerun()

# ------------------------------------------------------------------ app
if not SUP:
    creditar_mes()
    liberar_sonho()
if st.session_state.get("warn"):
    st.session_state["msg"] = st.session_state.pop("warn")
if st.session_state["msg"]:
    st.toast(st.session_state["msg"])
    st.session_state["msg"] = None

def _tema():
    st.session_state["tema"] = "light" if st.session_state["tema"] == "dark" else "dark"
    db()["contas"][st.session_state["u"]]["d"]["tema"] = st.session_state["tema"]
    salvar()

def _sair():
    sessoes().pop(st.query_params.get("s"), None)
    st.query_params.clear()
    st.session_state.update(u=None, modo=None, tela="login", chal=secrets.token_urlsafe(32))

def _nav(v):
    st.session_state["nav"] = v

st.button("☀️" if st.session_state["tema"] == "dark" else "🌙", key="b_tema", on_click=_tema, help="Alternar tema")
st.button("🔒", key="b_sair", on_click=_sair, help="Encerrar sessão")

tab = st.session_state["tab"]
if st.session_state["nav"]:
    with st.container(key="nav"):
        st.button("‹", key="b_min", on_click=_nav, args=(False,), help="Recolher")
        aba = st.radio("Navegação", ABAS, index=tab, key="aba", horizontal=True, label_visibility="collapsed")
        if st.button("🛡️" if SUP else "＋", key="b_plus", help="Painel dos pais" if SUP else "Novo lançamento"):
            (dlg_pais if SUP else dlg_novo)()
    idx = ABAS.index(aba)
else:
    st.button(ABAS[tab].split()[0], key="bolha", on_click=_nav, args=(True,), help="Abrir menu")
    idx = tab
if idx != tab:
    st.session_state.update(dir="R" if idx > tab else "L", tab=idx)

st.markdown('<div class="hd"><div class="k">' + TITULOS[idx] + '</div><h1>' + html.escape(CONTA["nome"]) + '</h1></div>', unsafe_allow_html=True)

if SUP:
    st.markdown('<div class="sup">🔐 Modo Supervisão: somente leitura, lançamentos ocultos.</div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    if idx == 0:
        st.markdown(v_home(), unsafe_allow_html=True)
        if not SUP and S.get("caixas"):
            if st.button("🗑️ Excluir caixinha", key="b_del", use_container_width=True):
                dlg_excluir()
    elif idx == 1:
        st.markdown(v_ext(), unsafe_allow_html=True)
        st.download_button("⬇️ Baixar extrato (CSV)", get_csv_extrato(), file_name=f"extrato_future_{agora():%Y-%m-%d}.csv", mime="text/csv", use_container_width=True, disabled=not S["extrato"])
    elif idx == 2:
        st.markdown(v_proj(), unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("🖼️ Baixar Card (HTML)", relatorio_html(), file_name=f"card_future_{agora():%Y-%m-%d}.html", mime="text/html", use_container_width=True)
        with col2:
            st.download_button("⬇️ Baixar Tabela", get_csv_proj(), file_name=f"projecao_future_{agora():%Y-%m-%d}.csv", mime="text/csv", use_container_width=True)
    elif idx == 3:
        st.markdown(v_idea(), unsafe_allow_html=True)
    elif idx == 4:
        v_ajustes()

if st.session_state["fx"]:
    st.markdown(fx_html(st.session_state["fx"]), unsafe_allow_html=True)
    st.session_state["fx"] = None

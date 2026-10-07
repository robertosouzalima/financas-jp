# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

NADA sensível fica neste arquivo. Configure em Streamlit Cloud > Settings > Secrets:

    supabase_url = "https://SEU-PROJETO.supabase.co"
    supabase_key = "CHAVE_SERVER_SIDE"         
    backup_key   = "texto-longo-e-aleatorio"   
    gemini_key   = "CHAVE_DO_GOOGLE_GEMINI"    # <<< CHAVE PARA O CHATBOT INTELIGENTE

    # conta inicial (opcional):
    seed_user = "joao"  seed_nome = "João"  seed_codigo = "..."  seed_pin = "..."
"""
import csv, io, json, random, time, html, hmac, hashlib, base64, secrets, threading, urllib.request, unicodedata
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse
import streamlit as st
import streamlit.components.v1 as components

# Tenta importar as bibliotecas adicionais
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

# Integração de Inteligência Artificial Real
try:
    import google.generativeai as genai
    HAS_AI = True
except ImportError:
    HAS_AI = False

st.set_page_config(page_title="FUTURE", page_icon="🚀", layout="centered", initial_sidebar_state="collapsed")


def secret_str(nome, padrao=""):
    try:
        v = st.secrets.get(nome, padrao)
        return padrao if v is None else str(v)
    except Exception:
        return padrao


CODIGO, PIN_PAIS = secret_str("seed_codigo"), secret_str("seed_pin")
SEED, SEED_NOME = secret_str("seed_user", "joao"), secret_str("seed_nome", "João")
SB_URL, SB_KEY = secret_str("supabase_url").rstrip("/"), secret_str("supabase_key")
_BACKUP_KEY = secret_str("backup_key")
BK = hashlib.sha256(_BACKUP_KEY.encode()).digest() if _BACKUP_KEY else None
GEMINI_KEY = secret_str("gemini_key")

if HAS_AI and GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

ARQ = Path(__file__).with_name("future_db.json")
XL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SESSAO_SEG = 30 * 86400

TIPOS = {"in": ("📥", "Recebi"), "out": ("💸", "Gastei"), "save": ("🔒", "Guardei"),
         "take": ("🔓", "Resgatei"), "yld": ("📈", "Rendeu"), "mov": ("🔁", "Movi"),
         "del": ("🗑️", "Excluí")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"], ["Início", "Extrato", "Projeção", "Ideias"]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PALETAS = {
    "Padrão": {"pur": "#8b5cf6", "blue": "#3b82f6", "gold": "#f59e0b", "grn": "#10b981", "red": "#ef4444"},
    "Neon": {"pur": "#d946ef", "blue": "#06b6d4", "gold": "#eab308", "grn": "#22c55e", "red": "#f43f5e"},
    "Oceano": {"pur": "#6366f1", "blue": "#0ea5e9", "gold": "#f59e0b", "grn": "#14b8a6", "red": "#f43f5e"},
    "Outono": {"pur": "#8b5cf6", "blue": "#2563eb", "gold": "#d97706", "grn": "#65a30d", "red": "#dc2626"},
}

for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", paleta="Padrão", tab=0, nav=False, dir="R", fx=None, msg=None,
                   chal=secrets.token_urlsafe(32), fid_done=None, bak_done=None, launch=False, db_obj=None, db_ts=0.0,
                   recarregar=False, base_v={}, storage_mode="local", bak_hash=None, bak_payload=None).items():
    st.session_state.setdefault(_k, _v)


def agora(): return datetime.now(TZ) if TZ else datetime.now()
def hoje_txt():
    h = agora()
    return f"{DIAS[h.weekday()]}, {h.day} {MESES[h.month - 1]}"

def brl(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "R$ " + s

def kf(v): return f"{v / 1000:.1f}".replace(".", ",") + "k"
def fmt_dt(iso): return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")

def chave(n):
    n = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")
    return " ".join(n.lower().split())

def b64d(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
def mk(txt):
    s = secrets.token_bytes(16)
    return s.hex(), hashlib.pbkdf2_hmac("sha256", txt.encode(), s, 150000).hex()

def confere(txt, s, h):
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", txt.encode(), bytes.fromhex(s), 150000).hex(), h)
def _th(t): return hashlib.sha256((t or "").encode()).hexdigest()

def safe_float(v, padrao=0.0):
    try: return float(v)
    except Exception: return padrao


def nova_conta(nome, senha, pin, nasc="2014-01-01", seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {}, "caixas_meta": {}, "extrato": [], "tema": "dark", "paleta": "Padrão", "nasc": nasc,
         "_v": 0.0 if seed else time.time(), "chat": [],
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None, "meta": 10000.0,
                 "reserva": 100.0, "tutorial": not seed, "ajustado": False},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:
        d["livre"] = safe_float(secret_str("seed_livre", "0"))
        try: bruto = json.loads(secret_str("seed_caixas_json", "{}"))
        except Exception: bruto = {}
        try: meta = json.loads(secret_str("seed_caixas_meta_json", "{}"))
        except Exception: meta = {}
        caixas = {str(k): round(safe_float(v), 2) for k, v in bruto.items()} if isinstance(bruto, dict) else {}
        d["caixas"] = caixas
        d["caixas_meta"] = {k: (meta[k] if isinstance(meta.get(k), list) and len(meta[k]) == 3 else [k.title(), "pur", ""]) for k in caixas}
        d["cfg"].update(renda=safe_float(secret_str("seed_renda", "0")), guardar=safe_float(secret_str("seed_guardar", "0")),
                        gastos=safe_float(secret_str("seed_gastos", "0")), meta=safe_float(secret_str("seed_meta", "10000"), 10000.0),
                        reserva=safe_float(secret_str("seed_reserva", "100"), 100.0), tutorial=False)
    return {"nome": nome, "s": s, "h": h, "ps": ps, "ph": ph, "fid": {}, "sess": {}, "d": d}


def supabase_configurado(): return bool(SB_URL and SB_KEY)

def _sb(metodo, path="", corpo=None):
    if not supabase_configurado():
        raise RuntimeError("Supabase não configurado.")
    h = {"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(SB_URL + "/rest/v1/future" + path, headers=h, method=metodo, data=None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode())
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()

def carregar_local():
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
        return d if isinstance(d, dict) else {}
    except Exception: return {}

def salvar_local(dados):
    tmp = ARQ.with_name(ARQ.name + ".tmp")
    try:
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(ARQ)
        return True
    except Exception:
        try: tmp.unlink()
        except Exception: pass
        return False

def ler_fonte():
    if supabase_configurado():
        try:
            r = json.loads(_sb("GET", "?id=eq.db&select=dados"))
            d = r[0].get("dados") if r else None
            return True, (d if isinstance(d, dict) else None)
        except Exception: return False, None
    d = carregar_local()
    return True, (d or None)

def _ver(c):
    try: return float((c.get("d") or {}).get("_v", 0) or 0)
    except Exception: return 0.0

def _merge(a, b):
    out = {"contas": {}}
    for src in (a or {}, b or {}):
        for u, c in (src.get("contas") or {}).items():
            if isinstance(c, dict) and (u not in out["contas"] or _ver(c) > _ver(out["contas"][u])):
                out["contas"][u] = c
    return out

@st.cache_resource
def trava(): return threading.RLock()

def _gravar(dados, nuvem=True):
    ok_l, ok_n = salvar_local(dados), True
    if supabase_configurado() and nuvem:
        try: _sb("POST", "", [{"id": "db", "dados": dados}])
        except Exception: ok_n = False
    return ok_l, ok_n

def carregar_db():
    ok, fonte = ler_fonte()
    local = carregar_local()
    d = _merge(fonte, local)
    contas = d["contas"]
    for src in (fonte, local):
        for h, r in ((src or {}).get("sessoes") or {}).items():
            if isinstance(r, list) and len(r) >= 3 and r[0] in contas:
                contas[r[0]].setdefault("sess", {}).setdefault(h, r)
    criou = False
    if SEED and CODIGO and PIN_PAIS and SEED not in contas:
        contas[SEED] = nova_conta(SEED_NOME, CODIGO, PIN_PAIS, seed=True)
        criou = True
    nv = {u: _ver(c) for u, c in ((fonte or {}).get("contas") or {}).items()}
    if criou or (supabase_configurado() and ok and any(_ver(c) > nv.get(u, -1) for u, c in contas.items())):
        _gravar(d, nuvem=ok)
    st.session_state["storage_mode"] = ("cloud" if ok else "local-fallback") if supabase_configurado() else "local"
    return d

def refrescar_db(force=False):
    ss = st.session_state
    if force or ss.get("recarregar") or ss.get("db_obj") is None or time.time() - ss.get("db_ts", 0) > 8:
        d = carregar_db()
        ss.update(db_obj=d, db_ts=time.time(), recarregar=False, base_v={u: _ver(c) for u, c in d["contas"].items()})

def db(): return st.session_state["db_obj"]

def salvar(forcar_u=None):
    ss = st.session_state
    u = forcar_u or ss.get("u")
    dados = db()
    if u in dados["contas"]:
        dados["contas"][u]["d"]["_v"] = max(time.time(), _ver(dados["contas"][u]) + 0.001)
    with trava():
        ok, fonte = ler_fonte()
        if ok and fonte and u:
            rc = (fonte.get("contas") or {}).get(u)
            if rc is not None and _ver(rc) != ss["base_v"].get(u):
                ss["recarregar"] = True
                ss["warn"] = "⚠️ Dados alterados em outro aparelho. Repita a ação."
                return False
        if ok:
            for k, c in _merge(fonte, dados)["contas"].items():
                dados["contas"][k] = c
        ok_l, ok_n = _gravar(dados, nuvem=ok)
        ss["base_v"] = {k: _ver(c) for k, c in dados["contas"].items()}
        if supabase_configurado():
            ss["storage_mode"] = "cloud" if (ok and ok_n) else "local-fallback"
    return True


# ------------------------------------------------------------------ visual
def get_css(tema, nome):
    p = PALETAS.get(nome, PALETAS["Padrão"])
    if tema == "light": p = {k: "color-mix(in srgb," + v + " 85%,#000)" for k, v in p.items()}
    cores = f"--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']}"
    if tema == "light":
        return ":root{--bg:#f2f2f7;--c1:#ffffff;--c2:#f2f2f7;--tx:#1c1c1e;--mu:#8e8e93;--ln:rgba(0,0,0,.06);--s1:rgba(0,0,0,.04);--glass:rgba(255,255,255,.8);color-scheme:light;" + cores + "}"
    return ":root{--bg:#000000;--c1:#1c1c1e;--c2:#2c2c2e;--tx:#f2f2f7;--mu:#8e8e93;--ln:rgba(255,255,255,.08);--s1:rgba(0,0,0,.2);--glass:rgba(28,28,30,.8);color-scheme:dark;" + cores + "}"

CSS_BASE = """
html,body,[data-testid="stApp"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:var(--bg)!important;overscroll-behavior-y:none;margin:0;padding:0}
.stApp{color:var(--tx);overflow-x:hidden}
header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
.block-container{max-width:520px!important;padding:2rem 1.5rem 10rem!important;margin:0 auto!important}
.stApp p,.stApp label,.stApp h1,.stApp li,[data-testid="stDialog"] *{color:var(--tx)}
.stApp input,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"], textarea{background:var(--c2)!important;color:var(--tx)!important;border-radius:12px!important;border:1px solid transparent!important;transition:border .2s}
.stApp input:focus,[data-baseweb="select"]>div:focus-within, textarea:focus{border:1px solid var(--pur)!important}
div[role="dialog"]{background:var(--c1)!important;border-radius:24px!important;border:1px solid var(--ln)!important;box-shadow:0 20px 40px rgba(0,0,0,.15)!important;max-width:calc(100vw - 32px)!important;animation:dialogIn .28s cubic-bezier(.16,1,.3,1)}
@keyframes dialogIn{from{opacity:0;transform:translateY(10px) scale(.985)}to{opacity:1;transform:none}}
button[kind="secondary"],[data-testid="stBaseButton-secondary"]{background:var(--c2);border:1px solid var(--ln);border-radius:14px}
button[kind="secondary"] p,[data-testid="stBaseButton-secondary"] p{color:var(--tx);font-weight:500}
button[kind="primary"],[data-testid="stBaseButton-primary"]{background:var(--pur)!important;border:0!important;border-radius:14px!important;box-shadow:0 4px 12px color-mix(in srgb,var(--pur) 25%,transparent)!important}
button[kind="primary"] *,[data-testid="stBaseButton-primary"] *{color:#fff!important;font-weight:600!important}
button{transition:transform .2s ease,opacity .2s ease!important}button:active{transform:scale(.97)!important;opacity:.8}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
.hd h1{margin:0;font-size:28px;letter-spacing:-.03em;padding:0}.hd{margin-bottom:20px}
.logo{font-size:56px;line-height:1;display:inline-block;animation:fadeScale .6s cubic-bezier(.16,1,.3,1) both}
@keyframes fadeScale{from{opacity:0;transform:scale(.9) translateY(10px)}to{opacity:1;transform:none}}
.brand{font-size:32px;font-weight:700;letter-spacing:-1px;line-height:1.1;color:var(--tx)}
.card{background:var(--c1);border:1px solid var(--ln);border-radius:20px;padding:20px;box-shadow:0 4px 14px rgba(0,0,0,.03);margin-bottom:16px;transition:transform .2s ease}
.k{color:var(--mu);font-size:13px}.lb{font-size:14px;font-weight:500}.big{font-size:32px;font-weight:700;letter-spacing:-.03em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.as{font-size:14px;border-style:dashed}.sup{background:color-mix(in srgb,var(--gold) 12%,transparent);border:1px solid var(--gold);border-radius:16px;padding:12px 14px;margin-bottom:16px;font-size:14px}
.sp{display:flex;gap:10px;align-items:flex-start;padding:7px 0}.sp>span{font-size:18px;line-height:1.3}
.tx{display:flex;align-items:center;gap:14px;padding:14px 0;border-bottom:1px solid var(--ln)}.tx:last-child{border:0}.tx .g{flex:1;min-width:0}
.ic{width:44px;height:44px;border-radius:12px;background:var(--c2);display:grid;place-items:center;font-size:20px;flex:none;border:0}
table{width:100%;border-collapse:collapse;font-size:14px}th{color:var(--mu);font-weight:500;text-align:right;padding:12px 0;border-bottom:1px solid var(--ln)}td{padding:12px 0;text-align:right;border-bottom:1px solid var(--ln)}th:first-child,td:first-child{text-align:left}
.bar{fill:var(--grn);opacity:.9;border-radius:4px}.bt{fill:var(--mu);font-size:10px;text-anchor:middle}.tl{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1.2}
.al{display:flex;justify-content:space-between;align-items:baseline}.al b{font-size:18px;font-weight:600}
.st-key-nav,.st-key-bolha{position:fixed;left:16px;bottom:calc(30px + env(safe-area-inset-bottom,0px));z-index:999;width:auto!important}
.st-key-nav{width:min(calc(100vw - 32px),420px)!important;display:flex!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:6px;overflow:hidden;background:var(--glass);backdrop-filter:blur(24px) saturate(150%);-webkit-backdrop-filter:blur(24px) saturate(150%);border:1px solid var(--ln);border-radius:30px;box-shadow:0 10px 30px rgba(0,0,0,.1);animation:stretch .4s cubic-bezier(.16,1,.3,1) forwards}
@keyframes stretch{from{width:58px!important;padding:0;opacity:0}}
.st-key-nav>div{width:auto!important;animation:fi .4s .1s cubic-bezier(.16,1,.3,1) both}@keyframes fi{from{opacity:0;transform:translateX(-10px)}}
.st-key-aba{flex:1!important}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:8px 0;border-radius:24px;cursor:pointer}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:10px;line-height:1.3;font-weight:600;text-align:center;word-spacing:100vw;margin:0;opacity:.5;transition:opacity .3s}
.st-key-nav label p::first-line{font-size:20px}
.st-key-nav label:has(input:checked){background:color-mix(in srgb,var(--pur) 20%,transparent)}
.st-key-nav label:has(input:checked) p{opacity:1;color:var(--pur)}
.st-key-b_min button,.st-key-b_plus button,.st-key-bolha button,.st-key-b_tema button,.st-key-b_ajustes_top button,.st-key-b_sair button, .st-key-b_chat button{border-radius:50%;padding:0;background:var(--glass);backdrop-filter:blur(20px);border:1px solid var(--ln)}
.st-key-b_min button{width:34px;height:34px}.st-key-b_plus button{width:46px;height:46px;border:0;background:var(--pur)}
.st-key-b_plus button p{color:#fff;font-size:24px;line-height:1;font-weight:400}
.st-key-bolha{animation:popin .3s cubic-bezier(.2,1.4,.4,1)}.st-key-bolha button{width:58px;height:58px;font-size:24px;box-shadow:0 10px 30px var(--s1)}
@keyframes popin{from{transform:scale(.6);opacity:0}}
.st-key-b_tema,.st-key-b_chat,.st-key-b_ajustes_top,.st-key-b_sair{position:fixed;z-index:1000;width:auto!important;top:calc(16px + env(safe-area-inset-top,0px))}
.st-key-b_tema{right:170px}.st-key-b_chat{right:118px}.st-key-b_ajustes_top{right:66px}.st-key-b_sair{right:14px}
.st-key-b_tema button,.st-key-b_chat button,.st-key-b_ajustes_top button,.st-key-b_sair button{width:44px;height:44px;font-size:18px}
[class*="_fromR"]{animation:slR .4s cubic-bezier(.25,1,.5,1) forwards}[class*="_fromL"]{animation:slL .4s cubic-bezier(.25,1,.5,1) forwards}
@keyframes slR{from{transform:translateX(30px);opacity:0}to{transform:none;opacity:1}}@keyframes slL{from{transform:translateX(-30px);opacity:0}to{transform:none;opacity:1}}
html,body,.stApp,p,label,input,textarea,button{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif!important}
.big,.hd h1,.al b,.lb,.brand{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",system-ui,sans-serif!important}
.dh{font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--mu);padding:16px 0 8px}.dh:first-child{padding-top:8px}
.chat-msg {padding: 12px 16px; border-radius: 16px; margin-bottom: 12px; font-size: 15px; line-height: 1.4; display: inline-block; max-width: 90%; clear: both;}
.chat-user {background: var(--pur); color: #fff; float: right; border-bottom-right-radius: 4px;}
.chat-ai {background: var(--c2); color: var(--tx); float: left; border-bottom-left-radius: 4px; border: 1px solid var(--ln);}
"""
st.markdown("<style>" + get_css(st.session_state["tema"], st.session_state["paleta"]) + CSS_BASE + "</style>", unsafe_allow_html=True)

try: refrescar_db(force=st.session_state["u"] is None)
except Exception: st.error("Erro ao carregar dados."); st.stop()


# ------------------------------- componentes e webauthn
def _componente(nome, html_src):
    d = Path(__file__).with_name("_" + nome)
    try: d.mkdir(exist_ok=True); (d / "index.html").write_text(html_src, "utf-8")
    except Exception: pass
    return components.declare_component(nome, path=str(d))

BAK_HTML = """<!DOCTYPE html><html><body><script>
const P=(t,d)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
let first=true,last="";
addEventListener("message",ev=>{if(ev.data.type!="streamlit:render")return;const A=ev.data.args||{};
let m={};try{m=JSON.parse(localStorage.getItem("future_bak")||"{}")}catch(e){}
if(A.save&&A.save!==last){last=A.save;try{const o=JSON.parse(A.save);m[o.u]=o;localStorage.setItem("future_bak",JSON.stringify(m))}catch(e){}}
if(first){first=false;P("streamlit:setComponentValue",{value:{n:Date.now()+Math.random(),itens:Object.values(m)},dataType:"json"})}
P("streamlit:setFrameHeight",{height:0})});
P("streamlit:componentReady",{apiVersion:1});</script></body></html>"""

FACEID_HTML = """<!DOCTYPE html><html><body style="margin:0;font-family:-apple-system,system-ui,sans-serif"><button id="b"></button><div id="m"></div><script>
const P=(t,d)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
const e64=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\\+/g,"-").replace(/\\//g,"_").replace(/=+$/,"");
const d64=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")),c=>c.charCodeAt(0));
const B=document.getElementById("b"),M=document.getElementById("m");let A={};
const done=v=>P("streamlit:setComponentValue",{value:Object.assign({n:Date.now()+Math.random()},v),dataType:"json"});
async function reg(){try{const c=await navigator.credentials.create({publicKey:{challenge:d64(A.chal),rp:{name:"FUTURE",id:location.hostname},user:{id:new TextEncoder().encode(A.user),name:A.user,displayName:A.user},pubKeyCredParams:[{type:"public-key",alg:-7},{type:"public-key",alg:-257}],authenticatorSelection:{authenticatorAttachment:"platform",userVerification:"required"},timeout:60000}});const r=c.response,L=JSON.parse(localStorage.getItem("future_auth")||"[]").filter(x=>x.id!=c.id);L.push({id:c.id,user:A.user});localStorage.setItem("future_auth",JSON.stringify(L));done({kind:"reg",id:c.id,pk:e64(r.getPublicKey()),alg:r.getPublicKeyAlgorithm(),cd:e64(r.clientDataJSON)});}catch(e){M.textContent="Erro: "+e.name}}
async function get(){try{const L=JSON.parse(localStorage.getItem("future_auth")||"[]");if(!L.length){M.textContent="Ative nos Ajustes.";return}const c=await navigator.credentials.get({publicKey:{challenge:d64(A.chal),rpId:location.hostname,allowCredentials:L.map(x=>({type:"public-key",id:d64(x.id)})),userVerification:"required",timeout:60000}});const r=c.response,u=(L.find(x=>x.id==c.id)||{}).user;done({kind:"get",id:c.id,user:u,ad:e64(r.authenticatorData),cd:e64(r.clientDataJSON),sg:e64(r.signature)});}catch(e){M.textContent="Cancelado."}}
addEventListener("message",ev=>{if(ev.data.type!="streamlit:render")return;A=ev.data.args;const d=A.tema=="dark";document.body.style.color=d?"#8b8b9a":"#656575";M.style.cssText="font-size:12px;text-align:center;margin-top:6px";B.style.cssText="width:100%;padding:14px;border-radius:14px;font-size:15px;font-weight:600;cursor:pointer;border:1px solid "+(d?"rgba(255,255,255,.1)":"rgba(0,0,0,.1)")+";background:"+(d?"#2c2c2e":"#f2f2f7")+";color:"+(d?"#f2f2f7":"#1c1c1e");B.textContent=(A.modo=="reg"?"Ativar Face ID":"Entrar com Face ID");B.onclick=A.modo=="reg"?reg:get;P("streamlit:setFrameHeight",{height:88})});
P("streamlit:componentReady",{apiVersion:1});</script></body></html>"""

BACKUP, FACEID = _componente("bak", BAK_HTML), _componente("faceid", FACEID_HTML)

def _fernet():
    if not (BK and HAS_CRYPTO): return None
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(BK))

def _payload():
    f, u = _fernet(), st.session_state.get("u")
    if not f or u not in db()["contas"]: return None
    corpo = json.dumps(db()["contas"][u], sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(corpo.encode()).hexdigest()
    if st.session_state.get("bak_hash") != h:
        blob = f.encrypt(json.dumps({"u": u, "c": json.loads(corpo)}, ensure_ascii=False).encode()).decode()
        st.session_state.update(bak_hash=h, bak_payload=json.dumps({"u": _th(u), "blob": blob}))
    return st.session_state["bak_payload"]

if _fernet():
    _bk_val = BACKUP(save=_payload(), key="bak", default=None)

def _cd(p, tipo):
    try: cd = json.loads(b64d(p["cd"]))
    except Exception: return None
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
    if not (cd and cr and HAS_CRYPTO): return None
    try:
        ad = b64d(p["ad"])
        host = urlparse(cd["origin"]).hostname or ""
        msg = ad + hashlib.sha256(b64d(p["cd"])).digest()
        pub, sig = serialization.load_der_public_key(b64d(cr["pk"])), b64d(p["sg"])
        if cr["alg"] == -7: pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))
        else: pub.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())
        return p["user"]
    except Exception: return None


# ------------------------------------------------------------ login / sessão
def achar_sessao(token):
    th = _th(token)
    for u, c in db()["contas"].items():
        r = (c.get("sess") or {}).get(th)
        if r and time.time() - r[2] < SESSAO_SEG: return u, r[1]
    return None

def entrar(u, modo):
    tok = secrets.token_urlsafe(24)
    sess = db()["contas"][u].setdefault("sess", {})
    for h in [h for h, r in sess.items() if time.time() - r[2] >= SESSAO_SEG]: sess.pop(h, None)
    sess[_th(tok)] = [u, modo, time.time()]
    st.query_params["s"] = tok
    salvar(u)
    d = db()["contas"][u]["d"]
    st.session_state.update(u=u, modo=modo, tela="login", launch=True, tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
    st.rerun()

def _ir(t): st.session_state["tela"] = t

@st.cache_resource
def _tent(): return {}

def _espera(k):
    t = _tent().get(k)
    e = (t[1] - time.time()) if t else 0
    if e > 0: st.error(f"Aguarde {int(e) + 1}s para tentar novamente.")
    return e > 0

def _falha(k):
    tt = _tent()
    t = tt.setdefault(k, [0, 0.0])
    t[0] += 1
    if t[0] >= 5: t[:] = [0, time.time() + 60]
    st.error("Dados incorretos.")

def tela_login():
    t = st.session_state["tela"]
    sub = {"login": "INICIAR SESSÃO", "criar": "CRIAR CONTA", "pais": "CONTROLE PARENTAL"}[t]
    st.markdown('<div style="display:flex;flex-direction:column;align-items:center;width:100%;text-align:center;padding:8vh 0 4vh">'
                '<div class="logo" style="margin-bottom:8px;">🚀</div>'
                '<div class="brand">FUTURE</div>'
                '<div style="color:var(--mu);font-size:12px;font-weight:600;letter-spacing:1px;margin-top:4px;">' + sub + '</div></div>', unsafe_allow_html=True)
    if t == "login":
        with st.form("f_login"):
            n = st.text_input("Nome", placeholder="Nome da conta", label_visibility="collapsed", max_chars=24)
            p = st.text_input("Senha", type="password", placeholder="Senha", label_visibility="collapsed")
            go = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if go:
            k = "f:" + chave(n)[:40]
            if not _espera(k):
                c = db()["contas"].get(chave(n))
                if c and confere(p, c["s"], c["h"]):
                    entrar(chave(n), "filho")
                else: _falha(k)
        if HAS_CRYPTO:
            r = FACEID(modo="get", chal=st.session_state["chal"], user="", tema=st.session_state["tema"], key="fid_get", default=None)
            if r and r.get("kind") == "get" and r["n"] != st.session_state["fid_done"]:
                st.session_state["fid_done"] = r["n"]
                u = fid_entrar(r)
                if u: entrar(u, "filho")
        st.button("🛡️ Controle parental", key="b_pais", use_container_width=True, on_click=_ir, args=("pais",))
        st.button("Criar nova conta", key="b_criar", use_container_width=True, on_click=_ir, args=("criar",))
        return
    if t == "criar":
        with st.form("f_criar"):
            n = st.text_input("Nome da conta", max_chars=24)
            p = st.text_input("Senha (mín. 4 caracteres)", type="password")
            pin = st.text_input("PIN dos pais (4 números)", type="password", max_chars=4)
            nasc = st.date_input("Data de nascimento", value=date(2014, 1, 1), min_value=date(1950, 1, 1), max_value=agora().date(), format="DD/MM/YYYY")
            if st.form_submit_button("Criar conta", type="primary", use_container_width=True):
                k = chave(n)
                if len(p) >= 4 and pin.isdigit() and len(pin) == 4 and k not in db()["contas"]:
                    db()["contas"][k] = nova_conta(n.strip(), p, pin, nasc=nasc.isoformat())
                    if salvar(k): entrar(k, "filho")
        st.button("← Voltar", key="b_volta2", use_container_width=True, on_click=_ir, args=("login",))

if not st.session_state["u"]:
    _r = achar_sessao(st.query_params.get("s", ""))
    if _r:
        _d = db()["contas"][_r[0]]["d"]
        st.session_state.update(u=_r[0], modo=_r[1], tema=_d.get("tema", "dark"), paleta=_d.get("paleta", "Padrão"))
        st.rerun()
if not st.session_state["u"]:
    tela_login()
    st.stop()

U, SUP = st.session_state["u"], st.session_state["modo"] == "pais"
CONTA = db()["contas"][U]
S = CONTA["d"]
S.setdefault("caixas", {})
S.setdefault("caixas_meta", {})
S.setdefault("chat", [])
for _k, _v in dict(meta=62000.0, reserva=100.0, tutorial=False, ajustado=True, cdi=9.5, gastos=0.0, renda=0.0, guardar=0.0).items():
    S["cfg"].setdefault(_k, _v)

def total(): return round(S["livre"] + sum(S["caixas"].values()), 2)
def idade_info():
    try: n = date.fromisoformat(S.get("nasc", "2014-01-01"))
    except: n = date(2014, 1, 1)
    h = agora().date()
    b18 = n.replace(year=n.year + 18)
    meses = 0 if h >= b18 else max(1, (b18.year - h.year) * 12 + b18.month - h.month)
    return h.year - n.year, b18, meses

def reg(t, v, cx, obs, ts=None, dest=None):
    M = S["caixas_meta"]
    S["extrato"].append({"t": t, "v": round(v, 2), "c": cx, "d": dest, "o": obs, "ts": (ts or agora()).isoformat(),
                         "cn": M.get(cx, [None])[0] if cx else None, "dn": M.get(dest, [None])[0] if dest else None})

def fx(valor): st.session_state["fx"] = {"txt": "+" + brl(valor), "n": int(time.time() * 1000)}

def fecha(msg=None):
    S["livre"] = round(S["livre"], 2)
    for k in S["caixas"]: S["caixas"][k] = round(S["caixas"][k], 2)
    st.session_state["msg"] = msg or "Lançado em " + fmt_dt(S["extrato"][-1]["ts"])
    salvar()

def visivel(k): return S["caixas"][k] > 0.004 or not any(x.get("c") == k or x.get("d") == k for x in S["extrato"])

# Função segura para pegar nome/cor da caixinha antiga ou nova
def nome_cx(k):
    return S["caixas_meta"].get(k, ["Caixinha"])[0]


# --- Componentes Visuais Universais que faltaram na última ---
def fx_html(d):
    random.seed(d["n"])
    itens = "".join('<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
                    % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
                       random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return '<div class="fx">' + itens + '<b>' + d["txt"] + '</b></div>'

def card(cor, tit, val, sub="", extra=""):
    return ('<div class="card" style="--c:var(--' + cor + ')"><div class="lb" style="color:var(--' + cor + ')">' + tit + '</div>'
            '<div class="big">' + val + '</div>' + extra + '<div class="k">' + sub + '</div></div>')

def svg_barras(L, meta):
    W, H = 340, 210
    mx = max([meta] + [x[3] for x in L]) * 1.12 if meta > 0 else 1000.0
    bw = W / max(1, len(L))
    ty = H - 24 - meta / mx * (H - 44)
    s = ('<svg viewBox="0 0 %d %d" style="width:100%%;height:auto;touch-action:pan-y"><line class="tl" x1="0" x2="%d" y1="%.1f" y2="%.1f"/>'
         '<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="%.1f">Meta %s</text>' % (W, H, W, ty, ty, ty - 5, kf(meta)))
    for i, (ano, ap, j, b) in enumerate(L):
        h = b / mx * (H - 44)
        x = i * bw + bw * .17
        s += ('<rect class="bar" style="animation-delay:%dms" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="4"/><text class="bt" x="%.1f" y="%.1f">%s</text><text class="bt" x="%.1f" y="%d">%s</text>'
              % (i * 70, x, H - 24 - h, bw * .66, h, x + bw * .33, H - 28 - h, kf(b), x + bw * .33, H - 7, ano))
    return s + "</svg>"


def aplicar(t, v, cx=None, obs=""):
    v, reserva, cxs = round(safe_float(v), 2), safe_float(S["cfg"]["reserva"]), S["caixas"]
    if v <= 0: return "Informe um valor maior que zero."
    if t == "save":
        if S["livre"] - v < reserva - 1e-9: return f"Reserva de {brl(reserva)} protegida."
        S["livre"] -= v; cxs[cx] += v
    elif t == "take":
        if v > cxs[cx] + 1e-9: return "Saldo insuficiente na caixinha."
        cxs[cx] -= v; S["livre"] += v
    elif t == "yld": cxs[cx] += v
    elif t == "out":
        if v > S["livre"] + 1e-9: return "Saldo livre insuficiente."
        S["livre"] -= v
    elif t == "in": S["livre"] += v
    reg(t, v, cx if t in ("save", "take", "yld") else None, obs)
    fecha()
    return ""

def mover(o, d, v, obs=""):
    v = round(safe_float(v), 2)
    if v > S["caixas"][o] + 1e-9: return "Saldo insuficiente."
    S["caixas"][o] -= v; S["caixas"][d] += v
    reg("mov", v, o, obs, dest=d); fecha()
    return ""

def excluir_caixinha(cx, resgatar):
    v = S["caixas"][cx]
    if resgatar: S["livre"] += v; reg("take", v, cx, "Resgate")
    else: reg("del", v, cx, "Excluída")
    S["caixas"].pop(cx, None); S["caixas_meta"].pop(cx, None)
    fecha("Caixinha excluída")

# Projeção
def _passos(extra=0.0, limite_meses=None):
    c, h = S["cfg"], agora()
    r = (1 + max(0.0, safe_float(c["cdi"])) / 100) ** (1 / 12) - 1
    cx = {k: max(0.0, safe_float(v)) for k, v in S["caixas"].items()}
    lv, ap, main = max(0.0, safe_float(S["livre"])), total(), next(iter(S["caixas"]), None)
    renda, gastos, guard, extra = (max(0.0, safe_float(c["renda"])), max(0.0, safe_float(c["gastos"])), max(0.0, safe_float(c["guardar"])), safe_float(extra))
    net = renda - gastos + extra
    g = (min(guard, max(0.0, renda - gastos)) + extra) if main else 0.0
    ano, mes, passos = h.year, h.month, 0
    while limite_meses is None or passos < limite_meses:
        mes += 1
        if mes > 12: mes, ano = 1, ano + 1
        lv = max(0.0, lv * (1 + r) + net - g)
        for k in cx: cx[k] *= 1 + r
        if main: cx[main] += g
        ap += net; passos += 1
        yield ano, mes, lv + sum(cx.values()), ap, lv, dict(cx)

def projetar():
    h = agora()
    limite = idade_info()[2] if idade_info()[2] > 0 else 120
    por_ano, ult, estado = {}, None, (total(), total(), S["livre"], dict(S["caixas"]))
    for ano, mes, b, ap, lv, cx in _passos(limite_meses=limite):
        estado, ult = (b, ap, lv, cx), (ano, mes)
        if mes == 12: por_ano[ano] = estado
    linhas = [(a, v[1], v[0] - v[1], v[0]) for a, v in sorted(por_ano.items())]
    if not linhas: linhas.append((h.year, estado[1], estado[0] - estado[1], estado[0]))
    meta = S["cfg"]["meta"]
    return linhas, 0.0, ult[0] if ult else h.year, meta, estado[2:]


# --- CHATBOT INTELIGENTE ---
@st.dialog("🤖 Consultor FUTURE")
def dlg_chat():
    st.markdown('<div class="dh" style="padding-top:0;">O que você quer saber sobre suas finanças?</div>', unsafe_allow_html=True)
    
    chat_container = st.container(height=380)
    
    if not S["chat"]:
        S["chat"].append({"r": "ai", "t": f"Olá, {CONTA['nome']}! Sou a inteligência artificial do FUTURE. Posso analisar suas caixinhas, projetar metas ou dar dicas baseadas na sua realidade hoje. Como posso te ajudar?"})
        
    with chat_container:
        for msg in S["chat"]:
            cor = "chat-user" if msg["r"] == "user" else "chat-ai"
            st.markdown(f'<div class="chat-msg {cor}">{msg["t"]}</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        pergunta = col1.text_input("Pergunta", label_visibility="collapsed", placeholder="Ex: Qual caixinha rende mais?")
        enviou = col2.form_submit_button("Enviar", use_container_width=True, type="primary")

    if enviou and pergunta.strip():
        S["chat"].append({"r": "user", "t": pergunta.strip()})
        st.rerun()
        
    if S["chat"] and S["chat"][-1]["r"] == "user":
        if not (HAS_AI and GEMINI_KEY):
            S["chat"].append({"r": "ai", "t": "⚠️ **Integração de IA desativada.** Para que eu possa 'pensar na hora' e analisar seus dados, adicione sua chave `gemini_key` nos Secrets do painel Streamlit."})
            salvar()
            st.rerun()
            
        with chat_container:
            st.markdown(f'<div class="chat-msg chat-ai"><i>Pensando...</i></div>', unsafe_allow_html=True)
            
        t_patrimonio = total()
        cxs_info = ", ".join([f"{S['caixas_meta'].get(k,[''])[0]}: R$ {v:.2f}" for k, v in S["caixas"].items() if v > 0])
        contexto_seguro = f"""Você é o Consultor Financeiro FUTURE, um assistente direto e muito educado de dentro do app do usuário.
Usuário: {CONTA['nome']}
Meta Financeira: R$ {S['cfg']['meta']:.2f}
Reserva de Emergência Ideal: R$ {S['cfg']['reserva']:.2f}
Saldo Livre Atual: R$ {S['livre']:.2f}
Patrimônio Total Atual: R$ {t_patrimonio:.2f}
Caixinhas: {cxs_info or 'Nenhuma no momento'}
Rendimento Padrão configurado pelo usuário: {S['cfg']['cdi']}% a.a.

INSTRUÇÕES PARA A IA:
1. Responda diretamente e sem usar marcações exageradas.
2. Utilize os dados reais acima para justificar qualquer conselho. Nunca invente dados da conta dele.
3. Foque em educação financeira e otimização das caixinhas."""

        try:
            modelo = genai.GenerativeModel("gemini-1.5-flash", system_instruction=contexto_seguro)
            historico = [{"role": "user" if m["r"] == "user" else "model", "parts": [m["t"]]} for m in S["chat"][-10:-1]]
            chat_sessao = modelo.start_chat(history=historico)
            resposta = chat_sessao.send_message(S["chat"][-1]["t"]).text
            S["chat"].append({"r": "ai", "t": resposta})
        except Exception as e:
            S["chat"].append({"r": "ai", "t": f"Ocorreu um erro ao processar: {str(e)}"})
            
        salvar()
        st.rerun()


# --- TELAS DO APLICATIVO ---
def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    _, _, ano_fim, meta, _ = projetar()
    pc = min(100, t / meta * 100) if meta > 0 else 0
    out = f'<div style="text-align:center; padding: 10px 0 24px;"><div style="color:var(--mu); font-size:13px; font-weight:600; text-transform:uppercase;">Saldo Disponível</div><div style="font-size:46px; font-weight:700;">{brl(f)}</div></div>'
    out += f'<div class="card" style="padding: 24px; border: 0; background: linear-gradient(135deg, var(--pur), var(--blue)); color: #fff; box-shadow: 0 10px 30px color-mix(in srgb, var(--pur) 20%, transparent);"><div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom: 12px;"><div><div style="color: rgba(255,255,255,0.8); font-size:13px; font-weight:500;">Patrimônio Total</div><div style="font-size:26px; font-weight:700;">{brl(t)}</div></div><div style="color: #fff; font-weight:600;">{pc:.1f}% da meta</div></div></div>'
    if S["caixas"]:
        out += '<div class="dh" style="margin-top: 24px;">MINHAS CAIXINHAS</div>'
        for k, v in S["caixas"].items():
            if visivel(k): 
                # Leitura segura para contas antigas que tinham listas menores no dict
                meta_array = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
                cor_cx = meta_array[1] if len(meta_array) > 1 else "blue"
                out += card(cor_cx, nome_cx(k), brl(v), "Rende 100% do CDI")
    return out

def dia_rotulo(iso):
    d, h = datetime.fromisoformat(iso).date(), agora().date()
    if d == h: return "Hoje"
    if (h - d).days == 1: return "Ontem"
    return f"{DIAS[d.weekday()]}, {d.day} {MESES[d.month - 1]}" + (f" {d.year}" if d.year != h.year else "")

def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k" style="text-align:center; padding: 20px 0;">🌱 Nenhuma movimentação. Toque em ＋ para adicionar.</div></div>'
    rows, ult = "", None
    for _, x in sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True):
        dia = dia_rotulo(x["ts"])
        if dia != ult:
            rows, ult = rows + '<div class="dh" style="margin-top:16px;">' + dia + '</div>', dia
        ic, nome = TIPOS[x["t"]]
        tr, ps = x["t"] in ("save", "take", "mov"), x["t"] in ("in", "yld")
        cor = "tx" if tr else "grn" if ps else "tx"
        sg = {"save": "→ ", "take": "← ", "mov": "↔ "}.get(x["t"], "+" if ps else "−")
        det = (html.escape(x.get("cn") or "") + " · " if x.get("c") else "") + (html.escape(x["o"]) + " · " if x["o"] else "") + fmt_dt(x["ts"])
        rows += ('<div class="tx"><span class="ic">' + ic + '</span><div class="g"><b>' + nome + '</b><div class="k" style="margin-top:2px;">' + det + '</div></div>'
                 '<b style="color:var(--' + cor + ')">' + sg + brl(x["v"]) + '</b></div>')
    return '<div class="card" style="padding:4px 20px">' + rows + '</div>'

def v_proj():
    L, falta, ano_fim, meta, (lv, cxf) = projetar()
    fim, c = L[-1][3], S["cfg"]
    sub = f"Evolução projetada do seu patrimônio até {ano_fim}."
    topo = card("grn" if fim >= meta else "gold", "Projeção Financeira", brl(fim), sub)
    tab = '<table><tr><th>Ano</th><th>Total Acumulado</th></tr>'
    for a, p, j, b in L:
        tab += '<tr><td>' + str(a) + '</td><td><b>' + brl(b) + '</b></td></tr>'
    resto = ('<div class="card">' + svg_barras(L, meta) + '</div>'
             '<div class="card">' + tab + '</table></div>'
             '<div class="k" style="padding:0 6px">Projeção considerando 100% do CDI estimado.</div>')
    return topo, resto

def v_idea():
    reserva = S["cfg"]["reserva"]
    ex = round(max(0.0, S["livre"] - reserva), 2)
    out = ""
    for k, v in S["caixas"].items():
        if v > 0.004:
            meta_array = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
            cor_cx = meta_array[1] if len(meta_array) > 1 else "blue"
            out += card(cor_cx, nome_cx(k), brl(v), "Disponível para resgate imediato.")
    sub = "Disponível para ir à caixinha principal." if ex > 0 else "Seu saldo livre precisa passar de " + brl(reserva) + " para sobrar."
    out += card("blue", "Saldo acima da reserva", brl(ex), sub)
    return out

@st.dialog("Ajustes")
def dlg_ajustes():
    c = S["cfg"]
    t1, t2, t3 = st.tabs(["Perfil", "Dinheiro", "Aparência"])
    with t1:
        nome = st.text_input("Como quer ser chamado?", CONTA["nome"], max_chars=24)
        if st.button("Salvar Perfil", use_container_width=True): CONTA["nome"] = nome; salvar(); st.rerun()
    with t2:
        meta = st.number_input("Sua meta principal (R$)", value=float(c["meta"]))
        reserva = st.number_input("Reserva de emergência (R$)", value=float(c["reserva"]))
        cdi = st.number_input("CDI estimado (% a.a.)", value=float(c["cdi"]))
        if st.button("Salvar Dinheiro", use_container_width=True): S["cfg"].update(meta=meta, reserva=reserva, cdi=cdi); salvar(); st.rerun()
    with t3:
        pal = list(PALETAS)
        paleta = st.selectbox("Cor de Destaque", pal, index=pal.index(S["paleta"]) if S.get("paleta") in pal else 0)
        if st.button("Salvar Visual", use_container_width=True): S["paleta"] = st.session_state["paleta"] = paleta; salvar(); st.rerun()

st.button("☀️" if st.session_state["tema"] == "dark" else "🌙", key="b_tema", on_click=lambda: st.session_state.update(tema="light" if st.session_state["tema"] == "dark" else "dark"), help="Modo Escuro")
if not SUP:
    st.button("💬", key="b_chat", on_click=dlg_chat, help="Consultor de IA (Chat)")
if not SUP:
    st.button("⚙️", key="b_ajustes_top", help="Ajustes", on_click=dlg_ajustes)
st.button("🔒", key="b_sair", help="Sair", on_click=lambda: st.session_state.update(u=None, tela="login"))

tab = st.session_state["tab"]
st.button(ABAS[tab].split()[0], key="bolha", on_click=lambda: st.session_state.update(nav=True))
if st.session_state["nav"]:
    with st.container(key="nav"):
        st.button("‹", key="b_min", on_click=lambda: st.session_state.update(nav=False))
        aba = st.radio("Atalhos", ABAS, index=tab, key="aba", horizontal=True, label_visibility="collapsed")
    idx = ABAS.index(aba)
    if idx != tab: st.session_state.update(dir="R" if idx > tab else "L", tab=idx)
else: idx = tab

st.markdown(f'<div class="hd"><div class="k">{TITULOS[idx]} · {hoje_txt()}</div><h1>{html.escape(CONTA["nome"])}</h1></div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    if idx == 0: st.markdown(v_home(), unsafe_allow_html=True)
    elif idx == 1: st.markdown(v_ext(), unsafe_allow_html=True)
    elif idx == 2: 
        topo, resto = v_proj()
        st.markdown(topo, unsafe_allow_html=True)
        st.markdown(resto, unsafe_allow_html=True)
    else: 
        st.markdown(v_idea(), unsafe_allow_html=True)

if st.session_state["fx"]:
    st.markdown(fx_html(st.session_state["fx"]), unsafe_allow_html=True)
    st.session_state["fx"] = None
if st.session_state["launch"]:
    st.session_state["launch"] = False

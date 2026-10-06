# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography   openpyxl
Salvamento: automático. Os dados ficam no servidor E em um backup no próprio aparelho, que
restaura tudo sozinho quando o Streamlit "dorme" e perde os arquivos. Sem configurar nada.
Opcional (vários aparelhos): Secrets  supabase_url / supabase_key  e, no Supabase:
  create table future (id text primary key, dados jsonb not null);
  alter table future enable row level security;
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
CODIGO, PIN_PAIS, SEED = "5102", "5102", "joao"
try:
    SB_URL, SB_KEY = str(st.secrets["supabase_url"]).rstrip("/"), str(st.secrets["supabase_key"])
except Exception:
    SB_URL = SB_KEY = ""
try:
    _bk = str(st.secrets["backup_key"])
except Exception:
    _bk = "future-" + CODIGO + PIN_PAIS
BK = hashlib.sha256(_bk.encode()).digest()
ARQ = Path(__file__).with_name("future_db.json")
XL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

TIPOS = {"in": ("📥", "Recebi dinheiro"), "out": ("💸", "Gastei dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Rendimento / juros"), "mov": ("🔁", "Mover entre caixinhas"),
         "del": ("🗑️", "Caixinha excluída")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"], ["Início", "Extrato", "Projeção", "Ideias"]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PALETAS = {
    "Padrão": {"pur": "#b57bff", "blue": "#4aa3ff", "gold": "#f0c24b", "grn": "#3fdc78", "red": "#ff6b62"},
    "Neon": {"pur": "#ff00ff", "blue": "#00ffff", "gold": "#ffff00", "grn": "#00ff00", "red": "#ff0000"},
    "Oceano": {"pur": "#3a0ca3", "blue": "#4361ee", "gold": "#4cc9f0", "grn": "#2ec4b6", "red": "#e71d36"},
    "Outono": {"pur": "#6a4c93", "blue": "#1982c4", "gold": "#ffca3a", "grn": "#8ac926", "red": "#ff595e"},
}
for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", paleta="Padrão", tab=0, nav=False, dir="R", fx=None, msg=None,
                   tent=0, bloq=0.0, chal=secrets.token_urlsafe(32), fid_done=None, bak_done=None, launch=False).items():
    st.session_state.setdefault(_k, _v)


# ---------------------------------------------------------------- utilidades
def agora():
    return datetime.now(TZ) if TZ else datetime.now()


def hoje_txt():
    h = agora()
    return f"{DIAS[h.weekday()]}, {h.day} {MESES[h.month - 1]}"


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


def _th(t):
    return hashlib.sha256((t or "").encode()).hexdigest()


def nova_conta(nome, senha, pin, nasc="2014-01-01", seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {}, "caixas_meta": {}, "extrato": [], "tema": "dark", "paleta": "Padrão", "nasc": nasc,
         "_v": 0.0 if seed else time.time(),
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None, "meta": 10000.0,
                 "reserva": 100.0, "tutorial": not seed, "ajustado": False},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:  # dados reais do Nubank: total R$ 2.038,40
        d["livre"] = 100.00
        d["caixas"] = {"futuro": 966.55, "sonho": 971.85}
        d["caixas_meta"] = {"futuro": ["Caixinha Futuro", "pur", "Principal · rende 100% do CDI"],
                            "sonho": ["Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato"]}
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
    if SB_URL:      # nuvem: se falhar, o app para (nunca sobrescreve dados salvos)
        r = json.loads(_sb("GET", "?id=eq.db&select=dados"))
        d = r[0]["dados"] if r else None
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


def sessoes():
    return db().setdefault("sessoes", {})


def salvar():
    u = st.session_state.get("u")
    if u in db()["contas"]:
        db()["contas"][u]["d"]["_v"] = time.time()
    with trava():
        try:
            if SB_URL:
                _sb("POST", "", [{"id": "db", "dados": db()}])
            else:
                ARQ.write_text(json.dumps(db(), ensure_ascii=False), "utf-8")
        except Exception:
            st.session_state["warn"] = "⚠️ Não consegui salvar na nuvem. Seus dados seguem salvos neste aparelho."


# ------------------------------------------------------------------ visual
def get_css(tema, nome):
    p = PALETAS.get(nome, PALETAS["Padrão"])
    if tema == "light":
        p = {k: "color-mix(in srgb," + v + " 70%,#000)" for k, v in p.items()}
    cores = f"--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']}"
    if tema == "light":
        return ":root{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--glass:rgba(255,255,255,.68);" + cores + "}"
    return ":root{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--glass:rgba(34,34,48,.58);" + cores + "}"


CSS_BASE = """
html,body,[data-testid="stApp"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:var(--bg)!important;overscroll-behavior-y:none;margin:0;padding:0}
.stApp{color:var(--tx);overflow-x:hidden;transition:background .3s}
header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
.block-container{max-width:480px!important;padding:1.2rem 1rem 10rem!important;margin:0 auto!important}
.stApp p,.stApp label,.stApp h1,.stApp li,[data-testid="stDialog"] *{color:var(--tx)}
.stApp input,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"]{background:var(--c2)!important;color:var(--tx)!important;border-radius:14px!important}
div[role="dialog"]{background:var(--c1)!important;border-radius:28px!important}
button[kind="secondary"],[data-testid="stBaseButton-secondary"]{background:var(--c2);border:1px solid var(--ln);border-radius:16px}
button[kind="secondary"] p,[data-testid="stBaseButton-secondary"] p{color:var(--tx)}
button[kind="primary"],[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--pur),var(--blue))!important;border:0!important;border-radius:16px!important}
button[kind="primary"] *,[data-testid="stBaseButton-primary"] *{color:#fff!important}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
.st-key-bak{position:fixed;left:0;bottom:0;width:0;height:0;overflow:hidden;opacity:0;pointer-events:none}
.hd h1{margin:0;font-size:26px;letter-spacing:-.03em;padding:0}.hd{margin-bottom:16px}
.rkw{position:relative;display:inline-block}
.rkw::before{content:"";position:absolute;inset:-22px;border-radius:50%;background:radial-gradient(circle,color-mix(in srgb,var(--pur) 38%,transparent),transparent 68%);animation:halo 3.4s ease-in-out infinite}
.logo{position:relative;font-size:64px;line-height:1;display:inline-block;animation:rocketLaunch .8s cubic-bezier(.175,.885,.32,1.275) forwards,bob 3.4s ease-in-out .9s infinite}
@keyframes rocketLaunch{0%{transform:translateY(80px) scale(.4);opacity:0}60%{transform:translateY(-15px) scale(1.1);opacity:1}100%{transform:none;opacity:1}}
@keyframes bob{50%{transform:translateY(-7px) rotate(-3deg)}}
@keyframes halo{50%{opacity:.45;transform:scale(1.12)}}
.card{background:linear-gradient(145deg,var(--c1),var(--c2));border:1px solid color-mix(in srgb,var(--c,var(--ln)) 50%,transparent);border-radius:26px;padding:18px;box-shadow:9px 9px 22px var(--s1),-5px -5px 16px var(--s2);margin-bottom:16px;transition:transform .2s cubic-bezier(.25,1,.5,1)}
.card:active{transform:scale(.97)}
button,label{transition:transform .15s ease,background .3s!important}button:active,label:active{transform:scale(.94)!important}
.k{color:var(--mu);font-size:13px}.lb{font-size:14px;font-weight:600}.big{font-size:34px;font-weight:700;letter-spacing:-.035em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.pg{height:8px;border-radius:9px;background:var(--ln);overflow:hidden;margin:6px 0}
.pg i{display:block;height:100%;border-radius:9px;background:linear-gradient(90deg,var(--blue),var(--grn));animation:grow 1.4s cubic-bezier(.25,1,.5,1)}
@keyframes grow{from{width:0}}
.rkbar{position:relative;padding-top:14px}
.rkbar s{position:absolute;top:-6px;margin-left:-9px;font-size:17px;text-decoration:none;animation:fly 1.4s cubic-bezier(.25,1,.5,1),bob 3s ease-in-out 1.4s infinite}
@keyframes fly{from{left:0}}
.as{font-size:15px;border-style:dashed}.sup{background:color-mix(in srgb,var(--gold) 16%,transparent);border:1px solid var(--gold);border-radius:18px;padding:12px 14px;margin-bottom:16px;font-size:14px}
.sp{display:flex;gap:10px;align-items:flex-start;padding:7px 0}.sp>span{font-size:18px;line-height:1.3}.sp.ok b{text-decoration:line-through;opacity:.5}
.tx{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--ln)}.tx:last-child{border:0}.tx .g{flex:1;min-width:0}
.ic{width:40px;height:40px;border-radius:14px;background:var(--c2);display:grid;place-items:center;font-size:19px;flex:none;border:1px solid var(--ln)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th{color:var(--mu);font-weight:500;text-align:right;padding:6px 0}td{padding:10px 0;text-align:right;border-top:1px solid var(--ln)}th:first-child,td:first-child{text-align:left}
.bar{fill:var(--grn);opacity:.9}.bt{fill:var(--mu);font-size:10px;text-anchor:middle}.tl{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1.2}
.al{display:flex;justify-content:space-between;align-items:baseline}.al b{font-size:20px}
.st-key-nav,.st-key-bolha{position:fixed;left:16px;bottom:calc(66px + env(safe-area-inset-bottom,0px));z-index:999;width:auto!important}
.st-key-nav{width:min(calc(100vw - 32px),420px)!important;display:flex!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:6px;overflow:hidden;background:var(--glass);backdrop-filter:blur(28px) saturate(180%);-webkit-backdrop-filter:blur(28px) saturate(180%);border:1px solid var(--ln);border-radius:34px;box-shadow:0 14px 40px var(--s1),inset 0 1px 0 rgba(255,255,255,.14);animation:stretch .7s cubic-bezier(.16,1,.3,1) forwards}
@keyframes stretch{from{width:58px!important;padding:0;opacity:0}}
.st-key-nav>div{width:auto!important;animation:fi .6s .15s cubic-bezier(.16,1,.3,1) both}@keyframes fi{from{opacity:0;transform:translateX(-16px)}}
.st-key-aba{flex:1!important}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:8px 0;border-radius:26px;cursor:pointer}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:10px;line-height:1.3;font-weight:600;text-align:center;word-spacing:100vw;margin:0;opacity:.55;transition:opacity .3s}
.st-key-nav label p::first-line{font-size:21px}
.st-key-nav label:has(input:checked){background:color-mix(in srgb,var(--pur) 26%,transparent)}
.st-key-nav label:has(input:checked) p{opacity:1}
.st-key-b_min button,.st-key-b_plus button,.st-key-bolha button,.st-key-b_tema button,.st-key-b_ajustes_top button,.st-key-b_sair button{border-radius:50%;padding:0;background:var(--glass);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid var(--ln)}
.st-key-b_min button{width:34px;height:34px}.st-key-b_plus button{width:46px;height:46px;border:0;background:linear-gradient(135deg,var(--pur),var(--blue))}
.st-key-b_plus button p{color:#fff;font-size:24px;line-height:1}
.st-key-bolha{animation:popin .4s cubic-bezier(.2,1.4,.4,1)}.st-key-bolha button{width:58px;height:58px;font-size:24px;box-shadow:0 10px 30px var(--s1)}
@keyframes popin{from{transform:scale(.4);opacity:0}}
.st-key-b_tema,.st-key-b_ajustes_top,.st-key-b_sair{position:fixed;z-index:1000;width:auto!important;top:calc(12px + env(safe-area-inset-top,0px))}
.st-key-b_tema{right:118px}.st-key-b_ajustes_top{right:66px}.st-key-b_sair{right:14px}
.st-key-b_tema button,.st-key-b_ajustes_top button,.st-key-b_sair button{width:44px;height:44px;font-size:18px}
[class*="_fromR"]{animation:slR .6s cubic-bezier(.25,1,.5,1) forwards}[class*="_fromL"]{animation:slL .6s cubic-bezier(.25,1,.5,1) forwards}
@keyframes slR{from{transform:translateX(50px);opacity:0}to{transform:none;opacity:1}}@keyframes slL{from{transform:translateX(-50px);opacity:0}to{transform:none;opacity:1}}
.fx,.lift{position:fixed;inset:0;pointer-events:none;z-index:2000;overflow:hidden}
.fx i{position:absolute;bottom:-50px;font-style:normal;opacity:0;animation:rise 2.4s ease-out forwards}
.fx b{position:absolute;left:50%;top:36%;font-size:36px;color:var(--grn);opacity:0;animation:pop 2.4s ease forwards;text-shadow:0 4px 24px rgba(0,0,0,.35)}
@keyframes rise{0%{transform:translateY(0) scale(.6);opacity:0}15%{opacity:1}100%{transform:translateY(-90vh) rotate(25deg) scale(1.1);opacity:0}}
@keyframes pop{0%{opacity:0;transform:translate(-50%,30px) scale(.7)}20%{opacity:1;transform:translate(-50%,0) scale(1.05)}80%{opacity:1}100%{opacity:0;transform:translate(-50%,-40px)}}
.lift i{position:absolute;left:6%;bottom:-70px;font-size:56px;font-style:normal;filter:drop-shadow(0 0 18px var(--gold));animation:blast 1.4s cubic-bezier(.5,0,.9,.4) forwards}
@keyframes blast{to{transform:translate(78vw,-118vh) scale(.6)}}
html,body,.stApp,.stApp p,.stApp label,.stApp input,.stApp textarea,.stApp button,.stApp [data-baseweb],div[role="dialog"] p{font-family:Inter,-apple-system,"SF Pro Text",system-ui,sans-serif!important}
.big,.hd h1,.al b,.lb{font-family:"Plus Jakarta Sans",Inter,system-ui,sans-serif!important}
@media (prefers-reduced-motion:reduce){*,::before,::after{animation:none!important;transition:none!important}}
"""
FONTES = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');"
st.markdown("<style>" + FONTES + get_css(st.session_state["tema"], st.session_state["paleta"]) + CSS_BASE + "</style>", unsafe_allow_html=True)

try:
    db()
except Exception:
    st.error("Não foi possível conectar ao banco de dados. Atualize a página em instantes.")
    st.stop()


# ------------------------------- componentes de navegador (backup + Face ID)
def _componente(nome, html_src):
    d = Path(__file__).with_name("_" + nome)
    try:
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(html_src, "utf-8")
    except Exception:
        pass
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
BACKUP, FACEID = _componente("bak", BAK_HTML), _componente("faceid", FACEID_HTML)


def _payload():
    u = st.session_state.get("u")
    if u not in db()["contas"]:
        return None
    th = _th(st.query_params.get("s", ""))
    body = json.dumps({"c": db()["contas"][u], "s": {th: sessoes()[th]} if th in sessoes() else {}}, sort_keys=True, ensure_ascii=False)
    return json.dumps({"u": u, "body": body, "sig": hmac.new(BK, body.encode(), "sha256").hexdigest()})


def restaurar(itens):
    """Restaura do aparelho contas que o servidor perdeu (ou o João recém-recriado). Só aceita backups assinados."""
    mudou = False
    for it in itens or []:
        try:
            if not hmac.compare_digest(hmac.new(BK, it["body"].encode(), "sha256").hexdigest(), it["sig"]):
                continue
            b, u = json.loads(it["body"]), it["u"]
            atual = db()["contas"].get(u)
            if (atual is None or atual["d"].get("_v", 0) == 0) and b["c"]["d"].get("_v", 0) > 0:
                db()["contas"][u] = b["c"]
                for h, r in b["s"].items():
                    if time.time() - r[2] < 30 * 86400:
                        sessoes()[h] = r
                mudou = True
        except Exception:
            continue
    if mudou:
        salvar()
    return mudou


_bk_val = BACKUP(save=_payload(), key="bak", default=None)
if _bk_val and _bk_val.get("n") != st.session_state["bak_done"]:
    st.session_state["bak_done"] = _bk_val["n"]
    if restaurar(_bk_val.get("itens")):
        st.rerun()


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
    sessoes()[_th(tok)] = [u, modo, time.time()]
    st.query_params["s"] = tok
    salvar()
    d = db()["contas"][u]["d"]
    st.session_state.update(u=u, modo=modo, tela="login", tent=0, launch=True, tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
    st.rerun()


def _ir(t):
    st.session_state["tela"] = t


def _falha():
    st.session_state["tent"] += 1
    if st.session_state["tent"] >= 3:
        st.session_state.update(bloq=time.time() + 60, tent=0)
    st.error("Dados incorretos. Após 3 erros o acesso é bloqueado por 1 minuto.")


def _espera():
    e = st.session_state["bloq"] - time.time()
    if e > 0:
        st.error(f"Segurança ativada. Aguarde {int(e) + 1}s para tentar novamente.")
    return e > 0


def tela_login():
    t = st.session_state["tela"]
    sub = {"login": "INICIAR SESSÃO", "criar": "CRIAR CONTA", "pais": "CONTROLE PARENTAL"}[t]
    st.markdown('<div style="display:flex;flex-direction:column;align-items:center;width:100%;text-align:center;padding:5vh 0 2vh">'
                '<div class="rkw"><div class="logo">🚀</div></div>'
                '<h1 style="font-size:36px;margin:14px 0 5px;padding:0;font-weight:800;letter-spacing:-1px;width:100%;text-align:center">FUTURE</h1>'
                '<div style="color:var(--mu);font-size:13px;letter-spacing:.2em;width:100%;text-align:center">' + sub + '</div></div>', unsafe_allow_html=True)
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
        st.button("Criar nova conta", key="b_criar", use_container_width=True, on_click=_ir, args=("criar",))
        st.caption("💾 Seus dados ficam salvos automaticamente, mesmo se o servidor reiniciar.")
        return
    if t == "criar":
        with st.form("f_criar"):
            n = st.text_input("Nome da conta", max_chars=24)
            p = st.text_input("Senha (mín. 4 caracteres)", type="password")
            pin = st.text_input("PIN dos pais (4 números)", type="password", max_chars=4)
            nasc = st.date_input("Data de nascimento", value=date(2014, 1, 1), min_value=date(1950, 1, 1), max_value=agora().date(), format="DD/MM/YYYY")
            go = st.form_submit_button("Criar conta", type="primary", use_container_width=True)
        if go:
            k = chave(n)
            if not 2 <= len(k) <= 24:
                st.error("Use um nome entre 2 e 24 caracteres.")
            elif k in db()["contas"]:
                st.error("Esse nome já existe.")
            elif len(p) < 4:
                st.error("A senha precisa de no mínimo 4 caracteres.")
            elif not (pin.isdigit() and len(pin) == 4):
                st.error("O PIN dos pais precisa ter exatamente 4 números.")
            else:
                db()["contas"][k] = nova_conta(n.strip(), p, pin, nasc=nasc.isoformat())
                salvar()
                entrar(k, "filho")
    else:
        with st.form("f_pais"):
            n = st.text_input("Nome da conta supervisionada", max_chars=24)
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
    r = sessoes().get(_th(st.query_params.get("s", "")))        # lembra a sessão (30 dias)
    if r and r[0] in db()["contas"] and time.time() - r[2] < 30 * 86400:
        d = db()["contas"][r[0]]["d"]
        st.session_state.update(u=r[0], modo=r[1], tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
        st.rerun()
if not st.session_state["u"]:
    tela_login()
    st.stop()

U, SUP = st.session_state["u"], st.session_state["modo"] == "pais"
CONTA = db()["contas"][U]
S = CONTA["d"]
S.setdefault("caixas", {})
S.setdefault("caixas_meta", {})
for _k, _v in dict(meta=62000.0, reserva=100.0, tutorial=False, ajustado=True, cdi=9.5, gastos=0.0, renda=0.0, guardar=0.0).items():
    S["cfg"].setdefault(_k, _v)
for _k, _t in (("futuro", ["Caixinha Futuro", "pur", "Principal · rende 100% do CDI"]), ("sonho", ["Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato"])):
    if _k in S["caixas"]:
        S["caixas_meta"].setdefault(_k, _t)


# ------------------------------------------------------------ regras de negócio
def total():
    return round(S["livre"] + sum(S["caixas"].values()), 2)


def idade_info():
    try:
        n = date.fromisoformat(S.get("nasc", "2014-01-01"))
    except Exception:
        n = date(2014, 1, 1)
    h = agora().date()
    idade = h.year - n.year - ((h.month, h.day) < (n.month, n.day))
    try:
        b18 = n.replace(year=n.year + 18)
    except ValueError:
        b18 = date(n.year + 18, 3, 1)
    meses = max(0, (b18.year - h.year) * 12 + b18.month - h.month - (1 if b18.day < h.day else 0))
    return idade, b18, meses


def prazo_txt(m):
    a, mm = divmod(m, 12)
    p = ([f"{a} ano" + ("s" if a > 1 else "")] if a else []) + ([f"{mm} " + ("mês" if mm == 1 else "meses")] if mm else [])
    return " e ".join(p) or "menos de 1 mês"


def reg(t, v, cx, obs, ts=None, dest=None):
    M = S["caixas_meta"]
    S["extrato"].append({"t": t, "v": round(v, 2), "c": cx, "d": dest, "o": obs, "ts": (ts or agora()).isoformat(),
                         "cn": M.get(cx, [None])[0] if cx else None, "dn": M.get(dest, [None])[0] if dest else None})


def fx(valor):
    st.session_state["fx"] = {"txt": "+" + brl(valor), "n": int(time.time() * 1000)}


def fecha(msg=None):
    S["livre"] = round(S["livre"], 2)
    for k in S["caixas"]:
        S["caixas"][k] = round(S["caixas"][k], 2)
    st.session_state["msg"] = msg or "Lançado em " + fmt_dt(S["extrato"][-1]["ts"])
    salvar()


def visivel(k):
    """Caixinha zerada some da tela, exceto se acabou de ser criada (nunca foi usada)."""
    return S["caixas"][k] > 0.004 or not any(x.get("c") == k or x.get("d") == k for x in S["extrato"])


def nome_cx(k):
    return S["caixas_meta"].get(k, ["Caixinha"])[0]


def aplicar(t, v, cx=None, obs=""):
    v, reserva, cxs = round(v, 2), S["cfg"]["reserva"], S["caixas"]
    if v <= 0:
        return "Informe um valor maior que zero."
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
            return "Essa caixinha não tem saldo para render."
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
    if v > S["caixas"][o] + 1e-9:
        return f"{nome_cx(o)} tem só {brl(S['caixas'][o])}."
    S["caixas"][o] -= v
    S["caixas"][d] += v
    reg("mov", v, o, obs, dest=d)
    fecha()
    return ""


def excluir_caixinha(cx, resgatar):
    v, nome = S["caixas"][cx], nome_cx(cx)
    if resgatar:
        S["livre"] += v
        reg("take", v, cx, "Resgate por exclusão")
    else:
        reg("del", v, cx, "Saldo removido do patrimônio")
    S["caixas"].pop(cx, None)
    S["caixas_meta"].pop(cx, None)
    fecha(f"{nome} excluída")


def liberar_sonho():
    sd = S["cfg"].get("sonho_data")
    if sd and agora().date().isoformat() >= sd:
        if "sonho" in S["caixas"] and "futuro" in S["caixas"] and S["caixas"]["sonho"] > 0.004:
            mover("sonho", "futuro", S["caixas"]["sonho"], "Sonho liberada → Futuro")
        S["cfg"]["sonho_data"] = None
        salvar()


def creditar_mes():
    """Todo dia 1: entra a renda, saem os gastos fixos e o valor definido vai para a primeira caixinha."""
    h, c = agora(), S["cfg"]
    a, m = S["ultimo_credito"].split("-")
    ult, atual = int(a) * 12 + int(m) - 1, h.year * 12 + h.month - 1
    if atual <= ult:
        return
    g, n = min(c["guardar"], max(0.0, c["renda"] - c["gastos"])), 0
    cx = next(iter(S["caixas"]), None)
    for k in range(ult + 1, atual + 1):
        if c["renda"] <= 0 and c["gastos"] <= 0:
            break
        ano, mes = divmod(k, 12)
        ts = datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=TZ)
        if c["renda"] > 0:
            S["livre"] += c["renda"]
            reg("in", c["renda"], None, "Renda mensal programada", ts)
        if c["gastos"] > 0:
            S["livre"] -= c["gastos"]
            reg("out", c["gastos"], None, "Gastos fixos do mês", ts)
        if g > 0 and cx:
            S["livre"] -= g
            S["caixas"][cx] += g
            reg("save", g, cx, "Aporte automático mensal", ts)
        n += 1
    S["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    if n:
        fx(c["renda"])
        fecha("Entradas e saídas do mês lançadas automaticamente.")
    else:
        salvar()


def projetar():
    c, h = S["cfg"], agora()
    r = (1 + c["cdi"] / 100) ** (1 / 12) - 1
    b = ap = total()
    n, linhas = 0, []
    idade, b18, meses = idade_info()
    ano_fim = b18.year if meses > 0 else h.year + 10
    aporte = max(0.0, c["renda"] - c["gastos"])
    for ano in range(h.year, ano_fim + 1):
        for _ in range(12 - h.month if ano == h.year else 12):
            b = b * (1 + r) + aporte
            ap += aporte
            n += 1
        linhas.append((ano, ap, b - ap, b))
    g = (1 + r) ** n
    falta = max(0.0, (c["meta"] - total() * g) / ((g - 1) / r)) if n and r > 0 else (max(0.0, (c["meta"] - total()) / n) if n else 0.0)
    return linhas, falta, ano_fim, c["meta"]


def destino(x):
    s = x.get("cn") or (nome_cx(x["c"]) if x.get("c") else "")
    d = x.get("dn") or (nome_cx(x["d"]) if x.get("d") else "")
    return s + (" → " + d if d else "")


# ------------------------------------------------------------------ downloads
def _csv(cab, linhas):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(cab)
    w.writerows(linhas)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _xlsx(titulo, cab, linhas, fmts, larg, notas=(), grafico=False):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.chart import BarChart, Reference
        from openpyxl.utils import get_column_letter as col
    except Exception:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = titulo
    ws.sheet_view.showGridLines = False
    ws["A1"] = "🚀 FUTURE · " + titulo
    ws["A1"].font = Font(bold=True, size=16, color="5B2BE0")
    ws["A2"] = f"{CONTA['nome']} · gerado em {agora():%d/%m/%Y às %H:%M}"
    ws["A2"].font = Font(size=10, color="888888")
    for j, c in enumerate(cab, 1):
        x = ws.cell(4, j, c)
        x.font, x.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="5B2BE0")
        x.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[col(j)].width = larg[j - 1]
    ws.row_dimensions[4].height = 24
    for i, lin in enumerate(linhas, 1):
        for j, v in enumerate(lin, 1):
            x = ws.cell(4 + i, j, v)
            if fmts[j - 1]:
                x.number_format = fmts[j - 1]
            if i % 2 == 0:
                x.fill = PatternFill("solid", fgColor="F3EEFF")
    ws.freeze_panes = "A5"
    n = len(linhas) + 6
    for k, (a, v, f) in enumerate(notas):
        ws.cell(n + k, 1, a).font = Font(bold=True)
        x = ws.cell(n + k, 2, v)
        if f:
            x.number_format = f
    if grafico and linhas:
        ch = BarChart()
        ch.title, ch.height, ch.width, ch.legend = "Patrimônio projetado", 8, 16, None
        ch.add_data(Reference(ws, min_col=4, min_row=4, max_row=4 + len(linhas)), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=4 + len(linhas)))
        ws.add_chart(ch, col(len(cab) + 2) + "4")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00'


def proj_dados():
    L, _, _, meta = projetar()
    return [(a, p, j, b, b / meta if meta > 0 else 0) for a, p, j, b in L]


def xlsx_proj():
    c = S["cfg"]
    return _xlsx("Projeção", ["Ano", "Capital investido", "Juros acumulados", "Patrimônio total", "% da meta"], proj_dados(),
                 [None, MOEDA, MOEDA, MOEDA, "0.0%"], [10, 22, 22, 22, 14],
                 [("Meta (R$)", c["meta"], MOEDA), ("Ponto de partida (R$)", total(), MOEDA), ("Aporte líquido mensal (R$)", max(0.0, c["renda"] - c["gastos"]), MOEDA),
                  ("CDI estimado (% a.a.)", c["cdi"], None)], True)


def csv_proj():
    m = lambda v: f"{v:.2f}".replace(".", ",")
    return _csv(["Ano", "Capital investido (R$)", "Juros acumulados (R$)", "Patrimônio total (R$)", "% da meta"],
                [(a, m(p), m(j), m(b), f"{q * 100:.1f}".replace(".", ",") + "%") for a, p, j, b, q in proj_dados()])


def _extrato_linhas():
    out = []
    for x in sorted(S["extrato"], key=lambda e: e["ts"], reverse=True):
        v = x["v"] if x["t"] in ("in", "yld") else -x["v"] if x["t"] in ("out", "del") else x["v"]
        out.append((datetime.fromisoformat(x["ts"]).replace(tzinfo=None), TIPOS[x["t"]][1], destino(x), x["o"], v))
    return out


def xlsx_ext():
    return _xlsx("Extrato", ["Data e hora", "Tipo", "Caixinha", "Observação", "Valor (R$)"], _extrato_linhas(),
                 ["dd/mm/yyyy hh:mm", None, None, None, MOEDA], [20, 26, 34, 32, 18], [("Patrimônio atual (R$)", total(), MOEDA)])


def csv_ext():
    return _csv(["Data", "Hora", "Tipo", "Caixinha", "Valor (R$)", "Observação"],
                [(d.strftime("%d/%m/%Y"), d.strftime("%H:%M:%S"), t, c, f"{v:.2f}".replace(".", ","), ("'" + o if o[:1] in "=+-@" and o else o))
                 for d, t, c, o, v in _extrato_linhas()])


RELATORIO = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Relatório FUTURE</title><style>
:root{--gold:#d69b00}*{box-sizing:border-box}body{margin:0;background:#f3f1fb;color:#1a1530;font:15px/1.5 Inter,-apple-system,"Segoe UI",Roboto,sans-serif}
.w{max-width:760px;margin:0 auto;padding:28px 18px}.hero{background:linear-gradient(135deg,#6d3fe0,#3b82f6);color:#fff;border-radius:24px;padding:26px}
.hero small{opacity:.85;letter-spacing:.14em;text-transform:uppercase;font-size:11px}.hero h1{margin:6px 0 2px;font-size:38px;letter-spacing:-.03em}
.ch{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.ch span{background:rgba(255,255,255,.2);border-radius:99px;padding:6px 12px;font-size:13px}
.c{background:#fff;border-radius:22px;padding:18px;margin-top:16px;box-shadow:0 8px 30px rgba(60,40,140,.08)}
table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:right;color:#7a7596;font-weight:600;padding:8px 6px;border-bottom:2px solid #eee}td{text-align:right;padding:10px 6px;border-bottom:1px solid #f0eef8}th:first-child,td:first-child{text-align:left}.g{color:#12843f}
.bar{fill:#6d3fe0}.bt{fill:#7a7596;font-size:10px;text-anchor:middle}.tl{stroke:#d69b00;stroke-dasharray:4 4;stroke-width:1.2}
.n{color:#7a7596;font-size:12px;margin-top:14px}button{margin-top:16px;width:100%;padding:14px;border:0;border-radius:14px;background:#6d3fe0;color:#fff;font-size:15px;font-weight:600;cursor:pointer}
@media print{body{background:#fff}button{display:none}.c{box-shadow:none;border:1px solid #eee}}
</style></head><body><div class="w"><div class="hero"><small>🚀 FUTURE · Projeção financeira de __NOME__</small><h1>__FIM__</h1><div>__SUB__</div><div class="ch">__CHIPS__</div></div>
<div class="c">__SVG__</div><div class="c"><table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th><th>Meta</th></tr>__ROWS__</table></div>
<div class="n">__NOTA__</div><button onclick="window.print()">Imprimir / salvar como PDF</button></div></body></html>"""


def relatorio_html():
    L, falta, ano_fim, meta = projetar()
    fim = L[-1][3] if L else total()
    c = S["cfg"]
    sub = f"Projeção para {ano_fim} · meta de {brl(meta)}" + (" alcançada ✅" if fim >= meta else f" · faltam {brl(meta - fim)}")
    chips = "".join("<span>" + x + "</span>" for x in (f"Hoje: {brl(total())}", f"Aporte: {brl(max(0.0, c['renda'] - c['gastos']))}/mês", f"CDI: {c['cdi']}% a.a.", f"Gerado em {agora():%d/%m/%Y}"))
    rows = "".join(f'<tr><td>{a}</td><td>{brl(p)}</td><td class="g">{brl(j)}</td><td><b>{brl(b)}</b></td><td>{q * 100:.0f}%</td></tr>' for a, p, j, b, q in proj_dados())
    nota = "Simulação educativa com rendimento de 100% do CDI estimado, bruto e sem impostos. Não é recomendação de investimento."
    rep = {"__NOME__": html.escape(CONTA["nome"]), "__FIM__": brl(fim), "__SUB__": sub, "__CHIPS__": chips, "__SVG__": svg_barras(L, meta), "__ROWS__": rows, "__NOTA__": nota}
    out = RELATORIO
    for k, v in rep.items():
        out = out.replace(k, v)
    return out.encode("utf-8")


# ------------------------------------------------------------------ telas
def fx_html(d):
    random.seed(d["n"])
    itens = "".join('<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
                    % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
                       random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return '<div class="fx">' + itens + '<b>' + d["txt"] + '</b></div>'


def card(cor, tit, val, sub="", extra=""):
    return ('<div class="card" style="--c:var(--' + cor + ')"><div class="lb" style="color:var(--' + cor + ')">' + tit + '</div>'
            '<div class="big">' + val + '</div>' + extra + '<div class="k">' + sub + '</div></div>')


def passos():
    c = S["cfg"]
    p = [("Definir sua meta e reserva", "Toque em ⚙️ no topo da tela", c["ajustado"]),
         ("Cadastrar renda e gastos do mês", "⚙️ › Balanço mensal (cai todo dia 1)", c["renda"] > 0),
         ("Criar sua primeira caixinha", "＋ › Montar Caixinha", bool(S["caixas"])),
         ("Fazer seu primeiro lançamento", "＋ › Conta ou Caixinhas", bool(S["extrato"]))]
    if HAS_CRYPTO:
        p.append(("Ativar o Face ID", "⚙️ › Ativar Face ID neste aparelho", bool(CONTA.get("fid"))))
    return p


def v_tutorial():
    idade, b18, meses = idade_info()
    ps = passos()
    feitos = sum(1 for p in ps if p[2])
    frase = (f"Faltam <b>{prazo_txt(meses)}</b> para os 18 anos. Cada mês conta!" if meses > 0
             else f"Você já tem {idade} anos, então a projeção olha 10 anos à frente.")
    lis = "".join('<div class="sp' + (" ok" if f else "") + '"><span>' + ("✅" if f else "⭕") + '</span><div><b>' + a + '</b><div class="k">' + b + '</div></div></div>' for a, b, f in ps)
    tit = "🎉 Tudo pronto!" if feitos == len(ps) else "👋 Vamos começar, " + html.escape(CONTA["nome"]) + "?"
    return ('<div class="card as" style="border-color:var(--pur)"><div class="lb" style="color:var(--pur);font-size:16px">' + tit + '</div>'
            '<div class="k" style="margin:4px 0 8px">' + frase + '</div><div class="pg"><i style="width:' + str(feitos / len(ps) * 100) + '%"></i></div>'
            '<div class="k">' + str(feitos) + ' de ' + str(len(ps)) + ' passos</div><div style="margin-top:8px">' + lis + '</div></div>')


def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    _, _, ano_fim, meta = projetar()
    idade, b18, meses = idade_info()
    reserva = c["reserva"]
    pc = min(100, t / meta * 100) if meta > 0 else 0
    if f > reserva + .005:
        msg = "Você tem <b>" + brl(f - reserva) + "</b> acima da reserva fixa. Veja onde aplicar na aba Ideias."
    elif f < reserva - .005:
        msg = "Atenção: faltam <b>" + brl(reserva - f) + "</b> para completar a sua reserva fixa."
    else:
        msg = "Sua reserva fixa está completa. Tudo em ordem."
    h = agora()
    prox = f"01/{h.month + 1:02d}/{h.year}" if h.month < 12 else f"01/01/{h.year + 1}"
    mesada = ("<br>Próxima entrada automática: " + prox) if (c["renda"] > 0 or c["gastos"] > 0) else "<br>Configure renda e gastos em ⚙️."
    pct = f"{pc:.1f}".replace(".", ",")
    prazo = f"faltam {prazo_txt(meses)} para os 18 anos" if meses > 0 else f"projeção até {ano_fim}"
    out = card("grn", "Patrimônio total", brl(t), f"{pct}% da meta de {brl(meta)} · {prazo}",
               '<div class="rkbar"><div class="pg"><i style="width:' + str(pc) + '%"></i></div><s style="left:' + str(max(pc, 2)) + '%">🚀</s></div>')
    out += '<div class="card as">💡 ' + msg + '</div>'
    out += card("blue", "Saldo livre", brl(f), "Reserva fixa: " + brl(reserva) + mesada)
    for k, v in S["caixas"].items():
        if visivel(k):
            m = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
            out += card(m[1], html.escape(m[0]), brl(v), html.escape(m[2]) or "Faça o primeiro aporte em ＋ › Caixinhas")
    return out


def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k">Nenhum lançamento ainda. Toque em ＋ para começar.</div></div>'
    rows = ""
    for _, x in sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True):
        ic, nome = TIPOS[x["t"]]
        tr, ps = x["t"] in ("save", "take", "mov"), x["t"] in ("in", "yld")
        cor = "blue" if tr else "grn" if ps else "red"
        sg = {"save": "→ ", "take": "← ", "mov": "↔ "}.get(x["t"], "+" if ps else "−")
        det = (html.escape(destino(x)) + " · " if x.get("c") else "") + (html.escape(x["o"]) + " · " if x["o"] else "") + fmt_dt(x["ts"])
        rows += ('<div class="tx"><span class="ic">' + ic + '</span><div class="g"><b>' + nome + '</b><div class="k">' + det + '</div></div>'
                 '<b style="color:var(--' + cor + ')">' + sg + brl(x["v"]) + '</b></div>')
    return '<div class="card" style="padding:6px 16px">' + rows + '</div>'


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
        s += ('<rect class="bar" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="7"/><text class="bt" x="%.1f" y="%.1f">%s</text><text class="bt" x="%.1f" y="%d">%s</text>'
              % (x, H - 24 - h, bw * .66, h, x + bw * .33, H - 28 - h, kf(b), x + bw * .33, H - 7, ano))
    return s + "</svg>"


def v_proj():
    L, falta, ano_fim, meta = projetar()
    fim = L[-1][3]
    ok = fim >= meta
    sub = (f"Meta de {brl(meta)} alcançada, com {brl(fim - meta)} de folga." if ok
           else f"Para chegar a {brl(meta)}, o aporte líquido precisa ser de cerca de {brl(falta)} por mês.")
    tab = '<table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th></tr>'
    for a, p, j, b in L:
        tab += '<tr><td>' + str(a) + '</td><td>' + brl(p) + '</td><td style="color:var(--grn)">' + brl(j) + '</td><td><b>' + brl(b) + '</b></td></tr>'
    c = S["cfg"]
    return (card("grn" if ok else "gold", "Projeção até " + str(ano_fim), brl(fim), sub)
            + '<div class="card">' + svg_barras(L, meta) + '</div><div class="card">' + tab + '</table></div>'
            + '<div class="k" style="padding:0 6px">Ponto de partida de hoje: ' + brl(total()) + ' · aporte líquido de ' + brl(max(0.0, c["renda"] - c["gastos"]))
            + '/mês · 100% do CDI a ' + str(c["cdi"]).replace(".", ",") + '% a.a. (bruto, estimado).</div>')


def v_idea():
    reserva = S["cfg"]["reserva"]
    ex = round(max(0.0, S["livre"] - reserva), 2)
    opc = [("Reserva de liquidez diária", 1.0 if ex < 50 else .4, "blue", "CDB ou RDB com liquidez diária pagando cerca de 100% do CDI. Dinheiro à mão para imprevistos."),
           ("RDB de longo prazo", .35, "pur", "Prazos de 2 a 5 anos costumam render acima do CDI. Confira a cobertura do FGC."),
           ("Tesouro IPCA+", .25, "gold", "Rende inflação mais juros fixos e protege o poder de compra. Escolha vencimento próximo da sua meta.")]
    if ex < 50:
        opc = opc[:1]
    sub = "Sugestão de divisão para esse valor:" if ex else "Seu saldo livre precisa passar de " + brl(reserva + 50) + " para liberar sugestões."
    out = card("blue", "Disponível acima da reserva", brl(ex), sub)
    if ex:
        for nome, p, cor, txt in opc:
            out += ('<div class="card" style="--c:var(--' + cor + ')"><div class="al"><span class="lb">' + nome + '</span><b style="color:var(--' + cor + ')">'
                    + brl(ex * p) + '</b></div><div class="k">' + str(round(p * 100)) + '% · ' + txt + '</div></div>')
    return out + '<div class="k" style="padding:0 6px">Sugestões educativas, não são recomendação personalizada de investimento.</div>'


# ------------------------------------------------------------------ diálogos
@st.dialog("⚙️ Ajustes da conta")
def dlg_ajustes():
    c = S["cfg"]
    tem_sonho = "sonho" in S["caixas"] and "futuro" in S["caixas"]
    pal = list(PALETAS)
    with st.form("f_ajustes"):
        nome = st.text_input("Nome da conta", CONTA["nome"], max_chars=24)
        paleta = st.selectbox("Cores do app", pal, index=pal.index(S["paleta"]) if S.get("paleta") in pal else 0)
        tutorial = st.checkbox("Mostrar tutorial na tela Início", value=c["tutorial"])
        st.caption("🎯 META E RESERVA")
        meta = st.number_input("Meta financeira (R$)", min_value=0.0, value=float(c["meta"]), step=1000.0, format="%.2f")
        reserva = st.number_input("Reserva fixa protegida no Saldo Livre (R$)", min_value=0.0, value=float(c["reserva"]), step=50.0, format="%.2f")
        st.caption("💰 BALANÇO MENSAL (lançado todo dia 1)")
        renda = st.number_input("Renda mensal (R$)", min_value=0.0, value=float(c["renda"]), step=50.0, format="%.2f")
        gast = st.number_input("Gastos fixos do mês (R$)", min_value=0.0, value=float(c["gastos"]), step=10.0, format="%.2f")
        guard = st.number_input("Guardar automático na primeira caixinha (R$)", min_value=0.0, value=float(c["guardar"]), step=50.0, format="%.2f")
        cdi = st.number_input("CDI estimado (% ao ano)", min_value=0.0, max_value=100.0, value=float(c["cdi"]), step=0.1, format="%.2f")
        sd = st.date_input("Liberar a Sonho para a Futuro em (opcional)", value=date.fromisoformat(c["sonho_data"]) if c.get("sonho_data") else None,
                           format="DD/MM/YYYY") if tem_sonho else None
        if st.form_submit_button("Salvar", type="primary", use_container_width=True):
            CONTA["nome"] = nome.strip() or CONTA["nome"]
            S["paleta"] = st.session_state["paleta"] = paleta
            S["cfg"].update(renda=renda, gastos=gast, guardar=min(guard, max(0.0, renda - gast)), cdi=cdi, meta=meta, reserva=reserva, tutorial=tutorial, ajustado=True)
            if tem_sonho:
                S["cfg"]["sonho_data"] = sd.isoformat() if sd else None
            fecha("Ajustes salvos!")
            st.rerun()
    if HAS_CRYPTO:
        st.divider()
        r = FACEID(modo="reg", chal=st.session_state["chal"], user=U, tema=st.session_state["tema"], key="fid_reg", default=None)
        if r and r.get("kind") == "reg" and r["n"] != st.session_state["fid_done"]:
            st.session_state["fid_done"] = r["n"]
            if fid_registrar(U, r):
                st.session_state["msg"] = "Face ID ativado neste aparelho!"
                st.rerun()
            st.error("Não foi possível validar o Face ID.")


def form_op(op):
    cx = cx2 = None
    if op in ("save", "take", "yld", "mov"):
        ops = [k for k in S["caixas"] if op == "save" or S["caixas"][k] > 0]
        if not ops:
            st.info("Nenhuma caixinha disponível ainda. Crie uma na aba ➕ Montar Caixinha." if op == "save" else "Nenhuma caixinha com saldo ainda.")
            return
        cx = st.selectbox("De" if op == "mov" else "Caixinha", ops, key="c_" + op, format_func=lambda k: nome_cx(k) + " · " + brl(S["caixas"][k]))
        if op == "mov":
            outras = [k for k in S["caixas"] if k != cx]
            if not outras:
                st.info("Crie outra caixinha para poder mover valores.")
                return
            cx2 = st.selectbox("Para", outras, key="d_mov", format_func=nome_cx)
    v = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=0.10 if op == "yld" else 1.0, format="%.2f", key="v_" + op)
    if op == "yld" and cx:
        st.caption(f"100% do CDI rende cerca de {brl(S['caixas'][cx] * ((1 + S['cfg']['cdi'] / 100) ** (1 / 252) - 1))} por dia útil nessa caixinha.")
    obs = st.text_input("Observação (opcional)", max_chars=40, key="o_" + op)
    if st.button("Confirmar", type="primary", use_container_width=True, key="ok_" + op):
        e = mover(cx, cx2, v, obs.strip()) if op == "mov" else aplicar(op, v, cx, obs.strip())
        if e:
            st.error(e)
        else:
            st.rerun()


def form_criar_cx():
    st.caption("Crie caixinhas para cada objetivo. Todas rendem 100% do CDI com resgate imediato.")
    nome = st.text_input("Nome do objetivo (ex: Intercâmbio)", max_chars=24)
    cor = st.selectbox("Cor", ["pur", "blue", "gold", "grn", "red"], format_func={"pur": "Roxo", "blue": "Azul", "gold": "Dourado", "grn": "Verde", "red": "Vermelho"}.get)
    desc = st.text_input("Descrição (opcional)", max_chars=40)
    if st.button("Criar caixinha", type="primary", use_container_width=True):
        if not nome.strip():
            st.error("Dê um nome para a caixinha.")
        else:
            k = chave(nome) + "-" + secrets.token_hex(2)
            S["caixas"][k] = 0.0
            S["caixas_meta"][k] = [nome.strip(), cor, desc.strip()]
            fecha("Caixinha criada! Agora guarde um valor nela em ＋ › Caixinhas.")
            st.rerun()


@st.dialog("Novo lançamento")
def dlg_novo():
    t1, t2, t3 = st.tabs(["💳 Conta", "🐷 Caixinhas", "➕ Montar Caixinha"])
    with t1:
        form_op(st.radio("Conta", ["in", "out"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r1"))
    with t2:
        form_op(st.radio("Caixinhas", ["save", "take", "yld", "mov"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r2"))
    with t3:
        form_criar_cx()


@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():
    ops = list(S["caixas"])
    if not ops:
        st.info("Nenhuma caixinha para excluir.")
        return
    cx = st.selectbox("Qual caixinha?", ops, format_func=lambda k: nome_cx(k) + " · " + brl(S["caixas"][k]))
    modo = st.radio("O que fazer com o saldo?", ["Resgatar para o Saldo Livre", "Apenas zerar (sai do patrimônio)"])
    if st.button("Excluir caixinha", type="primary", use_container_width=True):
        excluir_caixinha(cx, modo.startswith("Resgatar"))
        st.rerun()


@st.dialog("🛡️ Painel dos pais")
def dlg_pais():
    st.caption("Modo supervisão: somente leitura. Aqui você pode redefinir os acessos.")
    senha = st.text_input("Nova senha do titular (mín. 4)", type="password")
    pin = st.text_input("Novo PIN dos pais (4 números)", type="password", max_chars=4)
    if st.button("Salvar", type="primary", use_container_width=True):
        if (senha and len(senha) < 4) or (pin and not (pin.isdigit() and len(pin) == 4)):
            st.error("Senha com 4+ caracteres e PIN com exatamente 4 números.")
        else:
            if senha:
                CONTA["s"], CONTA["h"] = mk(senha)
            if pin:
                CONTA["ps"], CONTA["ph"] = mk(pin)
            salvar()
            st.session_state["msg"] = "Acessos atualizados"
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
    sessoes().pop(_th(st.query_params.get("s", "")), None)
    salvar()
    st.query_params.clear()
    st.session_state.update(u=None, modo=None, tela="login", chal=secrets.token_urlsafe(32))


def _nav(v):
    st.session_state["nav"] = v


st.button("☀️" if st.session_state["tema"] == "dark" else "🌙", key="b_tema", on_click=_tema, help="Alternar tema")
if not SUP and st.button("⚙️", key="b_ajustes_top", help="Ajustes da conta"):
    dlg_ajustes()
st.button("🔒", key="b_sair", on_click=_sair, help="Encerrar sessão")

tab = st.session_state["tab"]
if st.session_state["nav"]:
    with st.container(key="nav"):
        st.button("‹", key="b_min", on_click=_nav, args=(False,), help="Recolher menu")
        aba = st.radio("Atalhos", ABAS, index=tab, key="aba", horizontal=True, label_visibility="collapsed")
        if st.button("🛡️" if SUP else "＋", key="b_plus", help="Painel dos pais" if SUP else "Novo lançamento"):
            (dlg_pais if SUP else dlg_novo)()
    idx = ABAS.index(aba)
else:
    st.button(ABAS[tab].split()[0], key="bolha", on_click=_nav, args=(True,), help="Abrir menu")
    idx = tab
if idx != tab:
    st.session_state.update(dir="R" if idx > tab else "L", tab=idx)

st.markdown('<div class="hd"><div class="k">' + TITULOS[idx] + ' · ' + hoje_txt() + '</div><h1>' + html.escape(CONTA["nome"]) + '</h1></div>', unsafe_allow_html=True)
if SUP:
    st.markdown('<div class="sup">🔐 <b>Modo supervisão:</b> somente leitura. Lançamentos e ajustes ficam ocultos.</div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    if idx == 0:
        if S["cfg"]["tutorial"] and not SUP:
            st.markdown(v_tutorial(), unsafe_allow_html=True)
            if st.button("Concluir tutorial", key="b_tut", use_container_width=True):
                S["cfg"]["tutorial"] = False
                fecha("Tutorial concluído. Você pode reativá-lo em ⚙️ Ajustes.")
                st.rerun()
        st.markdown(v_home(), unsafe_allow_html=True)
        if not SUP and S["caixas"]:
            if st.button("🗑️ Excluir caixinha", key="b_del", use_container_width=True):
                dlg_excluir()
    elif idx == 1:
        st.markdown(v_ext(), unsafe_allow_html=True)
        if S["extrato"]:
            hoje, x = f"{agora():%Y-%m-%d}", xlsx_ext()
            c1, c2 = st.columns(2)
            if x:
                c1.download_button("📊 Baixar Excel", x, file_name=f"extrato_future_{hoje}.xlsx", mime=XL, use_container_width=True)
            c2.download_button("📄 Baixar CSV", csv_ext(), file_name=f"extrato_future_{hoje}.csv", mime="text/csv", use_container_width=True)
    elif idx == 2:
        st.markdown(v_proj(), unsafe_allow_html=True)
        hoje, x = f"{agora():%Y-%m-%d}", xlsx_proj()
        c1, c2 = st.columns(2)
        if x:
            c1.download_button("📊 Baixar Excel", x, file_name=f"projecao_future_{hoje}.xlsx", mime=XL, use_container_width=True)
        else:
            c1.download_button("📄 Baixar CSV", csv_proj(), file_name=f"projecao_future_{hoje}.csv", mime="text/csv", use_container_width=True)
        c2.download_button("🖨️ Relatório (PDF)", relatorio_html(), file_name=f"relatorio_future_{hoje}.html", mime="text/html", use_container_width=True)
    else:
        st.markdown(v_idea(), unsafe_allow_html=True)

if st.session_state["fx"]:
    st.markdown(fx_html(st.session_state["fx"]), unsafe_allow_html=True)
    st.session_state["fx"] = None
if st.session_state["launch"]:
    st.markdown('<div class="lift"><i>🚀</i></div>', unsafe_allow_html=True)
    st.session_state["launch"] = False

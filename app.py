# -*- coding: utf-8 -*-
"""Projeto 18 Anos - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography   (cryptography = verificação do Face ID)
Rodar: streamlit run app.py   |   Deploy: Streamlit Cloud (HTTPS é obrigatório para Face ID)
Contas novas começam zeradas. Senha 5102 abre a conta pré-carregada (dados do Nubank);
PIN 0506 abre essa mesma conta em Controle Parental. Para esconder esses códigos use Secrets:
codigo = "5102"  /  pin_pais = "0506"
"""
import csv, io, json, random, time, html, hmac, hashlib, base64, secrets, threading
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

st.set_page_config(page_title="Projeto 18 Anos", page_icon="💜", layout="centered", initial_sidebar_state="collapsed")
try:
    CODIGO, PIN_PAIS = str(st.secrets["codigo"]), str(st.secrets["pin_pais"])
except Exception:
    CODIGO, PIN_PAIS = "5102", "0506"

SEED = "projeto18"
ARQ = Path(__file__).with_name("projeto18_db.json")
META, RESERVA, ANO_FIM = 62000.0, 100.0, 2032
CAIXAS = {"futuro": ("Caixinha Futuro", "pur", "Principal · rende 100% do CDI"),
          "sonho": ("Caixinha Sonho", "gold", "Rende 100% do CDI · resgate imediato")}
TIPOS = {"in": ("📥", "Recebi dinheiro"), "out": ("💸", "Gastei dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Rendimento / juros"), "mov": ("🔁", "Mover entre caixinhas"),
         "del": ("🗑️", "Caixinha zerada")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠", "🧾", "📈", "💡"], ["Início", "Extrato", "Projeção", "Ideias"]

for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", tab=0, nav=True, dir="R", fx=None, msg=None,
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


def b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mk(txt):
    s = secrets.token_bytes(16)
    return s.hex(), hashlib.pbkdf2_hmac("sha256", txt.encode(), s, 150000).hex()


def confere(txt, s, h):
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", txt.encode(), bytes.fromhex(s), 150000).hex(), h)


def nova_conta(nome, senha, pin, seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {"futuro": 0.0, "sonho": 0.0}, "extrato": [], "tema": "dark",
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:  # dados reais do Nubank: total R$ 2.038,40
        d["livre"], d["caixas"] = 100.00, {"futuro": 966.55, "sonho": 971.85}
        d["cfg"].update(renda=600.0, guardar=500.0)
    return {"nome": nome, "s": s, "h": h, "ps": ps, "ph": ph, "fid": {}, "d": d}


@st.cache_resource
def db():
    try:
        d = json.loads(ARQ.read_text("utf-8"))
    except Exception:
        d = {}
    d.setdefault("contas", {})
    if SEED not in d["contas"]:
        d["contas"][SEED] = nova_conta("Minha Conta", CODIGO, PIN_PAIS, True)
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
            ARQ.write_text(json.dumps(db(), ensure_ascii=False), "utf-8")
        except Exception:
            pass


# ------------------------------------------------------------------ visual
TEMAS = {
    "dark": ":root{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--blue:#4aa3ff;--pur:#b57bff;--gold:#f0c24b;--grn:#3fdc78;--red:#ff6b62;--glass:rgba(34,34,48,.58)}",
    "light": ":root{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--blue:#0a6fe0;--pur:#8a35d8;--gold:#9a6f00;--grn:#12843f;--red:#d9342b;--glass:rgba(255,255,255,.68)}",
}
CSS = """
.stApp{background:var(--bg)!important;color:var(--tx);overflow-x:hidden;font-family:-apple-system,"SF Pro Text",Roboto,system-ui,sans-serif}
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
.st-key-nav{width:min(calc(100vw - 32px),420px)!important;display:flex!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:6px;overflow:hidden;background:var(--glass);backdrop-filter:blur(28px) saturate(180%);-webkit-backdrop-filter:blur(28px) saturate(180%);border:1px solid var(--ln);border-radius:999px;box-shadow:0 14px 40px var(--s1),inset 0 1px 0 rgba(255,255,255,.14);animation:stretch .55s cubic-bezier(.2,.9,.2,1)}
@keyframes stretch{from{width:58px!important;padding:0}}
.st-key-nav>div{width:auto!important;animation:fi .5s .12s both}@keyframes fi{from{opacity:0;transform:translateX(-12px)}}
.st-key-aba{flex:1!important}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:11px 0;border-radius:999px;cursor:pointer;transition:background .3s}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:20px;line-height:1;opacity:.5;transition:opacity .3s}
.st-key-nav label:has(input:checked){background:color-mix(in srgb,var(--pur) 26%,transparent)}
.st-key-nav label:has(input:checked) p{opacity:1}
.st-key-b_min button,.st-key-b_plus button,.st-key-bolha button,.st-key-b_tema button,.st-key-b_sair button{border-radius:50%;padding:0;background:var(--glass);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid var(--ln)}
.st-key-b_min button{width:34px;height:34px}.st-key-b_plus button{width:46px;height:46px;border:0;background:linear-gradient(135deg,var(--pur),var(--blue))}
.st-key-b_plus button p{color:#fff;font-size:24px;line-height:1}
.st-key-bolha{animation:popin .4s cubic-bezier(.2,1.4,.4,1)}.st-key-bolha button{width:58px;height:58px;font-size:24px;box-shadow:0 10px 30px var(--s1)}
@keyframes popin{from{transform:scale(.4);opacity:0}}
.st-key-b_tema,.st-key-b_sair{position:fixed;z-index:1000;width:auto!important;top:calc(12px + env(safe-area-inset-top,0px))}
.st-key-b_tema{right:66px}.st-key-b_sair{right:14px}.st-key-b_tema button,.st-key-b_sair button{width:44px;height:44px;font-size:18px}
[class*="_fromR"]{animation:slR .4s cubic-bezier(.2,.8,.2,1)}[class*="_fromL"]{animation:slL .4s cubic-bezier(.2,.8,.2,1)}
@keyframes slR{from{transform:translateX(48px);opacity:0}}@keyframes slL{from{transform:translateX(-48px);opacity:0}}
.fx{position:fixed;inset:0;pointer-events:none;z-index:2000;overflow:hidden}
.fx i{position:absolute;bottom:-50px;font-style:normal;opacity:0;animation:rise 2.4s ease-out forwards}
.fx b{position:absolute;left:50%;top:36%;font-size:36px;color:var(--grn);opacity:0;animation:pop 2.4s ease forwards;text-shadow:0 4px 24px rgba(0,0,0,.35)}
@keyframes rise{0%{transform:translateY(0) scale(.6);opacity:0}15%{opacity:1}100%{transform:translateY(-90vh) rotate(25deg) scale(1.1);opacity:0}}
@keyframes pop{0%{opacity:0;transform:translate(-50%,30px) scale(.7)}20%{opacity:1;transform:translate(-50%,0) scale(1.05)}80%{opacity:1}100%{opacity:0;transform:translate(-50%,-40px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""
st.markdown("<style>" + TEMAS[st.session_state["tema"]] + CSS + "</style>", unsafe_allow_html=True)

# ------------------------------------------------- Face ID (WebAuthn / passkey)
FACEID_HTML = """<!DOCTYPE html><html><body style="margin:0;font-family:-apple-system,system-ui,sans-serif"><button id="b"></button><div id="m"></div><script>
const P=(t,d)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");
const e64=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\\+/g,"-").replace(/\\//g,"_").replace(/=+$/,"");
const d64=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")),c=>c.charCodeAt(0));
const B=document.getElementById("b"),M=document.getElementById("m");let A={};
const done=v=>P("streamlit:setComponentValue",{value:Object.assign({n:Date.now()+Math.random()},v),dataType:"json"});
async function reg(){try{
const c=await navigator.credentials.create({publicKey:{challenge:d64(A.chal),rp:{name:"Projeto 18 Anos",id:location.hostname},user:{id:new TextEncoder().encode(A.user),name:A.user,displayName:A.user},pubKeyCredParams:[{type:"public-key",alg:-7},{type:"public-key",alg:-257}],authenticatorSelection:{authenticatorAttachment:"platform",userVerification:"required"},timeout:60000}});
const r=c.response,L=JSON.parse(localStorage.getItem("p18")||"[]").filter(x=>x.id!=c.id);L.push({id:c.id,user:A.user});localStorage.setItem("p18",JSON.stringify(L));
done({kind:"reg",id:c.id,pk:e64(r.getPublicKey()),alg:r.getPublicKeyAlgorithm(),cd:e64(r.clientDataJSON)});
}catch(e){M.textContent="Não foi possível ativar ("+e.name+")"}}
async function get(){try{
const L=JSON.parse(localStorage.getItem("p18")||"[]");if(!L.length){M.textContent="Ative o Face ID em Novo lançamento > Ajustes depois de entrar.";return}
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
    st.session_state["chal"] = secrets.token_urlsafe(32)      # desafio de uso único
    if cd:
        db()["contas"][u]["fid"][p["id"]] = {"pk": p["pk"], "alg": p["alg"]}
        salvar()
    return bool(cd)


def fid_entrar(p):
    """Valida a assinatura do Face ID no servidor. Retorna o usuário ou None."""
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
    st.session_state.update(u=u, modo=modo, tela="login", tent=0, tema=db()["contas"][u]["d"].get("tema", "dark"))
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
    st.markdown(f'<div class="login"><div class="logo">💜</div><h1>Projeto 18 Anos</h1><div class="k" style="letter-spacing:.2em">{sub}</div></div>', unsafe_allow_html=True)
    if t == "login":
        with st.form("f_login"):
            n = st.text_input("Nome", placeholder="Nome da conta", label_visibility="collapsed", max_chars=24)
            p = st.text_input("Senha", type="password", placeholder="Senha", label_visibility="collapsed")
            go = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if go and not _espera():
            c = db()["contas"].get(n.strip().lower())
            if c and confere(p, c["s"], c["h"]):
                entrar(n.strip().lower(), "filho")
            elif p == CODIGO:
                entrar(SEED, "filho")
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
        return
    if t == "criar":
        with st.form("f_criar"):
            n = st.text_input("Nome da conta", max_chars=24)
            p = st.text_input("Senha (mín. 4 caracteres)", type="password")
            pin = st.text_input("PIN dos pais (4 números)", type="password", max_chars=4)
            go = st.form_submit_button("Criar conta", type="primary", use_container_width=True)
        if go:
            k = n.strip().lower()
            if not 2 <= len(k) <= 24:
                st.error("Use um nome de 2 a 24 caracteres.")
            elif k in db()["contas"]:
                st.error("Esse nome já existe.")
            elif len(p) < 4 or p == CODIGO:
                st.error("Escolha outra senha (mín. 4 caracteres).")
            elif not (pin.isdigit() and len(pin) == 4):
                st.error("O PIN dos pais precisa ter 4 números.")
            else:
                db()["contas"][k] = nova_conta(n.strip(), p, pin)
                salvar()
                entrar(k, "filho")
    else:
        with st.form("f_pais"):
            n = st.text_input("Nome da conta", max_chars=24)
            pin = st.text_input("PIN dos pais", type="password", max_chars=4)
            go = st.form_submit_button("Entrar em supervisão", type="primary", use_container_width=True)
        if go and not _espera():
            c = db()["contas"].get(n.strip().lower())
            if c and confere(pin, c["ps"], c["ph"]):
                entrar(n.strip().lower(), "pais")
            elif pin == PIN_PAIS:
                entrar(SEED, "pais")
            else:
                _falha()
    st.button("← Voltar", key="b_volta", use_container_width=True, on_click=_ir, args=("login",))


if not st.session_state["u"]:
    r = sessoes().get(st.query_params.get("s"))                   # lembra a sessão após recarregar
    if r and r[0] in db()["contas"]:
        st.session_state.update(u=r[0], modo=r[1], tema=db()["contas"][r[0]]["d"].get("tema", "dark"))
        st.rerun()
if not st.session_state["u"]:
    tela_login()
    st.stop()                                                      # nada financeiro é exibido sem login

U, SUP = st.session_state["u"], st.session_state["modo"] == "pais"
CONTA = db()["contas"][U]
S = CONTA["d"]


# ------------------------------------------------------------ regras de negócio
def total():
    return round(S["livre"] + sum(S["caixas"].values()), 2)


def reg(t, v, cx, obs, ts=None, dest=None):
    S["extrato"].append({"t": t, "v": round(v, 2), "c": cx, "d": dest, "o": obs, "ts": (ts or agora()).isoformat()})


def fx(valor):
    st.session_state["fx"] = {"txt": "+" + brl(valor), "n": int(time.time() * 1000)}


def fecha(msg=None):
    S["livre"] = round(S["livre"], 2)
    for k in S["caixas"]:
        S["caixas"][k] = round(S["caixas"][k], 2)
    salvar()
    st.session_state["msg"] = msg or "Lançado em " + fmt_dt(S["extrato"][-1]["ts"])


def aplicar(t, v, cx=None, obs=""):
    v = round(v, 2)
    if v <= 0:
        return "Informe um valor maior que zero."
    cxs = S["caixas"]
    if t == "save":
        if S["livre"] - v < RESERVA - 1e-9:
            return f"A reserva de {brl(RESERVA)} é protegida. Você pode guardar até {brl(max(0, S['livre'] - RESERVA))}."
        S["livre"] -= v
        cxs[cx] += v
    elif t == "take":
        if v > cxs[cx] + 1e-9:
            return f"Essa caixinha tem só {brl(cxs[cx])}."
        cxs[cx] -= v
        S["livre"] += v
    elif t == "yld":
        if cxs[cx] <= 0:
            return "Essa caixinha está sem saldo."
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
        return f"{CAIXAS[o][0]} tem só {brl(S['caixas'][o])}."
    S["caixas"][o] -= v
    S["caixas"][d] += v
    reg("mov", v, o, obs, dest=d)
    fecha()
    return ""


def excluir_caixinha(cx, resgatar):
    v = S["caixas"][cx]
    if resgatar:
        S["livre"] += v
        reg("take", v, cx, "Exclusão da caixinha")
    else:
        reg("del", v, cx, "Saldo removido do patrimônio")
    S["caixas"][cx] = 0.0
    fecha(f"{CAIXAS[cx][0]} excluída")


def liberar_sonho():
    """Quando a Caixinha Sonho fica disponível para resgate, o saldo vai para a Futuro (principal)."""
    sd = S["cfg"].get("sonho_data")
    if sd and agora().date().isoformat() >= sd:
        if S["caixas"]["sonho"] > 0.004:
            mover("sonho", "futuro", S["caixas"]["sonho"], "Sonho liberada → Futuro")
        S["cfg"]["sonho_data"] = None
        salvar()


def creditar_mes():
    """Todo dia 1 entra o aporte mensal: parte vai p/ Futuro e o resto fica livre, acumulando."""
    h = agora()
    a, m = S["ultimo_credito"].split("-")
    ult, atual = int(a) * 12 + int(m) - 1, h.year * 12 + h.month - 1
    if atual <= ult:
        return
    c = S["cfg"]
    g, n = min(c["guardar"], c["renda"]), 0
    for k in range(ult + 1, atual + 1):
        if c["renda"] <= 0:
            break
        ano, mes = divmod(k, 12)
        ts = datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=TZ)
        S["livre"] += c["renda"]
        reg("in", c["renda"], None, "Mesada automática", ts)
        if g > 0:
            S["livre"] -= g
            S["caixas"]["futuro"] += g
            reg("save", g, "futuro", "Aporte automático", ts)
        n += 1
    S["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    if n:
        fx(c["renda"] * n)
        fecha(f"Mesada de {brl(c['renda'])} creditada" if n == 1 else f"{n} mesadas creditadas")
    else:
        salvar()


def projetar():
    """Base real = Saldo Livre + Futuro + Sonho. Tudo rende 100% do CDI (resgate imediato) + aporte mensal."""
    c, h = S["cfg"], agora()
    r = (1 + c["cdi"] / 100) ** (1 / 12) - 1
    t = total()
    b = ap = t
    n, linhas = 0, []
    for ano in range(h.year, ANO_FIM + 1):
        for _ in range(12 - h.month if ano == h.year else 12):
            b = b * (1 + r) + c["renda"]
            ap += c["renda"]
            n += 1
        linhas.append((ano, ap, b - ap, b))
    g = (1 + r) ** n
    falta = max(0.0, (META - t * g) / ((g - 1) / r)) if n and r > 0 else max(0.0, (META - t) / n) if n else 0.0
    return linhas, falta


def csv_extrato():
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
    s = CAIXAS[x["c"]][0] if x.get("c") else ""
    return s + (" → " + CAIXAS[x["d"]][0] if x.get("d") else "")


# ------------------------------------------------------------------ telas
def fx_html(d):
    random.seed(d["n"])
    itens = "".join(
        '<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
        % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
           random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return f'<div class="fx">{itens}<b>{d["txt"]}</b></div>'


def card(cor, tit, val, sub="", extra=""):
    return (f'<div class="card" style="--c:var(--{cor})"><div class="lb" style="color:var(--{cor})">{tit}</div>'
            f'<div class="big">{val}</div>{extra}<div class="k">{sub}</div></div>')


def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    pc = min(100, t / META * 100)
    if f > RESERVA + .005:
        msg = f"Você tem <b>{brl(f - RESERVA)}</b> acima da reserva de {brl(RESERVA)}. Veja onde aplicar em Ideias."
    elif f < RESERVA - .005:
        msg = f"Atenção: faltam <b>{brl(RESERVA - f)}</b> para completar a reserva de {brl(RESERVA)}."
    else:
        msg = f"Reserva de {brl(RESERVA)} completa. Tudo em ordem."
    h = agora()
    prox = f"01/{h.month + 1:02d}/{h.year}" if h.month < 12 else f"01/01/{h.year + 1}"
    mesada = (f"<br>Próxima mesada de {brl(c['renda'])}: {prox} ({brl(c['renda'] - min(c['guardar'], c['renda']))} ficam livres)"
              if c["renda"] > 0 else "<br>Configure o aporte mensal em Novo lançamento › Ajustes.")
    pct = f"{pc:.1f}".replace(".", ",")
    out = card("grn", "Patrimônio total", brl(t), f"{pct}% da meta de {brl(META)} aos 18 anos", f'<div class="pg"><i style="width:{pc}%"></i></div>')
    out += f'<div class="card as">💡 {msg}</div>'
    out += card("blue", "Saldo livre", brl(f), f"Reserva fixa de {brl(RESERVA)}{mesada}")
    for k, (nome, cor, sub) in CAIXAS.items():
        if S["caixas"][k] > 0.004:
            out += card(cor, nome, brl(S["caixas"][k]), sub)
    return out


def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k">Nenhum lançamento ainda.</div></div>'
    rows = ""
    for _, x in sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True):
        ic, nome = TIPOS[x["t"]]
        tr, ps = x["t"] in ("save", "take", "mov"), x["t"] in ("in", "yld")
        cor = "blue" if tr else "grn" if ps else "red"
        sg = {"save": "→ ", "take": "← ", "mov": "↔ "}.get(x["t"], "+" if ps else "−")
        det = (destino(x) + " · " if x.get("c") else "") + (html.escape(x["o"]) + " · " if x["o"] else "") + fmt_dt(x["ts"])
        rows += (f'<div class="tx"><span class="ic">{ic}</span><div class="g"><b>{nome}</b><div class="k">{det}</div></div>'
                 f'<b style="color:var(--{cor})">{sg}{brl(x["v"])}</b></div>')
    return f'<div class="card" style="padding:6px 16px">{rows}</div>'


def svg_barras(L):
    W, H = 340, 210
    mx = max([META] + [x[3] for x in L]) * 1.12
    bw = W / len(L)
    ty = H - 24 - META / mx * (H - 44)
    s = (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;touch-action:pan-y">'
         f'<line class="tl" x1="0" x2="{W}" y1="{ty:.1f}" y2="{ty:.1f}"/>'
         f'<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="{ty - 5:.1f}">Meta {kf(META)}</text>')
    for i, (ano, ap, j, b) in enumerate(L):
        h = b / mx * (H - 44)
        x = i * bw + bw * .17
        s += (f'<rect class="bar" x="{x:.1f}" y="{H - 24 - h:.1f}" width="{bw * .66:.1f}" height="{h:.1f}" rx="7"/>'
              f'<text class="bt" x="{x + bw * .33:.1f}" y="{H - 28 - h:.1f}">{kf(b)}</text>'
              f'<text class="bt" x="{x + bw * .33:.1f}" y="{H - 7}">{ano}</text>')
    return s + "</svg>"


def v_proj():
    L, falta = projetar()
    if not L:
        return card("grn", "Projeção", brl(total()), "Sem meses restantes até 2032.")
    fim = L[-1][3]
    ok = fim >= META
    sub = (f"Meta de {brl(META)} batida, com folga de {brl(fim - META)}." if ok
           else f"Para chegar a {brl(META)}, aporte cerca de {brl(falta)} por mês.")
    tab = ('<table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th></tr>'
           + "".join(f'<tr><td>{a}</td><td>{brl(p)}</td><td style="color:var(--grn)">{brl(j)}</td><td><b>{brl(b)}</b></td></tr>'
                     for a, p, j, b in L) + '</table>')
    cx, sd = S["caixas"], S["cfg"].get("sonho_data")
    nota = (f"Sonho ({brl(cx['sonho'])}) vai para a Futuro em {date.fromisoformat(sd):%d/%m/%Y}; a projeção já considera tudo na Futuro. "
            if sd and cx["sonho"] > 0 else "")
    cdi = str(S["cfg"]["cdi"]).replace(".", ",")
    return (card("grn" if ok else "gold", "Projeção até 2032", brl(fim), sub)
            + f'<div class="card">{svg_barras(L)}</div><div class="card">{tab}</div>'
            + f'<div class="k" style="padding:0 6px">Ponto de partida real: livre {brl(S["livre"])} + Futuro {brl(cx["futuro"])} + Sonho {brl(cx["sonho"])} = {brl(total())}. '
              f'{nota}Aporte de {brl(S["cfg"]["renda"])}/mês · 100% do CDI (resgate imediato) a {cdi}% a.a., bruto e estimado.</div>')


def v_idea():
    ex = round(max(0.0, S["livre"] - RESERVA), 2)
    opc = [("Reserva de liquidez diária", 1.0 if ex < 50 else .4, "blue", "CDB ou RDB com liquidez diária pagando cerca de 100% do CDI. Dinheiro disponível para imprevistos."),
           ("RDB de longo prazo", .35, "pur", "Prazos de 2 a 5 anos costumam render acima do CDI. Boa para a meta de 2032; confira a cobertura do FGC."),
           ("Tesouro IPCA+", .25, "gold", "Rende inflação mais juros fixos e protege o poder de compra. Escolha vencimento próximo de 2032.")]
    if ex < 50:
        opc = opc[:1]
    sub = "Sugestão de divisão para esse valor:" if ex else f"Seu saldo livre precisa passar de {brl(RESERVA + 50)} para liberar sugestões."
    out = card("blue", "Excedente acima da reserva", brl(ex), sub)
    if ex:
        for nome, p, cor, txt in opc:
            out += (f'<div class="card" style="--c:var(--{cor})"><div class="al"><span class="lb">{nome}</span>'
                    f'<b style="color:var(--{cor})">{brl(ex * p)}</b></div><div class="k">{round(p * 100)}% · {txt}</div></div>')
    return out + '<div class="k" style="padding:0 6px">Sugestões educativas, não são recomendação personalizada. Menores investem com acompanhamento do responsável.</div>'


# ------------------------------------------------------------------ diálogos
def form_op(op):
    cx = cx2 = None
    if op in ("save", "take", "yld", "mov"):
        ops = [k for k in CAIXAS if op == "save" or S["caixas"][k] > 0]
        if not ops:
            st.info("Nenhuma caixinha com saldo ainda. Guarde um valor primeiro.")
            return
        cx = st.selectbox("De" if op == "mov" else "Caixinha", ops, key="c_" + op,
                          format_func=lambda k: CAIXAS[k][0] + " · " + brl(S["caixas"][k]))
        if op == "mov":
            cx2 = st.selectbox("Para", [k for k in CAIXAS if k != cx], key="d_mov", format_func=lambda k: CAIXAS[k][0])
    v = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=0.10 if op == "yld" else 1.0, format="%.2f", key="v_" + op)
    if op == "yld" and cx:
        dia = S["caixas"][cx] * ((1 + S["cfg"]["cdi"] / 100) ** (1 / 252) - 1)
        st.caption(f"100% do CDI rende cerca de {brl(dia)} por dia útil nessa caixinha.")
    obs = st.text_input("Observação (opcional)", max_chars=40, key="o_" + op)
    if st.button("Confirmar", type="primary", use_container_width=True, key="ok_" + op):
        e = mover(cx, cx2, v, obs.strip()) if op == "mov" else aplicar(op, v, cx, obs.strip())
        if e:
            st.error(e)
        else:
            st.rerun()


def ajustes():
    c = S["cfg"]
    nome = st.text_input("Nome da conta", CONTA["nome"], max_chars=24, key="a_nome")
    renda = st.number_input("Aporte mensal (R$), entra todo dia 1", min_value=0.0, value=float(c["renda"]), step=50.0, format="%.2f", key="a_renda")
    guard = st.number_input("Desse valor, guardar na Caixinha Futuro (R$)", min_value=0.0, value=float(c["guardar"]), step=50.0, format="%.2f", key="a_g")
    gast = st.number_input("Gastos fixos mensais (R$)", min_value=0.0, value=float(c["gastos"]), step=10.0, format="%.2f", key="a_gf")
    cdi = st.number_input("CDI estimado (% ao ano)", min_value=0.0, max_value=100.0, value=float(c["cdi"]), step=0.1, format="%.2f", key="a_cdi")
    sd = st.date_input("Sonho disponível para resgate em (passa para a Futuro)", value=date.fromisoformat(c["sonho_data"]) if c.get("sonho_data") else None,
                       format="DD/MM/YYYY", key="a_sd")
    if st.button("Salvar ajustes", type="primary", use_container_width=True, key="a_ok"):
        CONTA["nome"] = nome.strip() or CONTA["nome"]
        S["cfg"] = {"renda": renda, "guardar": min(guard, renda), "gastos": gast, "cdi": cdi, "sonho_data": sd.isoformat() if sd else None}
        fecha("Ajustes salvos")
        st.rerun()
    if HAS_CRYPTO:
        st.divider()
        r = FACEID(modo="reg", chal=st.session_state["chal"], user=U, tema=st.session_state["tema"], key="fid_reg", default=None)
        if r and r.get("kind") == "reg" and r["n"] != st.session_state["fid_done"]:
            st.session_state["fid_done"] = r["n"]
            if fid_registrar(U, r):
                st.session_state["msg"] = "Face ID ativado neste aparelho"
                st.rerun()
            st.error("Não foi possível validar o Face ID.")


@st.dialog("Novo lançamento")
def dlg_novo():
    t1, t2, t3 = st.tabs(["💳 Conta", "🐷 Caixinhas", "⚙️ Ajustes"])
    with t1:
        form_op(st.radio("Conta", ["in", "out"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r1"))
    with t2:
        form_op(st.radio("Caixinhas", ["save", "take", "yld", "mov"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r2"))
    with t3:
        ajustes()


@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():
    ops = [k for k in CAIXAS if S["caixas"][k] > 0.004]
    if not ops:
        st.info("Nenhuma caixinha com saldo para excluir.")
        return
    cx = st.selectbox("Qual caixinha?", ops, format_func=lambda k: CAIXAS[k][0] + " · " + brl(S["caixas"][k]))
    modo = st.radio("O que fazer com o saldo?", ["Resgatar para o Saldo Livre", "Apenas zerar (sai do patrimônio)"])
    st.caption("O card some da tela principal e só reaparece com novo aporte.")
    if st.button("Excluir caixinha", type="primary", use_container_width=True):
        excluir_caixinha(cx, modo.startswith("Resgatar"))
        st.rerun()


@st.dialog("🛡️ Painel dos pais")
def dlg_pais():
    st.caption("Você está em modo supervisão: somente leitura. Aqui dá para redefinir os acessos.")
    senha = st.text_input("Nova senha do filho (mín. 4)", type="password")
    pin = st.text_input("Novo PIN dos pais (4 números)", type="password", max_chars=4)
    if st.button("Salvar", type="primary", use_container_width=True):
        if (senha and len(senha) < 4) or (senha and senha == CODIGO and U != SEED) or (pin and not (pin.isdigit() and len(pin) == 4)):
            st.error("Senha com 4+ caracteres e PIN com 4 números.")
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
    with st.container(key="nav"):                       # pílula Liquid Glass que "estica" ao abrir
        st.button("‹", key="b_min", on_click=_nav, args=(False,), help="Recolher")
        aba = st.radio("Navegação", ABAS, index=tab, key="aba", horizontal=True, label_visibility="collapsed")
        if st.button("🛡️" if SUP else "＋", key="b_plus", help="Painel dos pais" if SUP else "Novo lançamento"):
            (dlg_pais if SUP else dlg_novo)()
    idx = ABAS.index(aba)
else:
    st.button(ABAS[tab], key="bolha", on_click=_nav, args=(True,), help="Abrir menu")   # bolinha recolhida
    idx = tab
if idx != tab:
    st.session_state.update(dir="R" if idx > tab else "L", tab=idx)

st.markdown(f'<div class="hd"><div class="k">{TITULOS[idx]}</div><h1>{html.escape(CONTA["nome"])}</h1></div>', unsafe_allow_html=True)
if SUP:
    st.markdown('<div class="sup">🔐 Modo Supervisão: somente leitura, lançamentos ocultos.</div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    st.markdown([v_home, v_ext, v_proj, v_idea][idx](), unsafe_allow_html=True)
    if idx == 0 and not SUP and any(v > 0.004 for v in S["caixas"].values()):
        if st.button("🗑️ Excluir caixinha", key="b_del", use_container_width=True):
            dlg_excluir()
    if idx == 1:
        st.download_button("⬇️ Baixar tabela (CSV)", csv_extrato(), file_name=f"extrato_projeto18_{agora():%Y-%m-%d}.csv",
                           mime="text/csv", use_container_width=True, disabled=not S["extrato"])

if st.session_state["fx"]:
    st.markdown(fx_html(st.session_state["fx"]), unsafe_allow_html=True)
    st.session_state["fx"] = None

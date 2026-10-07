# -*- coding: utf-8 -*-
"""FUTURE - controle financeiro pessoal (Streamlit >= 1.40).

requirements.txt:  streamlit>=1.40   cryptography   openpyxl   google-generativeai

NADA sensível fica neste arquivo. Configure em Streamlit Cloud > Settings > Secrets:

    supabase_url = "https://SEU-PROJETO.supabase.co"
    supabase_key = "CHAVE_SERVER_SIDE"
    backup_key   = "texto-longo-e-aleatorio"
    gemini_key   = "CHAVE_DO_GOOGLE_GEMINI"
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

TIPOS = {"in": ("📥", "Recebi dinheiro"), "out": ("💸", "Gastei dinheiro"), "save": ("🔒", "Guardar na caixinha"),
         "take": ("🔓", "Resgatar da caixinha"), "yld": ("📈", "Rendimento / juros"), "mov": ("🔁", "Mover entre caixinhas"),
         "del": ("🗑️", "Caixinha excluída")}
CURTO = {"in": "📥 Receber", "out": "💸 Gastar", "save": "🔒 Guardar", "take": "🔓 Resgatar", "yld": "📈 Juros", "mov": "🔁 Mover"}
ABAS, TITULOS = ["🏠 Início", "🧾 Extrato", "📈 Projeção", "💡 Ideias"], ["Início", "Extrato", "Projeção", "Ideias"]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PALETAS = {
    "Padrão": {"pur": "#b57bff", "blue": "#4aa3ff", "gold": "#f0c24b", "grn": "#3fdc78", "red": "#ff6b62"},
    "Neon": {"pur": "#b026ff", "blue": "#00b4d8", "gold": "#ffd166", "grn": "#06d6a0", "red": "#ef476f"},
    "Oceano": {"pur": "#3a0ca3", "blue": "#4361ee", "gold": "#4cc9f0", "grn": "#2ec4b6", "red": "#e71d36"},
    "Outono": {"pur": "#6a4c93", "blue": "#1982c4", "gold": "#ffca3a", "grn": "#8ac926", "red": "#ff595e"},
}
for _k, _v in dict(u=None, modo=None, tela="login", tema="dark", paleta="Padrão", tab=0, nav=False, dir="R", fx=None, msg=None,
                   chal=secrets.token_urlsafe(32), fid_done=None, bak_done=None, launch=False, db_obj=None, db_ts=0.0,
                   recarregar=False, base_v={}, storage_mode="local", bak_hash=None, bak_payload=None).items():
    st.session_state.setdefault(_k, _v)


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


def safe_float(v, padrao=0.0):
    try:
        return float(v)
    except Exception:
        return padrao


def nova_conta(nome, senha, pin, nasc="2014-01-01", seed=False):
    s, h = mk(senha)
    ps, ph = mk(pin)
    a = agora()
    d = {"livre": 0.0, "caixas": {}, "caixas_meta": {}, "extrato": [], "tema": "dark", "paleta": "Padrão", "nasc": nasc,
         "_v": 0.0 if seed else time.time(),
         "cfg": {"renda": 0.0, "guardar": 0.0, "gastos": 0.0, "cdi": 9.5, "sonho_data": None, "meta": 10000.0,
                 "reserva": 100.0, "tutorial": not seed, "ajustado": False},
         "ultimo_credito": f"{a.year}-{a.month:02d}"}
    if seed:
        d["livre"] = safe_float(secret_str("seed_livre", "0"))
        try:
            bruto = json.loads(secret_str("seed_caixas_json", "{}"))
        except Exception:
            bruto = {}
        try:
            meta = json.loads(secret_str("seed_caixas_meta_json", "{}"))
        except Exception:
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        caixas = {str(k): round(safe_float(v), 2) for k, v in bruto.items()} if isinstance(bruto, dict) else {}
        d["caixas"] = caixas
        d["caixas_meta"] = {k: (meta[k] if isinstance(meta.get(k), list) and len(meta[k]) == 3 else [k.title(), "pur", ""]) for k in caixas}
        d["cfg"].update(renda=safe_float(secret_str("seed_renda", "0")), guardar=safe_float(secret_str("seed_guardar", "0")),
                        gastos=safe_float(secret_str("seed_gastos", "0")), meta=safe_float(secret_str("seed_meta", "10000"), 10000.0),
                        reserva=safe_float(secret_str("seed_reserva", "100"), 100.0), tutorial=False)
    return {"nome": nome, "s": s, "h": h, "ps": ps, "ph": ph, "fid": {}, "sess": {}, "d": d}


def supabase_configurado():
    return bool(SB_URL and SB_KEY)


def _sb(metodo, path="", corpo=None):
    if not supabase_configurado():
        raise RuntimeError("Supabase não configurado.")
    h = {"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json",
         "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(SB_URL + "/rest/v1/future" + path, headers=h, method=metodo,
                                 data=None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode())
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def carregar_local():
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def salvar_local(dados):
    tmp = ARQ.with_name(ARQ.name + ".tmp")
    try:
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(ARQ)
        return True
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass
        return False


def ler_fonte():
    if supabase_configurado():
        try:
            r = json.loads(_sb("GET", "?id=eq.db&select=dados"))
            d = r[0].get("dados") if r else None
            return True, (d if isinstance(d, dict) else None)
        except Exception:
            return False, None
    d = carregar_local()
    return True, (d or None)


def _ver(c):
    try:
        return float((c.get("d") or {}).get("_v", 0) or 0)
    except Exception:
        return 0.0


def _merge(a, b):
    out = {"contas": {}}
    for src in (a or {}, b or {}):
        for u, c in (src.get("contas") or {}).items():
            if isinstance(c, dict) and (u not in out["contas"] or _ver(c) > _ver(out["contas"][u])):
                out["contas"][u] = c
    return out


@st.cache_resource
def trava():
    return threading.RLock()


def _gravar(dados, nuvem=True):
    ok_l, ok_n = salvar_local(dados), True
    if supabase_configurado() and nuvem:
        try:
            _sb("POST", "", [{"id": "db", "dados": dados}])
        except Exception:
            ok_n = False
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


def db():
    return st.session_state["db_obj"]


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
                ss["warn"] = "⚠️ Dados alterados em outro aparelho. Atualizado."
                return False
        if ok:
            for k, c in _merge(fonte, dados)["contas"].items():
                dados["contas"][k] = c
        ok_l, ok_n = _gravar(dados, nuvem=ok)
        ss["base_v"] = {k: _ver(c) for k, c in dados["contas"].items()}
        if supabase_configurado():
            ss["storage_mode"] = "cloud" if (ok and ok_n) else "local-fallback"
    return True


def get_css(tema, nome):
    p = PALETAS.get(nome, PALETAS["Padrão"])
    if tema == "light":
        p = {k: "color-mix(in srgb," + v + " 70%,#000)" for k, v in p.items()}
    cores = f"--blue:{p['blue']};--pur:{p['pur']};--gold:{p['gold']};--grn:{p['grn']};--red:{p['red']}"
    if tema == "light":
        return ":root{--bg:#eceef4;--c1:#fff;--c2:#f3f4f9;--tx:#14141c;--mu:#656575;--ln:rgba(0,0,0,.09);--s1:rgba(120,125,150,.3);--s2:rgba(255,255,255,.95);--glass:rgba(255,255,255,.68);color-scheme:light;" + cores + "}"
    return ":root{--bg:#07070b;--c1:#16161f;--c2:#0e0e15;--tx:#f4f4f8;--mu:#8b8b9a;--ln:rgba(255,255,255,.09);--s1:rgba(0,0,0,.6);--s2:rgba(255,255,255,.04);--glass:rgba(34,34,48,.58);color-scheme:dark;" + cores + "}"


CSS_BASE = """
html,body,[data-testid="stApp"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:var(--bg)!important;overscroll-behavior-y:none;margin:0;padding:0}
[data-testid="stApp"]{background:radial-gradient(900px 520px at 12% -8%,color-mix(in srgb,var(--pur) 13%,transparent),transparent 62%),radial-gradient(760px 460px at 100% 6%,color-mix(in srgb,var(--blue) 10%,transparent),transparent 60%),var(--bg)!important;background-attachment:fixed!important}
.stApp{color:var(--tx);overflow-x:hidden}
header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
.block-container{max-width:580px!important;padding:2rem 1.5rem 10rem!important;margin:0 auto!important}
.stApp p,.stApp label,.stApp h1,.stApp li,[data-testid="stDialog"] *{color:var(--tx)}
.stApp input,[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"]{background:var(--c2)!important;color:var(--tx)!important;border-radius:14px!important}
div[role="dialog"]{background:var(--c1)!important;border-radius:28px!important;border:1px solid var(--ln)!important;max-width:calc(100vw - 24px)!important;box-shadow:0 24px 70px rgba(0,0,0,.3)!important;animation:dialogIn .28s cubic-bezier(.16,1,.3,1)}
@keyframes dialogIn{from{opacity:0;transform:translateY(10px) scale(.985)}to{opacity:1;transform:none}}
button[kind="secondary"],[data-testid="stBaseButton-secondary"]{background:var(--c2);border:1px solid var(--ln);border-radius:16px}
button[kind="secondary"] p,[data-testid="stBaseButton-secondary"] p{color:var(--tx)}
button[kind="primary"],[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--pur),var(--blue))!important;border:0!important;border-radius:16px!important}
button[kind="primary"] *,[data-testid="stBaseButton-primary"] *{color:#fff!important}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
.hd h1{margin:0;font-size:28px;letter-spacing:-.03em;padding:0}.hd{margin-bottom:16px}
.rkw{position:relative;display:inline-block}
.logo{font-size:64px;line-height:1;display:inline-block;animation:rocketLaunch .7s cubic-bezier(.175,.885,.32,1.275) both}
@keyframes rocketLaunch{0%{transform:translateY(80px) scale(.4);opacity:0}60%{transform:translateY(-15px) scale(1.1);opacity:1}100%{transform:none;opacity:1}}
.brand{font-size:34px;font-weight:800;letter-spacing:.14em;text-indent:.14em;line-height:1.1;margin:14px 0 6px;color:var(--tx)}
.card{background:linear-gradient(145deg,var(--c1),var(--c2));border:1px solid color-mix(in srgb,var(--c,var(--ln)) 50%,transparent);border-radius:25px;padding:20px;box-shadow:8px 9px 24px var(--s1),-4px -4px 16px var(--s2),inset 0 1px 0 rgba(255,255,255,.05);backdrop-filter:blur(14px) saturate(140%);-webkit-backdrop-filter:blur(14px) saturate(140%);margin-bottom:16px}
button{transition:transform .18s cubic-bezier(.2,.8,.2,1),background .25s ease,box-shadow .25s ease!important}button:active{transform:scale(.97)!important}
.k{color:var(--mu);font-size:13px}.lb{font-size:14px;font-weight:600}.big{font-size:34px;font-weight:700;letter-spacing:-.035em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.pg{height:8px;border-radius:9px;background:var(--ln);overflow:hidden;margin:6px 0}
.pg i{display:block;height:100%;border-radius:9px;background:linear-gradient(90deg,var(--blue),var(--grn))}
.rkbar{position:relative;padding-top:14px}
.rkbar s{position:absolute;top:-6px;margin-left:-9px;font-size:17px;text-decoration:none}
.as{font-size:15px;border-style:dashed}.sup{background:color-mix(in srgb,var(--gold) 16%,transparent);border:1px solid var(--gold);border-radius:18px;padding:12px 14px;margin-bottom:16px;font-size:14px}
.sp{display:flex;gap:10px;align-items:flex-start;padding:7px 0}.sp>span{font-size:18px;line-height:1.3}.sp.ok b{text-decoration:line-through;opacity:.5}
.tx{display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--ln)}.tx:last-child{border:0}.tx .g{flex:1;min-width:0}
.ic{width:40px;height:40px;border-radius:14px;background:var(--c2);display:grid;place-items:center;font-size:19px;flex:none;border:1px solid var(--ln)}
table{width:100%;border-collapse:collapse;font-size:13.5px}th{color:var(--mu);font-weight:500;text-align:right;padding:6px 0}td{padding:10px 0;text-align:right;border-top:1px solid var(--ln)}th:first-child,td:first-child{text-align:left}
.bar{fill:var(--grn);opacity:.9}.bt{fill:var(--mu);font-size:10px;text-anchor:middle}.tl{stroke:var(--gold);stroke-dasharray:4 4;stroke-width:1.2}
.al{display:flex;justify-content:space-between;align-items:baseline}.al b{font-size:20px}
.st-key-nav,.st-key-bolha{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(24px + env(safe-area-inset-bottom,0px));z-index:999;width:auto!important}
.st-key-nav{width:min(calc(100vw - 32px),440px)!important;display:flex!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:6px;background:var(--glass);backdrop-filter:blur(20px);border:1px solid var(--ln);border-radius:34px;box-shadow:0 14px 40px var(--s1)}
.st-key-aba{flex:1!important}
.st-key-nav [role="radiogroup"]{display:flex;flex-wrap:nowrap;gap:2px;width:100%}
.st-key-nav label{flex:1;justify-content:center;margin:0;padding:8px 0;border-radius:26px;cursor:pointer}
.st-key-nav label>div:first-child{display:none}
.st-key-nav label p{font-size:10px;line-height:1.3;font-weight:600;text-align:center;word-spacing:100vw;margin:0;opacity:.55}
.st-key-nav label p::first-line{font-size:21px}
.st-key-nav label:has(input:checked){background:color-mix(in srgb,var(--pur) 26%,transparent)}
.st-key-nav label:has(input:checked) p{opacity:1}
.st-key-b_min button,.st-key-b_plus button,.st-key-bolha button,.st-key-b_tema button,.st-key-b_ajustes_top button,.st-key-b_sair button,.st-key-b_lunatic button{border-radius:50%;padding:0;background:var(--glass);backdrop-filter:blur(20px);border:1px solid var(--ln)}
.st-key-b_min button{width:34px;height:34px}.st-key-b_plus button{width:46px;height:46px;border:0;background:linear-gradient(135deg,var(--pur),var(--blue))}
.st-key-b_plus button p{color:#fff;font-size:24px;line-height:1}
.st-key-bolha{animation:popin .4s cubic-bezier(.2,1.4,.4,1)}.st-key-bolha button{width:58px;height:58px;font-size:24px;box-shadow:0 10px 30px var(--s1)}
@keyframes popin{from{transform:scale(.4);opacity:0}}
.st-key-b_tema,.st-key-b_lunatic,.st-key-b_ajustes_top,.st-key-b_sair{position:fixed;z-index:1000;width:auto!important;top:calc(16px + env(safe-area-inset-top,0px))}
.st-key-b_tema{right:170px}.st-key-b_lunatic{right:118px}.st-key-b_ajustes_top{right:66px}.st-key-b_sair{right:14px}
.st-key-b_tema button,.st-key-b_lunatic button,.st-key-b_ajustes_top button,.st-key-b_sair button{width:44px;height:44px;font-size:18px}
html,body,.stApp,.stApp p,.stApp label,.stApp input,.stApp textarea,.stApp button{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",system-ui,sans-serif!important}
.big,.hd h1,.al b,.lb,.brand{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",system-ui,sans-serif!important}
.dh{font-size:11.5px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--mu);padding:12px 0 2px}
.mes{display:flex;gap:8px;margin-top:8px}.mes>div{flex:1}.mes b{font-size:16px;font-variant-numeric:tabular-nums}
[data-testid="stAlert"]{background:color-mix(in srgb,var(--pur) 12%,var(--c1))!important;border:1px solid var(--ln)!important;border-radius:16px!important}
"""
st.markdown("<style>" + get_css(st.session_state["tema"], st.session_state["paleta"]) + CSS_BASE + "</style>", unsafe_allow_html=True)

try:
    refrescar_db(force=st.session_state["u"] is None)
except Exception:
    st.error("Não foi possível carregar os dados.")
    st.stop()


def achar_sessao(token):
    th = _th(token)
    for u, c in db()["contas"].items():
        r = (c.get("sess") or {}).get(th)
        if r and time.time() - r[2] < SESSAO_SEG:
            return u, r[1]
    return None


def entrar(u, modo):
    tok = secrets.token_urlsafe(24)
    sess = db()["contas"][u].setdefault("sess", {})
    for h in [h for h, r in sess.items() if time.time() - r[2] >= SESSAO_SEG]:
        sess.pop(h, None)
    sess[_th(tok)] = [u, modo, time.time()]
    st.query_params["s"] = tok
    salvar(u)
    d = db()["contas"][u]["d"]
    st.session_state.update(u=u, modo=modo, tela="login", launch=True, tema=d.get("tema", "dark"), paleta=d.get("paleta", "Padrão"))
    st.rerun()


def _ir(t):
    st.session_state["tela"] = t


@st.cache_resource
def _tent():
    return {}


def _espera(k):
    t = _tent().get(k)
    e = (t[1] - time.time()) if t else 0
    return e > 0


def _falha(k):
    tt = _tent()
    t = tt.setdefault(k, [0, 0.0])
    t[0] += 1
    if t[0] >= 5:
        t[:] = [0, time.time() + 60]
    st.error("Dados incorretos.")


def tela_login():
    t = st.session_state["tela"]
    sub = {"login": "INICIAR SESSÃO", "criar": "CRIAR CONTA", "pais": "CONTROLE PARENTAL"}[t]
    st.markdown('<div style="display:flex;flex-direction:column;align-items:center;width:100%;text-align:center;padding:5vh 0 2vh">'
                '<div class="rkw"><div class="logo">🚀</div></div>'
                '<div class="brand">FUTURE</div>'
                '<div style="color:var(--mu);font-size:13px;letter-spacing:.2em;width:100%;text-align:center">' + sub + '</div></div>', unsafe_allow_html=True)
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
                else:
                    _falha(k)
        st.button("🛡️ Controle parental", key="b_pais", use_container_width=True, on_click=_ir, args=("pais",))
        st.button("Criar nova conta", key="b_criar", use_container_width=True, on_click=_ir, args=("criar",))
        st.caption("☁️ Armazenamento principal em nuvem (Supabase).")
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
            if k in db()["contas"]:
                st.error("Esse nome já existe.")
            elif len(p) < 4:
                st.error("Senha curta.")
            else:
                db()["contas"][k] = nova_conta(n.strip(), p, pin, nasc=nasc.isoformat())
                if salvar(k):
                    entrar(k, "filho")
    else:
        with st.form("f_pais"):
            n = st.text_input("Nome da conta supervisionada", max_chars=24)
            pin = st.text_input("PIN dos pais", type="password", max_chars=4)
            go = st.form_submit_button("Entrar em supervisão", type="primary", use_container_width=True)
        if go:
            c = db()["contas"].get(chave(n))
            if c and confere(pin, c["ps"], c["ph"]):
                entrar(chave(n), "pais")
            else:
                st.error("PIN incorreto.")
    st.button("← Voltar", key="b_volta", use_container_width=True, on_click=_ir, args=("login",))


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
for _k, _v in dict(meta=62000.0, reserva=100.0, tutorial=False, ajustado=True, cdi=9.5, gastos=0.0, renda=0.0, guardar=0.0).items():
    S["cfg"].setdefault(_k, _v)


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
    meses = 0 if h >= b18 else max(1, (b18.year - h.year) * 12 + b18.month - h.month - (1 if b18.day < h.day else 0))
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
    st.session_state["msg"] = msg or "Lançamento efetuado com sucesso."
    salvar()


def visivel(k):
    return S["caixas"][k] > 0.004 or not any(x.get("c") == k or x.get("d") == k for x in S["extrato"])


def nome_cx(k):
    return S["caixas_meta"].get(k, ["Caixinha"])[0]


def aplicar(t, v, cx=None, obs=""):
    v, reserva, cxs = round(safe_float(v), 2), safe_float(S["cfg"]["reserva"]), S["caixas"]
    if v <= 0:
        return "Informe um valor maior que zero."
    if t in ("save", "take", "yld") and cx not in cxs:
        return "Escolha uma caixinha válida."
    if t == "save":
        if S["livre"] - v < reserva - 1e-9:
            return f"Reserva de {brl(reserva)} protegida."
        S["livre"] -= v
        cxs[cx] += v
    elif t == "take":
        if v > cxs[cx] + 1e-9:
            return f"Saldo insuficiente na caixinha."
        cxs[cx] -= v
        S["livre"] += v
    elif t == "yld":
        cxs[cx] += v
    elif t == "out":
        if v > S["livre"] + 1e-9:
            return f"Saldo livre insuficiente."
        S["livre"] -= v
    elif t == "in":
        S["livre"] += v
    reg(t, v, cx if t in ("save", "take", "yld") else None, obs)
    if t in ("in", "yld"):
        fx(v)
    fecha()
    return ""


def mover(o, d, v, obs=""):
    v = round(safe_float(v), 2)
    if v <= 0:
        return "Informe um valor maior que zero."
    if o not in S["caixas"] or d not in S["caixas"] or o == d:
        return "Escolha duas caixinhas diferentes."
    if v > S["caixas"][o] + 1e-9:
        return "Saldo insuficiente na caixinha de origem."
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
        reg("del", v, cx, "Excluída")
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
    h, c = agora(), S["cfg"]
    try:
        a, m = S["ultimo_credito"].split("-")
        ult = int(a) * 12 + int(m) - 1
    except Exception:
        ult = h.year * 12 + h.month - 2
    atual = h.year * 12 + h.month - 1
    if atual <= ult:
        return
    renda, gastos, guardar = (max(0.0, safe_float(c[k])) for k in ("renda", "gastos", "guardar"))
    cx, n = next(iter(S["caixas"]), None), 0
    if renda > 0 or gastos > 0:
        for k in range(ult + 1, atual + 1):
            ano, mes = divmod(k, 12)
            ts = datetime(ano, mes + 1, 1, 0, 0, 0, tzinfo=TZ)
            if renda > 0:
                S["livre"] += renda
                reg("in", renda, None, "Renda mensal", ts)
            gasto = min(gastos, max(0.0, S["livre"]))
            if gasto > 0:
                S["livre"] -= gasto
                reg("out", gasto, None, "Gastos fixos", ts)
            aporte = min(guardar, max(0.0, renda - gasto), max(0.0, S["livre"])) if cx else 0.0
            if aporte > 0:
                S["livre"] -= aporte
                S["caixas"][cx] += aporte
                reg("save", aporte, cx, "Aporte automático", ts)
            n += 1
    S["ultimo_credito"] = f"{h.year}-{h.month:02d}"
    if n:
        if renda > 0:
            fx(renda)
        fecha("Balanço mensal processado.")
    else:
        salvar()


def _passos(extra=0.0, limite_meses=None):
    c, h = S["cfg"], agora()
    r = (1 + max(0.0, safe_float(c["cdi"])) / 100) ** (1 / 12) - 1
    cx = {k: max(0.0, safe_float(v)) for k, v in S["caixas"].items()}
    lv, ap, main = max(0.0, safe_float(S["livre"])), total(), next(iter(S["caixas"]), None)
    renda, gastos, guard, extra = (max(0.0, safe_float(c["renda"])), max(0.0, safe_float(c["gastos"])),
                                   max(0.0, safe_float(c["guardar"])), safe_float(extra))
    net = renda - gastos + extra
    g = (min(guard, max(0.0, renda - gastos)) + extra) if main else 0.0
    ano, mes, passos = h.year, h.month, 0
    while limite_meses is None or passos < limite_meses:
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
        lv = max(0.0, lv * (1 + r) + net - g)
        for k in cx:
            cx[k] *= 1 + r
        if main:
            cx[main] += g
        ap += net
        passos += 1
        yield ano, mes, lv + sum(cx.values()), ap, lv, dict(cx)


def _limite():
    meses = idade_info()[2]
    return meses if meses > 0 else 120


def periodo_txt():
    h, (idade, b18, meses) = agora().date(), idade_info()
    fim = b18 if meses > 0 else date(h.year + 10, h.month, min(h.day, 28))
    return f"Período: {h:%d/%m/%Y} até {fim:%d/%m/%Y}" + (" (aos 18 anos)" if meses > 0 else " (10 anos)")


def projetar():
    h = agora()
    limite, meses = _limite(), idade_info()[2]
    por_ano, ult, estado = {}, None, (total(), total(), S["livre"], dict(S["caixas"]))
    for ano, mes, b, ap, lv, cx in _passos(limite_meses=limite):
        estado, ult = (b, ap, lv, cx), (ano, mes)
        if mes == 12:
            por_ano[ano] = estado
    linhas = [(a, v[1], v[0] - v[1], v[0]) for a, v in sorted(por_ano.items())]
    ano_fim = ult[0] if ult else h.year
    rotulo = "18 anos" if meses > 0 else ano_fim
    if ult and ult[1] == 12 and linhas and linhas[-1][0] == ult[0]:
        linhas[-1] = (rotulo,) + linhas[-1][1:]
    else:
        linhas.append((rotulo, estado[1], estado[0] - estado[1], estado[0]))
    r = (1 + max(0.0, safe_float(S["cfg"]["cdi"])) / 100) ** (1 / 12) - 1
    meta, g = S["cfg"]["meta"], (1 + r) ** limite
    falta = max(0.0, (meta - total() * g) / ((g - 1) / r)) if r > 0 else max(0.0, (meta - total()) / limite)
    return linhas, falta, ano_fim, meta, estado[2:]


def mes_meta():
    h, meta = agora(), S["cfg"]["meta"]
    if total() >= meta:
        return h.year, h.month
    for ano, mes, b, *_ in _passos(limite_meses=_limite()):
        if b >= meta:
            return ano, mes
    return None


def fmt_mes(t):
    return f"{MESES[t[1] - 1]}/{t[0]}" if t else "fora do período"


def destino(x):
    s = x.get("cn") or (nome_cx(x["c"]) if x.get("c") else "")
    d = x.get("dn") or (nome_cx(x["d"]) if x.get("d") else "")
    return s + (" → " + d if d else "")


def _csv(cab, linhas):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(cab)
    w.writerows(linhas)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _xlsx(titulo, cab, linhas, fmts, larg):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter as col
    except Exception:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = titulo
    ws["A1"] = "🚀 FUTURE · " + titulo
    ws["A1"].font = Font(bold=True, size=16, color="5B2BE0")
    for j, c in enumerate(cab, 1):
        x = ws.cell(4, j, c)
        x.font, x.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="5B2BE0")
        ws.column_dimensions[col(j)].width = larg[j - 1]
    for i, lin in enumerate(linhas, 1):
        for j, v in enumerate(lin, 1):
            x = ws.cell(4 + i, j, v)
            if fmts[j - 1]:
                x.number_format = fmts[j - 1]
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00'


def xlsx_ext():
    out = []
    for x in sorted(S["extrato"], key=lambda e: e["ts"], reverse=True):
        v = x["v"] if x["t"] in ("in", "yld") else -x["v"] if x["t"] in ("out", "del") else x["v"]
        out.append((datetime.fromisoformat(x["ts"]).replace(tzinfo=None), TIPOS[x["t"]][1], destino(x), x["o"], v))
    return _xlsx("Extrato", ["Data e hora", "Tipo", "Caixinha", "Observação", "Valor (R$)"], out,
                 ["dd/mm/yyyy hh:mm", None, None, None, MOEDA], [20, 26, 34, 32, 18])


def csv_ext():
    out = []
    for x in sorted(S["extrato"], key=lambda e: e["ts"], reverse=True):
        v = x["v"] if x["t"] in ("in", "yld") else -x["v"] if x["t"] in ("out", "del") else x["v"]
        d = datetime.fromisoformat(x["ts"])
        out.append((d.strftime("%d/%m/%Y"), d.strftime("%H:%M"), TIPOS[x["t"]][1], destino(x), f"{v:.2f}".replace(".", ","), x["o"]))
    return _csv(["Data", "Hora", "Tipo", "Caixinha", "Valor (R$)", "Observação"], out)


# --- ASSISTENTE LUNATIC ---
@st.dialog("🤖 Consultor Lunatic")
def dlg_lunatic():
    st.markdown('<div class="dh" style="padding-top:0;">Pergunte o que quiser ao Lunatic com base nas suas finanças.</div>', unsafe_allow_html=True)
    
    if "lunatic_msgs" not in st.session_state:
        st.session_state["lunatic_msgs"] = [
            {"role": "assistant", "content": f"Olá, {CONTA['nome']}! Sou o Lunatic. Como posso ajudar com suas finanças hoje?"}
        ]
        
    for msg in st.session_state["lunatic_msgs"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    prompt = st.chat_input("Digite sua dúvida financeira...")
    if prompt:
        st.session_state["lunatic_msgs"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            if not (HAS_AI and GEMINI_KEY):
                resposta = "⚠️ Chave `gemini_key` não configurada nos Secrets."
                st.markdown(resposta)
                st.session_state["lunatic_msgs"].append({"role": "assistant", "content": resposta})
            else:
                with st.spinner("Pensando..."):
                    t_patrimonio = total()
                    cxs_info = ", ".join([f"{nome_cx(k)}: R$ {v:.2f}" for k, v in S["caixas"].items() if v > 0])
                    contexto = f"""Você é o Lunatic, assistente financeiro inteligente do app FUTURE.
Usuário: {CONTA['nome']}
Meta: R$ {S['cfg']['meta']:.2f}
Reserva Fixa: R$ {S['cfg']['reserva']:.2f}
Saldo Livre: R$ {S['livre']:.2f}
Patrimônio Total: R$ {t_patrimonio:.2f}
Caixinhas: {cxs_info or 'Nenhuma'}
CDI: {S['cfg']['cdi']}% a.a.
INSTRUÇÕES: Responda de forma direta e inteligente com base nos dados fornecidos."""
                    try:
                        modelo = genai.GenerativeModel("gemini-2.5-flash", system_instruction=contexto)
                        historico = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state["lunatic_msgs"][:-1]]
                        chat_sessao = modelo.start_chat(history=historico)
                        resposta = chat_sessao.send_message(prompt).text
                        st.markdown(resposta)
                        st.session_state["lunatic_msgs"].append({"role": "assistant", "content": resposta})
                    except Exception as e:
                        err_msg = f"Erro ao contatar o Lunatic: {str(e)}"
                        st.markdown(err_msg)
                        st.session_state["lunatic_msgs"].append({"role": "assistant", "content": err_msg})


def fx_html(d):
    random.seed(d["n"])
    itens = "".join('<i style="left:%d%%;font-size:%dpx;animation-delay:%.2fs;animation-duration:%.2fs">%s</i>'
                    % (random.randint(4, 90), random.randint(22, 38), random.random() * .9, 1.8 + random.random() * 1.2,
                       random.choice(["💵", "💸", "🪙", "💰"])) for _ in range(16))
    return '<div class="fx">' + itens + '<b>' + d["txt"] + '</b></div>'


def card(cor, tit, val, sub="", extra=""):
    return ('<div class="card" style="--c:var(--' + cor + ')"><div class="lb" style="color:var(--' + cor + ')">' + tit + '</div>'
            '<div class="big">' + val + '</div>' + extra + '<div class="k">' + sub + '</div></div>')


def v_home():
    t, f, c = total(), S["livre"], S["cfg"]
    _, _, ano_fim, meta, _ = projetar()
    idade, b18, meses = idade_info()
    reserva = c["reserva"]
    pc = min(100, t / meta * 100) if meta > 0 else 0
    prazo = f"faltam {prazo_txt(meses)} para os 18 anos" if meses > 0 else f"projeção até {ano_fim}"
    
    # PATRIMÔNIO FINO E BASIQUINHO NO TOPO
    pct = f"{pc:.1f}".replace(".", ",")
    out = f'<div class="card" style="padding:12px 18px; display:flex; justify-content:space-between; align-items:center;">' \
          f'<div><div class="k">Patrimônio Total</div><div style="font-size:20px; font-weight:700;">{brl(t)}</div></div>' \
          f'<div style="text-align:right;"><div class="k">{pct}% da meta</div><div style="font-size:12px; color:var(--mu)">{prazo}</div></div></div>'
    
    out += card("blue", "Saldo livre", brl(f), "Reserva fixa protegida: " + brl(reserva))
    out += v_mes()
    for k, v in S["caixas"].items():
        if visivel(k):
            m = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
            out += card(m[1], html.escape(m[0]), brl(v), html.escape(m[2]) or "Rende 100% do CDI")
    return out


def v_mes():
    h = agora()
    pre = f"{h.year}-{h.month:02d}"
    e = sd = r = 0.0
    for x in S["extrato"]:
        if x["ts"][:7] == pre:
            if x["t"] == "in": e += x["v"]
            elif x["t"] == "out": sd += x["v"]
            elif x["t"] == "yld": r += x["v"]
    cel = lambda t, v, cor: '<div><div class="k">' + t + '</div><b style="color:var(--' + cor + ')">' + brl(v) + '</b></div>'
    return ('<div class="card"><div class="lb">Balanço do mês · ' + MESES[h.month - 1] + '/' + str(h.year) + '</div><div class="mes">'
            + cel("Entrou", e, "grn") + cel("Saiu", sd, "red") + cel("Rendeu", r, "pur") + '</div></div>')


def dia_rotulo(iso):
    d, h = datetime.fromisoformat(iso).date(), agora().date()
    if d == h: return "Hoje"
    if (h - d).days == 1: return "Ontem"
    return f"{DIAS[d.weekday()]}, {d.day} {MESES[d.month - 1]}"


def v_ext():
    if not S["extrato"]:
        return '<div class="card"><div class="k">🌱 Nenhum lançamento ainda.</div></div>'
    rows, ult = "", None
    for _, x in sorted(enumerate(S["extrato"]), key=lambda p: (p[1]["ts"], p[0]), reverse=True):
        dia = dia_rotulo(x["ts"])
        if dia != ult:
            rows, ult = rows + '<div class="dh">' + dia + '</div>', dia
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
    s = ('<svg viewBox="0 0 %d %d" style="width:100%%;height:auto"><line class="tl" x1="0" x2="%d" y1="%.1f" y2="%.1f"/>'
         '<text class="bt" style="fill:var(--gold);text-anchor:start" x="2" y="%.1f">Meta %s</text>' % (W, H, W, ty, ty, ty - 5, kf(meta)))
    for i, (ano, ap, j, b) in enumerate(L):
        h = b / mx * (H - 44)
        x = i * bw + bw * .17
        s += ('<rect class="bar" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="7"/><text class="bt" x="%.1f" y="%.1f">%s</text><text class="bt" x="%.1f" y="%d">%s</text>'
              % (x, H - 24 - h, bw * .66, h, x + bw * .33, H - 28 - h, kf(b), x + bw * .33, H - 7, ano))
    return s + "</svg>"


def v_proj():
    L, falta, ano_fim, meta, _ = projetar()
    fim = L[-1][3]
    meta_em = mes_meta()
    sub = f"Meta alcançada em {fmt_mes(meta_em)}." if meta_em else "Projeção de longo prazo."
    topo = card("grn" if fim >= meta else "gold", "Projeção", brl(fim), sub + "<br>" + periodo_txt())
    tab = '<table><tr><th>Ano</th><th>Investido</th><th>Juros</th><th>Total</th></tr>'
    for a, p, j, b in L:
        tab += '<tr><td>' + str(a) + '</td><td>' + brl(p) + '</td><td style="color:var(--grn)">' + brl(j) + '</td><td><b>' + brl(b) + '</b></td></tr>'
    return topo, '<div class="card">' + svg_barras(L, meta) + '</div><div class="card">' + tab + '</table></div>'


def v_idea():
    reserva = S["cfg"]["reserva"]
    ex = round(max(0.0, S["livre"] - reserva), 2)
    out = ""
    for k, v in S["caixas"].items():
        if v <= 0.004: continue
        m = S["caixas_meta"].get(k, ["Caixinha", "blue", ""])
        out += card(m[1], html.escape(m[0]), brl(v), "Rende 100% do CDI.")
    out += card("blue", "Saldo livre acima da reserva", brl(ex), "Disponível.")
    return out


# --- CONFIGURAÇÕES EM ABAS (IDÊNTICO AO LANÇAMENTO) ---
@st.dialog("⚙️ Ajustes da Conta")
def dlg_ajustes():
    c = S["cfg"]
    pal = list(PALETAS)
    t1, t2, t3 = st.tabs(["👤 Perfil", "🎯 Metas & Reservas", "💰 Balanço Mensal"])
    with t1:
        nome = st.text_input("Nome", CONTA["nome"], max_chars=24)
        paleta = st.selectbox("Tema de Cores", pal, index=pal.index(S["paleta"]) if S.get("paleta") in pal else 0)
        if st.button("Salvar Perfil", type="primary", use_container_width=True):
            CONTA["nome"] = nome.strip() or CONTA["nome"]
            S["paleta"] = st.session_state["paleta"] = paleta
            fecha("Perfil atualizado!")
            st.rerun()
    with t2:
        meta = st.number_input("Meta (R$)", value=float(c["meta"]), step=1000.0)
        reserva = st.number_input("Reserva Fixa (R$)", value=float(c["reserva"]), step=50.0)
        if st.button("Salvar Metas", type="primary", use_container_width=True):
            S["cfg"].update(meta=meta, reserva=reserva, ajustado=True)
            fecha("Metas atualizadas!")
            st.rerun()
    with t3:
        renda = st.number_input("Renda Mensal (R$)", value=float(c["renda"]), step=50.0)
        gast = st.number_input("Gastos Fixos (R$)", value=float(c["gastos"]), step=10.0)
        cdi = st.number_input("CDI (% a.a.)", value=float(c["cdi"]), step=0.1)
        if st.button("Salvar Balanço", type="primary", use_container_width=True):
            S["cfg"].update(renda=renda, gastos=gast, cdi=cdi, ajustado=True)
            fecha("Balanço atualizado!")
            st.rerun()


def form_op(op):
    cx = cx2 = None
    if op in ("save", "take", "yld", "mov"):
        ops = [k for k in S["caixas"] if op == "save" or S["caixas"][k] > 0]
        if not ops:
            st.info("Crie uma caixinha primeiro.")
            return
        cx = st.selectbox("Caixinha", ops, key="c_" + op, format_func=lambda k: nome_cx(k) + " · " + brl(S["caixas"][k]))
        if op == "mov":
            cx2 = st.selectbox("Para", [k for k in S["caixas"] if k != cx], key="d_mov", format_func=nome_cx)
    v = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="v_" + op)
    obs = st.text_input("Observação", max_chars=40, key="o_" + op)
    if st.button("Confirmar", type="primary", use_container_width=True, key="ok_" + op):
        e = mover(cx, cx2, v, obs.strip()) if op == "mov" else aplicar(op, v, cx, obs.strip())
        if e: st.error(e)
        else: st.rerun()


@st.dialog("Novo Lançamento")
def dlg_novo():
    t1, t2, t3 = st.tabs(["💳 Conta", "🐷 Caixinhas", "➕ Nova Caixinha"])
    with t1:
        form_op(st.radio("Tipo", ["in", "out"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r1"))
    with t2:
        form_op(st.radio("Ação", ["save", "take", "yld", "mov"], horizontal=True, format_func=CURTO.get, label_visibility="collapsed", key="r2"))
    with t3:
        nome = st.text_input("Nome da Caixinha", max_chars=24)
        cor = st.selectbox("Cor", ["pur", "blue", "gold", "grn", "red"], format_func={"pur": "Roxo", "blue": "Azul", "gold": "Dourado", "grn": "Verde", "red": "Vermelho"}.get)
        if st.button("Criar Caixinha", type="primary", use_container_width=True):
            if nome.strip():
                k = chave(nome) + "-" + secrets.token_hex(2)
                S["caixas"][k] = 0.0
                S["caixas_meta"][k] = [nome.strip(), cor, ""]
                fecha("Caixinha criada!")
                st.rerun()


@st.dialog("🗑️ Excluir caixinha")
def dlg_excluir():
    ops = list(S["caixas"])
    if not ops: return
    cx = st.selectbox("Caixinha", ops, format_func=lambda k: nome_cx(k))
    modo = st.radio("Destino", ["Resgatar para o Saldo Livre", "Apenas zerar"])
    if st.button("Confirmar", type="primary", use_container_width=True):
        excluir_caixinha(cx, modo.startswith("Resgatar"))
        st.rerun()


@st.dialog("🛡️ Painel dos pais")
def dlg_pais():
    senha = st.text_input("Nova senha", type="password")
    pin = st.text_input("Novo PIN (4 números)", type="password", max_chars=4)
    if st.button("Atualizar", type="primary", use_container_width=True):
        if senha: CONTA["s"], CONTA["h"] = mk(senha)
        if pin: CONTA["ps"], CONTA["ph"] = mk(pin)
        salvar()
        st.rerun()


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
    u = st.session_state["u"]
    if u in db()["contas"]:
        db()["contas"][u].get("sess", {}).pop(_th(st.query_params.get("s", "")), None)
        salvar()
    st.session_state.pop("lunatic_msgs", None)
    st.query_params.clear()
    st.session_state.update(u=None, modo=None, tela="login", chal=secrets.token_urlsafe(32), launch=False, nav=False, tab=0, recarregar=True)


def _nav(v):
    st.session_state["nav"] = v


st.button("☀️" if st.session_state["tema"] == "dark" else "🌙", key="b_tema", on_click=_tema, help="Tema")
if not SUP:
    st.button("🤖", key="b_lunatic", on_click=dlg_lunatic, help="Lunatic (IA)")
if not SUP and st.button("⚙️", key="b_ajustes_top", help="Ajustes"):
    dlg_ajustes()
st.button("🔒", key="b_sair", on_click=_sair, help="Sair")

tab = st.session_state["tab"]
if st.session_state["nav"]:
    with st.container(key="nav"):
        st.button("‹", key="b_min", on_click=_nav, args=(False,))
        aba = st.radio("Atalhos", ABAS, index=tab, key="aba", horizontal=True, label_visibility="collapsed")
        if st.button("🛡️" if SUP else "＋", key="b_plus"):
            (dlg_pais if SUP else dlg_novo)()
    idx = ABAS.index(aba)
else:
    st.button(ABAS[tab].split()[0], key="bolha", on_click=_nav, args=(True,))
    idx = tab
if idx != tab:
    st.session_state.update(dir="R" if idx > tab else "L", tab=idx)

st.markdown('<div class="hd" style="margin-top:8px"><div class="k">' + TITULOS[idx] + ' · ' + hoje_txt() + '</div><h1>' + html.escape(CONTA["nome"]) + '</h1></div>', unsafe_allow_html=True)
if SUP:
    st.markdown('<div class="sup" style="margin-top:0">🔐 <b>Modo supervisão:</b> somente leitura.</div>', unsafe_allow_html=True)

with st.container(key=f"view_{idx}_from{st.session_state['dir']}"):
    if idx == 0:
        st.markdown(v_home(), unsafe_allow_html=True)
        if not SUP and S["caixas"]:
            if st.button("🗑️ Excluir caixinha", key="b_del", use_container_width=True):
                dlg_excluir()
    elif idx == 1:
        st.markdown(v_ext(), unsafe_allow_html=True)
        if S["extrato"]:
            hoje, x = f"{agora():%Y-%m-%d}", xlsx_ext()
            with st.container(key="dl"):
                c1, c2 = st.columns(2)
                if x: c1.download_button("📊 Excel", x, file_name=f"extrato_{hoje}.xlsx", mime=XL, use_container_width=True)
                c2.download_button("📄 CSV", csv_ext(), file_name=f"extrato_{hoje}.csv", mime="text/csv", use_container_width=True)
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
    st.markdown('<div class="lift"><i>🚀</i></div>', unsafe_allow_html=True)
    st.session_state["launch"] = False

"""
app.py — Site (Streamlit) do sistema de conferência de armaduras.
Rodar no computador:   streamlit run app.py
"""
import json, os, tempfile
import streamlit as st
import pandas as pd

import extrator, etiquetas, exportar

st.set_page_config(page_title="Conferência de Armaduras — BIM/TQS", page_icon="🏗️", layout="centered")
st.title("🏗️ Conferência de Armaduras")
st.caption("IFC do TQS → pilares, vigas e lajes com suas barras → etiquetas QR + Firebase")


# ---------- Firebase (opcional: só funciona se a chave estiver nos Secrets) ----------
@st.cache_resource
def _conectar(chave_json):
    import firebase_db
    return firebase_db.conectar(json.loads(chave_json))

db, erro_fb = None, None
try:
    tem_chave = "firebase" in st.secrets
except Exception:          # nenhum secrets configurado
    tem_chave = False
if tem_chave:
    try:
        db = _conectar(json.dumps(dict(st.secrets["firebase"])))
    except Exception as e:
        erro_fb = f"{type(e).__name__}: {e}"

if db is not None:
    st.success(f"Conectado ao Firebase ({st.secrets['firebase'].get('project_id', '')}).", icon="✅")
elif erro_fb:
    st.error("A chave do Firebase está nos Secrets, mas deu erro ao conectar:\n\n" + erro_fb)
else:
    st.info("Firebase não configurado — o site funciona, mas só gera os arquivos para baixar. "
            "Veja o README para colocar a chave em *Secrets*.", icon="ℹ️")

aba_proc, aba_rel = st.tabs(["📤 Processar IFC", "📊 Relatório de obra"])

# ---------------------------------------------------------------- processar
with aba_proc:
    nome_obra = st.text_input("Nome da obra", placeholder="Ex.: Casa PD")
    arq = st.file_uploader("Arquivo IFC (exportado do TQS)", type=["ifc"])
    if st.button("🚀 Processar", type="primary", disabled=not (nome_obra and arq)):
        barra = st.progress(0.0, text="Lendo IFC…")
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(arq.getbuffer()); caminho = tmp.name
        try:
            dados = extrator.extrair(caminho, nome_obra,
                                     progresso=lambda p, etapa: barra.progress(min(p, 1.0), text=etapa))
            dados["obra"]["arquivo_ifc"] = arq.name
        finally:
            os.unlink(caminho)
        barra.progress(1.0, text="Gerando etiquetas…")
        st.session_state["dados"] = dados
        st.session_state["pdf"] = etiquetas.gerar_pdf(dados)
        st.session_state["xlsx"] = exportar.gerar_excel(dados)
        st.session_state.pop("enviado", None)
        barra.empty()

    dados = st.session_state.get("dados")
    if dados:
        o = dados["obra"]
        st.success(f"Obra **{o['nome']}** processada.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pilares", o["n_pilares"]); c2.metric("Vigas", o["n_vigas"])
        c3.metric("Lajes", o["n_lajes"]); c4.metric("Barras", o["n_barras_total"])
        if o["n_barras_sem_elemento"] or o["n_barras_aproximadas"]:
            st.warning(f"{o['n_barras_sem_elemento']} barras sem elemento e "
                       f"{o['n_barras_aproximadas']} associadas por proximidade "
                       "(fora da caixa de qualquer elemento) — vale conferir.")
        tabela = pd.DataFrame([{"Tipo": e["tipo"], "Nome": e["nome"], "Pavimento": e["pavimento"],
                                "Seção": e["secao"], "Barras": e["n_barras"], "Resumo": e["resumo"]}
                               for e in dados["elementos"]])
        filtro = st.multiselect("Filtrar tipo", ["Pilar", "Viga", "Laje"], default=["Pilar", "Viga", "Laje"])
        st.dataframe(tabela[tabela["Tipo"].isin(filtro)], hide_index=True, use_container_width=True)

        base = o["id"]
        d1, d2, d3 = st.columns(3)
        d1.download_button("🏷️ Etiquetas (PDF)", st.session_state["pdf"], f"etiquetas_{base}.pdf", "application/pdf")
        d2.download_button("📊 Relatório (Excel)", st.session_state["xlsx"], f"relatorio_{base}.xlsx")
        d3.download_button("🧾 Dados (JSON)", json.dumps(dados, ensure_ascii=False, indent=1),
                           f"dados_{base}.json", "application/json")

        if db is not None:
            if st.session_state.get("enviado"):
                st.success(st.session_state["enviado"])
            elif st.button("☁️ Enviar para o Firebase"):
                import firebase_db
                pb = st.progress(0.0, text="Enviando…")
                total, mantidos = firebase_db.enviar_obra(db, dados, progresso=lambda p: pb.progress(p))
                pb.empty()
                st.session_state["enviado"] = (f"{total} elementos gravados no Firebase"
                                               + (f" ({mantidos} já existiam — conferências mantidas)." if mantidos else "."))
                st.rerun()

# ---------------------------------------------------------------- relatório
with aba_rel:
    if db is None:
        st.write("Disponível depois que o Firebase estiver configurado.")
    else:
        import firebase_db
        obras = firebase_db.listar_obras(db)
        if not obras:
            st.write("Nenhuma obra no banco ainda.")
        else:
            nomes = {f"{x.get('nome', x['id'])} ({x['id']})": x["id"] for x in obras}
            escolha = st.selectbox("Obra", list(nomes))
            if st.button("Carregar situação atual"):
                d = firebase_db.ler_obra(db, nomes[escolha])
                els = d["elementos"]
                feitos = sum(e.get("status") == "CONFERIDO" for e in els)
                st.metric("Conferidos", f"{feitos} / {len(els)}")
                st.progress(feitos / max(len(els), 1))
                st.dataframe(pd.DataFrame([{"Tipo": e.get("tipo"), "Nome": e.get("nome"),
                                            "Pavimento": e.get("pavimento"), "Status": e.get("status"),
                                            "Conferido por": e.get("conferido_por"),
                                            "Data": e.get("data_conferencia")} for e in els]),
                             hide_index=True, use_container_width=True)
                st.download_button("📊 Baixar relatório (Excel)", exportar.gerar_excel(d),
                                   f"relatorio_{nomes[escolha]}.xlsx")
                st.download_button("🏷️ Reimprimir etiquetas (PDF)", etiquetas.gerar_pdf(d),
                                   f"etiquetas_{nomes[escolha]}.pdf", "application/pdf")
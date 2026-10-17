"""
firebase_db.py — Grava e lê os dados no Firebase (Firestore).

Estrutura no banco (o "contrato" com o aplicativo Android):
  obras/{obraId}
      nome, arquivo_ifc, data_upload, n_pilares, n_vigas, n_lajes, ...
  obras/{obraId}/elementos/{idUnico}
      tipo, nome, pavimento, secao, resumo, n_barras, barras[ {posicao, bitola,
      comprimento_cm, tipo, qtd} ], status, conferido_por, data_conferencia
  obras/{obraId}/conferencias/{auto}      <- o APP grava aqui (histórico)

Credenciais: chave da conta de serviço (Console Firebase > Configurações do
projeto > Contas de serviço > Gerar nova chave privada). NUNCA coloque esse
arquivo no GitHub. No Streamlit Cloud ele vai em Settings > Secrets.
"""
import firebase_admin
from firebase_admin import credentials, firestore

CAMPOS_CONFERENCIA = ("status", "conferido_por", "data_conferencia")
_app = None


def conectar(chave):
    """chave = dict (conteúdo do JSON da conta de serviço) ou caminho do arquivo."""
    global _app
    if _app is None:
        _app = firebase_admin.initialize_app(credentials.Certificate(chave))
    return firestore.client(app=_app)


def enviar_obra(db, dados, progresso=None):
    """Grava a obra e seus elementos. Se a obra já existir (IFC reenviado),
    atualiza os dados técnicos mas NÃO apaga conferências já feitas."""
    obra = dict(dados["obra"])
    ref_obra = db.collection("obras").document(obra["id"])
    ref_obra.set(obra, merge=True)

    col = ref_obra.collection("elementos")
    existentes = {d.id for d in col.select([]).stream()}
    els = dados["elementos"]
    batch, n = db.batch(), 0
    for i, e in enumerate(els):
        doc = {k: v for k, v in e.items() if k != "id"}
        if e["id"] in existentes:   # preserva status/quem/quando
            for k in CAMPOS_CONFERENCIA:
                doc.pop(k, None)
        batch.set(col.document(e["id"]), doc, merge=True)
        n += 1
        if n == 400:                # limite do Firestore: 500 operações por lote
            batch.commit(); batch, n = db.batch(), 0
            if progresso: progresso((i + 1) / len(els))
    if n:
        batch.commit()
    if progresso: progresso(1.0)
    return len(els), len(existentes & {e["id"] for e in els})


def listar_obras(db):
    return [{"id": d.id, **d.to_dict()} for d in db.collection("obras").stream()]


def ler_obra(db, obra_id):
    """Lê a obra inteira (com o status atual das conferências) no mesmo formato
    do extrator, para gerar relatório/etiquetas novamente."""
    ref = db.collection("obras").document(obra_id)
    obra = ref.get().to_dict() or {}
    obra["id"] = obra_id
    elementos = [{"id": d.id, **d.to_dict()} for d in ref.collection("elementos").stream()]
    ordem = {"Pilar": 0, "Viga": 1, "Laje": 2}
    elementos.sort(key=lambda e: (ordem.get(e.get("tipo"), 9), e.get("pavimento", ""), e.get("nome", "")))
    return {"obra": obra, "elementos": elementos}

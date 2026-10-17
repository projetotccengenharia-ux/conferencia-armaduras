# ROTEIRO DO TCC: App de Conferência de Armaduras (BIM/IFC/TQS)

> **Como usar este arquivo:** ao começar uma conversa nova com o Claude, envie este arquivo (e o .zip do código, se for mexer nele) e diga em que fase está. Atualize a seção "Registro" e as caixas ☐/☑ sempre que avançar.

## 1. Identificação

- **Aluno:** Dumar Esteves Jardim, Engenharia Civil, UFVJM (TCC em dupla)
- **Professor/tema:** Danilo
- **Base:** dissertação de mestrado de **Thiago Freire Alves Ferreira** (UFVJM/PPGTAS): extração de dados de IFC do TQS com Python + IfcOpenShell, site Streamlit, Google Sheets como banco, etiquetas QR e app no **AppSheet** para conferir **pilares**.
  - Site do Thiago: `https://app-mestrado-bim-edpenk2vjdm6ccwwafxhuz.streamlit.app`
- **Objetivo do TCC:** estender para **vigas e lajes** (refazendo pilares) e trocar o AppSheet por um **aplicativo Android próprio**, publicável na Play Store, sem depender de outro app.

## 2. Arquitetura escolhida

```
TQS → IFC → SITE (Python/Streamlit) ──grava──► FIREBASE (Firestore) ◄──lê/grava── APP ANDROID (Kotlin)
                 │                                                                  ▲
                 └── PDF de etiquetas QR → impressas → presas na armadura → escaneadas
```

| Peça | Tecnologia | Por quê |
|---|---|---|
| Site de extração | Python + IfcOpenShell + Streamlit (Streamlit Community Cloud) | É o mesmo modelo do Thiago; o Python fica no servidor |
| Banco de dados | **Firebase Firestore** (plano Spark, grátis) | Não depende da conta pessoal; offline embutido; login; tempo real |
| Login | Firebase Authentication (conta Google de cada usuário) | Registra quem conferiu |
| App | **Kotlin + Jetpack Compose** (Android Studio) | Linguagem oficial do Android. Python no Android não vale a pena |
| Leitura do QR | CameraX + ML Kit Barcode Scanning | Biblioteca embutida no app |
| Relatório | Excel gerado pelo site a partir do Firestore | Substitui a "planilha" do Thiago para orientador e texto |

**Decisões tomadas (e motivo):**
- Firebase em vez de Google Sheets ou Apps Script: não depende da conta pessoal, funciona offline e tem login. Criar o projeto com um **Gmail exclusivo do projeto** e adicionar pelo menos 1 colega como **proprietário**.
- Cada usuário do app entra com a **própria conta Google**. A conta dona do projeto só administra.
- Associação barra → elemento **por geometria**, não pelo nome (ver seção 5).
- ID único no mesmo formato do Thiago.

## 3. Estrutura de dados (o "contrato" entre o site e o app)

```
obras/{obraId}                      ex.: CASAPD
   nome, arquivo_ifc, data_upload, n_pilares, n_vigas, n_lajes,
   n_barras_total, n_barras_sem_elemento, n_barras_aproximadas

obras/{obraId}/elementos/{idUnico}  ex.: V201-13PLu1N8x1Wp2N1Z8W65J8-PRIMEIRO-CASAPD
   tipo ("Pilar"|"Viga"|"Laje"), nome, pavimento, secao, obra_id, guids[],
   resumo ("6 ø10.0 + 38 ø5.0"), n_barras, n_barras_aproximadas,
   barras: [ {posicao:"P1", bitola:10.0, comprimento_cm:655.4, tipo:"Negativa", qtd:2}, ... ],
   status ("A CONFERIR"|"CONFERIDO"), conferido_por, data_conferencia
   (o app também pode gravar: barras_conferidas, observacao)

obras/{obraId}/conferencias/{auto}  ← só o APP cria (histórico: quem, quando, elemento, resultado)
```

- **QR code:** contém só o `idUnico`.
- **ID:** `{Nome}-{GUID}-{PAVIMENTO}-{OBRA}`
- **Regras de segurança:** o site grava com a conta de serviço. O app (usuário logado) só lê e altera os campos de conferência (arquivo `firestore.rules`).

## 4. Fases

### Fase 0: Preparação
- ☐ Criar Gmail do projeto
- ☐ Pedir ao Thiago/orientador o código do site (GitHub), para comparar com o nosso
- ☐ Instalar Android Studio, Python, VS Code; criar conta no GitHub
- ☐ Alinhar com o orientador a troca Google Sheets/AppSheet → Firebase/app próprio

### Fase 1: Firebase
- ☐ Criar projeto (Gmail do projeto) e adicionar colega como proprietário
- ☐ Ativar Firestore (região southamerica-east1)
- ☐ Ativar Authentication → Google
- ☐ Colar `firestore.rules`
- ☐ Gerar chave da conta de serviço → `secrets.toml` (nunca no GitHub)

### Fase 2: Site Python (extração + QR) ← **código pronto (v1)**
- ☑ Extrair IfcColumn, IfcBeam, IfcSlab com seção e pavimento
- ☑ Associar barras por geometria (pontos a cada 10 cm)
- ☑ Juntar barras exportadas em pedaços
- ☑ Agrupar trechos de viga com o mesmo nome
- ☑ ID único + PDF de etiquetas (QR testado e lido corretamente)
- ☑ Relatório Excel + JSON
- ☑ Gravação no Firestore preservando conferências ao reenviar (testado com banco simulado)
- ☑ Site Streamlit (abas: Processar IFC / Relatório de obra)
- ☐ Testar com o Firebase de verdade
- ☐ Publicar no Streamlit Community Cloud
- ☐ Conferir alguns elementos contra as pranchas do TQS (validação do método)
- ☐ (melhoria) Acelerar o processamento (~150 s no IFC CASA_PD)

### Fase 3: App Android (Kotlin)
- ☐ Projeto Empty Activity (Compose) + `google-services.json`
- ☐ Tela de login Google (Firebase Auth)
- ☐ Lista de obras
- ☐ Scanner de QR (CameraX + ML Kit)
- ☐ Detalhe do elemento: seção, barras, checklist por posição
- ☐ Botão Validar: status + data + usuário + registro em `conferencias`
- ☐ Lista "a conferir / conferidos" por pavimento
- ☐ Modo offline do Firestore

### Fase 4: Relatório
- ☑ Exportar Excel pelo site (aba "Relatório de obra", lendo do Firestore)

### Fase 5: Teste e publicação
- ☐ Teste completo com a CASA_PD (imprimir, escanear, validar)
- ☐ Instalar APK nos celulares do grupo
- ☐ (opcional) Play Store: conta US$ 25, teste fechado (12 testadores/14 dias), política de privacidade, formulário de segurança dos dados

## 5. Descobertas técnicas sobre o IFC do TQS (importante para o texto do TCC)

1. **O IFC não liga a barra ao elemento.** Não existe IfcRelAggregates nem IfcRelConnects entre IfcReinforcingBar e o pilar, a viga ou a laje. A barra fica ligada só ao pavimento.
2. **No nome `1 P11 Ø10.00 C=874.00`, o "P11" é a POSIÇÃO da barra**, não o pilar P11. O primeiro número é a quantidade e o C é o comprimento em cm. O método do Thiago lia "1 P1" como Pilar P1, o que mistura barras de elementos diferentes. A Figura 7 da dissertação mostra um P1 14x35 com mais de 800 barras, sinal do problema.
3. **A descrição da barra indica o tipo de elemento e de armadura:** "Armadura transversal pilares", "Armadura longitudinal vigas negativa", "Armadura longitudinal positiva lajes" etc.
4. **Barras em pedaços:** as negativas de viga e as secundárias de laje vêm como IfcFaceBasedSurfaceModel, com reta + ganchos em objetos separados de mesmo nome. Os 4.573 objetos viram **4.321 barras físicas**.
5. **Vigas divididas em trechos:** vários IfcBeam com o mesmo nome no mesmo pavimento (ex.: V201) são agrupados num elemento só.
6. **Algumas barras vêm com `C=0.00`** (ex.: algumas P1/P3 ø10 de laje). É dado do TQS, não do script.
7. **Lajes treliçadas** têm só a capa como geometria. Por isso negativos sobre as vigas às vezes ficam fora da caixa da laje e são marcados como "aproximados".
8. **IFC CASA_PD:** 71 lances de pilar, 34 vigas, 24 lajes, 4.321 barras, 0 sem elemento, 75 aproximadas (50 na L1 da Fundação, que é uma laje maciça sobre solo h=20, e 25 na L7 do Primeiro).
9. **Pilares:** cada lance (pavimento) é um elemento. A barra longitudinal que atravessa dois lances fica no lance onde está a maior parte dela.

## 6. Pendências e decisões em aberto

- ☐ A conferência será **por elemento** ou **por posição de barra** (checklist)? Recomendação: por posição.
- ☐ Negativos de laje entre duas lajes: ficam na laje com a maior parte da barra (atual) ou num grupo por pavimento?
- ☐ Validar com o orientador se o Firebase e o app próprio são aceitos no lugar de Sheets/AppSheet.

## 7. Arquivos do projeto

Pasta `conferencia_ifc/`:
- `extrator.py`: leitura do IFC e associação geométrica
- `etiquetas.py`: PDF das etiquetas com QR
- `exportar.py`: relatório Excel
- `firebase_db.py`: gravação e leitura no Firestore
- `app.py`: site Streamlit
- `firestore.rules`: regras de segurança
- `requirements.txt`, `.gitignore`, `.streamlit/secrets.toml.exemplo`
- `README.md`: como rodar, configurar o Firebase e publicar
- `ROTEIRO_TCC.md`: este arquivo

## 8. Registro (o que foi feito, quando)

- **17/10/2026**: Analisado o IFC CASA_PD (TQS 24.7.2, IFC2X3) e lida a dissertação do Thiago. Escolhida a arquitetura (Firebase + Kotlin). Construída a Fase 2 v1: extrator geométrico, etiquetas, Excel, Firestore e site Streamlit, testados com a CASA_PD.
- *(próximo)*: Fase 1 (criar o Firebase) e testar o envio real; começar a Fase 3.

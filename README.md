# Conferência de Armaduras: site de extração (Fase 2)

Este site recebe o IFC exportado pelo TQS e identifica os **pilares, vigas e lajes**, com as barras de cada um. Depois ele gera:

- **etiquetas em PDF** com QR code (o QR guarda só o ID único do elemento);
- **relatório em Excel**, com as abas Resumo, Elementos e Barras;
- **dados em JSON**;
- **gravação no Firebase** (Firestore), que o aplicativo Android lê.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `extrator.py` | Lê o IFC e associa cada barra ao seu elemento **por geometria** |
| `etiquetas.py` | Gera o PDF de etiquetas com QR |
| `exportar.py` | Gera o Excel |
| `firebase_db.py` | Grava e lê os dados no Firestore |
| `app.py` | O site (Streamlit) |
| `firestore.rules` | Regras de segurança do banco (colar no console do Firebase) |
| `.streamlit/secrets.toml.exemplo` | Modelo de onde vai a chave do Firebase |

## 1. Rodar no seu computador

```bash
# 1x só: instalar as bibliotecas
pip install -r requirements.txt

# abrir o site (abre no navegador em http://localhost:8501)
streamlit run app.py

# ou só extrair, sem site (gera um .json ao lado do IFC)
python extrator.py CASA_PD_FINAL.IFC "Casa PD"
```

O processamento do IFC da CASA_PD leva de 2 a 3 minutos, porque a geometria de cada uma das 4.573 barras é calculada.

## 2. Configurar o Firebase

1. Acesse console.firebase.google.com com o **Gmail do projeto** e clique em **Criar projeto**.
2. Vá em **Firestore Database**, clique em **Criar banco de dados** e escolha a região `southamerica-east1` (São Paulo).
3. Em **Firestore > Regras**, cole o conteúdo de `firestore.rules` e publique.
4. Em **Authentication > Método de login**, ative o **Google** (o app vai precisar).
5. Em **Configurações do projeto > Contas de serviço**, clique em **Gerar nova chave privada** e baixe o JSON.
   ⚠️ Esse arquivo é uma senha de administrador do banco: **nunca coloque no GitHub**.
6. Copie `.streamlit/secrets.toml.exemplo` para `.streamlit/secrets.toml` e preencha com os valores do JSON.
7. Rode `streamlit run app.py`. O aviso "Firebase não configurado" deve sumir e aparece o botão **Enviar para o Firebase**.

## 3. Publicar o site (Streamlit Community Cloud, grátis)

1. Crie um repositório no GitHub e envie esta pasta. O `.gitignore` já impede que o `secrets.toml` seja enviado.
2. Em share.streamlit.io, clique em **Create app**, escolha o repositório e o arquivo `app.py`.
3. Em **Advanced settings > Secrets**, cole o mesmo conteúdo do seu `secrets.toml`.
4. Clique em Deploy. O site ganha um endereço `https://<nome>.streamlit.app`.

## Como a barra é associada ao elemento

- O IFC do TQS **não liga** a barra ao elemento. O "P11" do nome `1 P11 Ø10.00 C=874.00` é a **posição** da barra, não o pilar P11.
- A **descrição** da barra informa o tipo de elemento ("…pilares", "…vigas", "…lajes").
- Pontos são distribuídos a cada 10 cm ao longo da barra, e o programa conta quantos caem dentro da caixa de cada elemento daquele tipo. O elemento com mais pontos é o dono da barra.
- Se nenhum ponto cair dentro de algum elemento, a barra vai para o elemento mais próximo e é contada como **"aproximada"**. Isso acontece, por exemplo, com negativos de laje sobre as vigas.
- Algumas barras (negativas de viga, secundárias de laje) chegam **em pedaços**: a reta e cada gancho são objetos separados com o mesmo nome. O programa junta os pedaços que se tocam e conta **1 barra física**.
- Vigas que o TQS divide em trechos (vários objetos `V201` no mesmo pavimento) viram **um elemento só**.

## ID único (vai no QR code)

`{Nome}-{GUID do 1º objeto}-{PAVIMENTO}-{OBRA}`, por exemplo `V201-13PLu1N8x1Wp2N1Z8W65J8-PRIMEIRO-CASAPD`.
É o mesmo formato da dissertação do Thiago. Também é o ID do documento no Firestore.

## Reenviar o IFC de uma obra

Se o projeto for revisado e o IFC for enviado de novo com o **mesmo nome de obra**, os dados técnicos são atualizados, mas **as conferências já feitas** (status, quem e quando) **são mantidas**.

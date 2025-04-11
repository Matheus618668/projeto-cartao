import streamlit as st

# ✅ CONFIGURAÇÃO DA PÁGINA — PRIMEIRO COMANDO DO STREAMLIT
st.set_page_config(page_title="Validador de Compras", layout="centered")

# Agora sim pode seguir o resto
import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
<<<<<<< HEAD
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
=======
>>>>>>> 43b9019 (Atualiza requirements com versões compatíveis)

# ================================
# 1. Autenticação Google Sheets e Drive
# ================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file"
]
credentials_dict = st.secrets["google_service_account"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
gc = gspread.authorize(credentials)

# PyDrive auth
gauth = GoogleAuth()
gauth.credentials = credentials
drive = GoogleDrive(gauth)

# ================================
# 2. Google Sheets
# ================================
SHEET_ID = "1CcrV5Gs3LwrLXgjLBgk2M02SAnDVJGuHhqY_pi56Mnw"
worksheet = gc.open_by_key(SHEET_ID).sheet1

# ================================
<<<<<<< HEAD
# 3. IDs das pastas fixas no Google Drive
# ================================
PASTAS_EMPRESA = {
    "Moon Ventures": "1pVdro4IFN08GEUSaCYDOwvS5dTCNAl41",
    "Minimal Club": "1c_lrNDj3s18j_vlGQCJLWjXYno9JgFrT",
    "Hoomy": "1wBwFFxuEYBnuPyMY13cH0zKEMqZtHDd9"
}

# ================================
# 4. Mapeamento fixo dos cartões e empresas
# ================================
cartoes = [
    "Inter Moon Ventures",
    "Inter Minimal",
    "Inter Hoomy",
    "Bradesco Minimal",
    "Conta Simples Hoomy",
    "Conta Simples Moon Ventures"
]

mapa_empresas = {
    "Inter Moon Ventures": "Moon Ventures",
    "Bradesco Moon Ventures": "Moon Ventures",
    "Conta Simples Moon Ventures": "Moon Ventures",
    "Inter Minimal": "Minimal Club",
    "Bradesco Minimal": "Minimal Club",
    "Inter Hoomy": "Hoomy",
    "Bradesco Hoomy": "Hoomy",
    "Conta Simples Hoomy": "Hoomy"
}

# ================================
# 5. Função para upload no Google Drive
# ================================
def upload_to_drive(file, empresa):
    folder_id = PASTAS_EMPRESA.get(empresa)
    if not folder_id:
        st.error(f"❌ ID da pasta não encontrado para a empresa: {empresa}")
        st.stop()

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[-1]) as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}"

    try:
        gfile = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
        gfile.SetContentFile(tmp_path)
        gfile.Upload()
        gfile.InsertPermission({
            'type': 'anyone',
            'value': 'anyone',
            'role': 'reader'
        })
        return gfile['alternateLink'], tmp_path

    except Exception as e:
        st.error(f"❌ Erro ao fazer upload para o Drive: {e}")
        st.stop()

# ================================
# 6. Envio de Email com Anexo
# ================================
def enviar_email(destinatario, dados, anexo_path=None, anexo_nome=None):
    config = st.secrets["email"]

    msg = MIMEMultipart()
    msg['From'] = config["sender"]
    msg['To'] = destinatario
    msg['Subject'] = "Confirmação de Registro de Compra"

    corpo = "".join([f"<b>{chave}:</b> {valor}<br>" for chave, valor in dados.items()])
    msg.attach(MIMEText(corpo, 'html'))

    if anexo_path and anexo_nome:
        try:
            with open(anexo_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={anexo_nome}")
                msg.attach(part)
        except Exception as e:
            st.warning(f"❗ Não foi possível anexar o arquivo: {e}")

    try:
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["sender"], config["password"])
            server.sendmail(config["sender"], destinatario, msg.as_string())
    except Exception as e:
        st.warning(f"❌ Email não enviado: {e}")

# ================================
# 7. App Principal
# ================================
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante"]
=======
# 3. Função para upload no Google Drive
# ================================
def upload_to_drive(file, empresa):
    # Cria pasta se não existir (cache em memoria por sessão)
    if "folders" not in st.session_state:
        st.session_state.folders = {}

    if empresa not in st.session_state.folders:
        folder_metadata = {
            'title': empresa,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        st.session_state.folders[empresa] = folder['id']
    else:
        folder_id = st.session_state.folders[empresa]

    # Salvar arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    # Upload para o Drive
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}"
    gfile = drive.CreateFile({'title': filename, 'parents': [{'id': st.session_state.folders[empresa]}]})
    gfile.SetContentFile(tmp_path)
    gfile.Upload()

    # Deletar arquivo temporário
    os.remove(tmp_path)

    # Gerar link público
    gfile.InsertPermission({
        'type': 'anyone',
        'value': 'anyone',
        'role': 'reader'
    })
    return gfile['alternateLink']

# ================================
# 4. Configurações do app
# ================================
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Comprador", "Comprovante"]

>>>>>>> 43b9019 (Atualiza requirements com versões compatíveis)
if not os.path.exists(data_file):
    pd.DataFrame(columns=colunas_corretas).to_excel(data_file, index=False)

<<<<<<< HEAD
if "new" in st.query_params:
    for chave in list(st.session_state.keys()):
        if chave not in ["google_service_account", "email"]:
            del st.session_state[chave]
    st.query_params.clear()

st.markdown("""
<style>
    .main {
        padding-left: 40px;
        padding-right: 40px;
    }
</style>
""", unsafe_allow_html=True)

st.title("💳 Gestor de Compras Corporativas")
menu = st.sidebar.selectbox("📌 Navegação", ["Inserir Compra", "Visualizar Compras"])

if menu == "Inserir Compra":
    st.subheader("Inserção de Dados da Compra")

    campos = {
        "fornecedor": "",
        "valor_str": "",
        "parcelado": "Não",
        "parcelas": 1,
        "comprador": "",
        "descricao": "",
        "email_opcional": ""
    }

    for campo, valor_inicial in campos.items():
        if campo not in st.session_state:
            st.session_state[campo] = valor_inicial

    cartao = st.selectbox("💳 Nome do cartão", cartoes)
    fornecedor = st.text_input("📦 Nome do Fornecedor", key="fornecedor")
    valor_str = st.text_input("💰 Valor da Compra (total)", placeholder="Ex: 399,80", key="valor_str")
=======
st.set_page_config(page_title="Validador de Compras", layout="centered")
st.title("📟 Validador de Compras com Cartão de Crédito")
st.subheader("Inserção de Dados da Compra")

cartoes = [
    "Inter Moon Ventures",
    "Inter Minimal",
    "Inter Hoomy",
    "Bradesco Minimal",
    "Bradesco Hoomy",
    "Bradesco Moon Ventures"
]
mapa_empresas = {
    "Inter Moon Ventures": "Moon Ventures",
    "Bradesco Moon Ventures": "Moon Ventures",
    "Inter Minimal": "Minimal Club",
    "Bradesco Minimal": "Minimal Club",
    "Inter Hoomy": "Hoomy",
    "Bradesco Hoomy": "Hoomy"
}

# Entradas
data = datetime.today().strftime('%Y-%m-%d')
cartão = st.selectbox("💳 Nome do cartão", cartoes)
fornecedor = st.text_input("📦 Nome do Fornecedor")
valor = st.number_input("💰 Valor da Compra", min_value=0.0, format="%.2f")
parcelado = st.radio("💳 Foi parcelado?", ["Não", "Sim"])
parcelas = st.number_input("📅 Quantidade de Parcelas", min_value=1, max_value=12, value=1) if parcelado == "Sim" else 1
comprador = st.text_input("👤 Nome do Comprador")
comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

# Botão de salvar
if st.button("✅ Salvar Compra"):
    if fornecedor and valor > 0 and comprador and cartão:
        empresa = mapa_empresas.get(cartão, "Outros")

        link_drive = "Nenhum"
        if comprovante:
            link_drive = upload_to_drive(comprovante, empresa)

        df = pd.read_excel(data_file)
        if list(df.columns) != colunas_corretas:
            df = df.reindex(columns=colunas_corretas)

        nova_linha = pd.DataFrame(
            [[data, cartão, fornecedor, valor, parcelado, parcelas, comprador, link_drive]],
            columns=colunas_corretas
        )
        df = pd.concat([df, nova_linha], ignore_index=True)
        df.to_excel(data_file, index=False)

        worksheet.append_row([data, cartão, fornecedor, valor, parcelado, parcelas, comprador, link_drive])
>>>>>>> 43b9019 (Atualiza requirements com versões compatíveis)

    try:
        valor_float = float(valor_str.replace("R$", "").replace(".", "").replace(",", "."))
    except:
        valor_float = 0.0

    valor = valor_float
    valor_formatado = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.markdown(f"🔎 Valor interpretado: **{valor_formatado}**")

    parcelado = st.radio("💳 Foi parcelado?", ["Não", "Sim"], key="parcelado")
    if parcelado == "Sim":
        parcelas = st.number_input("📅 Quantidade de Parcelas", min_value=1, max_value=12, value=st.session_state["parcelas"], key="parcelas")
    else:
<<<<<<< HEAD
        parcelas = 1

    valor_parcela = valor / parcelas if parcelas > 0 else 0.0
    st.markdown(f"💵 **Valor de cada parcela:** R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    comprador = st.text_input("👤 Nome do Comprador", key="comprador")
    email_opcional = st.text_input("📧 E-mail (opcional)", key="email_opcional")
    descricao = st.text_area("📝 Descrição da Compra", key="descricao")
    comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

    if st.button("✅ Salvar Compra"):
        erros = []
        if not fornecedor: erros.append("Fornecedor não informado.")
        if valor <= 0: erros.append("Valor deve ser maior que zero.")
        if not comprador: erros.append("Nome do comprador não informado.")
        if not descricao: erros.append("Descrição da compra não informada.")
        if not comprovante: erros.append("Comprovante não anexado.")

        if erros:
            st.error("\n".join(["❌ " + erro for erro in erros]))
        else:
            empresa = mapa_empresas.get(cartao, "Outros")
            link_drive, path_comprovante = upload_to_drive(comprovante, empresa)

            df = pd.read_excel(data_file)
            if list(df.columns) != colunas_corretas:
                df = df.reindex(columns=colunas_corretas)

            novas_linhas = []
            for i in range(parcelas):
                parcela_atual = f"{i+1}/{parcelas}" if parcelas > 1 else "1/1"
                novas_linhas.append([
                    datetime.today().strftime('%Y-%m-%d'), cartao, fornecedor, valor, parcelado, parcelas, valor_parcela, comprador, parcela_atual, descricao, link_drive
                ])

            df = pd.concat([df, pd.DataFrame(novas_linhas, columns=colunas_corretas)], ignore_index=True)
            df.to_excel(data_file, index=False)
            for linha in novas_linhas:
                worksheet.append_row(linha)

            if email_opcional:
                dados_email = {
                    "Data": datetime.today().strftime('%Y-%m-%d'),
                    "Cartão": cartao,
                    "Fornecedor": fornecedor,
                    "Valor Total": valor_formatado,
                    "Parcelado": parcelado,
                    "Parcelas": parcelas,
                    "Valor da Parcela": f"R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "Comprador": comprador,
                    "Descrição": descricao
                }
                enviar_email(email_opcional, dados_email, anexo_path=path_comprovante, anexo_nome=comprovante.name)

            st.success("✅ Compra registrada com sucesso!")
            st.session_state["compra_salva"] = True

    if st.session_state.get("compra_salva", False):
        st.markdown("---")
        if st.button("🆕 Nova Compra"):
            st.query_params["new"] = "1"
            st.session_state["compra_salva"] = False
            st.rerun()

elif menu == "Visualizar Compras":
    st.subheader("📊 Visualização de Compras Registradas")
    rows = worksheet.get_all_values()
    headers = rows[0]
    dados = rows[1:]
    df = pd.DataFrame(dados, columns=headers)

    def parse_valor(valor_str):
        try:
            return float(valor_str.replace("R$", "").replace(".", "").replace(",", "."))
        except:
            return None

    df["Valor"] = df["Valor"].apply(parse_valor)
    df["Valor Parcela"] = df["Valor Parcela"].apply(parse_valor)

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_cartao = st.selectbox("Filtrar por Cartão:", options=["Todos"] + sorted(df["Cartão"].dropna().unique().tolist()))
    with col2:
        filtro_comprador = st.selectbox("Filtrar por Comprador:", options=["Todos"] + sorted(df["Comprador"].dropna().unique().tolist()))
    with col3:
        filtro_empresa = st.selectbox("Filtrar por Empresa:", options=["Todos", "Moon Ventures", "Minimal Club", "Hoomy"])

    if filtro_cartao != "Todos":
        df = df[df["Cartão"] == filtro_cartao]
    if filtro_comprador != "Todos":
        df = df[df["Comprador"] == filtro_comprador]
    if filtro_empresa != "Todos":
        cartoes_empresa = [k for k, v in mapa_empresas.items() if v == filtro_empresa]
        df = df[df["Cartão"].isin(cartoes_empresa)]

    df_exibicao = df.copy()
    df_exibicao["Valor"] = df_exibicao["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x else "")
    df_exibicao["Valor Parcela"] = df_exibicao["Valor Parcela"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x else "")

    st.dataframe(df_exibicao, use_container_width=True)

    st.markdown("---")
    st.markdown("### 💳 Gastos por Cartão")
    if not df.empty:
        df_grafico = df.drop_duplicates(subset=["Data", "Cartão", "Fornecedor", "Valor", "Comprador"])
        grafico = df_grafico.groupby("Cartão")["Valor"].sum().reset_index()
        grafico["Total Formatado"] = grafico["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.dataframe(grafico[["Cartão", "Total Formatado"]], use_container_width=True)
        st.bar_chart(data=grafico, x="Cartão", y="Valor")
    else:
        st.info("Nenhum dado para exibir o gráfico.")
=======
        st.error("❌ Por favor, preencha todos os campos obrigatórios.")
>>>>>>> 43b9019 (Atualiza requirements com versões compatíveis)

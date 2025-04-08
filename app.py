import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile

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
# 3. IDs das pastas fixas no Google Drive
# ================================
PASTAS_EMPRESA = {
    "Moon Ventures": "1IdJl9n5l3OG6OudbqJmiJaPrzUskgcjY",
    "Minimal Club": "1bnK4KzsDOZDb0szxEo3H2bplFQcmhen7",
    "Hoomy": "1dyoMhSu-Xmu1B5qvRAcyF9ESEs-DzC7O"
}

# ================================
# 4. Função para upload no Google Drive
# ================================
def upload_to_drive(file, empresa):
    folder_id = PASTAS_EMPRESA.get(empresa)
    if not folder_id:
        st.error(f"❌ ID da pasta não encontrado para a empresa: {empresa}")
        st.stop()

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.name}"

    try:
        gfile = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
        gfile.SetContentFile(tmp_path)
        gfile.Upload()
        os.remove(tmp_path)

        gfile.InsertPermission({
            'type': 'anyone',
            'value': 'anyone',
            'role': 'reader'
        })

        return gfile['alternateLink']

    except Exception as e:
        st.error(f"❌ Erro ao fazer upload para o Drive: {e}")
        st.stop()

# ================================
# 5. Configurações do app
# ================================
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Comprador", "Comprovante"]

if not os.path.exists(data_file):
    df = pd.DataFrame(columns=colunas_corretas)
    df.to_excel(data_file, index=False)

st.set_page_config(page_title="Validador de Compras", layout="centered")
st.title("🧾 Validador de Compras com Cartão de Crédito")
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

        st.success("✅ Compra registrada com sucesso!")
    else:
        st.error("❌ Por favor, preencha todos os campos obrigatórios.")

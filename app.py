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
    "Moon Ventures": "1pVdro4IFN08GEUSaCYDOwvS5dTCNAl41",
    "Minimal Club": "1c_lrNDj3s18j_vlGQCJLWjXYno9JgFrT",
    "Hoomy": "1wBwFFxuEYBnuPyMY13cH0zKEMqZtHDd9"
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
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Comprador", "Descrição da Compra", "Comprovante"]

if not os.path.exists(data_file):
    df = pd.DataFrame(columns=colunas_corretas)
    df.to_excel(data_file, index=False)

st.set_page_config(page_title="Validador de Compras", layout="centered")
st.title("🧾 Validador de Compras com Cartão de Crédito")

menu = st.sidebar.selectbox("📌 Navegação", ["Inserir Compra", "Visualizar Compras"])

# ================================
# 6. Página: Inserção de Dados
# ================================
if menu == "Inserir Compra":
    st.subheader("Inserção de Dados da Compra")

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
        "Inter Minimal": "Minimal Club",
        "Bradesco Minimal": "Minimal Club",
        "Inter Hoomy": "Hoomy",
        "Bradesco Hoomy": "Hoomy",
        "Conta Simples Hoomy": "Hoomy",
        "Conta Simples Moon Ventures": "Moon Ventures"
    }

    # Entradas
    data = datetime.today().strftime('%Y-%m-%d')
    cartão = st.selectbox("💳 Nome do cartão", cartoes)
    fornecedor = st.text_input("📦 Nome do Fornecedor")
    valor = st.number_input("💰 Valor da Compra", min_value=0.0, format="%.2f")
    parcelado = st.radio("💳 Foi parcelado?", ["Não", "Sim"])
    parcelas = st.number_input("📅 Quantidade de Parcelas", min_value=1, max_value=12, value=1) if parcelado == "Sim" else 1
    comprador = st.text_input("👤 Nome do Comprador")
    descricao = st.text_area("📝 Descrição da Compra")
    comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

    # Botão de salvar
    if st.button("✅ Salvar Compra"):
        erros = []
        if not fornecedor:
            erros.append("Fornecedor não informado.")
        if valor <= 0:
            erros.append("Valor deve ser maior que zero.")
        if not comprador:
            erros.append("Nome do comprador não informado.")
        if not cartão:
            erros.append("Cartão não selecionado.")
        if not descricao:
            erros.append("Descrição da compra não informada.")
        if not comprovante:
            erros.append("Comprovante não anexado.")

        if erros:
            st.error("\n".join(["❌ " + erro for erro in erros]))
        else:
            empresa = mapa_empresas.get(cartão, "Outros")
            link_drive = upload_to_drive(comprovante, empresa)

            df = pd.read_excel(data_file)
            if list(df.columns) != colunas_corretas:
                df = df.reindex(columns=colunas_corretas)

            nova_linha = pd.DataFrame(
                [[data, cartão, fornecedor, valor, parcelado, parcelas, comprador, descricao, link_drive]],
                columns=colunas_corretas
            )
            df = pd.concat([df, nova_linha], ignore_index=True)
            df.to_excel(data_file, index=False)

            worksheet.append_row([data, cartão, fornecedor, valor, parcelado, parcelas, comprador, descricao, link_drive])

            st.success("✅ Compra registrada com sucesso!")

# ================================
# 7. Página: Visualização de Compras (direto do Google Sheets)
# ================================
elif menu == "Visualizar Compras":
    st.subheader("📊 Visualização de Compras Registradas")

    rows = worksheet.get_all_records()
    df = pd.DataFrame(rows)

    col1, col2 = st.columns(2)
    with col1:
        filtro_cartao = st.selectbox("Filtrar por Cartão:", options=["Todos"] + sorted(df["Cartão"].dropna().unique().tolist()))
    with col2:
        filtro_comprador = st.selectbox("Filtrar por Comprador:", options=["Todos"] + sorted(df["Comprador"].dropna().unique().tolist()))

    if filtro_cartao != "Todos":
        df = df[df["Cartão"] == filtro_cartao]
    if filtro_comprador != "Todos":
        df = df[df["Comprador"] == filtro_comprador]

    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.markdown("### 💳 Gastos por Cartão")
    if not df.empty:
        grafico = df.groupby("Cartão")["Valor"].sum().reset_index()
        st.bar_chart(data=grafico, x="Cartão", y="Valor")
    else:
        st.info("Nenhum dado para exibir o gráfico.")

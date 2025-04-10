import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
import plotly.express as px

# ================================ Autenticação ================================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file"
]
credentials_dict = st.secrets["google_service_account"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
gc = gspread.authorize(credentials)
gauth = GoogleAuth()
gauth.credentials = credentials
drive = GoogleDrive(gauth)

# ================================ Google Sheets ================================
SHEET_ID = "1CcrV5Gs3LwrLXgjLBgk2M02SAnDVJGuHhqY_pi56Mnw"
worksheet = gc.open_by_key(SHEET_ID).sheet1

# ================================ Pastas Google Drive ================================
PASTAS_EMPRESA = {
    "Moon Ventures": "1pVdro4IFN08GEUSaCYDOwvS5dTCNAl41",
    "Minimal Club": "1c_lrNDj3s18j_vlGQCJLWjXYno9JgFrT",
    "Hoomy": "1wBwFFxuEYBnuPyMY13cH0zKEMqZtHDd9"
}

# ================================ Mapeamento Cartão/Empresa ================================
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

# ================================ Upload para Google Drive ================================
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
        gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
        return gfile['alternateLink']
    except Exception as e:
        st.error(f"❌ Erro ao fazer upload para o Drive: {e}")
        st.stop()

# ================================ Configurações ================================
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante"]
if not os.path.exists(data_file):
    pd.DataFrame(columns=colunas_corretas).to_excel(data_file, index=False)

st.set_page_config(page_title="Validador de Compras", layout="centered")
st.title("🧾 Validador de Compras com Cartão de Crédito")
menu = st.sidebar.selectbox("📌 Navegação", ["Inserir Compra", "Visualizar Compras"])

# ================================ Página: Inserção de Dados ================================
if menu == "Inserir Compra":
    st.subheader("Inserção de Dados da Compra")

    with st.form("form_compras", clear_on_submit=True):
        data = datetime.today().strftime('%Y-%m-%d')
        cartao = st.selectbox("💳 Nome do cartão", cartoes)
        fornecedor = st.text_input("📦 Nome do Fornecedor")

        valor_str = st.text_input("💰 Valor da Compra (total)", placeholder="Ex: 399,80")
        try:
            valor = float(valor_str.replace("R$", "").replace(".", "").replace(",", "."))
        except:
            valor = 0.0
        st.markdown(f"🔎 Valor interpretado: R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        parcelado = st.radio("💳 Foi parcelado?", ["Não", "Sim"], horizontal=True)
        parcelas = 1
        if parcelado == "Sim":
            parcelas = st.number_input("📅 Quantidade de Parcelas", min_value=1, max_value=12, value=1)

        valor_parcela = valor / parcelas if parcelas > 0 else 0.0
        st.markdown(f"💵 **Valor de cada parcela:** R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        comprador = st.text_input("👤 Nome do Comprador")
        descricao = st.text_area("📝 Descrição da Compra")
        comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

        submitted = st.form_submit_button("✅ Salvar Compra")

        if submitted:
            erros = []
            if not fornecedor: erros.append("Fornecedor não informado.")
            if valor <= 0: erros.append("Valor deve ser maior que zero.")
            if not comprador: erros.append("Nome do comprador não informado.")
            if not cartao: erros.append("Cartão não selecionado.")
            if not descricao: erros.append("Descrição da compra não informada.")
            if not comprovante: erros.append("Comprovante não anexado.")

            if erros:
                st.error("\n".join(["❌ " + erro for erro in erros]))
            else:
                empresa = mapa_empresas.get(cartao, "Outros")
                link_drive = upload_to_drive(comprovante, empresa)
                df = pd.read_excel(data_file)
                if list(df.columns) != colunas_corretas:
                    df = df.reindex(columns=colunas_corretas)

                novas_linhas = []
                for i in range(parcelas):
                    parcela_atual = f"{i+1}/{parcelas}" if parcelas > 1 else "1/1"
                    novas_linhas.append([
                        data, cartao, fornecedor, valor, parcelado, parcelas, valor_parcela,
                        comprador, parcela_atual, descricao, link_drive
                    ])

                df = pd.concat([df, pd.DataFrame(novas_linhas, columns=colunas_corretas)], ignore_index=True)
                df.to_excel(data_file, index=False)
                for linha in novas_linhas:
                    worksheet.append_row(linha)
                st.success("✅ Compra registrada com sucesso!")

# ================================ Página: Visualização de Compras ================================
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
        filtro_cartao = st.selectbox("Filtrar por Cartão:", ["Todos"] + sorted(df["Cartão"].dropna().unique().tolist()))
    with col2:
        filtro_comprador = st.selectbox("Filtrar por Comprador:", ["Todos"] + sorted(df["Comprador"].dropna().unique().tolist()))
    with col3:
        filtro_empresa = st.selectbox("Filtrar por Empresa:", ["Todos", "Moon Ventures", "Minimal Club", "Hoomy"])

    if filtro_cartao != "Todos":
        df = df[df["Cartão"] == filtro_cartao]
    if filtro_comprador != "Todos":
        df = df[df["Comprador"] == filtro_comprador]
    if filtro_empresa != "Todos":
        cartoes_empresa = [k for k, v in mapa_empresas.items() if v == filtro_empresa]
        df = df[df["Cartão"].isin(cartoes_empresa)]

    df_exibicao = df.copy()
    df_exibicao["Valor"] = df_exibicao["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "")
    df_exibicao["Valor Parcela"] = df_exibicao["Valor Parcela"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "")
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

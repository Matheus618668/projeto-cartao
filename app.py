import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Autenticação com Google Sheets via secrets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = st.secrets["google_service_account"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
gc = gspread.authorize(credentials)

# Planilha no Google Sheets
SHEET_ID = "1CcrV5Gs3LwrLXgjLBgk2M02SAnDVJGuHhqY_pi56Mnw"
worksheet = gc.open_by_key(SHEET_ID).sheet1

# Caminhos de rede
comprovante_base = r"G:\Drives compartilhados\Moon Ventures - Admin Fin\Comprovantes"

# Verifica se a pasta principal existe
if not os.path.exists(comprovante_base):
    st.error("❌ Pasta de comprovantes não encontrada. Verifique se o disco G: está conectado.")
    st.stop()

# Caminho da planilha local
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)

# Colunas esperadas
colunas_corretas = ["Data", "Cartão", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Comprador", "Comprovante"]

# Criar planilha local se não existir
if not os.path.exists(data_file):
    df = pd.DataFrame(columns=colunas_corretas)
    df.to_excel(data_file, index=False)

# Configuração da interface
st.set_page_config(page_title="Validador de Compras", layout="centered")
st.title("🧾 Validador de Compras com Cartão de Crédito")
st.subheader("Inserção de Dados da Compra")

# Lista de cartões
cartoes = [
    "Inter Moon Ventures",
    "Inter Minimal",
    "Inter Hoomy",
    "Bradesco Minimal",
    "Bradesco Hoomy",
    "Bradesco Moon Ventures"
]

# Mapeamento cartão → empresa
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
        # Determina a subpasta da empresa
        empresa = mapa_empresas.get(cartão, "Outros")
        pasta_empresa = os.path.join(comprovante_base, empresa)

        # Verifica se a subpasta existe
        if not os.path.exists(pasta_empresa):
            st.error(f"❌ A subpasta '{empresa}' não foi encontrada em: {pasta_empresa}")
            st.stop()

        # Salvar comprovante
        comprovante_path = ""
        filename = "Nenhum"
        if comprovante:
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{comprovante.name}"
            comprovante_path = os.path.join(pasta_empresa, filename)

            try:
                with open(comprovante_path, "wb") as f:
                    f.write(comprovante.read())
                st.success(f"📁 Comprovante salvo em: {comprovante_path}")
            except Exception as e:
                st.error(f"❌ Erro ao salvar comprovante: {e}")
                st.stop()

        # Atualizar planilha local
        df = pd.read_excel(data_file)
        if list(df.columns) != colunas_corretas:
            df = df.reindex(columns=colunas_corretas)

        nova_linha = pd.DataFrame(
            [[data, cartão, fornecedor, valor, parcelado, parcelas, comprador, comprovante_path]],
            columns=colunas_corretas
        )
        df = pd.concat([df, nova_linha], ignore_index=True)
        df.to_excel(data_file, index=False)

        # Enviar ao Google Sheets
        worksheet.append_row([data, cartão, fornecedor, valor, parcelado, parcelas, comprador, filename])

        st.success("✅ Compra registrada com sucesso!")
    else:
        st.error("❌ Por favor, preencha todos os campos obrigatórios.")

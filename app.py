import streamlit as st

# ✅ CONFIGURAÇÃO DA PÁGINA — PRIMEIRO COMANDO DO STREAMLIT
st.set_page_config(page_title="Validador de Compras", layout="centered")

# Agora sim pode seguir o resto
import pandas as pd
import os
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

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
spreadsheet = gc.open_by_key(SHEET_ID)

# ================================
# 3. IDs das pastas fixas no Google Drive
# ================================
PASTAS_EMPRESA = {
    "Moon Ventures": "1pVdro4IFN08GEUSaCYDOwvS5dTCNAl41",
    "Minimal Club": "1c_lrNDj3s18j_vlGQCJLWjXYno9JgFrT",
    "Hoomy": "1wBwFFxuEYBnuPyMY13cH0zKEMqZtHDd9"
}

# ================================
# 4. Lista das empresas
# ================================
empresas = [
    "Minimal Club",
    "Hoomy", 
    "Moon Ventures"
]

# ================================
# 5. Função para obter a aba da empresa
# ================================
def get_worksheet_by_empresa(empresa):
    try:
        # Primeiro tenta encontrar a aba pelo nome exato
        return spreadsheet.worksheet(empresa)
    except gspread.exceptions.WorksheetNotFound:
        try:
            # Se não encontrar, lista todas as abas para verificar se existe algo similar
            worksheets = spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in worksheets]
            st.info(f"Abas disponíveis: {worksheet_names}")
            
            # Tenta encontrar uma aba com nome similar (ignorando case)
            for ws in worksheets:
                if ws.title.lower() == empresa.lower():
                    return ws
            
            # Se chegou até aqui, a aba realmente não existe
            # Vamos usar a primeira aba (Sheet1) e adicionar os dados lá
            # com identificação da empresa
            st.warning(f"Aba '{empresa}' não encontrada. Usando a primeira aba disponível.")
            return worksheets[0]
            
        except Exception as e:
            st.error(f"Erro ao acessar as abas da planilha: {e}")
            # Como último recurso, usa a primeira aba
            return spreadsheet.sheet1
    except Exception as e:
        st.error(f"Erro inesperado ao acessar a aba '{empresa}': {e}")
        return spreadsheet.sheet1

# ================================
# 6. Função para upload no Google Drive
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
# 7. Envio de Email com Anexo
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
# 8. App Principal
# ================================
data_file = "data/compras.xlsx"
os.makedirs("data", exist_ok=True)
colunas_corretas = ["Data", "Empresa", "4 Últimos Dígitos", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante", "Data da Compra"]
if not os.path.exists(data_file):
    pd.DataFrame(columns=colunas_corretas).to_excel(data_file, index=False)

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
        "ultimos_digitos": "",
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

    empresa = st.selectbox("🏢 Empresa", empresas)
    ultimos_digitos = st.text_input("💳 4 Últimos Dígitos do Cartão", max_chars=4, placeholder="Ex: 1234", key="ultimos_digitos")
    data_compra = st.date_input("📅 Data da Compra", value=date.today())
    fornecedor = st.text_input("📦 Nome do Fornecedor", key="fornecedor")
    valor_str = st.text_input("💰 Valor da Compra (total)", placeholder="Ex: 399,80", key="valor_str")

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
        parcelas = 1

    valor_parcela = valor / parcelas if parcelas > 0 else 0.0
    st.markdown(f"💵 **Valor de cada parcela:** R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    comprador = st.text_input("👤 Nome do Comprador", key="comprador")
    email_opcional = st.text_input("📧 E-mail (opcional)", key="email_opcional")
    descricao = st.text_area("📝 Descrição da Compra", key="descricao")
    comprovante = st.file_uploader("📁 Anexar Comprovante", type=["pdf", "jpg", "png"])

    if st.button("✅ Salvar Compra"):
        erros = []
        if not empresa: erros.append("Empresa não selecionada.")
        if len(ultimos_digitos) != 4 or not ultimos_digitos.isdigit(): erros.append("4 últimos dígitos do cartão devem conter exatamente 4 números.")
        if not fornecedor: erros.append("Fornecedor não informado.")
        if valor <= 0: erros.append("Valor deve ser maior que zero.")
        if not comprador: erros.append("Nome do comprador não informado.")
        if not descricao: erros.append("Descrição da compra não informada.")
        if not comprovante: erros.append("Comprovante não anexado.")

        if erros:
            st.error("\n".join(["❌ " + erro for erro in erros]))
        else:
            link_drive, path_comprovante = upload_to_drive(comprovante, empresa)
            
            # Obter a aba específica da empresa
            worksheet = get_worksheet_by_empresa(empresa)
            
            # Verificar se é a primeira linha (cabeçalho) e adicionar se necessário
            try:
                headers_existentes = worksheet.row_values(1)
                headers_esperados = ["Data", "Empresa", "4 Últimos Dígitos", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante", "Data da Compra"]
                
                # Se não há cabeçalhos ou são diferentes, adiciona/atualiza
                if not headers_existentes or headers_existentes != headers_esperados:
                    if not headers_existentes:  # Se a planilha está vazia
                        worksheet.append_row(headers_esperados)
                    else:  # Se há dados mas cabeçalhos diferentes, adiciona uma linha em branco e depois os novos cabeçalhos
                        worksheet.append_row([])  # linha em branco
                        worksheet.append_row(headers_esperados)
            except Exception as e:
                st.warning(f"Aviso ao verificar cabeçalhos: {e}")
                # Continua mesmo se houver erro nos cabeçalhos

            df = pd.read_excel(data_file)
            if list(df.columns) != colunas_corretas:
                df = df.reindex(columns=colunas_corretas)

            novas_linhas = []
            for i in range(parcelas):
                parcela_atual = f"{i+1}/{parcelas}" if parcelas > 1 else "1/1"
                linha = [
                    datetime.today().strftime('%Y-%m-%d'), 
                    empresa, 
                    ultimos_digitos, 
                    fornecedor, 
                    valor, 
                    parcelado, 
                    parcelas, 
                    valor_parcela, 
                    comprador, 
                    parcela_atual, 
                    descricao, 
                    link_drive,
                    data_compra.strftime('%Y-%m-%d')
                ]
                novas_linhas.append(linha)

            df = pd.concat([df, pd.DataFrame(novas_linhas, columns=colunas_corretas)], ignore_index=True)
            df.to_excel(data_file, index=False)
            
            # Adicionar na aba específica da empresa
            for linha in novas_linhas:
                worksheet.append_row(linha)

            if email_opcional:
                dados_email = {
                    "Data": datetime.today().strftime('%Y-%m-%d'),
                    "Empresa": empresa,
                    "4 Últimos Dígitos": ultimos_digitos,
                    "Fornecedor": fornecedor,
                    "Valor Total": valor_formatado,
                    "Parcelado": parcelado,
                    "Parcelas": parcelas,
                    "Valor da Parcela": f"R$ {valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "Comprador": comprador,
                    "Descrição": descricao,
                    "Data da Compra": data_compra.strftime('%d/%m/%Y')
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
    
    # Primeiro, vamos ver quais abas estão disponíveis
    try:
        worksheets = spreadsheet.worksheets()
        abas_disponiveis = [ws.title for ws in worksheets]
        st.info(f"Abas disponíveis na planilha: {', '.join(abas_disponiveis)}")
        
        # Permite selecionar entre as empresas ou as abas disponíveis
        opcoes_visualizacao = empresas + [aba for aba in abas_disponiveis if aba not in empresas]
        empresa_selecionada = st.selectbox("🏢 Selecione a Empresa/Aba", opcoes_visualizacao)
        
    except Exception as e:
        st.error(f"Erro ao listar abas: {e}")
        empresa_selecionada = st.selectbox("🏢 Selecione a Empresa", empresas)
    
    try:
        worksheet = get_worksheet_by_empresa(empresa_selecionada)
        rows = worksheet.get_all_values()
        
        if len(rows) > 0:  # Se há dados
            headers = rows[0] if rows[0] else ["Data", "Empresa", "4 Últimos Dígitos", "Fornecedor", "Valor", "Parcelado", "Parcelas", "Valor Parcela", "Comprador", "Parcela", "Descrição", "Comprovante", "Data da Compra"]
            dados = rows[1:] if len(rows) > 1 else []
            
            if dados:  # Se há dados além do cabeçalho
                # Garante que temos o número correto de colunas
                dados_limpos = []
                for linha in dados:
                    if len(linha) < len(headers):
                        linha.extend([''] * (len(headers) - len(linha)))
                    dados_limpos.append(linha[:len(headers)])
                
                df = pd.DataFrame(dados_limpos, columns=headers)

                def parse_valor(valor_str):
                    try:
                        return float(str(valor_str).replace("R$", "").replace(".", "").replace(",", "."))
                    except:
                        return 0.0

                if "Valor" in df.columns:
                    df["Valor"] = df["Valor"].apply(parse_valor)
                if "Valor Parcela" in df.columns:
                    df["Valor Parcela"] = df["Valor Parcela"].apply(parse_valor)

                col1, col2 = st.columns(2)
                with col1:
                    if "Comprador" in df.columns:
                        filtro_comprador = st.selectbox("Filtrar por Comprador:", options=["Todos"] + sorted(df["Comprador"].dropna().unique().tolist()))
                    else:
                        filtro_comprador = "Todos"
                with col2:
                    if "4 Últimos Dígitos" in df.columns:
                        filtro_digitos = st.selectbox("Filtrar por 4 Últimos Dígitos:", options=["Todos"] + sorted(df["4 Últimos Dígitos"].dropna().unique().tolist()))
                    else:
                        filtro_digitos = "Todos"

                if filtro_comprador != "Todos" and "Comprador" in df.columns:
                    df = df[df["Comprador"] == filtro_comprador]
                if filtro_digitos != "Todos" and "4 Últimos Dígitos" in df.columns:
                    df = df[df["4 Últimos Dígitos"] == filtro_digitos]

                df_exibicao = df.copy()
                if "Valor" in df_exibicao.columns:
                    df_exibicao["Valor"] = df_exibicao["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x else "")
                if "Valor Parcela" in df_exibicao.columns:
                    df_exibicao["Valor Parcela"] = df_exibicao["Valor Parcela"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x else "")

                st.dataframe(df_exibicao, use_container_width=True)

                st.markdown("---")
                st.markdown("### 💳 Gastos por Cartão (4 últimos dígitos)")
                if not df.empty and "Valor" in df.columns and "4 Últimos Dígitos" in df.columns:
                    colunas_duplicacao = ["Data", "4 Últimos Dígitos", "Fornecedor", "Valor", "Comprador"]
                    colunas_existentes = [col for col in colunas_duplicacao if col in df.columns]
                    
                    if colunas_existentes:
                        df_grafico = df.drop_duplicates(subset=colunas_existentes)
                        grafico = df_grafico.groupby("4 Últimos Dígitos")["Valor"].sum().reset_index()
                        grafico["Total Formatado"] = grafico["Valor"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

                        st.dataframe(grafico[["4 Últimos Dígitos", "Total Formatado"]], use_container_width=True)
                        st.bar_chart(data=grafico, x="4 Últimos Dígitos", y="Valor")
                    else:
                        st.info("Colunas necessárias para o gráfico não encontradas.")
                else:
                    st.info("Nenhum dado para exibir o gráfico.")
            else:
                st.info(f"Nenhuma compra registrada para {empresa_selecionada}.")
        else:
            st.info(f"A aba {empresa_selecionada} está vazia.")
            
    except Exception as e:
        st.error(f"Erro ao carregar dados de {empresa_selecionada}: {e}")
        st.info("Tentando usar a primeira aba disponível...")
        try:
            worksheet = spreadsheet.sheet1
            st.info("Usando a primeira aba da planilha.")
        except Exception as e2:
            st.error(f"Não foi possível acessar nenhuma aba: {e2}")

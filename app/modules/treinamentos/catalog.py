"""Catálogo fechado: nunca resolva caminhos recebidos do navegador."""

from pathlib import Path

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "treinamentos"

MATERIALS = {
    "guia-geral": ("manuais/guia-do-sistema.pdf", "application/pdf"),
    "manual-liraa": ("manuais/tutorial-liraa.pdf", "application/pdf"),
    "manual-sinan": ("manuais/tutorial-sinan.pdf", "application/pdf"),
    "manual-mapa": ("manuais/tutorial-mapa-de-risco.pdf", "application/pdf"),
    "manual-publicacoes": ("manuais/tutorial-compartilhamento.pdf", "application/pdf"),
    "csv-territorio": ("testes/01_Cadastro_territorial_Centro_Pesqueira_poligonos_DEMO.csv", "text/csv"),
    "csv-amostra": ("testes/02_Amostra_Centro_Pesqueira_agente_DEMO.csv", "text/csv"),
    "csv-visitas": ("testes/03_Visitas_LIRAa_Centro_Pesqueira_coordenadas_reais_DEMO.csv", "text/csv"),
    "csv-sinan": ("testes/04_SINAN_Dengue_2026_Pesqueira_DEMO.csv", "text/csv"),
    "imagem-acao": ("testes/05_Imagem_Acao_Demonstrativa.jpg", "image/jpeg"),
    "texto-acao": ("testes/06_Texto_Acao_Demonstrativa.txt", "text/plain"),
    "kit-testes": ("kit-testes-pesqueira-demo.zip", "application/zip"),
}

SECTIONS = (
    dict(id="liraa", title="LIRAa e focal", icon="bi-clipboard-check",
         description="Planejamento, visitas e indicadores.", manual="manual-liraa",
         endpoint="main.vigilancia_planejamento", flag="VIGILANCIA_IMPORT_ENABLED",
         files=(
             ("csv-territorio", "01 · Cadastro territorial", "Importe em Planejamento → Cadastro territorial."),
             ("csv-amostra", "02 · Amostra do levantamento", "Abra o levantamento em rascunho e importe a amostra."),
             ("csv-visitas", "03 · Visitas realizadas", "Após liberar o levantamento, importe as visitas e selecione o destino."),
         )),
    dict(id="sinan", title="SINAN", icon="bi-activity",
         description="Importação e consulta de notificações.", manual="manual-sinan",
         endpoint="main.vigilancia_sinan", flag="SINAN_ENABLED",
         files=(("csv-sinan", "04 · Casos fictícios de dengue", "SINAN → Importar dados → Arquivo CSV. Pesqueira, dengue, 2026."),)),
    dict(id="mapa", title="Mapa de risco", icon="bi-map",
         description="Confira o território e interprete os resultados.", manual="manual-mapa",
         endpoint="main.vigilancia_risco", flag="VIGILANCIA_IMPORT_ENABLED", files=()),
    dict(id="publicacoes", title="Publicações e compartilhamento", icon="bi-megaphone",
         description="Prepare, revise e divulgue uma ação.", manual="manual-publicacoes",
         endpoint="main.acoes_listar", flag="ACOES_PUBLICAS_ENABLED",
         files=(
             ("imagem-acao", "05 · Imagem de demonstração", "Adicione ao rascunho da ação."),
             ("texto-acao", "06 · Texto para a publicação", "Use os campos de exemplo para preencher o rascunho."),
         )),
)

# O catálogo é explícito: publicar um arquivo em output/ não o torna acessível.
# Cada entrada corresponde a uma cópia conferida junto da aplicação.
GUIDE_GROUPS = (
    dict(id="apresentacoes", title="Apresentações das atualizações", icon="bi-easel",
         documents=(
             ("atualizacoes-liraa-mapas", "LIRAa e mapas de risco", 6,
              "01_Atualizacoes_LIRAa_e_Mapas_de_Risco_20261021.pdf"),
             ("atualizacoes-acoes-publicas", "Ações públicas e compartilhamento", 4,
              "02_Atualizacoes_Acoes_Publicas_e_Compartilhamento_20261021.pdf"),
             ("atualizacoes-treinamentos", "Central de Treinamentos", 3,
              "03_Atualizacoes_Central_de_Treinamentos_20261021.pdf"),
         )),
    dict(id="cidadao", title="Cidadão e atendimento", icon="bi-people",
         documents=(
             ("guia-triagem-denuncias", "Triagem de denúncias", 15,
              "manual-administrativo-triagem-denuncias.pdf"),
             ("guia-suspeitas-adoecimento", "Suspeitas de adoecimento", 10,
              "guia-suspeitas-adoecimento-ija-system-2026-10-17.pdf"),
             ("guia-assistente-cidadao", "Assistente com IA do Portal do Cidadão", 6,
              "guia-chatbot-portal-cidadao.pdf"),
             ("guia-contatos-municipais", "Contatos municipais e assistente Azul", 8,
              "guia-contatos-prefeituras-azul-ija-system-2026-10-17.pdf"),
         )),
    dict(id="relatorios-documentos", title="Relatórios e documentos", icon="bi-file-earmark-text",
         documents=(
             ("guia-consultas-personalizadas", "Consultas personalizadas", 9,
              "guia-consultas-personalizadas-ija-system-2026-10-17.pdf"),
             ("guia-documentos-prefeitura", "Marca d’água nos documentos da prefeitura", 3,
              "guia-marca-dagua-prefeituras-ija.pdf"),
         )),
    dict(id="acesso-edicao", title="Acesso e edição", icon="bi-shield-lock",
         documents=(
             ("guia-protecao-login", "Proteção de login", 3,
              "guia-protecao-login-ija.pdf"),
             ("guia-expiracao-senhas", "Expiração de senhas", 3,
              "guia-expiracao-senhas-ija.pdf"),
             ("guia-edicao-protegida", "Edição protegida", 3,
              "guia-edicao-protegida-ija.pdf"),
         )),
    dict(id="vigilancia-complementar", title="Vigilância · guias complementares", icon="bi-journal-medical",
         documents=(
             ("guia-novas-funcionalidades", "Visão geral de SINAN, LIRAa e ações realizadas", 12,
              "IJA-System-Novas-Funcionalidades.pdf"),
             ("guia-sinan-implementacao", "SINAN: implementação e funcionamento", 8,
              "tela de dados SINAN.pdf"),
             ("guia-liraa-iip-risco", "LIRAa, IIP e análise espacial", 5,
              "guia-explicativo-liraa-iip-mapa-de-risco.pdf"),
             ("guia-liraa-csv-manual", "LIRAa: importação e registro manual", 4,
              "IJA-System-Tutorial-LIRAa-CSV-e-Registro-Manual.pdf"),
             ("guia-atualizacoes-vigilancia", "Relatório integrado de vigilância e compartilhamento", 5,
              "IJA-System-Atualizacoes-LIRAa-Mapa-de-Risco-e-Compartilhamento.pdf"),
         )),
)

for group in GUIDE_GROUPS:
    for material_id, _title, _pages, filename in group["documents"]:
        MATERIALS[material_id] = (f"manuais/biblioteca/{filename}", "application/pdf")


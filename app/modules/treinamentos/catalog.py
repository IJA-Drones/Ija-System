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


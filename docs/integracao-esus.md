# Integração e-SUS APS (PEC)

Atende ao TR 4.6 / 4.6.1 (interação com sistemas do Ministério da Saúde, de forma síncrona ou
assíncrona, com uma funcionalidade única por processo de negócio). Traz do PEC do município as
visitas dos ACS/ACE registradas na **Ficha de Visita Domiciliar e Territorial** (e-SUS Território)
e o **cadastro de domicílios**, guarda nas tabelas do IJA e expõe uma API para terceiros.

Código: `app/modules/integracoes/esus.py` (conector, simulador, sincronização) e
`app/modules/integracoes/esus_routes.py` (telas e API). Migração `4956d97d273e`.

## Telas

| Tela | Endereço | Quem |
|---|---|---|
| e-SUS APS: status, execuções, totais, visitas com filtros, botões de sincronização | `/integracoes/esus` | coordenação de campo (`prefeitura.vigilancia.consultar`; sincronizar exige `prefeitura.vigilancia.editar`) |
| Configuração (modo, conexão, conjunto simulado, token da API) | `/integracoes/esus/configuracao` | só admin global/dev |
| Seção "Visitas do e-SUS (ACS/ACE)" em Agentes em campo | `/vigilancia/agentes` | igual à tela de agentes |

O card **e-SUS APS (PEC)** aparece na Central de Vigilância.

## Modos de conexão

Os dois modos executam **a mesma consulta SQL** (`SQL_VISITAS` e `SQL_DOMICILIOS`), sobre as tabelas
do PEC: `tb_fat_visita_domiciliar`, `tb_fat_cad_domiciliar`, `tb_cds_ficha_visita_domiciliar`
(data/hora da ficha) e as dimensões `tb_dim_tempo`, `tb_dim_profissional`, `tb_dim_cbo`,
`tb_dim_equipe`, `tb_dim_unidade_saude`, `tb_dim_municipio`, `tb_dim_turno`,
`tb_dim_desfecho_visita` e `tb_dim_tipo_imovel`. Filtros: CBO 515105 (ACS) e 515140 (ACE) e o
código IBGE do município.

* **Banco do PEC (PostgreSQL)**: host, porta, base, usuário e senha (cifrada com a chave do
  sistema, como a senha do SMTP). A sessão abre com `default_transaction_read_only=on` e
  `statement_timeout` de 2 min. Recomenda-se um usuário do PostgreSQL só com `SELECT`.
* **Ambiente simulado**: o botão "Gerar conjunto simulado" recria o schema `esus_sim` do banco
  local com dados fictícios no layout do PEC: profissionais ACS/ACE com CNS fictício, equipes (INE),
  unidades (CNES simulados), microáreas, domicílios com coordenadas em torno do centro informado
  (padrão: Pesqueira) e visitas em dias úteis com data/hora, turno, desfecho
  (realizada/recusada/ausente), motivos (`st_mot_vis_*`, incluindo controle de ambientes/vetores
  e as ações `st_ctrl_amb_vet_*`) e geolocalização. Padrão: 6 ACS, 2 ACE, 300 domicílios e
  1.500 visitas nos últimos 30 dias.

## Sincronização

Uma função por processo de negócio: `sincronizar(prefeitura_id, "domicilios" | "visitas", forma)`.

* **Síncrona**: botão "Sincronizar agora".
* **Assíncrona**: botão "Sincronizar em segundo plano" (thread) e agendamento opcional
  ("Sincronização automática (min)", verificado a cada minuto).

Cada execução fica em `integracao_esus_execucoes` (forma, modo, status, lidos, novos,
atualizados, removidos, erros e mensagem). As visitas consideram os últimos 90 dias: o que
sumiu do PEC nessa janela é removido. Registros incompletos são ignorados e contados em `erros`.
Uma falha (conexão, tabela ausente) registra `falhou` sem gravar nada parcial.

Dados gravados: `integracao_esus_visitas` (profissional, CNS, CBO/categoria, equipe/INE,
unidade/CNES, microárea, domicílio, data, hora, turno, desfecho, motivos, `motivo_aedes`,
lat/lng) e `integracao_esus_domicilios`.

## API para terceiros

O token é gerado na tela de configuração e aparece uma única vez. Só o hash SHA-256 fica
guardado. Gerar um novo token substitui o anterior, e "Revogar" desativa o acesso. O token só
dá acesso aos dados da prefeitura em que foi gerado e deixa de valer se a integração for
desativada.

### `GET /api/integracoes/esus/status`

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:5055/api/integracoes/esus/status
```

```json
{"prefeitura_id": 1, "modo": "simulado", "ativo": true, "intervalo_min": 0, "em_execucao": false,
 "totais": {"visitas": 1500, "profissionais": 8, "domicilios": 300,
            "primeira_visita": "2026-09-22", "ultima_visita": "2026-10-21"},
 "ultima_sincronizacao": {"domicilios": "2026-10-22T23:18:51", "visitas": "2026-10-22T23:18:52"},
 "execucoes": [{"id": 6, "processo": "visitas", "forma": "sincrona", "modo": "simulado", "status": "concluida",
                "lidos": 1500, "inseridos": 1500, "atualizados": 0, "removidos": 0, "erros": 0, "...": "..."}]}
```

### `GET /api/integracoes/esus/visitas`

Parâmetros (todos opcionais):

| Parâmetro | Descrição |
|---|---|
| `de`, `ate` | período AAAA-MM-DD (padrão: últimos 30 dias até hoje; máximo 366 dias) |
| `profissional` | CNS exato ou parte do nome |
| `categoria` | `ACS` ou `ACE` |
| `desfecho` | `realizada`, `recusada`, `ausente` ou `nao_informado` |
| `microarea` | código da microárea |
| `aedes` | `1` = só visitas com motivo controle de vetores/Aedes |
| `page`, `per_page` | paginação (padrão 1 e 100; `per_page` máximo 500) |

```bash
curl -s -G -H "Authorization: Bearer $TOKEN" http://localhost:5055/api/integracoes/esus/visitas \
  --data-urlencode "de=2026-10-01" --data-urlencode "ate=2026-10-22" \
  --data-urlencode "profissional=Edneide" --data-urlencode "per_page=2"
```

```json
{"prefeitura_id": 1, "de": "2026-10-01", "ate": "2026-10-22", "page": 1, "per_page": 2, "total": 133, "pages": 67,
 "items": [{"id": "1434", "ficha_uuid": "9940526-2f30…", "data": "2026-10-21", "hora": "11:47", "turno": "Manhã",
            "profissional": {"nome": "EDNEIDE GOMES PEREIRA", "cns": "735941138280818", "cbo": "515140", "categoria": "ACE"},
            "equipe": {"ine": "9962765934", "nome": "ESF Centro 1 (simulada)"},
            "unidade": {"cnes": "9940526", "nome": "USF Centro (simulada)"},
            "microarea": "04", "domicilio_uuid": "9950288-7a72…", "tipo_imovel": "Domicílio",
            "desfecho": "realizada", "motivos": ["Controle de ambientes/vetores (Aedes)", "Orientação/prevenção"],
            "motivo_aedes": true, "latitude": -8.354248, "longitude": -36.706941, "origem": "simulado"}]}
```

Visitas de ACE com motivo Aedes:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:5055/api/integracoes/esus/visitas?categoria=ACE&aedes=1&per_page=500&page=1"
```

Respostas de erro: sem token ou com token inválido, `401` com `WWW-Authenticate: Bearer`. Com
parâmetro de data inválido, `400` em JSON.

## Testes

```bash
DATABASE_URL=sqlite:///:memory: .venv/bin/python -m pytest tests/test_integracao_esus.py -q
```

No SQLite o "PEC simulado" fica no próprio banco de teste. Os testes cobrem a geração, a
sincronização síncrona, em segundo plano e agendada, o painel de produção, a API com e sem
token e o registro de falha de conexão ao PEC.

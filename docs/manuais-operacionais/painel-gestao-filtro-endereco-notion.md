# Painel de Gestão: novo filtro por endereço

## Objetivo

Foi adicionado um novo filtro por **endereço** no **Painel de Gestão**, para facilitar a localização de solicitações com base no local da operação.

Esse filtro ajuda principalmente quando a equipe precisa encontrar rapidamente um pedido por:

- rua
- número
- complemento
- bairro
- cidade
- UF
- CEP

---

## O que mudou

No bloco **Filtros de Busca** do Painel de Gestão, agora existe o campo:

**Endereço**

O usuário pode digitar um trecho do endereço e o sistema irá retornar as solicitações compatíveis.

Exemplos de busca:

- `Rua Francisco Mendes`
- `283`
- `Socorro`
- `04766050`
- `São Paulo`
- `Francisco Mendes 283`

---

## Como o filtro funciona

O filtro por endereço faz uma busca textual parcial nos principais campos do endereço da solicitação.

Campos considerados na busca:

- `logradouro`
- `numero`
- `complemento`
- `bairro`
- `cidade`
- `uf`
- `cep`

Na prática, isso significa que não é necessário digitar o endereço completo.
Basta informar uma parte relevante para localizar o registro.

---

## Regras de comportamento

- A busca aceita endereço completo ou parcial.
- Se o usuário digitar mais de uma palavra, o sistema tenta encontrar solicitações que combinem com os termos informados.
- O filtro funciona junto com os demais filtros já existentes, como:
  - status
  - unidade
  - região
  - apoio CET
  - tipo de visita
  - tipo de imóvel
  - foco
  - protocolo
  - período de agendamento

---

## Onde a alteração se aplica

A nova busca por endereço foi aplicada nos seguintes pontos:

- **Painel de Gestão**
- **Tela de Solicitações Canceladas**
- **Exportação para Excel**

Isso garante consistência entre a visualização na tela e os dados exportados.

---

## Benefícios práticos

- Mais agilidade para localizar solicitações específicas
- Menor dependência de protocolo ou unidade para encontrar um pedido
- Melhor apoio operacional para consultas rápidas
- Mais precisão na exportação de relatórios filtrados

---

## Exemplo de uso operacional

### Cenário

A equipe precisa localizar todas as solicitações relacionadas a uma rua específica.

### Como fazer

1. Acessar o **Painel de Gestão**
2. Abrir **Filtros de Busca**
3. Preencher o campo **Endereço**
4. Digitar, por exemplo: `Rua Francisco Mendes`
5. Clicar em **Filtrar**

### Resultado esperado

O sistema exibirá as solicitações que possuam correspondência com esse endereço, inclusive quando o dado estiver cadastrado apenas parcialmente nos campos do local.

---

## Observação importante

O filtro depende da qualidade do endereço cadastrado na solicitação.
Se houver abreviações, variações de escrita ou dados incompletos, o ideal é testar buscas por partes do endereço, como:

- nome da rua
- número
- bairro
- CEP

---

## Resumo curto

Foi criado um novo filtro por **endereço** no Painel de Gestão, permitindo localizar solicitações por rua, número, bairro, cidade, UF, complemento ou CEP.
Esse filtro também foi mantido na tela de canceladas e na exportação em Excel.

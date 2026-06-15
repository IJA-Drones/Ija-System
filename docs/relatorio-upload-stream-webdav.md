# Relatório técnico: upload assíncrono de mídias para o Skybox via WebDAV

## 1. Contexto

A aplicação Flask, servida em produção via Gunicorn, apresentava falhas durante o upload de mídias grandes, especialmente fotos e vídeos de drones vinculados a Ordens de Serviço.

O erro observado era:

```text
CRITICAL: WORKER TIMEOUT
```

Esse erro acontece quando um worker do Gunicorn fica ocupado por tempo demais processando uma única requisição. No caso da aplicação, o upload era feito por um formulário HTML tradicional, com `multipart/form-data`, e o backend precisava receber o arquivo para, em seguida, repassá-lo ao storage externo Skybox/Nextcloud.

## 2. Causa raiz

O fluxo anterior concentrava muitas responsabilidades em uma única requisição sincronizada:

1. O usuário preenchia o formulário da OS.
2. O navegador enviava os campos e o arquivo via formulário HTML tradicional.
3. O Flask recebia o arquivo como `request.files`.
4. O backend validava e processava o arquivo.
5. O backend repassava o arquivo para o Skybox/Nextcloud.
6. A resposta ao usuário só era enviada depois de todo o processo terminar.

Para arquivos grandes, esse processo podia ultrapassar o limite de timeout do Gunicorn. Quando isso acontecia, o Gunicorn encerrava o worker, interrompendo o upload e causando instabilidade na aplicação.

O problema não era apenas o tamanho do arquivo, mas o fato de o worker ficar bloqueado durante todo o ciclo de upload e repasse ao armazenamento externo.

## 3. Papel do Gunicorn

O Gunicorn é um servidor WSGI usado para executar aplicações Python em produção. No desenvolvimento, normalmente o Flask pode ser iniciado com o servidor embutido, mas esse servidor interno não é indicado para produção. Em ambientes reais, o Flask precisa ser executado por um servidor WSGI, e o Gunicorn cumpre esse papel.

Na prática, o Gunicorn fica responsável por receber as requisições HTTP encaminhadas pelo servidor web, ou pela plataforma de hospedagem, e entregá-las à aplicação Flask. Ele também cria e gerencia processos chamados workers. Cada worker é uma unidade de trabalho capaz de atender requisições da aplicação.

Um fluxo simplificado fica assim:

```text
Usuário
  -> navegador
  -> servidor/plataforma
  -> Gunicorn
  -> worker
  -> Flask
```

Cada worker tem um limite de tempo para responder. Quando uma requisição demora demais, o Gunicorn entende que o worker travou ou ficou indisponível.

Nesse caso, o worker não estava necessariamente travado; ele estava ocupado fazendo upload e repasse de mídia grande. Mesmo assim, para o Gunicorn, o resultado era o mesmo: a requisição excedia o tempo permitido.

O erro `CRITICAL: WORKER TIMEOUT` era, portanto, um sintoma do fluxo de upload pesado e sincronizado.

O papel do Gunicorn no problema foi evidenciar que uma requisição longa demais estava prendendo um worker. O papel da correção foi reduzir o peso desse trabalho dentro do Flask, usando um fluxo de upload mais direto e em streaming para o armazenamento remoto.

## 4. Solução implementada

A solução foi separar o upload da mídia principal do envio tradicional do formulário e criar um fluxo assíncrono, usando JavaScript Vanilla no frontend e uma nova rota `PUT` no backend.

O novo endpoint criado foi:

```text
PUT /api/os/<os_id>/upload-stream
```

O upload agora é feito com bytes brutos, usando o próprio objeto `File` como corpo da requisição:

```javascript
const response = await fetch(`/api/os/${osId}/upload-stream`, {
  method: "PUT",
  headers: {
    "Content-Type": file.type || "application/octet-stream",
    "X-File-Name": encodeURIComponent(file.name),
  },
  body: file,
});
```

No backend, o ponto principal da otimização foi repassar o stream recebido diretamente para o WebDAV:

```python
response = requests.put(
    file_url,
    data=request.stream,
    headers=upload_headers,
    auth=auth,
    timeout=WEBDAV_TIMEOUT,
)
```

O uso de `data=request.stream` evita carregar o arquivo inteiro na memória RAM antes de enviá-lo ao Skybox/Nextcloud.

## 5. WebDAV, Skybox e Nextcloud

O Skybox/Nextcloud é o armazenamento remoto usado para guardar os arquivos. O WebDAV é o protocolo/API usado para enviar e buscar arquivos nesse armazenamento.

Em outras palavras:

```text
Navegador
  -> envia bytes para o Flask

Flask
  -> repassa request.stream com requests.put()

WebDAV
  -> recebe o arquivo

Skybox/Nextcloud
  -> armazena a mídia
```

Portanto, o Flask envia a foto para o Skybox usando WebDAV.

## 6. Variáveis de ambiente

A nova rota usa as variáveis:

```env
WEBDAV_URL
WEBDAV_USER
WEBDAV_PASS
```

Também foi mantido fallback para as variáveis que o projeto já usava para o Skybox:

```env
SKYBOX_WEBDAV_URL
SKYBOX_USERNAME
SKYBOX_APP_PASSWORD
```

Isso permite reaproveitar a configuração existente, sem obrigar uma mudança imediata no ambiente.

## 7. Fluxo novo

O novo fluxo de upload da foto principal ficou assim:

1. O usuário seleciona a foto no campo `input type="file"`.
2. O usuário clica no botão de upload.
3. O JavaScript desabilita o botão e mostra o status de carregamento.
4. O frontend envia o arquivo via `fetch()`, com método `PUT`.
5. O Flask recebe o corpo bruto da requisição.
6. O Flask lê o nome do arquivo pelo header `X-File-Name`.
7. O Flask cria a pasta da OS no WebDAV com `MKCOL`.
8. O Flask envia o arquivo para o WebDAV com `requests.put(..., data=request.stream)`.
9. O backend salva a referência remota no banco.
10. O frontend mostra uma mensagem de sucesso ou erro.

## 8. Arquivos alterados

### `app/templates/piloto_os_formulario.html`

Foi substituído o envio tradicional da foto principal por:

- `input type="file" id="imagemPrincipal"`;
- botão dedicado de upload;
- função assíncrona com `fetch()`;
- headers `Content-Type` e `X-File-Name`;
- feedback visual de carregando, sucesso e falha.

### `app/modules/piloto_os/routes.py`

Foi criada a rota:

```text
PUT /api/os/<int:os_id>/upload-stream
```

Responsabilidades da rota:

- validar a permissão da OS;
- decodificar o header `X-File-Name`;
- montar `folder_url = f"{WEBDAV_URL}/{os_id}"`;
- montar `file_url = f"{folder_url}/{file_name}"`;
- criar a pasta remota com `MKCOL`;
- enviar o arquivo com `requests.put(..., data=request.stream)`;
- salvar a referência remota no banco;
- retornar JSON de sucesso ou erro.

Também foi criada uma rota para exibir a foto principal:

```text
GET /os/<int:os_id>/imagem-principal
```

### `app/modules/piloto_os/service.py`

Foi adicionada uma função para obter a foto principal, respeitando as regras de acesso já existentes no módulo.

## 9. Benefícios

A mudança trouxe os seguintes benefícios:

- reduz o risco de `CRITICAL: WORKER TIMEOUT`;
- evita carregar arquivos grandes inteiros na memória do Flask;
- desacopla o upload da mídia do salvamento completo do formulário;
- melhora a experiência do usuário com status de envio;
- mantém compatibilidade com o Skybox/Nextcloud via WebDAV;
- permite que a foto principal remota continue sendo exibida no formulário.

## 10. Testes recomendados

### Teste funcional no navegador

1. Abrir uma OS editável.
2. Selecionar uma imagem JPG ou PNG pequena.
3. Clicar em `Enviar foto principal`.
4. Confirmar que o botão fica desabilitado durante o envio.
5. Confirmar a mensagem de sucesso.
6. Recarregar a página.
7. Confirmar que a foto principal aparece.
8. Conferir se o arquivo foi criado no Skybox/Nextcloud.

### Teste com arquivo grande

1. Selecionar uma foto grande ou mídia pesada.
2. Fazer o upload pelo novo botão.
3. Observar os logs do Gunicorn.
4. Confirmar que não aparece `CRITICAL: WORKER TIMEOUT`.
5. Confirmar que o arquivo aparece no Skybox/Nextcloud.

### Testes de erro

Testar os seguintes cenários:

- clicar em enviar sem selecionar arquivo;
- usar credenciais WebDAV ausentes ou inválidas;
- testar arquivo com nome contendo espaços ou acentos;
- tentar upload em OS sem permissão;
- tentar upload em OS concluída ou bloqueada para edição.

## 11. Validações realizadas

Foi executada a validação de sintaxe Python:

```powershell
.\venv\Scripts\python.exe -m py_compile app\modules\piloto_os\routes.py app\modules\piloto_os\service.py
```

Também foi validado que a rota nova foi registrada no mapa de rotas Flask.

## 12. Conclusão

O problema principal era um fluxo de upload pesado, sincronizado e acoplado ao formulário completo da OS. Isso mantinha o worker do Gunicorn ocupado por tempo demais e podia resultar em `CRITICAL: WORKER TIMEOUT`.

A solução implementada criou um upload assíncrono e em streaming para o Skybox/Nextcloud via WebDAV. O backend agora repassa o corpo recebido diretamente para o storage usando `request.stream`, reduzindo o consumo de memória e diminuindo o risco de timeout.

O resultado é um fluxo mais robusto para arquivos grandes e uma experiência melhor para o usuário durante o envio de mídias.

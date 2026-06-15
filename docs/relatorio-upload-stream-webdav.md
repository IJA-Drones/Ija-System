# Relatório técnico: upload assíncrono de mídias para o Skybox via WebDAV

Data: 15 de junho de 2026.

## 1. Contexto

A aplicação Flask, servida em produção via Gunicorn, apresentava falhas durante o upload de mídias grandes, especialmente fotos e vídeos de drones vinculados a Ordens de Serviço.

O erro observado era:

```text
CRITICAL: WORKER TIMEOUT
```

Esse erro acontece quando um worker do Gunicorn fica ocupado por tempo demais processando uma única requisição. No caso da aplicação, o upload era feito por um formulário HTML tradicional, com `multipart/form-data`, e o backend precisava receber o arquivo para, em seguida, repassá-lo ao storage externo Skybox/Nextcloud.

## 2. Papel do Gunicorn

O Gunicorn é um servidor WSGI usado para executar aplicações Python em produção. No desenvolvimento, o Flask pode rodar com o servidor embutido, mas esse servidor interno não é indicado para produção. Em ambientes reais, o Flask precisa ser executado por um servidor WSGI, e o Gunicorn cumpre esse papel.

Na prática, o Gunicorn recebe as requisições HTTP encaminhadas pelo servidor web, ou pela plataforma de hospedagem, e entrega essas requisições à aplicação Flask. Ele também cria e gerencia processos chamados workers. Cada worker é uma unidade de trabalho capaz de atender requisições da aplicação.

Um fluxo simplificado fica assim:

```text
Usuário
  -> navegador
  -> servidor/plataforma
  -> Gunicorn
  -> worker
  -> Flask
```

Cada worker tem um limite de tempo para responder. Quando uma requisição demora demais, o Gunicorn entende que o worker travou ou ficou indisponível. Nesse caso, o worker não estava necessariamente travado; ele estava ocupado fazendo upload e repasse de mídia grande. Mesmo assim, para o Gunicorn, o resultado era o mesmo: a requisição excedia o tempo permitido.

O erro `CRITICAL: WORKER TIMEOUT` era, portanto, um sintoma do fluxo de upload pesado e sincronizado.

## 3. Causa raiz

O fluxo anterior concentrava muitas responsabilidades em uma única requisição sincronizada:

1. O usuário preenchia o formulário da OS.
2. O navegador enviava os campos e o arquivo via formulário HTML tradicional.
3. O Flask recebia o arquivo como `request.files`.
4. O backend validava e processava o arquivo.
5. O backend repassava o arquivo para o Skybox/Nextcloud.
6. A resposta ao usuário só era enviada depois de todo o processo terminar.

Para arquivos grandes, esse processo podia ultrapassar o limite de timeout do Gunicorn. Quando isso acontecia, o Gunicorn encerrava o worker, interrompendo o upload e causando instabilidade na aplicação.

O problema não era apenas o tamanho do arquivo, mas o fato de o worker ficar bloqueado durante todo o ciclo de upload e repasse ao armazenamento externo.

## 4. Solução implementada

A solução foi separar o upload da foto principal, das imagens complementares e do vídeo do envio tradicional do formulário. Foi criado um fluxo assíncrono usando JavaScript Vanilla no frontend e rotas `PUT` no backend.

Os endpoints de upload criados foram:

```text
PUT /api/os/<os_id>/upload-stream
PUT /api/os/<os_id>/upload-complementary-stream
PUT /api/os/<os_id>/upload-video-stream
```

Também foram adicionadas rotas de remoção direta:

```text
DELETE /api/os/<os_id>/imagem-principal
DELETE /api/os/<os_id>/imagem-complementar/<image_index>
DELETE /api/os/<os_id>/video
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

No backend, o ponto principal da otimização foi repassar o fluxo recebido para o WebDAV em partes, sem carregar o arquivo inteiro na memória:

```python
def stream_chunks():
    while True:
        chunk = request.stream.read(chunk_size)
        if not chunk:
            break
        yield chunk

response = requests.put(
    file_url,
    data=stream_chunks(),
    headers=upload_headers,
    auth=auth,
    timeout=webdav_timeout,
)
```

Esse fluxo reduz o consumo de memória do Flask e diminui o risco de timeout em uploads grandes.

## 5. WebDAV, Skybox e Nextcloud

O Skybox/Nextcloud é o armazenamento remoto usado para guardar os arquivos. O WebDAV é o protocolo/API usado para enviar, buscar e remover arquivos nesse armazenamento.

Em outras palavras:

```text
Navegador
  -> envia bytes para o Flask

Flask
  -> repassa o fluxo para o WebDAV com requests.put()

WebDAV
  -> recebe o arquivo

Skybox/Nextcloud
  -> armazena a mídia
```

Portanto, o Flask envia a foto principal, as imagens complementares e o vídeo para o Skybox usando WebDAV.

## 6. Pasta raiz no Skybox

Foi corrigido um detalhe importante: as pastas das OS não devem ser criadas diretamente na raiz do Skybox. Elas devem ficar dentro da pasta raiz já usada pelo sistema:

```text
dados ordens de serviço
```

O destino correto passou a ser:

```text
<WEBDAV_URL>/dados ordens de serviço/<os_id>/<arquivo>
```

Internamente, a referência salva no banco usa marcador remoto:

```text
webdav://dados ordens de serviço/<os_id>/<arquivo>
```

Isso garante que novos uploads fiquem dentro da pasta raiz correta, em vez de criar pastas com o ID da OS fora dela.

## 7. Variáveis de ambiente

A integração usa as variáveis:

```env
WEBDAV_URL
WEBDAV_USER
WEBDAV_PASS
WEBDAV_BASE_DIR
WEBDAV_CONNECT_TIMEOUT_SECONDS
WEBDAV_TRANSFER_TIMEOUT_SECONDS
WEBDAV_UPLOAD_CHUNK_SIZE_BYTES
```

Também foi mantido fallback para variáveis já usadas pelo projeto:

```env
SKYBOX_WEBDAV_URL
SKYBOX_USERNAME
SKYBOX_APP_PASSWORD
SKYBOX_BASE_DIR
```

Se `WEBDAV_BASE_DIR` e `SKYBOX_BASE_DIR` não forem configuradas, o sistema usa como padrão:

```text
dados ordens de serviço
```

## 8. Fluxo novo

O novo fluxo de upload ficou assim:

1. O usuário seleciona a foto principal, as imagens complementares ou o vídeo.
2. O usuário clica no botão de upload específico.
3. O JavaScript desabilita o botão e mostra o status de carregamento.
4. O frontend envia o arquivo via `fetch()`, com método `PUT`.
5. O Flask recebe o corpo bruto da requisição.
6. O Flask lê o nome do arquivo pelo header `X-File-Name`.
7. O Flask cria a pasta raiz e a pasta da OS no WebDAV com `MKCOL`.
8. O Flask envia o arquivo para o WebDAV em streaming/chunks.
9. O backend salva a referência remota no banco.
10. O frontend atualiza a tela e mostra sucesso ou erro.

No caso das imagens complementares, quando vários arquivos são selecionados, o frontend envia uma imagem por vez. Após cada sucesso, a nova imagem é adicionada à galeria atual sem precisar recarregar a página.

## 9. Remoção de mídias

Antes, as imagens complementares só podiam ser removidas em bloco. Agora, cada imagem complementar tem seu próprio botão `Remover`.

Também foram adicionados botões de remoção para:

- foto principal;
- vídeo da OS;
- imagem complementar individual.

Ao remover uma mídia, o sistema:

1. Exibe confirmação no padrão de alertas do sistema.
2. Mostra loading enquanto a exclusão acontece.
3. Chama a rota `DELETE` correspondente.
4. Remove a referência do banco.
5. Tenta apagar o arquivo remoto no WebDAV/Skybox.
6. Atualiza a interface.
7. Exibe alerta de sucesso.

Também foi ajustado o fluxo de limpeza da galeria para apagar arquivos remotos `webdav://`, e não apenas limpar a lista no banco. Com isso, quando a galeria é limpa ou uma mídia é removida, o sistema também tenta excluir o arquivo correspondente no Skybox.

## 10. Interface do formulário

O template `app/templates/piloto_os_formulario.html` foi atualizado para:

- substituir uploads tradicionais por inputs e botões específicos;
- enviar foto principal, imagens complementares e vídeo por `fetch()`;
- desabilitar botões durante o envio;
- mostrar mensagens de carregamento, sucesso e falha;
- exibir a imagem complementar enviada imediatamente na galeria;
- remover mídias com alertas padronizados;
- mostrar loading durante exclusão;
- mostrar alerta de sucesso após exclusão;
- corrigir a acentuação dos textos visíveis do formulário de OS.

## 11. Arquivos alterados

### `app/templates/piloto_os_formulario.html`

Foram adicionados:

- `input type="file" id="imagemPrincipal"`;
- `input type="file" id="outras_imagens_files"`;
- `input type="file" id="video_file"`;
- botões dedicados de upload;
- botões dedicados de remoção;
- funções assíncronas com `fetch()`;
- headers `Content-Type` e `X-File-Name`;
- feedback visual de carregando, sucesso e falha;
- atualização dinâmica da galeria de imagens complementares;
- alertas padronizados para confirmação, loading e sucesso;
- correções de acentuação na interface.

### `app/modules/piloto_os/routes.py`

Foram criadas ou ajustadas as rotas:

```text
PUT /api/os/<int:os_id>/upload-stream
PUT /api/os/<int:os_id>/upload-complementary-stream
PUT /api/os/<int:os_id>/upload-video-stream
DELETE /api/os/<int:os_id>/imagem-principal
DELETE /api/os/<int:os_id>/imagem-complementar/<int:image_index>
DELETE /api/os/<int:os_id>/video
GET /os/<int:os_id>/imagem-principal
```

Responsabilidades principais:

- validar a permissão da OS;
- decodificar o header `X-File-Name`;
- montar o caminho remoto dentro da pasta raiz do Skybox;
- criar a pasta raiz e a pasta da OS com `MKCOL`;
- enviar o arquivo com `requests.put(..., data=stream_chunks())`;
- salvar marcador `webdav://...` no banco;
- buscar mídia remota para exibição no formulário;
- remover arquivos remotos no WebDAV;
- retornar JSON de sucesso ou erro.

### `app/modules/piloto_os/service.py`

O serviço foi ajustado para tratar marcadores `webdav://` na rotina antiga de remoção/limpeza de arquivos. Assim, quando a galeria atual é limpa pelo formulário, os arquivos remotos também são apagados do Skybox quando possível.

## 12. Benefícios

A mudança trouxe os seguintes benefícios:

- reduz o risco de `CRITICAL: WORKER TIMEOUT`;
- evita carregar arquivos grandes inteiros na memória do Flask;
- desacopla uploads pesados do salvamento completo do formulário;
- mantém compatibilidade com o Skybox/Nextcloud via WebDAV;
- mantém os arquivos dentro da pasta raiz correta no Skybox;
- permite upload de foto principal, imagens complementares e vídeo;
- permite remover foto principal, vídeo e imagens complementares individualmente;
- remove arquivos do Skybox ao apagar mídias no sistema;
- melhora a experiência do usuário com status, loading e alertas padronizados;
- atualiza a galeria sem precisar recarregar a página após upload.

## 13. Testes recomendados

### Teste funcional no navegador

1. Abrir uma OS editável.
2. Selecionar uma imagem JPG ou PNG pequena.
3. Clicar em `Enviar foto principal`.
4. Confirmar que o botão fica desabilitado durante o envio.
5. Confirmar a mensagem de sucesso.
6. Recarregar a página.
7. Confirmar que a foto principal aparece.
8. Conferir se o arquivo foi criado em `dados ordens de serviço/<os_id>` no Skybox.
9. Clicar em `Remover` na foto principal.
10. Confirmar o alerta, o loading e a mensagem de sucesso.
11. Confirmar que a foto sumiu do formulário e do Skybox.
12. Selecionar uma ou mais imagens complementares.
13. Clicar em `Enviar imagens`.
14. Confirmar que cada imagem aparece na galeria sem recarregar a página.
15. Clicar em `Remover` em uma imagem complementar específica.
16. Confirmar que apenas essa imagem é removida.
17. Recarregar a página.
18. Confirmar que as demais imagens continuam aparecendo.
19. Selecionar um vídeo MP4, MOV, WEBM ou M4V.
20. Clicar em `Enviar vídeo`.
21. Confirmar que o vídeo aparece e reproduz.
22. Clicar em `Remover` no vídeo.
23. Confirmar o alerta, o loading, a mensagem de sucesso e a remoção no Skybox.

### Teste com arquivo grande

1. Selecionar uma foto grande ou vídeo pesado.
2. Fazer o upload pelo novo botão.
3. Observar os logs do Gunicorn.
4. Confirmar que não aparece `CRITICAL: WORKER TIMEOUT`.
5. Confirmar que o arquivo aparece no Skybox/Nextcloud dentro da pasta raiz correta.

### Testes de erro

Testar os seguintes cenários:

- clicar em enviar sem selecionar arquivo;
- usar credenciais WebDAV ausentes ou inválidas;
- testar arquivo com nome contendo espaços ou acentos;
- tentar upload em OS sem permissão;
- tentar upload em OS concluída ou bloqueada para edição;
- tentar remover mídia inexistente;
- remover uma imagem complementar do meio da lista e confirmar que os links das demais continuam funcionando;
- limpar a galeria atual e confirmar que os arquivos remotos também são removidos.

## 14. Validações realizadas

Foi executada a validação de sintaxe Python:

```powershell
.\venv\Scripts\python.exe -m py_compile app\modules\piloto_os\routes.py app\modules\piloto_os\service.py
```

Também foi executada validação de diff do template:

```powershell
git diff --check -- app\templates\piloto_os_formulario.html
```

## 15. Conclusão

O problema principal era um fluxo de upload pesado, sincronizado e acoplado ao formulário completo da OS. Isso mantinha o worker do Gunicorn ocupado por tempo demais e podia resultar em `CRITICAL: WORKER TIMEOUT`.

A solução implementada criou uploads assíncronos e em streaming para o Skybox/Nextcloud via WebDAV. O backend agora repassa o corpo recebido em chunks para o storage, reduzindo o consumo de memória e diminuindo o risco de timeout.

Além disso, o formulário ficou mais claro para o usuário: os uploads têm status próprio, as remoções têm confirmação/loading/sucesso, a galeria atualiza imediatamente e os arquivos passam a ser salvos dentro da pasta raiz correta do Skybox.

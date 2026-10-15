(() => {
  'use strict';
  const missingCode = 'video_upload_session_missing';

  function httpError(message, status, payload = {}) {
    const error = new Error(message);
    error.status = status;
    error.code = payload.code;
    // Recognize the old server response during a rolling deployment as well.
    if (status === 404 && payload.error === 'Sessao de upload de video nao encontrada.') {
      error.code = missingCode;
    }
    return error;
  }

  async function upload({file, chunkBytes, createSession, sendChunk, complete,
                         onProgress = () => {}, onAssembling = () => {}, onRestart = () => {}}) {
    // A vanished session has lost its parts; never continue at the old chunk index.
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const session = await createSession(file);
      const totalChunks = Math.ceil(file.size / chunkBytes);
      try {
        for (let index = 0; index < totalChunks; index += 1) {
          const start = index * chunkBytes;
          const end = Math.min(file.size, start + chunkBytes);
          await sendChunk(session.session_id, index, file.slice(start, end), loaded => {
            onProgress(Math.min(file.size, start + loaded), file.size, index + 1, totalChunks, attempt);
          });
          onProgress(end, file.size, index + 1, totalChunks, attempt);
        }
        onAssembling();
        return await complete(session.session_id);
      } catch (error) {
        // Do not replay an uncertain completion or retry authentication/access failures.
        if (error.status !== 404 || error.code !== missingCode) throw error;
        if (attempt === 1) {
          throw httpError('O servidor perdeu a sessão do vídeo novamente. O envio não foi concluído. '
            + 'Mantenha o arquivo selecionado e avise o suporte antes de tentar novamente.', 404,
            {code: missingCode});
        }
        onRestart();
      }
    }
  }
  window.IjaVideoUploadRecovery = {upload, httpError};
})();

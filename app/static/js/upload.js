document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('video-file');
  const editor = document.getElementById('trim-editor');
  const preview = document.getElementById('trim-preview');
  const startInput = document.getElementById('trim-start');
  const endInput = document.getElementById('trim-end');
  const durationLabel = document.getElementById('trim-duration');
  if (!fileInput || !editor || !preview || !startInput || !endInput) return;

  let objectUrl = null;
  const formatSeconds = value => Math.max(0, Number(value) || 0).toFixed(2);

  function updateDurationLabel() {
    const start = Number(startInput.value) || 0;
    const end = Number(endInput.value) || 0;
    if (durationLabel) {
      durationLabel.textContent = end > start
        ? `解析範囲: ${formatSeconds(end - start)} 秒`
        : '終了位置は開始位置より後に設定してください。';
    }
  }

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    preview.src = objectUrl;
    editor.style.display = 'block';
    endInput.value = '';
    updateDurationLabel();
  });

  preview.addEventListener('loadedmetadata', () => {
    const duration = Number.isFinite(preview.duration) ? preview.duration : 0;
    startInput.max = String(duration);
    endInput.max = String(duration);
    endInput.value = formatSeconds(duration);
    updateDurationLabel();
  });

  startInput.addEventListener('change', () => {
    const start = Math.max(0, Math.min(Number(startInput.max) || Infinity, Number(startInput.value) || 0));
    startInput.value = formatSeconds(start);
    if (preview.currentTime < start) preview.currentTime = start;
    updateDurationLabel();
  });
  endInput.addEventListener('change', updateDurationLabel);

  document.getElementById('mark-trim-start')?.addEventListener('click', () => {
    startInput.value = formatSeconds(preview.currentTime);
    startInput.dispatchEvent(new Event('change'));
  });
  document.getElementById('mark-trim-end')?.addEventListener('click', () => {
    endInput.value = formatSeconds(preview.currentTime);
    updateDurationLabel();
  });

  editor.closest('form')?.addEventListener('submit', event => {
    const start = Number(startInput.value) || 0;
    const end = Number(endInput.value);
    if (!Number.isFinite(end) || end <= start) {
      event.preventDefault();
      endInput.setCustomValidity('終了位置は開始位置より後に設定してください。');
      endInput.reportValidity();
      return;
    }
    endInput.setCustomValidity('');
  });
});

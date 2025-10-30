(function () {
  const dz = document.getElementById('nazDrop');
  const input = document.getElementById('nazFile');
  const meta = document.getElementById('nazMeta');
  const nameSpan = document.getElementById('nazName');
  const uploadBtn = document.getElementById('nazUpload');
  const clearBtn = document.getElementById('nazClear');

  if (!dz || !input) return; // Geen uploadrechten? Stop.

  function setFile(file) {
    if (!file) return;
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Kies een PDF-bestand (.pdf).');
      return;
    }
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;

    if (nameSpan) nameSpan.textContent = file.name;
    if (meta) meta.style.display = '';
    if (uploadBtn) uploadBtn.disabled = false;
    if (clearBtn) clearBtn.style.display = '';
  }

  input.addEventListener('change', () => setFile(input.files[0]));

  ['dragenter', 'dragover'].forEach(ev =>
    dz.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dz.classList.add('is-dragover'); })
  );
  ['dragleave', 'drop'].forEach(ev =>
    dz.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dz.classList.remove('is-dragover'); })
  );
  dz.addEventListener('drop', e => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setFile(f);
  });

  clearBtn && clearBtn.addEventListener('click', () => {
    input.value = '';
    if (nameSpan) nameSpan.textContent = '';
    if (meta) meta.style.display = 'none';
    if (uploadBtn) uploadBtn.disabled = true;
    clearBtn.style.display = 'none';
  });
})();

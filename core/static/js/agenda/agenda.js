(() => {
  const dz = document.getElementById('dropzone');
  const input = document.getElementById('agendaFile');
  const meta = document.getElementById('fileMeta');
  const nameSpan = document.getElementById('fileName');
  const uploadBtn = document.getElementById('uploadBtn');
  const clearBtn = document.getElementById('clearBtn');

  function setFile(file){
    if(!file) return;
    if(file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')){
      alert('Kies een PDF-bestand (.pdf).'); return;
    }
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;

    nameSpan.textContent = file.name;
    meta.style.display = '';
    uploadBtn.disabled = false;
    clearBtn.style.display = '';
  }

  input?.addEventListener('change', () => setFile(input.files[0]));

  ['dragenter','dragover'].forEach(ev =>
    dz?.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dz.classList.add('is-dragover'); })
  );
  ['dragleave','drop'].forEach(ev =>
    dz?.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dz.classList.remove('is-dragover'); })
  );
  dz?.addEventListener('drop', e => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if(f) setFile(f);
  });

  clearBtn?.addEventListener('click', () => {
    input.value = '';
    nameSpan.textContent = '';
    meta.style.display = 'none';
    uploadBtn.disabled = true;
    clearBtn.style.display = 'none';
  });
})();

(function(){
  // --- Dropzone (no-op als elementen ontbreken)
  function wireUpload(inputId, dropId, metaId, nameId, uploadBtnId, clearBtnId){
    const dz = document.getElementById(dropId);
    const input = document.getElementById(inputId);
    const meta = document.getElementById(metaId);
    const nameSpan = document.getElementById(nameId);
    const uploadBtn = document.getElementById(uploadBtnId);
    const clearBtn = document.getElementById(clearBtnId);

    if (!dz || !input) return;

    function setFile(file){
      if(!file) return;
      const ok = ['.csv','.xlsx','.xls'].some(ext => file.name.toLowerCase().endsWith(ext));
      if(!ok){ alert('Kies een CSV of Excel-bestand.'); return; }
      const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
      if (nameSpan) nameSpan.textContent = file.name;
      if (meta) meta.style.display = '';
      if (uploadBtn) uploadBtn.disabled = false;
      if (clearBtn) clearBtn.style.display = '';
    }

    input.addEventListener('change', ()=> setFile(input.files[0]));
    ['dragenter','dragover'].forEach(ev =>
      dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('is-dragover'); })
    );
    ['dragleave','drop'].forEach(ev =>
      dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('is-dragover'); })
    );
    dz.addEventListener('drop', e => { const f = e.dataTransfer.files?.[0]; if(f) setFile(f); });
    clearBtn && clearBtn.addEventListener('click', ()=>{
      input.value=''; if (nameSpan) nameSpan.textContent='';
      if (meta) meta.style.display='none';
      if (uploadBtn) uploadBtn.disabled=true;
      clearBtn.style.display='none';
    });
  }

  if (document.getElementById('medForm')) {
    wireUpload('medFile','medDrop','medMeta','medName','medUpload','medClear');
  }
  if (document.getElementById('nazForm')) {
    wireUpload('nazFile','nazDrop','nazMeta','nazName','nazUpload','nazClear');
  }

  // --- Live zoeken + "Toon meer"
  function enableLiveSearch(tableId, inputId, toggleId){
    const STEP = 20;
    const table = document.getElementById(tableId);
    const q = document.getElementById(inputId);
    const toggleBtn = document.getElementById(toggleId);
    if (!table || !q) return;

    let currentLimit = STEP;

    function applyFilter(){
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const needle = (q.value || '').trim().toLowerCase();
      const matched = [];

      rows.forEach(tr => {
        const ok = tr.textContent.toLowerCase().includes(needle);
        tr.style.display = 'none';
        if (ok) matched.push(tr);
      });

      const visible = Math.min(currentLimit, matched.length);
      matched.slice(0, visible).forEach(tr => tr.style.display = '');

      if (toggleBtn){
        if (matched.length > visible){
          toggleBtn.style.display = '';
          toggleBtn.textContent = 'Toon meer';
        } else {
          toggleBtn.style.display = 'none';
        }
      }
    }

    q.addEventListener('input', () => {
      currentLimit = STEP;
      applyFilter();
    });

    toggleBtn && toggleBtn.addEventListener('click', () => {
      currentLimit += STEP;
      applyFilter();
    });

    applyFilter();
  }

  enableLiveSearch('medTable','medSearch','medToggle');
})();
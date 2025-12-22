(function(){
  // --- 1. Dropzone Logica (Behouden)
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
      const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
      if (nameSpan) nameSpan.textContent = file.name;
      if (meta) meta.style.display = '';
      if (uploadBtn) uploadBtn.disabled = false;
      if (clearBtn) clearBtn.style.display = '';
    }

    input.addEventListener('change', ()=> setFile(input.files[0]));
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('is-dragover'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('is-dragover'));
    dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('is-dragover'); const f = e.dataTransfer.files?.[0]; if(f) setFile(f); });
    clearBtn && clearBtn.addEventListener('click', ()=>{
      input.value=''; if (meta) meta.style.display='none';
      if (uploadBtn) uploadBtn.disabled=true; clearBtn.style.display='none';
    });
  }

  // --- 2. Live Zoeken gekoppeld aan table.js
  function initMedSearch() {
    const searchInput = document.getElementById('medSearch');
    const table = document.getElementById('medTable');
    const wrapper = document.querySelector('[data-crud]');
    if (!searchInput || !table || !wrapper) return;

    searchInput.addEventListener('input', () => {
      const needle = searchInput.value.toLowerCase();
      const rows = table.querySelectorAll('tbody tr');

      rows.forEach(tr => {
        const text = tr.innerText.toLowerCase();
        // We gebruiken display none om rijen echt uit te sluiten voor de table.js logic
        tr.style.display = text.includes(needle) ? '' : 'none';
      });

      // Vertel table.js dat de resultaten zijn veranderd
      wrapper.dispatchEvent(new CustomEvent('crud:reset'));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    wireUpload('medFile','medDrop','medMeta','medName','medUpload','medClear');
    initMedSearch();
  });
})();
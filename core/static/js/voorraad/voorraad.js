(function(){
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
        tr.style.display = text.includes(needle) ? '' : 'none';
      });

      wrapper.dispatchEvent(new CustomEvent('crud:reset'));
    });
  }

  function initEmailSelect2() {
    const el = document.getElementById('id_recipients');
    if (!el || !window.$) return;

    const $select = $('#id_recipients');
    if ($select.hasClass('select2-hidden-accessible')) return;

    $select.select2({
      width: '100%',
      placeholder: "Zoek en selecteer apotheken...",
      allowClear: false,
      dropdownParent: $('#emailModal'),
      closeOnSelect: false,
    });
  }

  window.toggleEmailModal = function() {
    const modal = document.getElementById('emailModal');
    if (!modal) return;

    if (modal.style.display === 'block') {
      modal.style.display = 'none';
      return;
    }

    modal.style.display = 'block';
    initEmailSelect2();
  };

  window.selectAllApotheken = function() {
    if (!window.$) return;
    $('#id_recipients > option').prop('selected', true);
    $('#id_recipients').trigger('change');
  };

  window.deselectAllApotheken = function() {
    if (!window.$) return;
    $('#id_recipients').val(null).trigger('change');
  };

  window.onclick = function(event) {
    const modal = document.getElementById('emailModal');
    if (modal && event.target === modal) {
      modal.style.display = 'none';
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    wireUpload('medFile','medDrop','medMeta','medName','medUpload','medClear');
    initMedSearch();
    initEmailSelect2();
  });
})();

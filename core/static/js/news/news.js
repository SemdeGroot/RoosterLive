(function(){
  // --- Upload UI
  const dz = document.getElementById('newsDrop'),
        input = document.getElementById('newsFile'),
        meta = document.getElementById('newsMeta'),
        nameSpan = document.getElementById('newsName'),
        uploadBtn = document.getElementById('newsUpload'),
        clearBtn = document.getElementById('newsClear');

  if (dz && input) {
    function setFile(file){
      if(!file) return;
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      if(!isPdf){ alert('Kies een PDF (.pdf).'); return; }
      const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
      if(nameSpan) nameSpan.textContent = file.name;
      if(meta) meta.style.display = '';
      if(uploadBtn) uploadBtn.disabled = false;
      if(clearBtn) clearBtn.style.display = '';
    }
    input.addEventListener('change', ()=> setFile(input.files[0]));
    ['dragenter','dragover'].forEach(ev=> dz && dz.addEventListener(ev, e=>{e.preventDefault(); dz.classList.add('is-dragover');}));
    ['dragleave','drop'].forEach(ev=> dz && dz.addEventListener(ev, e=>{e.preventDefault(); dz.classList.remove('is-dragover');}));
    dz && dz.addEventListener('drop', e=>{const f=e.dataTransfer.files?.[0]; if(f) setFile(f);});
    clearBtn && clearBtn.addEventListener('click', ()=>{
      input.value=''; if(nameSpan) nameSpan.textContent='';
      if(meta) meta.style.display='none';
      if(uploadBtn) uploadBtn.disabled=true;
      clearBtn.style.display='none';
    });
  }

  // --- "Toon meer" voor PNG's
  const pages = document.getElementById('newsPages');
  const moreBtn = document.getElementById('newsMore');
  const STEP = 10;
  let currentLimit = STEP;

  function applyLimit(){
    if(!pages) return;
    const cards = Array.from(pages.children);
    const total = cards.length;

    cards.forEach((el, idx) => {
      el.style.display = (idx < currentLimit) ? '' : 'none';
    });

    if(moreBtn){
      if(total > currentLimit){
        moreBtn.style.display = '';
        moreBtn.disabled = false;
        moreBtn.textContent = 'Toon meer';
      } else {
        moreBtn.style.display = 'none';
      }
    }
  }

  if (pages) applyLimit();

  moreBtn && moreBtn.addEventListener('click', () => {
    currentLimit += STEP;
    applyLimit();
  });

  // --- Inline delete via fetch naar DEZELFDE URL
  if(pages){
    function getCSRF(){
      const m=document.cookie.match(/csrftoken=([^;]+)/); return m?m[1]:"";
    }
    pages.addEventListener('click', async (e)=>{
      const btn = e.target.closest('.del-btn');
      if(!btn) return;
      const img = btn.getAttribute('data-img');
      if(!img) return;
      if(!confirm('Weet je zeker dat je de PDF wilt verwijderen?')) return;
      btn.disabled = true;

      try{
        const resp = await fetch(window.location.href, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCSRF(),
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded"
          },
          body: "action=delete&img=" + encodeURIComponent(img)
        });
        const data = await resp.json();
        if(data && data.ok){
          const hash = data.hash;
          document.querySelectorAll('.page').forEach(card=>{
            const u = card.getAttribute('data-img') || '';
            if(u.includes('/cache/news/'+hash+'/')) card.remove();
          });
          applyLimit();
        }else{
          alert(data && data.error ? data.error : "Verwijderen mislukt.");
          btn.disabled = false;
        }
      }catch(err){
        alert("Netwerkfout bij verwijderen.");
        btn.disabled = false;
      }
    });
  }
})();

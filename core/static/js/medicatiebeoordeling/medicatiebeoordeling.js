document.addEventListener("DOMContentLoaded", function() {
    
    // ==========================================
    // 1. HELPERS (CSRF & SVG)
    // ==========================================
    
    // Functie om de CSRF token uit de cookie te halen (nodig voor delete forms)
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // Het SVG icoontje als string variabele om de code leesbaar te houden
    const deleteSvgIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`;

    // ==========================================
    // 2. LIVE SEARCH (Detail Pagina)
    // ==========================================
    const liveInput = document.getElementById("liveSearchPatient");
    const detailTable = document.getElementById("tableDetailPatient");

    if (liveInput && detailTable) {
        liveInput.addEventListener("input", function() {
            const filter = liveInput.value.toLowerCase();
            const tbody = detailTable.querySelector("tbody");
            const rows = tbody.querySelectorAll("tr");

            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                if (text.includes(filter)) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            });
        });
    }

    // ==========================================
    // 3. AJAX LIST LOADER (List Pagina)
    // ==========================================

    // State management: We beginnen op pagina 2 voor "Toon Meer", 
    // want pagina 1 is al door Django ingeladen.
    const state = {
        afdeling: { page: 2, query: '', loading: false },
        patient:  { page: 2, query: '', loading: false }
    };

    /**
     * loadData functie
     * Haalt data op en bouwt de HTML rijen op inclusief Delete forms.
     */
    function loadData(type, isSearch = false) {
        const s = state[type];
        if (s.loading) return;

        // Als we zoeken, resetten we naar pagina 1
        if (isSearch) {
            s.page = 1;
        }

        s.loading = true;
        const btnMore = type === 'afdeling' ? document.getElementById('btnMoreAfdeling') : document.getElementById('btnMorePatient');
        
        // UI Feedback
        if(btnMore) btnMore.innerText = "Laden...";

        // API Call
        const url = `/medicatiebeoordeling/search/?type=${type}&q=${encodeURIComponent(s.query)}&page=${s.page}`;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                const tbody = type === 'afdeling' ? document.getElementById('tbodyAfdeling') : document.getElementById('tbodyPatient');
                
                // Bij een zoekopdracht maken we de tabel eerst leeg
                if (isSearch) {
                    tbody.innerHTML = '';
                }

                // Geen resultaten?
                if (data.results.length === 0 && isSearch) {
                    const colSpan = type === 'afdeling' ? 4 : 5;
                    tbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center; color:grey;">Geen resultaten gevonden.</td></tr>`;
                    if(btnMore) btnMore.style.display = 'none';
                    return;
                }

                // Loop door resultaten en bouw de HTML
                data.results.forEach(item => {
                    const row = document.createElement('tr');
                    
                    if (type === 'afdeling') {
                        // URL voor deleten van afdeling
                        const deleteUrl = `/medicatiebeoordeling/delete/afdeling/${item.id}/`;

                        row.innerHTML = `
                            <td>
                                <a href="${item.detail_url}" style="font-weight:bold; color:var(--text); text-decoration:none;">
                                    ${item.naam}
                                </a>
                            </td>
                            <td>${item.datum}</td>
                            <td>${item.door}</td>
                            <td>
                                <div style="display:flex; gap:6px;">
                                    <a href="${item.detail_url}" class="btn" style="padding:6px 10px; font-size:0.85rem;">Bekijk</a>
                                    
                                    <form method="post" action="${deleteUrl}" onsubmit="return confirm('Weet je het zeker?');" style="margin:0;">
                                        <input type="hidden" name="csrfmiddlewaretoken" value="${csrftoken}">
                                        <button type="submit" class="btn btn-danger" style="padding:6px; min-width:auto;" title="Verwijderen">
                                            ${deleteSvgIcon}
                                        </button>
                                    </form>
                                </div>
                            </td>
                        `;
} else { // Dit is het patiënt blok
                        const deleteUrl = `/medicatiebeoordeling/delete/patient/${item.id}/`;

                        row.innerHTML = `
                            <td><strong>${item.naam}</strong></td>
                            
                            <td>${item.geboortedatum}</td> 

                            <td style="color:var(--muted);">${item.afdeling}</td>
                            <td>${item.datum}</td>
                            <td>${item.door}</td>
                            <td>
                                <div style="display:flex; gap:6px;">
                                    <a href="${item.detail_url}" class="btn" style="padding:6px 10px; font-size:0.85rem;">Bekijk</a>
                                    <form method="post" action="${deleteUrl}" onsubmit="return confirm('Weet je het zeker?');" style="margin:0;">
                                        <input type="hidden" name="csrfmiddlewaretoken" value="${csrftoken}">
                                        <button type="submit" class="btn btn-danger" style="padding:6px; min-width:auto;" title="Verwijderen">${deleteSvgIcon}</button>
                                    </form>
                                </div>
                            </td>
                        `;
                    }
                    tbody.appendChild(row);
                });

                // Update "Toon Meer" knop logica
                if (data.has_next) {
                    s.page = data.next_page;
                    if(btnMore) {
                        btnMore.style.display = 'inline-block';
                        btnMore.innerText = "Toon meer";
                    }
                } else {
                    if(btnMore) btnMore.style.display = 'none';
                }
            })
            .catch(err => {
                console.error("Fout bij laden:", err);
                if(btnMore) btnMore.innerText = "Fout bij laden";
            })
            .finally(() => {
                s.loading = false;
            });
    }

    // ==========================================
    // 4. EVENT LISTENERS
    // ==========================================

    // --- AFDELING ---
    const btnSearchAfd = document.getElementById("btnSearchAfdeling");
    const inputAfd = document.getElementById("searchAfdelingInput");
    const btnMoreAfd = document.getElementById("btnMoreAfdeling");

    if (btnSearchAfd && inputAfd) {
        const handleSearchAfd = () => {
            state.afdeling.query = inputAfd.value;
            loadData('afdeling', true);
        };
        
        btnSearchAfd.addEventListener("click", handleSearchAfd);
        
        inputAfd.addEventListener("keypress", (e) => { 
            if (e.key === "Enter") handleSearchAfd(); 
        });

        if(btnMoreAfd) {
            btnMoreAfd.addEventListener("click", () => {
                loadData('afdeling', false);
            });
        }
    }

    // --- PATIENT ---
    const btnSearchPat = document.getElementById("btnSearchPatient");
    const inputPat = document.getElementById("searchPatientInput");
    const btnMorePat = document.getElementById("btnMorePatient");

    if (btnSearchPat && inputPat) {
        const handleSearchPat = () => {
            state.patient.query = inputPat.value;
            loadData('patient', true);
        };
        
        btnSearchPat.addEventListener("click", handleSearchPat);
        
        inputPat.addEventListener("keypress", (e) => { 
            if (e.key === "Enter") handleSearchPat(); 
        });

        if(btnMorePat) {
            btnMorePat.addEventListener("click", () => {
                loadData('patient', false);
            });
        }
    }
});
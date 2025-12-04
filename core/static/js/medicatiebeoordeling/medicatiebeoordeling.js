document.addEventListener("DOMContentLoaded", function() {
    
    function setupSearch(inputId, tableId) {
        const input = document.getElementById(inputId);
        const table = document.getElementById(tableId);
        
        if (!input || !table) return;

        input.addEventListener("input", function() {
            const filter = input.value.toLowerCase();
            // Zoek specifiek in de body van de tabel
            const tbody = table.querySelector("tbody");
            if (!tbody) return;
            
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

    setupSearch("searchAfdeling", "tableAfdeling");
    setupSearch("searchPatient", "tablePatient");
});
// core/static/js/admin/admin_panel.js

/* ---------- INLINE EDIT TOGGLES ---------- */
window.toggleEdit = function(id){
  const row = document.getElementById("edit-row-" + id);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "")
    ? "table-row"
    : "none";
};

window.toggleOrgEdit = function(id){
  const row = document.getElementById("org-edit-row-" + id);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "")
    ? "table-row"
    : "none";
};

/* ---------- CONFIRM DIALOGS ---------- */
window.confirmDelete = function(name){
  return confirm(
    "Weet je zeker dat je de gebruiker " +
    (name || "deze gebruiker") +
    " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!"
  );
};

window.confirmGroupDelete = function(name){
  return confirm(
    "Weet je zeker dat je de groep " +
    (name || "deze groep") +
    " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!"
  );
};

window.confirmOrgDelete = function(name){
  return confirm(
    "Weet je zeker dat je de organisatie " +
    (name || "deze organisatie") +
    " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!"
  );
};

/* ---------- LIVE SEARCH (BEWUST EXPLICIET) ---------- */
function liveSearch(inputId, tableId, rowClass){
  const input = document.getElementById(inputId);
  if(!input) return;

  input.addEventListener("input", function(){
    const q = this.value.toLowerCase();
    document.querySelectorAll(`#${tableId} .${rowClass}`).forEach(row=>{
      row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none";
    });

    // reset paginator (table.js)
    document
      .querySelector(`[data-table="#${tableId}"]`)
      ?.dispatchEvent(new Event("crud:reset"));
  });
}

document.addEventListener("DOMContentLoaded", function(){
  liveSearch("userSearch",  "userTable",  "user-row");
  liveSearch("groupSearch", "groupTable", "group-row");
  liveSearch("orgSearch",   "orgTable",   "org-row");
});
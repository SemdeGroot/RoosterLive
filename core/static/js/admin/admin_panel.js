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

window.toggleAfdelingEdit = function(id){
  const row = document.getElementById("afdeling-edit-row-" + id);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "") 
      ? "table-row" 
      : "none";
  };

window.toggleDagdeelEdit = function(code){
  const row = document.getElementById("dagdeel-edit-row-" + code);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "")
    ? "table-row"
    : "none";
};

window.toggleLocationEdit = function(id){
  const row = document.getElementById("location-edit-row-" + id);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "")
    ? "table-row"
    : "none";
};

window.toggleTaskEdit = function(id){
  const row = document.getElementById("task-edit-row-" + id);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "")
    ? "table-row"
    : "none";
};

window.confirmLocationDelete = function(name){
  return confirm(
    "Weet je zeker dat je de locatie '" +
    (name || "deze locatie") +
    "' wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!"
  );
};

window.confirmTaskDelete = function(name){
  return confirm(
    "Weet je zeker dat je de taak '" +
    (name || "deze taak") +
    "' wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!"
  );
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

window.confirmAfdelingDelete = function(name){
  return confirm(
    "Weet je zeker dat je de afdeling '" +
    (name || "deze afdeling") +
    "' wilt verwijderen?\n\n⚠️ Alle gekoppelde patiënten en historie worden verwijderd!"
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

function initTimeMasks(){
  if (typeof IMask === "undefined") return;

  document.querySelectorAll(".js-time").forEach((el) => {
    // voorkom dubbele init
    if (el.dataset.masked === "1") return;
    el.dataset.masked = "1";

    IMask(el, {
      mask: "Hh:Mm",
      blocks: {
        Hh: { mask: IMask.MaskedRange, from: 0, to: 23, maxLength: 2 },
        Mm: { mask: IMask.MaskedRange, from: 0, to: 59, maxLength: 2 },
      },
      overwrite: true,
    });
  });
}

document.addEventListener("DOMContentLoaded", function(){
  liveSearch("userSearch",  "userTable",  "user-row");
  liveSearch("groupSearch", "groupTable", "group-row");
  liveSearch("orgSearch",   "orgTable",   "org-row");
  liveSearch("afdelingSearch", "afdelingTable", "afdeling-row");
  liveSearch("locationSearch", "locationTable", "location-row");
  liveSearch("taskSearch", "taskTable", "task-row");

  initTimeMasks();
});
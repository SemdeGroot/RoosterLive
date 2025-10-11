window.toggleEdit = function(id){
  const row = document.getElementById("edit-row-" + id);
  if(!row) return;
  row.style.display = (row.style.display === "none" || row.style.display === "") ? "table-row" : "none";
}

window.confirmDelete = function(name){
  return confirm("Weet je zeker dat je " + (name || "deze gebruiker") + " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!");
}

window.confirmGroupDelete = function(name){
  return confirm("Weet je zeker dat je " + (name || "deze groep") + " wilt verwijderen?\n\n⚠️ Deze actie kan niet ongedaan worden gemaakt!");
}

/* Live gebruikers-zoekfunctie */
const userSearch = document.getElementById('userSearch');
if(userSearch){
  userSearch.addEventListener('input', function(){
    const q = this.value.toLowerCase();
    document.querySelectorAll('#userTable .user-row').forEach(row=>{
      const txt = row.innerText.toLowerCase();
      row.style.display = txt.includes(q) ? '' : 'none';
    });
  });
}
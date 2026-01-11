document.addEventListener("DOMContentLoaded", function(){
  const input = document.getElementById("whoSearch");
  if(!input) return;

  input.addEventListener("input", function(){
    const q = this.value.toLowerCase();
    document.querySelectorAll(`#whoTable .who-row`).forEach(row => {
      row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none";
    });

    // Reset paginator via jouw CustomEvent/reset
    document.querySelector(`[data-table="#whoTable"]`)
      ?.dispatchEvent(new CustomEvent("crud:reset"));
  });
});
// Optioneel: autofocus op het identifier veld, laat inline oninput gewoon staan.
document.addEventListener("DOMContentLoaded", () => {
  const id = document.getElementById("id_identifier");
  if (id) id.focus();
});

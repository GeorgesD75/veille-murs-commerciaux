/* Dates de calendrier locales : aucun rappel n'est envoyé par le navigateur. */
const SuiviMoteur = (() => {
  function dateValide(valeur) {
    if (typeof valeur !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(valeur)) return false;
    const d = new Date(valeur + "T12:00:00Z");
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0,10) === valeur;
  }
  function jourLocal(date = new Date()) {
    if (!Number.isFinite(date.getTime())) return "";
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
  }
  function etatRappel(s, jour = jourLocal()) {
    if (s?.statut === "abandonnee" || !dateValide(s?.rappel) || !dateValide(jour)) return "aucun";
    return s.rappel < jour ? "retard" : s.rappel === jour ? "aujourdhui" : "avenir";
  }
  function trier(a, b) {
    const da = dateValide(a.rappel) ? a.rappel : "9999-12-31";
    const db = dateValide(b.rappel) ? b.rappel : "9999-12-31";
    return da.localeCompare(db) || (b.maj || "").localeCompare(a.maj || "");
  }
  function formatDate(valeur) {
    return dateValide(valeur) ? valeur.split("-").reverse().join("/") : "";
  }
  return {dateValide, jourLocal, etatRappel, trier, formatDate};
})();

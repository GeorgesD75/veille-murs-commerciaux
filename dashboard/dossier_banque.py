"""Dossiers de financement Excel « à présenter au banquier », un par annonce.

Un classeur openpyxl à 3 feuilles, pré-rempli avec les données de l'annonce :
- Synthèse : le bien, le marché local, les hypothèses (cellules jaunes
  MODIFIABLES), le plan de financement, l'exploitation, le cash-flow et les
  ratios que regarde un banquier (DSCR, LTV) — le tout en FORMULES Excel :
  changer l'apport ou le taux recalcule tout, séance tenante, en rendez-vous ;
- Amortissement : tableau annuel indicatif + courbe du capital restant dû ;
- Annonce : les données brutes et sourcées (description, alertes, score).

Honnêteté avant tout : un loyer estimé est marqué comme tel, un rendement
suspect garde son avertissement — un dossier gonflé se retourne contre vous.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from pipeline.config import Config
from pipeline.modeles import Annonce, TypeMurs

# --- style : sobre, lisible, imprimable ------------------------------------

_MARQUE = "1D5240"
_TITRE = Font(name="Calibri", size=16, bold=True, color=_MARQUE)
_SECTION = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_SECTION_FOND = PatternFill("solid", fgColor=_MARQUE)
_LIBELLE = Font(name="Calibri", size=11, color="404040")
_VALEUR = Font(name="Calibri", size=11, bold=True)
_HYPOTHESE_FOND = PatternFill("solid", fgColor="FFF2CC")   # jaune : à ajuster
_NOTE = Font(name="Calibri", size=9, italic=True, color="808080")
_FILET = Border(bottom=Side(style="hair", color="D9D9D9"))

_EUR = '#,##0" €"'
_EUR_MOIS = '#,##0" €/mois"'
_PCT = "0.0%"
_M2 = '#,##0" m²"'

_LIGNES_AMORTISSEMENT = 30  # la durée est modifiable : IF() vide les années en trop


def _slug(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans_accents.lower()).strip("-") or "bien"


def _libelle_valeur(ws: Worksheet, ligne: int, libelle: str, valeur: Any,
                    fmt: str | None = None, hypothese: bool = False,
                    note: str | None = None) -> None:
    ws.cell(ligne, 1, libelle).font = _LIBELLE
    cellule = ws.cell(ligne, 2, valeur)
    cellule.font = _VALEUR
    if fmt:
        cellule.number_format = fmt
    if hypothese:
        cellule.fill = _HYPOTHESE_FOND
    ws.cell(ligne, 1).border = _FILET
    cellule.border = _FILET
    if note:
        n = ws.cell(ligne, 3, note)
        n.font = _NOTE
        n.alignment = Alignment(vertical="center")


def _section(ws: Worksheet, ligne: int, titre: str) -> None:
    ws.merge_cells(start_row=ligne, start_column=1, end_row=ligne, end_column=3)
    cellule = ws.cell(ligne, 1, titre)
    cellule.font = _SECTION
    cellule.fill = _SECTION_FOND
    cellule.alignment = Alignment(indent=1)


def _params(config: Config) -> dict[str, Any]:
    analyse = config["analyse"]
    d = dict(analyse.get("dossier_banque") or {})
    financement = analyse.get("financement") or {}
    return {
        "seuil_score": d.get("seuil_score", 60),
        "apport_pct": d.get("apport_pct", 20),
        "frais_acquisition_pct": d.get("frais_acquisition_pct", 8),
        "taxe_fonciere_mois_loyer": d.get("taxe_fonciere_mois_loyer", 1),
        "provision_entretien_pct": d.get("provision_entretien_pct", 5),
        "assurance_pno_eur_an": d.get("assurance_pno_eur_an", 300),
        "taux_pct": financement.get("taux_pct", 3.9),
        "duree_ans": financement.get("duree_ans", 20),
    }


def _verdict(annonce: Annonce, p: dict[str, Any]) -> str:
    """Phrase honnête pour la 1re page, aux hypothèses PAR DÉFAUT du classeur."""
    loyer = annonce.loyer_mensuel or annonce.loyer_mensuel_estime
    if not loyer or not annonce.prix:
        return ("Loyer inconnu à ce stade : le dossier est pré-rempli côté "
                "acquisition ; renseignez le loyer (feuille Synthèse) pour "
                "activer tous les calculs.")
    cout = annonce.prix * (1 + p["frais_acquisition_pct"] / 100)
    emprunt = cout * (1 - p["apport_pct"] / 100)
    t, n = p["taux_pct"] / 100 / 12, p["duree_ans"] * 12
    mensualite = emprunt * t / (1 - (1 + t) ** -n)
    charges = (loyer * p["taxe_fonciere_mois_loyer"] / 12
               + loyer * p["provision_entretien_pct"] / 100
               + p["assurance_pno_eur_an"] / 12)
    cf = loyer - mensualite - charges
    cf_txt = f"{abs(cf):,.0f}".replace(",", " ")
    taux_txt = str(p["taux_pct"]).replace(".", ",")
    prefixe = ("Sur la base d'un loyer ESTIMÉ (pas de bail signé à ce stade) : "
               if annonce.loyer_estime or not annonce.loyer_mensuel else "")
    hypotheses = (f"apport {p['apport_pct']} %, crédit {taux_txt} % "
                  f"sur {p['duree_ans']} ans, charges provisionnées")
    if cf >= 0:
        return (f"{prefixe}aux hypothèses de ce dossier ({hypotheses}), le bien "
                f"s'autofinance : le loyer couvre crédit et charges et laisse "
                f"environ +{cf_txt} €/mois.")
    return (f"{prefixe}aux hypothèses de ce dossier ({hypotheses}), il reste "
            f"environ {cf_txt} €/mois à financer en plus du loyer — "
            f"marge de négociation ou apport supplémentaire à prévoir.")


# --- feuille 1 : Synthèse ----------------------------------------------------

def _feuille_synthese(ws: Worksheet, a: Annonce, p: dict[str, Any]) -> None:
    ws.title = "Synthèse"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 17
    ws.column_dimensions["C"].width = 46
    ws.print_area = "A1:C56"

    ws.merge_cells("A1:C1")
    ws["A1"] = "Dossier de financement — Murs commerciaux"
    ws["A1"].font = _TITRE
    ws.merge_cells("A2:C2")
    ws["A2"] = a.titre
    ws["A2"].font = Font(size=12, bold=True)
    ws.merge_cells("A3:C3")
    ws["A3"] = f"{a.ville} ({a.code_postal}) — annonce {a.source} du {a.date_premiere_vue[:10]}"
    ws["A3"].font = _LIBELLE
    ws["A4"] = "Voir l'annonce en ligne"
    ws["A4"].hyperlink = a.url
    ws["A4"].font = Font(color="0563C1", underline="single", size=10)
    ws["B4"] = f"Dossier généré le {date.today():%d/%m/%Y}"
    ws["B4"].font = _NOTE

    _section(ws, 6, "LE BIEN")
    etat = ("Murs occupés — un locataire en place paie déjà un loyer"
            if a.type_murs is TypeMurs.MURS_OCCUPES
            else "Murs libres — local à louer après l'achat")
    _libelle_valeur(ws, 7, "État locatif", etat)
    _libelle_valeur(ws, 8, "Surface", a.surface_m2, _M2)
    _libelle_valeur(ws, 9, "Prix affiché", a.prix, _EUR)
    _libelle_valeur(ws, 10, "Prix au m²", "=IFERROR(B9/B8,\"\")", _EUR)
    note_loyer = None
    if a.loyer_mensuel:
        note_loyer = "loyer du bail en place (à faire confirmer par le bail)"
    elif a.loyer_mensuel_estime:
        note_loyer = "ESTIMATION au loyer de marché local — aucun bail ne le garantit"
    _libelle_valeur(ws, 11, "Loyer mensuel HT",
                    a.loyer_mensuel or a.loyer_mensuel_estime, _EUR,
                    hypothese=a.loyer_mensuel is None, note=note_loyer)
    if a.marche_prix_m2_bas and a.marche_prix_m2_haut:
        _libelle_valeur(
            ws, 12, "Marché local (prix/m²)",
            f"{a.marche_prix_m2_bas:,.0f} à {a.marche_prix_m2_haut:,.0f} €/m²".replace(",", " "),
            note=(f"ce bien est {abs(a.decote_pct):.0f} % "
                  f"{'SOUS' if a.decote_pct >= 0 else 'au-dessus de'} la médiane locale"
                  if a.decote_pct is not None else None),
        )

    _section(ws, 14, "HYPOTHÈSES — cellules jaunes à ajuster avec votre conseiller")
    _libelle_valeur(ws, 15, "Prix négocié retenu", a.prix, _EUR, hypothese=True,
                    note="par défaut le prix affiché — un prix demandé se négocie")
    _libelle_valeur(ws, 16, "Frais d'acquisition (notaire, garanties)",
                    p["frais_acquisition_pct"] / 100, _PCT, hypothese=True)
    _libelle_valeur(ws, 17, "Apport personnel", p["apport_pct"] / 100, _PCT, hypothese=True)
    _libelle_valeur(ws, 18, "Taux du crédit (hors assurance)",
                    p["taux_pct"] / 100, _PCT, hypothese=True)
    _libelle_valeur(ws, 19, "Durée du crédit (années)", p["duree_ans"], "0", hypothese=True)
    _libelle_valeur(ws, 20, "Taxe foncière (en mois de loyer par an)",
                    p["taxe_fonciere_mois_loyer"], "0.0", hypothese=True,
                    note="à remplacer par le montant réel dès que connu")
    _libelle_valeur(ws, 21, "Provision entretien & vacance (% du loyer)",
                    p["provision_entretien_pct"] / 100, _PCT, hypothese=True)
    _libelle_valeur(ws, 22, "Assurance propriétaire (PNO, €/an)",
                    p["assurance_pno_eur_an"], _EUR, hypothese=True)

    _section(ws, 24, "PLAN DE FINANCEMENT")
    _libelle_valeur(ws, 25, "Coût d'acquisition total", "=B15*(1+B16)", _EUR,
                    note="prix négocié + frais d'acquisition")
    _libelle_valeur(ws, 26, "Apport personnel", "=B25*B17", _EUR)
    _libelle_valeur(ws, 27, "Montant emprunté", "=B25-B26", _EUR)
    _libelle_valeur(ws, 28, "Mensualité du crédit", "=IFERROR(-PMT(B18/12,B19*12,B27),0)",
                    _EUR_MOIS)
    _libelle_valeur(ws, 29, "Service de la dette (annuel)", "=B28*12", _EUR)

    _section(ws, 31, "EXPLOITATION ANNUELLE")
    _libelle_valeur(ws, 32, "Loyers annuels HT", "=IFERROR(B11*12,0)", _EUR)
    _libelle_valeur(ws, 33, "− Taxe foncière", "=-IFERROR(B11*B20,0)", _EUR)
    _libelle_valeur(ws, 34, "− Entretien & vacance locative", "=-B32*B21", _EUR)
    _libelle_valeur(ws, 35, "− Assurance PNO", "=-B22", _EUR)
    _libelle_valeur(ws, 36, "Revenu net avant crédit", "=B32+B33+B34+B35", _EUR)
    _libelle_valeur(ws, 37, "− Remboursement du crédit", "=-B29", _EUR)
    _libelle_valeur(ws, 38, "Cash-flow annuel", "=B36-B29", _EUR)
    _libelle_valeur(ws, 39, "Cash-flow mensuel", "=B38/12", _EUR_MOIS,
                    note="positif : le bien se paie tout seul, loyer ≥ crédit + charges")
    ws["B39"].font = Font(size=13, bold=True)
    ws.conditional_formatting.add("B38:B39", CellIsRule(
        operator="greaterThanOrEqual", formula=["0"],
        fill=PatternFill("solid", fgColor="E2EFDA")))
    ws.conditional_formatting.add("B38:B39", CellIsRule(
        operator="lessThan", formula=["0"],
        fill=PatternFill("solid", fgColor="FCE4EC")))

    _section(ws, 41, "LES RATIOS QUE REGARDE LE BANQUIER")
    _libelle_valeur(ws, 42, "Rendement brut", "=IFERROR(B32/B15,\"\")", _PCT,
                    note="loyer annuel ÷ prix — la base de comparaison des biens")
    _libelle_valeur(ws, 43, "Rendement net avant crédit", "=IFERROR(B36/B25,\"\")", _PCT,
                    note="après taxe foncière, entretien et assurance")
    _libelle_valeur(ws, 44, "DSCR — couverture de la dette", "=IFERROR(B36/B29,\"\")", "0.00",
                    note="revenu net ÷ crédit : ≥ 1,20 rassure une banque")
    ws.conditional_formatting.add("B44", CellIsRule(
        operator="greaterThanOrEqual", formula=["1.2"],
        fill=PatternFill("solid", fgColor="E2EFDA")))
    ws.conditional_formatting.add("B44", CellIsRule(
        operator="lessThan", formula=["1"],
        fill=PatternFill("solid", fgColor="FCE4EC")))
    _libelle_valeur(ws, 45, "LTV — part financée par la banque", "=IFERROR(B27/B15,\"\")",
                    _PCT, note="≤ 80 % est la zone de confort bancaire")
    _libelle_valeur(ws, 46, "Effort d'épargne mensuel si négatif", "=MAX(0,-B38/12)",
                    _EUR_MOIS)
    _libelle_valeur(ws, 47, "Score de l'outil de veille",
                    f"{a.score}/100" if a.score is not None else "—",
                    note="rendement, emplacement, prix vs marché, proximité")

    # verdict en clair, pour un lecteur pressé ou néophyte
    ws.merge_cells("A49:C51")
    verdict = ws["A49"]
    verdict.value = "EN CLAIR — " + _verdict(a, p)
    verdict.alignment = Alignment(wrap_text=True, vertical="top")
    verdict.font = Font(size=11, italic=True)
    if "rendement_anormalement_eleve" in (a.flags or []):
        ws.merge_cells("A52:C53")
        alerte = ws["A52"]
        alerte.value = ("⚠ AVERTISSEMENT : le rendement affiché par le vendeur est "
                        "anormalement élevé. Exiger le bail et les quittances avant "
                        "toute offre — ce dossier reprend le loyer annoncé tel quel.")
        alerte.alignment = Alignment(wrap_text=True, vertical="top")
        alerte.font = Font(size=10, bold=True, color="98351B")

    # petit bloc de données pour le graphique (à droite, hors zone d'impression)
    ws["E6"] = "Loyer mensuel"
    ws["F6"] = "=IFERROR(B11,0)"
    ws["E7"] = "Crédit + charges / mois"
    ws["F7"] = "=B28-(B33+B34+B35)/12"
    ws["E8"] = "Cash-flow"
    ws["F8"] = "=B39"
    for r in (6, 7, 8):
        ws.cell(r, 5).font = _NOTE
        ws.cell(r, 6).number_format = _EUR

    graphique = BarChart()
    graphique.type = "col"
    graphique.title = "Le loyer paie-t-il le crédit ?"
    graphique.legend = None
    graphique.y_axis.numFmt = _EUR
    graphique.height, graphique.width = 8, 12
    graphique.add_data(Reference(ws, min_col=6, min_row=6, max_row=8))
    graphique.set_categories(Reference(ws, min_col=5, min_row=6, max_row=8))
    ws.add_chart(graphique, "E10")


# --- feuille 2 : Amortissement ----------------------------------------------

def _feuille_amortissement(ws: Worksheet) -> None:
    ws.title = "Amortissement"
    ws.sheet_view.showGridLines = False
    entetes = ["Année", "Capital dû en début d'année", "Intérêts de l'année",
               "Capital remboursé", "Capital restant dû"]
    for col, entete in enumerate(entetes, start=1):
        c = ws.cell(1, col, entete)
        c.font = _SECTION
        c.fill = _SECTION_FOND
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[chr(64 + col)].width = 22
    ws.cell(2, 6, "Tableau indicatif (pas annuel) — l'offre de prêt de la banque fait foi.").font = _NOTE

    duree = "$G$1"
    ws["G1"] = "='Synthèse'!B19"
    ws["G2"] = "='Synthèse'!B18"
    ws["G3"] = "='Synthèse'!B29"
    ws.column_dimensions["G"].hidden = True
    for i in range(_LIGNES_AMORTISSEMENT):
        r = i + 2
        ws.cell(r, 1, i + 1)
        debut = "'Synthèse'!$B$27" if i == 0 else f"E{r - 1}"
        garde = f"A{r}<={duree}"
        ws.cell(r, 2, f"=IF({garde},{debut},\"\")")
        ws.cell(r, 3, f"=IF({garde},B{r}*$G$2,\"\")")
        ws.cell(r, 4, f"=IF({garde},MIN(B{r},$G$3-C{r}),\"\")")
        ws.cell(r, 5, f"=IF({garde},MAX(0,B{r}-D{r}),\"\")")
        for col in (2, 3, 4, 5):
            ws.cell(r, col).number_format = _EUR

    courbe = LineChart()
    courbe.title = "Capital restant dû"
    courbe.legend = None
    courbe.y_axis.numFmt = _EUR
    courbe.x_axis.title = "Année"
    courbe.height, courbe.width = 9, 16
    courbe.add_data(Reference(ws, min_col=5, min_row=2,
                              max_row=_LIGNES_AMORTISSEMENT + 1))
    courbe.set_categories(Reference(ws, min_col=1, min_row=2,
                                    max_row=_LIGNES_AMORTISSEMENT + 1))
    ws.add_chart(courbe, "I2")


# --- feuille 3 : Annonce (les faits, sourcés) --------------------------------

def _feuille_annonce(ws: Worksheet, a: Annonce) -> None:
    ws.title = "Annonce"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 100
    lignes: list[tuple[str, Any]] = [
        ("Titre", a.titre),
        ("Lien", a.url),
        ("Ville", f"{a.ville} ({a.code_postal})"),
        ("Source", a.source),
        ("Première détection", a.date_premiere_vue[:10]),
        ("Type", "Murs occupés" if a.type_murs is TypeMurs.MURS_OCCUPES else "Murs libres"),
        ("Caractéristiques", " · ".join(a.caracteristiques) or "—"),
        ("Lecture du prix", a.lecture_prix or "—"),
        ("Alertes", " · ".join(a.flags) or "aucune"),
        ("Description", a.description or "—"),
    ]
    for r, (libelle, valeur) in enumerate(lignes, start=1):
        ws.cell(r, 1, libelle).font = Font(bold=True)
        cellule = ws.cell(r, 2, valeur)
        cellule.alignment = Alignment(wrap_text=True, vertical="top")
        if libelle == "Lien":
            cellule.hyperlink = a.url
            cellule.font = Font(color="0563C1", underline="single")
    ws.row_dimensions[len(lignes)].height = 110


# --- point d'entrée -----------------------------------------------------------

def generer_dossier(annonce: Annonce, config: Config, cible: Path) -> None:
    """Écrit le classeur d'UNE annonce (utile aux tests)."""
    p = _params(config)
    wb = Workbook()
    _feuille_synthese(wb.active, annonce, p)
    _feuille_amortissement(wb.create_sheet())
    _feuille_annonce(wb.create_sheet(), annonce)
    cible.parent.mkdir(parents=True, exist_ok=True)
    wb.save(cible)


def generer_dossiers(
    annonces: dict[str, Annonce], config: Config, dossier: Path
) -> dict[str, str]:
    """Génère les classeurs des annonces retenues à score ≥ seuil.

    Retourne {id annonce: nom de fichier} pour les liens du dashboard.
    Le répertoire est reconstruit à chaque run : pas de dossier fantôme
    pointant vers une annonce disparue.
    """
    seuil = _params(config)["seuil_score"]
    dossier.mkdir(parents=True, exist_ok=True)
    for ancien in dossier.glob("*.xlsx"):
        ancien.unlink()
    resultats: dict[str, str] = {}
    for a in annonces.values():
        if a.exclue or a.prix is None or (a.score or 0) < seuil:
            continue
        nom = f"dossier-{_slug(a.ville)}-{a.id[:8]}.xlsx"
        generer_dossier(a, config, dossier / nom)
        resultats[a.id] = nom
    return resultats

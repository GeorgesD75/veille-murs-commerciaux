"""Messages à relire et copier ; aucune transmission automatique."""
from pipeline.fiabilite import diagnostiquer
from pipeline.modeles import Annonce


def message_negociation(a: Annonce, plan: dict) -> str:
    """Question chiffrée à relire, sans déclaration ferme d'intention d'acheter."""
    prix = plan.get("prix_ouverture")
    if prix is None:
        return ""
    euros = lambda n: f"{n:,.0f} €".replace(",", " ")
    return "\n".join([
        f"Objet : {a.titre} à {a.ville} — échange sur le prix", "", "Bonjour,", "",
        f"Je m’intéresse à vos murs commerciaux : {a.url}",
        f"Au regard du loyer annoncé de {euros(a.loyer_mensuel)}/mois et de mon budget d’acquisition, "
        f"seriez-vous ouverts à une discussion autour de {euros(prix)} ?", "",
        "Avant de me positionner, je souhaite confirmer la disponibilité des murs seuls, le bail et les quittances, "
        "le loyer HT/HC effectivement encaissé, les charges restant au bailleur, la taxe foncière et les travaux votés.",
        "Pouvez-vous préciser la base du prix (net vendeur ou honoraires inclus), le montant et le redevable des honoraires, "
        "ainsi que le régime de TVA applicable ?", "",
        "Si ce niveau de prix peut être discuté, je souhaiterais recevoir les pièces du dossier et organiser une visite.", "",
        "Merci par avance pour votre retour.", "Cordialement,", "[Votre nom]", "[Votre téléphone]",
    ])


def messages_contact(a: Annonce) -> dict[str, str]:
    d = diagnostiquer(a)
    reference = f"{a.titre} à {a.ville}"
    intro = [f"Objet : {reference} — renseignements", "", "Bonjour,", "",
             f"Je vous contacte au sujet de cette annonce : {a.url}",
             "Je recherche des murs commerciaux pour un investissement locatif.", ""]
    essentiels = ["Le bien est-il toujours disponible, et le prix porte-t-il bien sur les murs seuls, hors fonds de commerce ou droit au bail ?"]
    if d["transaction"]["nature"] != "murs":
        essentiels[0] = "Le bien est-il toujours disponible, et le prix porte-t-il bien sur les murs seuls en pleine propriété, hors fonds de commerce ou droit au bail ?"
    if d["occupation"] == "libre":
        essentiels.extend(["Le local est-il toujours libre et depuis quand ?",
                           "Quel était le dernier loyer réellement encaissé, HT et hors charges (par mois ou par an) ?"])
    else:
        essentiels.extend(["Est-il actuellement loué ? Si oui, depuis quand et pour quelle durée de bail ?",
                           "Quel est le loyer actuel HT et hors charges (par mois ou par an) ?"])
    essentiels.extend(["Quel montant de charges reste au propriétaire, avec la taxe foncière comprise ou indiquée à part ?",
                       "Les loyers sont-ils à jour ? Y a-t-il eu des impayés récents ?"])
    signature = ["", "Merci par avance pour votre retour.", "Cordialement,", "[Votre nom]", "[Votre téléphone]"]
    court = "\n".join([f"Objet : {reference}", "", "Bonjour,", "",
                       f"Votre local m’intéresse : {a.url}",
                       "Avant de convenir d’une visite, pourriez-vous me confirmer ces quelques points ?", ""] +
                       [f"- {q}" for q in essentiels] + signature)
    pieces = ["Adresse exacte, référence du lot et plan coté avec ventilation des surfaces ; destination autorisée et règlement de copropriété.",
              "Prix net vendeur, honoraires (montant et personne redevable), régime de TVA et raison de la vente.",
              "Dernier avis de taxe foncière, décompte annuel des charges et répartition bailleur/locataire.",
              "Trois derniers procès-verbaux d’AG, travaux votés ou envisagés et appels de fonds restant à payer.",
              "Diagnostics disponibles, état du local et travaux de mise en conformité identifiés."]
    pieces.append("Activités autorisées et restrictions du bail ou de la copropriété ; éléments comparables justifiant le loyer de relocation et le délai de commercialisation, travaux de remise en location à prévoir.")
    if d["occupation"] == "libre":
        pieces.insert(1, "Dernier bail et dernier loyer encaissé, date et motif de libération, historique de commercialisation et travaux nécessaires avant relocation.")
    else:
        pieces.insert(1, "Bail signé et avenants, date d’effet, échéances triennales, congé éventuel, dépôt de garantie et répartition des travaux.")
        pieces.insert(2, "État des encaissements et éventuels impayés sur les douze derniers mois ; activité et ancienneté du locataire, éléments de solvabilité communicables.")
    dossier = "\n".join(intro + ["Pour étudier le dossier et préparer une visite utile, pourriez-vous me transmettre les éléments suivants, en masquant les données personnelles non nécessaires ?", ""] +
                         [f"- {q}" for q in pieces] + signature)
    relance = "\n".join([f"Objet : {reference} — suivi de ma demande", "", "Bonjour,", "",
                         f"Je reviens vers vous au sujet de cette annonce : {a.url}",
                         "Le bien est-il toujours disponible ? Je reste intéressé par les informations et documents demandés dans mon précédent message.",
                         "Si le dossier est toujours ouvert, quelles seraient vos disponibilités pour une visite ?"] + signature)
    return {"court": court, "dossier": dossier, "relance": relance}

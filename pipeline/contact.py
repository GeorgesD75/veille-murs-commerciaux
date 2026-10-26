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
    essentiels = ["Le bien est-il toujours disponible et s’agit-il bien de la vente des murs seuls, hors fonds de commerce et droit au bail ?",
                  "Pouvez-vous préciser la surface privative, dont la surface commerciale en rez-de-chaussée et les éventuelles annexes ?"]
    if d["occupation"] == "occupe":
        loyer = f"Le loyer annoncé de {a.loyer_mensuel:,.0f} €/mois".replace(",", " ") if a.loyer_mensuel else "Le loyer actuel"
        if a.loyer_origine == "rendement":
            loyer = "Le loyer actuel (plutôt que le seul taux de rendement annoncé)"
        essentiels.append(f"{loyer} est-il bien HT et hors charges, effectivement encaissé ? Quelle est la prochaine échéance de résiliation du bail ?")
    elif d["occupation"] == "libre":
        essentiels.append("Depuis quand le local est-il libre ? Quel était le dernier loyer réellement encaissé et à quelle date ?")
    else:
        essentiels.append("Le local sera-t-il vendu libre ou occupé ? S’il est loué, quel est le loyer annuel actuel HT/HC et la prochaine échéance du bail ?")
    essentiels.extend(["Quel est le prix total honoraires inclus, et quel budget annuel reste au propriétaire (charges, taxe foncière, travaux votés) ?"])
    if d["bloquant"]:
        essentiels.insert(1, "J’ai relevé des informations à rapprocher : pouvez-vous confirmer les chiffres de la fiche et de l’annonce (prix, surface et localisation) ?")
    signature = ["", "Merci par avance pour votre retour.", "Cordialement,", "[Votre nom]", "[Votre téléphone]"]
    court = "\n".join(intro + ["Avant d’envisager une visite, pourriez-vous me préciser ces points ?", ""] +
                       [f"- {q}" for q in essentiels] + signature)
    pieces = ["Adresse exacte, référence du lot et plan coté avec ventilation des surfaces ; destination autorisée et règlement de copropriété.",
              "Prix net vendeur, honoraires (montant et personne redevable), régime de TVA et raison de la vente.",
              "Dernier avis de taxe foncière, décompte annuel des charges et répartition bailleur/locataire.",
              "Trois derniers procès-verbaux d’AG, travaux votés ou envisagés et appels de fonds restant à payer.",
              "Diagnostics disponibles, état du local et travaux de mise en conformité identifiés."]
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

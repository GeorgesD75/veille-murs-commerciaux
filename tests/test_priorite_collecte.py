from sources.geolocaux import SourceGeolocaux


def test_budget_geolocaux_consomme_dabord_pres_du_domicile(monkeypatch):
    source = SourceGeolocaux(communes_prioritaires=["Paris", "Saint-Ouen"])
    listings = [("/loin", "77", "Meaux", "77100", 1),
                ("/proche", "93", "Saint-Ouen", "93400", 1),
                ("/paris", "75", None, None, 1)]
    vus = []
    monkeypatch.setattr(source, "_decouvrir_listings", lambda: listings)
    monkeypatch.setattr(source, "_collecter_listing", lambda chemin, *args: vus.append(chemin))
    source.collecter()
    assert vus == ["/paris", "/proche", "/loin"]

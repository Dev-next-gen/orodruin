# API Keys — à récupérer

Toutes gratuites. Range-les dans `backend/.env` (jamais commité). Format :
```
GOOGLE_MAPS_KEY=...        # déjà fourni ✅
FIRMS_MAP_KEY=...
ACLED_KEY=...
ACLED_EMAIL=...
AISSTREAM_KEY=...
SHODAN_KEY=...
```

---

## 🔴 Priorité 1 — à faire maintenant (instantané, gratuit)

### NASA FIRMS — feux actifs mondiaux (couche Feu, tous pays)
- **URL** : https://firms.modaps.eosdis.nasa.gov/api/map_key/
- **Procédure** : entre ton email → la MAP_KEY s'affiche immédiatement (pas de validation).
- **Débloque** : détections de feux VIIRS/MODIS sur toute la planète, mise à jour ~toutes les 3 h.
- **Variable** : `FIRMS_MAP_KEY`

### ACLED — conflits armés (185k+ événements géolocalisés)
- **URL** : https://acleddata.com/user/register (myACLED)
- **⚠️ Système OAuth, pas de clé statique** : l'app utilise email+password → token auto.
- **⚠️ BLOCAGE TIER** : l'accès API n'existe QUE pour les niveaux **Research / Partner / Enterprise**.
  Un compte email perso démarre en **Open** = pas d'API (403 "Access denied").
- **Pour débloquer** : dans myACLED, demander le passage en **Research** (usage recherche/veille),
  ou écrire à **access@acleddata.com** avec la justification. Délai ~1 jour ouvré.
  Un email institutionnel accélère l'attribution automatique.
- **État** : compte créé ✅ (OAuth OK), tier Open ❌ → module codé et prêt, en attente d'upgrade.
- **Variables** : `ACLED_EMAIL`, `ACLED_PASSWORD` (déjà dans `.env`)

### AISStream — trafic maritime temps réel (navires)
- **URL** : https://aisstream.io/apikeys (login GitHub/Google → *Create API Key*)
- **Débloque** : positions AIS des navires en direct (WebSocket), gratuit.
- **Variable** : `AISSTREAM_KEY`

---

## 🟠 Priorité 2 — utiles ensuite

### Shodan — infrastructures/systèmes exposés
- **URL** : https://account.shodan.io/register
- **Débloque** : recherche d'appareils/IPs exposés (couche cyber). Free tier limité mais suffisant.
- **Variable** : `SHODAN_KEY`

### Copernicus / Sentinel Hub — imagerie satellite (ESA, gratuit)
- **URL** : https://dataspace.copernicus.eu/ (crée un compte → *OAuth clients*)
- **Débloque** : imagerie Sentinel-2 10 m, overlays satellite à la demande.
- **Variables** : `SENTINELHUB_CLIENT_ID`, `SENTINELHUB_CLIENT_SECRET`

---

## 🟢 Priorité 3 — plus tard / niches

- **OpenSanctions** — entités sanctionnées. Données bulk **gratuites** (téléchargement), API payante. https://www.opensanctions.org/datasets/
- **GreyNoise** — bruit réseau internet. https://www.greynoise.io/ (community free)
- **Censys** — infra + TLS. https://search.censys.io/ (compte gratuit → API ID/secret)
- **ADS-B Exchange** — vols militaires. Via RapidAPI (payant) ou feed communautaire.

---

## ✅ Sans clé (déjà intégrés ou intégrables directement)

- **GDELT** — événements mondiaux /15 min. **Aucune clé.** ✅ (en prod)
- **USGS** — séismes temps réel (GeoJSON ouvert).
- **EFFIS** (European Forest Fire Info System) — WMS ouvert, complément Europe pour les feux.
- **ReliefWeb (UN OCHA)** — crises humanitaires, API ouverte `api.reliefweb.int`.

---

### Déjà fournie
- **Google Maps Platform** (`GOOGLE_MAPS_KEY`) — 3D photoréaliste. ✅

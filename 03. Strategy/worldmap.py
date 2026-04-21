"""
worldmap.py  —  Carte géographique des sièges et courtiers (Project 7 Seas)
"""

import folium

# ── Courtiers & dépositaires ──────────────────────────────────────────────────
#
# Note Revolut : deux entités distinctes
#   - Revolut Ltd (Londres)                    → crypto, FX, métaux physiques
#   - Revolut Securities Europe UAB (Vilnius)  → actions, ETFs clients UE
# Source : revolut.com/legal/terms — à vérifier si doute sur un produit précis

BROKERS = [
    {
        "name":       "Revolut Ltd",
        "subtitle":   "Crypto / FX / Métaux",
        "note":       "Entité UK — crypto, change, métaux précieux",
        "lat": 51.5036, "lon": -0.0196,
        "country":    "🇬🇧 Royaume-Uni",
        "color":      "purple",
        "regulator":  "FCA (Financial Conduct Authority)",
        "protection": "FSCS jusqu'à £85 000 (cash uniquement, pas les crypto)",
        "products":   ["Crypto", "FX", "Métaux physiques", "CFDs"],
        "website":    "revolut.com",
    },
    {
        "name":       "Revolut Securities Europe UAB",
        "subtitle":   "Courtier titres (UE)",
        "note":       "Entité lituanienne — actions, ETFs pour clients européens",
        "lat": 54.6872, "lon": 25.2797,
        "country":    "🇱🇹 Lituanie",
        "color":      "purple",
        "regulator":  "Banque de Lituanie (BdL)",
        "protection": "Garantie investisseur IID jusqu'à €20 000 par client",
        "products":   ["Actions", "ETFs", "Obligations"],
        "website":    "revolut.com",
    },
    {
        "name":       "N26 Bank GmbH",
        "subtitle":   "Néobanque",
        "note":       "Dépôts, épargne",
        "lat": 52.5200, "lon": 13.3800,
        "country":    "🇩🇪 Allemagne",
        "color":      "blue",
        "regulator":  "BaFin (Bundesanstalt für Finanzdienstleistungsaufsicht)",
        "protection": "Garantie dépôts DGS jusqu'à €100 000 par client",
        "products":   ["Compte courant", "Épargne", "Assurance"],
        "website":    "n26.com",
    },
    {
        "name":       "Interactive Brokers LLC",
        "subtitle":   "Courtier institutionnel",
        "note":       "Actions, options, futures, forex — siège Greenwich CT",
        "lat": 41.0534, "lon": -73.6272,
        "country":    "🇺🇸 États-Unis",
        "color":      "red",
        "regulator":  "SEC / FINRA (États-Unis), IIROC (Canada), FCA (UK)",
        "protection": "SIPC jusqu'à $500 000 (dont $250 000 cash) + Lloyd's excess",
        "products":   ["Actions", "Options", "Futures", "Forex", "ETFs", "Obligations", "CFDs"],
        "website":    "interactivebrokers.com",
    },
    {
        "name":       "Trade Republic Bank GmbH",
        "subtitle":   "Courtier / Banque",
        "note":       "Actions, ETFs, obligations, épargne",
        "lat": 52.5200, "lon": 13.4300,
        "country":    "🇩🇪 Allemagne",
        "color":      "green",
        "regulator":  "BaFin + BCE (licence bancaire depuis 2023)",
        "protection": "Garantie dépôts DGS €100 000 + garantie titres €20 000",
        "products":   ["Actions", "ETFs", "Crypto", "Obligations", "Plans d'épargne", "Comptes rémunérés"],
        "website":    "traderepublic.com",
    },
    {
        "name":       "Trading 212 EU Ltd",
        "subtitle":   "Courtier (clients EU)",
        "note":       "Entité chypriote — licence CySEC — actions, CFDs pour clients européens post-Brexit",
        "lat": 34.6751, "lon": 33.0441,
        "country":    "🇨🇾 Chypre",
        "color":      "orange",
        "regulator":  "CySEC (Cyprus Securities and Exchange Commission)",
        "protection": "Fonds de compensation investisseurs ICF jusqu'à €20 000",
        "products":   ["Actions", "ETFs", "CFDs", "Forex", "Comptes rémunérés"],
        "website":    "trading212.com",
    },
    {
        "name":       "BourseDirecte",
        "subtitle":   "Courtier français",
        "note":       "PEA, CTO, assurance-vie — filiale Société Générale",
        "lat": 48.8566, "lon": 2.3522,
        "country":    "🇫🇷 France",
        "color":      "darkblue",
        "regulator":  "AMF + ACPR (Autorité de Contrôle Prudentiel et de Résolution)",
        "protection": "Garantie titres FGDR €70 000 + garantie dépôts €100 000",
        "products":   ["PEA", "CTO", "Assurance-vie", "PEA-PME", "FCPI/FIP"],
        "website":    "boursedirect.fr",
    },
]

# ── Couleurs par secteur ──────────────────────────────────────────────────────

SECTOR_COLORS = {
    "IA/Tech":        "#3a86ff",
    "Santé":          "#ffd93d",
    "Infrastructure": "#a78bfa",
    "Défense":        "#4ecdc4",
    "Nucléaire":      "#06d6a0",
    "Conso":          "#aaaaaa",
    "Crypto":         "#ff9f1c",
    "Métaux":         "#f5c542",
    "Spatial":        "#ff6b6b",
    "Quantum":        "#b185db",
    "Spéculatif":     "#e63946",
}

# ── Sièges sociaux ────────────────────────────────────────────────────────────
#
# GLD, SLV, BTC-USD, ETH-USD, SOL-USD : pas de HQ corporate.
# Placés aux coordonnées de l'entité Revolut dépositaire.

COMPANY_HQ = [
    # ── IA / Tech ────────────────────────────────────────────────────────────
    {"ticker": "NVDA",    "name": "NVIDIA",               "lat": 37.3693, "lon": -122.0169, "sector": "IA/Tech",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Leader GPU pour IA, data centers, véhicules autonomes. Cuda ecosystem dominant."},
    {"ticker": "MSFT",    "name": "Microsoft",            "lat": 47.6423, "lon": -122.1301, "sector": "IA/Tech",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Cloud Azure #2 mondial, OpenAI partner, GitHub Copilot, Office 365."},
    {"ticker": "GOOGL",   "name": "Alphabet",             "lat": 37.4220, "lon": -122.0841, "sector": "IA/Tech",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Moteur de recherche dominant, Google Cloud, DeepMind, Waymo."},
    {"ticker": "META",    "name": "Meta",                 "lat": 37.4845, "lon": -122.1477, "sector": "IA/Tech",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Facebook/Instagram/WhatsApp. Investissement massif IA et Metaverse (Ray-Ban)."},
    {"ticker": "AAPL",    "name": "Apple",                "lat": 37.3346, "lon": -122.0090, "sector": "IA/Tech",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Écosystème fermé premium. Services en accélération. Apple Intelligence (IA on-device)."},
    {"ticker": "TSM",     "name": "TSMC",                 "lat": 24.7881, "lon": 120.9969,  "sector": "IA/Tech",
     "exchange": "NYSE (ADR)", "country": "🇹🇼 Taïwan",
     "desc": "Fondeur N°1 mondial — fabrique les puces NVIDIA, Apple, AMD. Nœuds 3nm/2nm."},
    {"ticker": "ORCL",    "name": "Oracle",               "lat": 30.2672, "lon": -97.7431,  "sector": "IA/Tech",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Bases de données cloud, Oracle Cloud Infrastructure. Croissance data center IA."},
    # ── Santé / Biotech ──────────────────────────────────────────────────────
    {"ticker": "LLY",     "name": "Eli Lilly",            "lat": 39.7684, "lon": -86.1581,  "sector": "Santé",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Leader GLP-1 (Mounjaro, Zepbound). Pipeline diabète/obésité/Alzheimer massif."},
    {"ticker": "VKTX",    "name": "Viking Therapeutics",  "lat": 32.9200, "lon": -117.2000, "sector": "Santé",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "GLP-1 oral en développement (VK2735). Concurrent direct de LLY/NVO."},
    {"ticker": "BEAM",    "name": "Beam Therapeutics",    "lat": 42.3650, "lon": -71.0900,  "sector": "Santé",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Édition de bases ADN (base editing). Pipeline drépanocytose, PCSK9, maladies rares."},
    {"ticker": "CATX",    "name": "Perspective Therap.",  "lat": 32.7500, "lon": -117.1500, "sector": "Santé",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Radiothérapie ciblée (alpha-emitters). Traitement cancers solides réfractaires."},
    {"ticker": "BDMD",    "name": "Baird Medical",        "lat": 22.5550, "lon": 114.0800,  "sector": "Santé",
     "exchange": "NASDAQ", "country": "🇨🇳 Chine (HK)",
     "desc": "Dispositifs médicaux ablation micro-ondes. Marché chinois thyroïde/sein."},
    # ── Infrastructure ───────────────────────────────────────────────────────
    {"ticker": "CAT",     "name": "Caterpillar",          "lat": 32.8537, "lon": -96.9743,  "sector": "Infrastructure",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Engins de chantier, moteurs, énergie. Bénéficie des plans infrastructure US/EU."},
    {"ticker": "DE",      "name": "John Deere",           "lat": 41.5067, "lon": -90.5151,  "sector": "Infrastructure",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Leader machinisme agricole mondial. Pivot vers l'agriculture de précision / IA."},
    {"ticker": "URI",     "name": "United Rentals",       "lat": 41.0534, "lon": -73.5387,  "sector": "Infrastructure",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Location d'équipements N°1 US. Exposition directe aux chantiers data centers et infra."},
    {"ticker": "HEI.DE",  "name": "Heidelberg Materials", "lat": 49.4075, "lon": 8.6924,    "sector": "Infrastructure",
     "exchange": "XETRA", "country": "🇩🇪 Allemagne",
     "desc": "Ciment, béton, granulats. Bénéficiaire plan ReArm Europe et reconstruction Ukraine."},
    # ── Défense ──────────────────────────────────────────────────────────────
    {"ticker": "RHM.DE",  "name": "Rheinmetall",          "lat": 51.2217, "lon": 6.7762,    "sector": "Défense",
     "exchange": "XETRA", "country": "🇩🇪 Allemagne",
     "desc": "Munitions, blindés (Lynx), systèmes de défense aérienne. Carnet de commandes record."},
    {"ticker": "HAG.DE",  "name": "Hensoldt",             "lat": 48.0430, "lon": 11.6150,   "sector": "Défense",
     "exchange": "XETRA", "country": "🇩🇪 Allemagne",
     "desc": "Capteurs, radars, optronique. Fournisseur Eurofighter, systèmes de surveillance."},
    {"ticker": "HO.PA",   "name": "Thales",               "lat": 48.8975, "lon": 2.2413,    "sector": "Défense",
     "exchange": "Euronext Paris", "country": "🇫🇷 France",
     "desc": "Défense, aérospatiale, cybersécurité, transport. Contrats OTAN et clients export."},
    {"ticker": "LDO.MI",  "name": "Leonardo",             "lat": 41.9028, "lon": 12.4964,   "sector": "Défense",
     "exchange": "Borsa Italiana", "country": "🇮🇹 Italie",
     "desc": "Hélicoptères (AW), électronique de défense, systèmes de combat. Actionnaire : État italien."},
    {"ticker": "BA.L",    "name": "BAE Systems",          "lat": 51.5200, "lon": -0.0800,   "sector": "Défense",
     "exchange": "LSE", "country": "🇬🇧 Royaume-Uni",
     "desc": "Sous-marins nucléaires, frégates, F-35, cyber. Contrats UK/US/Australie (AUKUS)."},
    # ── Nucléaire / Énergie ──────────────────────────────────────────────────
    {"ticker": "SMR",     "name": "NuScale Power",        "lat": 45.5231, "lon": -122.6765, "sector": "Nucléaire",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Petit réacteur modulaire (SMR) certifié NRC. Projets Utah UAMPS (suspendu) et export."},
    {"ticker": "CCJ",     "name": "Cameco",               "lat": 52.1332, "lon": -106.6700, "sector": "Nucléaire",
     "exchange": "NYSE / TSX", "country": "🇨🇦 Canada",
     "desc": "Producteur uranium N°2 mondial. Mines Cigar Lake, McArthur River. Westinghouse (49%)."},
    {"ticker": "NNE",     "name": "Nano Nuclear Energy",  "lat": 40.7580, "lon": -73.9700,  "sector": "Nucléaire",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Micro-réacteurs portables ZEUS et ODIN. Stade R&D, forte composante spéculative."},
    {"ticker": "OKLO",    "name": "Oklo",                 "lat": 37.3541, "lon": -121.9552, "sector": "Nucléaire",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Réacteur à neutrons rapides Aurora (1,5 MW). Accord avec Sam Altman (OpenAI)."},
    {"ticker": "ENPH",    "name": "Enphase Energy",       "lat": 37.5485, "lon": -121.9886, "sector": "Nucléaire",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Micro-onduleurs solaires + batteries résidentielles. Leader marchés US/EU."},
    # ── Conso / Services ─────────────────────────────────────────────────────
    {"ticker": "CL",      "name": "Colgate-Palmolive",    "lat": 40.7580, "lon": -73.9855,  "sector": "Conso",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Biens de grande consommation défensifs. Dentifrice, soins, Hill's Pet Nutrition."},
    {"ticker": "COST",    "name": "Costco",               "lat": 47.5301, "lon": -122.0326, "sector": "Conso",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Entrepôts-clubs à abonnement. Résilient en récession, croissance marges membership."},
    {"ticker": "UBER",    "name": "Uber",                 "lat": 37.7749, "lon": -122.4194, "sector": "Conso",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "VTC + livraison (Eats) + fret. Plateforme autonome en développement (Waymo partner)."},
    # ── Spatial ──────────────────────────────────────────────────────────────
    {"ticker": "RKLB",    "name": "Rocket Lab",           "lat": 33.7701, "lon": -118.1937, "sector": "Spatial",
     "exchange": "NASDAQ", "country": "🇺🇸 / 🇳🇿 NZ",
     "desc": "Lanceur Electron (petit sat), Neutron en développement. Composants spatiaux."},
    {"ticker": "LUNR",    "name": "Intuitive Machines",   "lat": 29.7604, "lon": -95.3698,  "sector": "Spatial",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Alunisseur IM-1 (Odysseus). Contrats NASA CLPS. Infrastructure luni lunaire."},
    {"ticker": "ASTS",    "name": "AST SpaceMobile",      "lat": 31.9973, "lon": -102.0779, "sector": "Spatial",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Réseau broadband satellite direct-to-smartphone. BlueBird constellation en déploiement."},
    # ── Quantum ──────────────────────────────────────────────────────────────
    {"ticker": "RGTI",    "name": "Rigetti Computing",    "lat": 37.8716, "lon": -122.2727, "sector": "Quantum",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "Processeurs quantiques supraconducteurs + cloud (QCS). Partenariats DARPA/NASA."},
    {"ticker": "QBTS",    "name": "D-Wave Quantum",       "lat": 49.2488, "lon": -122.9805, "sector": "Quantum",
     "exchange": "NYSE", "country": "🇨🇦 Canada",
     "desc": "Recuit quantique (annealing) — optim. logistique, IA. 5000+ qubits Advantage2."},
    {"ticker": "IONQ",    "name": "IonQ",                 "lat": 38.9807, "lon": -76.9369,  "sector": "Quantum",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Qubits piégeage d'ions — fidélité record. Accès cloud AWS/Azure/GCP."},
    # ── Spéculatif ───────────────────────────────────────────────────────────
    {"ticker": "SOUN",    "name": "SoundHound AI",        "lat": 37.3000, "lon": -121.9500, "sector": "Spéculatif",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "IA vocale pour auto et restauration. Clients : Stellantis, Hyundai, White Castle."},
    {"ticker": "AMPX",    "name": "Amprius Technologies", "lat": 37.5400, "lon": -121.9700, "sector": "Spéculatif",
     "exchange": "NYSE", "country": "🇺🇸 États-Unis",
     "desc": "Batteries silicium haute densité énergétique. Clients défense/aéro (drone, HAPS)."},
    {"ticker": "JMIA",    "name": "Jumia Technologies",   "lat": 25.2048, "lon": 55.2708,   "sector": "Spéculatif",
     "exchange": "NYSE", "country": "🌍 Afrique (HQ Dubaï)",
     "desc": "E-commerce panafricain. Présence 11 pays. Pari sur l'essor de la classe moyenne africaine."},
    {"ticker": "TCEHY",   "name": "Tencent",              "lat": 22.5431, "lon": 114.0579,  "sector": "Spéculatif",
     "exchange": "OTC (ADR)", "country": "🇨🇳 Chine",
     "desc": "WeChat, jeux (Riot/Epic/Supercell), cloud. Risque régulateur chinois persistant."},
    {"ticker": "NURO",    "name": "NeuroMetrix",          "lat": 42.4795, "lon": -71.1523,  "sector": "Spéculatif",
     "exchange": "NASDAQ", "country": "🇺🇸 États-Unis",
     "desc": "⚠️ Delisté (acquisition ECOR en cours fin 2024). Dispositifs neurostimulation."},
    # ── Métaux (ETF → Revolut Securities Europe, Vilnius) ────────────────────
    {"ticker": "GLD",     "name": "Gold ETF (SPDR)",      "lat": 54.6950, "lon": 25.2700,   "sector": "Métaux",
     "exchange": "NYSE Arca", "country": "🇺🇸 États-Unis",
     "note": "ETF — custodié via Revolut Securities Europe (Vilnius)",
     "desc": "ETF or physique — réserve de valeur, couverture inflation/risque géopolitique."},
    {"ticker": "SLV",     "name": "Silver ETF (iShares)", "lat": 54.6800, "lon": 25.2900,   "sector": "Métaux",
     "exchange": "NYSE Arca", "country": "🇺🇸 États-Unis",
     "note": "ETF — custodié via Revolut Securities Europe (Vilnius)",
     "desc": "ETF argent physique — valeur refuge + demande industrielle (solaire, électronique)."},
    # ── Crypto (→ Revolut Ltd, Londres) ─────────────────────────────────────
    {"ticker": "BTC-USD", "name": "Bitcoin",              "lat": 51.5036, "lon": -0.0050,   "sector": "Crypto",
     "exchange": "Crypto", "country": "🌐 Décentralisé",
     "note": "Crypto — custodié via Revolut Ltd (Londres)",
     "desc": "Réserve de valeur décentralisée. Halving 2024 passé. Adoption ETF spot US (BlackRock)."},
    {"ticker": "ETH-USD", "name": "Ethereum",             "lat": 51.5100, "lon":  0.0020,   "sector": "Crypto",
     "exchange": "Crypto", "country": "🌐 Décentralisé",
     "note": "Crypto — custodié via Revolut Ltd (Londres)",
     "desc": "Plateforme smart contracts N°1. L2 en pleine expansion (Arbitrum, Base). ETF spot US."},
    {"ticker": "SOL-USD", "name": "Solana",               "lat": 51.4980, "lon": -0.0300,   "sector": "Crypto",
     "exchange": "Crypto", "country": "🌐 Décentralisé",
     "note": "Crypto — custodié via Revolut Ltd (Londres)",
     "desc": "Blockchain haute perf. (65k TPS). Memecoins, DeFi, NFTs. ETF spot en attente SEC."},
]


def build_world_map() -> folium.Map:
    m = folium.Map(
        location=[30, 5],
        zoom_start=2,
        tiles="CartoDB dark_matter",
        prefer_canvas=True,
    )

    # ── Couche 1 : Courtiers ──────────────────────────────────────────────────
    broker_group = folium.FeatureGroup(name="🏦 Courtiers & dépositaires", show=True)
    for b in BROKERS:
        products_html = "".join(
            f"<span style='background:#333;color:#ccc;padding:1px 6px;"
            f"border-radius:8px;font-size:10px;margin:1px 2px 1px 0;display:inline-block'>"
            f"{p}</span>"
            for p in b.get("products", [])
        )
        popup_html = (
            f"<div style='font-family:sans-serif;min-width:230px;max-width:280px'>"
            f"<b style='font-size:13px'>{b['name']}</b><br>"
            f"<span style='color:#888;font-size:11px'>{b['subtitle']}</span>"
            f"<hr style='margin:5px 0;border-color:#555'>"
            f"<b style='font-size:11px'>{b['country']}</b><br>"
            f"<span style='color:#aaa;font-size:11px'>🏛️ {b.get('regulator','—')}</span><br>"
            f"<span style='color:#6dbf7e;font-size:11px'>🛡️ {b.get('protection','—')}</span>"
            f"<hr style='margin:5px 0;border-color:#444'>"
            f"<div style='margin-bottom:4px'>{products_html}</div>"
            f"<small style='color:#888'>🌐 {b.get('website','')}</small>"
            f"</div>"
        )
        folium.Marker(
            location=[b["lat"], b["lon"]],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=b["name"],
            icon=folium.Icon(color=b["color"], icon="bank", prefix="fa"),
        ).add_to(broker_group)
    broker_group.add_to(m)

    # ── Couche 2 : Sièges sociaux ─────────────────────────────────────────────
    hq_group = folium.FeatureGroup(name="🏢 Sièges sociaux", show=True)
    for c in COMPANY_HQ:
        color = SECTOR_COLORS.get(c["sector"], "#ffffff")
        note_line = (
            f"<br><small style='color:#999'>📦 {c['note']}</small>"
            if c.get("note") else ""
        )
        desc_line = (
            f"<div style='color:#ccc;font-size:11px;margin-top:5px;line-height:1.4'>"
            f"{c['desc']}</div>"
            if c.get("desc") else ""
        )
        popup_html = (
            f"<div style='font-family:sans-serif;min-width:200px;max-width:270px'>"
            f"<b style='font-size:13px'>{c['ticker']}</b>"
            f"<span style='color:#888;font-size:11px'> — {c['name']}</span><br>"
            f"<span style='"
            f"background:{color};color:#000;"
            f"padding:1px 7px;border-radius:10px;"
            f"font-size:11px;font-weight:bold"
            f"'>{c['sector']}</span>"
            f"<hr style='margin:5px 0;border-color:#444'>"
            f"<span style='color:#aaa;font-size:11px'>"
            f"📍 {c.get('country','—')} &nbsp;·&nbsp; 📊 {c.get('exchange','—')}"
            f"</span>"
            f"{desc_line}"
            f"{note_line}"
            f"</div>"
        )
        folium.CircleMarker(
            location=[c["lat"], c["lon"]],
            radius=7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=1.5,
            popup=folium.Popup(popup_html, max_width=290),
            tooltip=f"{c['ticker']} — {c['name']}",
        ).add_to(hq_group)
    hq_group.add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    return m

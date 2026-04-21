"""
data_feed.py  —  Download and cache daily close prices via yfinance.
"""

import os
import time
import requests
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ── Universe definition ───────────────────────────────────────────────────────

TICKERS = {
    # --- Risk-ON : Core quality ---
    "NVDA":    "NVIDIA",
    "ORCL":    "Oracle",
    "LLY":     "Eli Lilly",
    "RHM.DE":  "Rheinmetall",
    "LDO.MI":  "Leonardo",
    "HO.PA":   "Thales",
    "HEI.DE":  "Heidelberg Mat.",
    "HAG.DE":  "Hensoldt",         # IPO sep-2020, short history
    "BA.L":    "BAE Systems",
    # --- Risk-ON : Growth ---
    "TSM":     "TSMC",
    "GOOGL":   "Alphabet",
    "MSFT":    "Microsoft",
    "AAPL":    "Apple",
    "META":    "Meta",
    "CAT":     "Caterpillar",
    "BTC-USD": "Bitcoin",
    "SOL-USD": "Solana",           # available from ~2020
    # --- Defensive / Swing ---
    "GLD":     "Gold ETF",
    "SLV":     "Silver ETF",
    "CL":      "Colgate-Palmolive",
    "COST":    "Costco",
    "SMR":     "NuScale Power",
    "UBER":    "Uber",
    "ENPH":    "Enphase Energy",
    "CCJ":     "Cameco",
    "NNE":     "Nano Nuclear Energy",
    "OKLO":    "Oklo",
    "DE":      "Deere & Company",
    "URI":     "United Rentals",
    "NURO":    "NeuroMetrix",
    # --- Regime signals ---
    "SPY":     "S&P 500",
}

RISK_ON   = ["NVDA","ORCL","LLY","RHM.DE","LDO.MI","HO.PA","HEI.DE","HAG.DE",
             "TSM","GOOGL","MSFT","AAPL","META","CAT","BTC-USD","SOL-USD"]
DEFENSIVE = ["GLD","SLV"]
REGIME    = ["SPY","GLD"]

# ── Moonshot universe (speculative, for scanner only — not backtested) ────────

MOONSHOTS = {
    # Spatial
    "RKLB":  "Rocket Lab",
    "LUNR":  "Intuitive Machines",
    "ASTS":  "AST SpaceMobile",
    # Quantum
    "RGTI":  "Rigetti Computing",
    "QBTS":  "D-Wave Quantum",
    "IONQ":  "IonQ",
    # Biotech
    "CATX":  "Perspective Therapeutics",
    "BEAM":  "Beam Therapeutics",
    "VKTX":  "Viking Therapeutics",
    # Crypto
    "ETH-USD": "Ethereum",
    # Autres
    "SOUN":  "SoundHound AI",
    "AMPX":  "Amprius Technologies",
    "JMIA":  "Jumia Technologies",
    "TCEHY": "Tencent (OTC)",
    "BDMD":  "Baird Medical",
}

TICKERS.update(MOONSHOTS)

# ── Descriptions courtes (affichées dans l'UI) ────────────────────────────────

TICKER_DESC = {
    # Core Tech / IA
    "NVDA":    "Concepteur de GPU et accélérateurs IA, leader mondial des semi-conducteurs pour le deep learning. ~$3T de capitalisation, fondé en 1993 aux États-Unis.",
    "MSFT":    "Éditeur de logiciels et leader du cloud (Azure), avec une position forte dans l'IA via son partenariat avec OpenAI. ~$3T, fondé en 1975 aux États-Unis.",
    "GOOGL":   "Conglomérat technologique dominant la recherche en ligne, la publicité digitale et le cloud (GCP), avec des investissements massifs en IA. ~$2T, fondé en 1998 aux États-Unis.",
    "META":    "Propriétaire de Facebook, Instagram et WhatsApp, avec un pari stratégique sur le metaverse et l'IA générative. ~$1.5T, fondé en 2004 aux États-Unis.",
    "AAPL":    "Géant de l'électronique grand public (iPhone, Mac, iPad) et des services numériques, avec un écosystème très fidélisant. ~$3T, fondé en 1976 aux États-Unis.",
    "TSM":     "Fondeur de semi-conducteurs dominant à l'échelle mondiale, fabricant des puces pour Apple, NVIDIA et AMD. ~$900B, fondé en 1987 à Taïwan.",
    "ORCL":    "Éditeur de bases de données et de logiciels d'entreprise, en forte croissance sur le cloud et l'infrastructure IA. ~$500B, fondé en 1977 aux États-Unis.",
    # Thématiques qualité
    "LLY":     "Laboratoire pharmaceutique américain, leader mondial en diabétologie et obésité (tirzepatide/Mounjaro). ~$700B, fondé en 1876 aux États-Unis.",
    "COST":    "Chaîne de grande distribution en entrepôts (warehouse club), modèle d'abonnement très fidélisant et croissance solide. ~$400B, fondé en 1983 aux États-Unis.",
    "CL":      "Groupe de biens de consommation courante (Colgate, Palmolive), défensif avec une présence dans 200 pays et des marges stables. ~$60B, fondé en 1806 aux États-Unis.",
    "CAT":     "Leader mondial des engins de construction et d'exploitation minière, baromètre de l'investissement en infrastructures mondiales. ~$200B, fondé en 1925 aux États-Unis.",
    "UBER":    "Plateforme mondiale de mobilité et de livraison (Uber Eats), en voie de rentabilité après des années de pertes. ~$150B, fondé en 2009 aux États-Unis.",
    "SMR":     "Pionnier des petits réacteurs nucléaires modulaires (SMR), technologie en cours de certification NRC. Small cap, fondé en 2007 aux États-Unis.",
    # Défense européenne
    "RHM.DE":  "Groupe allemand d'armement et de défense, fournisseur majeur de l'OTAN en munitions, véhicules blindés et systèmes d'armes. ~$30B, fondé en 1849 en Allemagne.",
    "HAG.DE":  "Spécialiste allemand des capteurs et systèmes électroniques de défense (radar, optronique). ~$5B, coté depuis 2020 en Allemagne.",
    "BA.L":    "Groupe britannique de défense et d'aérospatiale (avions de combat, sous-marins, systèmes électroniques), l'un des plus grands groupes de défense mondiaux. ~£30B, fondé en 1977 au Royaume-Uni.",
    "HO.PA":   "Groupe français de haute technologie (défense, aérospatial, transport, identité numérique), fournisseur des armées et de l'aviation civile. ~$25B, fondé en 1893 en France.",
    "LDO.MI":  "Conglomérat industriel italien spécialisé dans l'aérospatial, la défense et la sécurité (hélicoptères, avions de combat, radars). ~$15B, fondé en 1948 en Italie.",
    "HEI.DE":  "Leader mondial des matériaux de construction (ciment, granulats, béton prêt à l'emploi), fortement exposé aux cycles d'infrastructure. ~$15B, fondé en 1873 en Allemagne.",
    # Crypto
    "BTC-USD":  "Première cryptomonnaie mondiale par capitalisation, réserve de valeur décentralisée et actif spéculatif majeur. Créée en 2009 par Satoshi Nakamoto.",
    "ETH-USD":  "Deuxième cryptomonnaie mondiale, blockchain programmable et infrastructure des contrats intelligents (DeFi, NFT, Layer 2). Lancée en 2015.",
    "SOL-USD":  "Blockchain haute performance concurrente d'Ethereum, privilégiant la vitesse et les faibles frais de transaction. Lancée en 2020.",
    # Métaux
    "GLD":     "ETF SPDR répliquant le cours de l'or physique, valeur refuge en période d'incertitude et de débasement monétaire. Lancé en 2004 aux États-Unis.",
    "SLV":     "ETF iShares répliquant le cours de l'argent physique, avec une double exposition métal précieux et métal industriel (solaire, électronique).",
    # Spatial
    "RKLB":    "Entreprise américaine de lanceurs spatiaux légers (Electron) et de satellites, en diversification vers les grandes missions. Small cap, fondé en 2006 en Nouvelle-Zélande.",
    "LUNR":    "Fournisseur de services lunaires commerciaux pour la NASA (programme CLPS), premier alunissage privé américain en 2024. Small cap, fondé en 2013 aux États-Unis.",
    "ASTS":    "Développeur d'un réseau de satellites en orbite basse pour connectivité mobile directe (partenariats AT&T, Vodafone). Small cap, fondé en 2017 aux États-Unis.",
    # Quantum
    "RGTI":    "Constructeur d'ordinateurs quantiques supraconducteurs, en compétition directe avec IBM et Google sur la puissance de calcul. Micro cap, fondé en 2013 aux États-Unis.",
    "QBTS":    "Pioneer du calcul quantique par recuit (annealing), avec des applications en optimisation et logistique. Micro cap, fondé en 1999 au Canada.",
    "IONQ":    "Développeur d'ordinateurs quantiques à ions piégés, considérés comme l'une des architectures les plus prometteuses. Small cap, fondé en 2015 aux États-Unis.",
    # Biotech
    "VKTX":    "Biotech spécialisée dans les traitements de l'obésité et du NASH (VK2735), en compétition directe avec Eli Lilly et Novo Nordisk. Small cap, fondée en 2012 aux États-Unis.",
    "BEAM":    "Biotech pionnière de l'édition de base de l'ADN (base editing), une évolution plus précise du CRISPR. Small cap, fondée en 2017 aux États-Unis.",
    "CATX":    "Biotech spécialisée dans la radiothérapie ciblée (actinium-225) pour les cancers avancés. Micro cap, anciennement Viewpoint Molecular Targeting.",
    # Construction / Infrastructure
    "DE":      "Constructeur américain de machines agricoles et d'engins de chantier (tracteurs, moissonneuses-batteuses), leader mondial sur son marché. ~$130B, fondé en 1837 aux États-Unis.",
    "URI":     "Premier loueur d'équipements de construction et industriels en Amérique du Nord, bénéficiaire direct des plans d'infrastructure. ~$50B, fondé en 1997 aux États-Unis.",
    # Nucléaire
    "CCJ":     "Premier producteur d'uranium coté en bourse, exposé directement au prix spot et long terme de l'uranium. ~$20B, fondé en 1988 au Canada.",
    "NNE":     "Développeur de micro-réacteurs nucléaires ultra-compacts (1-20 MW) pour sites isolés et applications de défense. Micro cap, fondé en 2022 aux États-Unis.",
    "OKLO":    "Concepteur de micro-réacteurs à neutrons rapides (Aurora), soutenu par Sam Altman. Technologie précommerciale, premier réacteur prévu avant 2030. Micro cap, fondé en 2013 aux États-Unis.",
    # Energie solaire
    "ENPH":    "Fabricant de micro-onduleurs solaires résidentiels et de systèmes de gestion d'énergie, leader sur le marché résidentiel américain. ~$10B, fondé en 2006 aux États-Unis.",
    # BCI
    "NURO":    "Développeur de dispositifs de neurostimulation non-invasive (DRG, douleur chronique). Micro cap très spéculatif, fondé en 1996 aux États-Unis.",
    # Autres
    "SOUN":    "Développeur de solutions d'IA vocale pour les restaurants, l'automobile et les services clients. Micro cap, fondé en 2016 aux États-Unis.",
    "AMPX":    "Fabricant de batteries lithium-silicium haute densité énergétique pour drones et applications de défense. Micro cap, fondé en 2008 aux États-Unis.",
    "JMIA":    "Plateforme e-commerce panafricaine opérant dans une dizaine de pays, en quête de rentabilité sur un marché en forte croissance. Small cap, fondée en 2012, cotée à New York.",
    "TCEHY":   "Conglomérat technologique chinois dominant les jeux vidéo, la messagerie (WeChat) et les paiements digitaux en Chine. ~$400B, fondé en 1998 en Chine.",
}


# ── Download helpers ──────────────────────────────────────────────────────────

# stooq.com suffix mapping
STOOQ_SUFFIX = {
    ".DE": ".de", ".MI": ".it", ".PA": ".fr", ".L": ".uk",
    "-USD": ".v",               # crypto vs USD on stooq (e.g. btc.v)
}

# IP bloquée stooq depuis >1 mois — désactivé, yfinance batch uniquement
STOOQ_AVAILABLE = False

def _stooq_symbol(ticker: str) -> str:
    """Convert ticker to stooq symbol."""
    for suffix, stooq_s in STOOQ_SUFFIX.items():
        if ticker.endswith(suffix):
            base = ticker[: -len(suffix)]
            if suffix == "-USD":
                return base.lower() + stooq_s
            return base.lower() + stooq_s
    return ticker.lower() + ".us"


def _fetch_stooq(ticker: str, start: str = "2014-01-01") -> pd.Series:
    sym  = _stooq_symbol(ticker)
    d1   = start.replace("-", "")
    d2   = pd.Timestamp.today().strftime("%Y%m%d")
    url  = f"https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or "No data" in r.text or len(r.text) < 50 or "Date" not in r.text:
            return pd.Series(dtype=float, name=ticker)
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), parse_dates=["Date"])
        df = df.set_index("Date").sort_index()
        s  = df["Close"].dropna()
        s.name = ticker
        return s
    except Exception as e:
        print(f"  stooq error {ticker}: {e}")
        return pd.Series(dtype=float, name=ticker)


def _fetch_yfinance(ticker: str, start: str = "2014-01-01") -> pd.Series:
    """Fetch daily close prices from yfinance (fallback when stooq is unavailable)."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
        if hist.empty:
            return pd.Series(dtype=float, name=ticker)
        s = hist["Close"].dropna()
        if s.index.tz is not None:
            s.index = s.index.tz_convert(None)
        else:
            s.index = s.index.tz_localize(None)
        s.name = ticker
        return s
    except Exception as e:
        print(f"  yfinance error {ticker}: {e}")
        return pd.Series(dtype=float, name=ticker)


def _fetch_yfinance_batch(tickers: list, start: str) -> pd.DataFrame:
    """Batch download via yf.download() — one request for all tickers."""
    import yfinance as yf
    if not tickers:
        return pd.DataFrame()
    try:
        raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"].copy()
            if isinstance(closes, pd.Series):
                closes = closes.to_frame(name=tickers[0])
        else:
            closes = raw[["Close"]].rename(columns={"Close": tickers[0]})
        if closes.index.tz is not None:
            closes.index = closes.index.tz_convert(None)
        else:
            closes.index = closes.index.tz_localize(None)
        return closes.sort_index()
    except Exception as e:
        print(f"  yfinance batch error: {e}")
        return pd.DataFrame()


def _fetch_batch(tickers: list, fetch_start: str) -> pd.DataFrame:
    """Download a batch of tickers via yfinance batch API (stooq banni)."""
    CHUNK = 30
    chunks = [tickers[i:i+CHUNK] for i in range(0, len(tickers), CHUNK)]
    frames = []
    for i, chunk in enumerate(chunks):
        print(f"  Batch {i+1}/{len(chunks)}: {len(chunk)} tickers...")
        df_chunk = _fetch_yfinance_batch(chunk, fetch_start)
        frames.append(df_chunk)
        if i < len(chunks) - 1:
            time.sleep(3)

    result = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()

    # Fallback individuel pour les tickers absents du résultat batch
    missing = [t for t in tickers if result.empty or t not in result.columns]
    for t in missing:
        print(f"  Batch missed {t} — individual fallback...")
        s = _fetch_yfinance(t, start=fetch_start)
        if not s.empty:
            result[t] = s
        time.sleep(2)

    return result


def _merge(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Concat existing + new, deduplicate index keeping newest values."""
    df = pd.concat([existing, new])
    return df[~df.index.duplicated(keep="last")].sort_index()


def load_prices(tickers: list = None, refresh: bool = False,
                start: str = "2014-01-01") -> pd.DataFrame:
    """Return a DataFrame of daily close prices, columns = tickers.

    refresh=False : return cache instantly if all tickers present;
                    fetch only missing tickers (full history) otherwise.
    refresh=True  : incremental update — fetch only since last cached date.
                    Falls back to full download if no cache exists.
    """
    if tickers is None:
        tickers = list(TICKERS.keys())

    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, "_prices.csv")

    existing_df = None
    if os.path.exists(cache_path):
        existing_df = pd.read_csv(cache_path, index_col=0, parse_dates=True)

    # ── Fast path: all tickers cached, no refresh ─────────────────────────────
    if existing_df is not None and not refresh:
        missing = [t for t in tickers if t not in existing_df.columns]
        if not missing:
            print(f"  Loaded from cache ({existing_df.shape[1]} tickers, "
                  f"up to {existing_df.index.max().date()})")
            return existing_df[tickers].sort_index()

        # New tickers only — need full history
        print(f"  {len(missing)} new ticker(s), fetching full history: {missing}")
        new_df = _fetch_batch(missing, start)
        if new_df.empty:
            print("  WARNING: fetch returned nothing, returning existing cache.")
            for t in missing:
                existing_df[t] = float("nan")
            return existing_df[tickers].sort_index()
        df = existing_df.join(new_df, how="outer").sort_index()
        df.to_csv(cache_path)
        return df[tickers].sort_index()

    # ── Incremental refresh ───────────────────────────────────────────────────
    if existing_df is not None and not existing_df.empty:
        last_date = existing_df.index.max()
        fetch_start = (last_date - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"  Incremental update from {fetch_start} "
              f"(last cached: {last_date.date()})...")
    else:
        fetch_start = start
        print(f"  No cache found — full download from {fetch_start}...")

    new_df = _fetch_batch(tickers, fetch_start)

    if new_df.empty:
        print("  ERROR: download returned no data, keeping existing cache untouched.")
        return existing_df if existing_df is not None else new_df

    if existing_df is not None:
        df = _merge(existing_df, new_df)
    else:
        df = new_df

    df.to_csv(cache_path)
    print(f"  Cache updated: {len(df)} rows, up to {df.index.max().date()}")
    return df[tickers].sort_index() if all(t in df.columns for t in tickers) else df.sort_index()


def _fetch_stooq_volume(ticker: str, start: str = "2014-01-01") -> pd.Series:
    """Same as _fetch_stooq but returns Volume column."""
    sym = _stooq_symbol(ticker)
    d1  = start.replace("-", "")
    d2  = pd.Timestamp.today().strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or "No data" in r.text or len(r.text) < 50 or "Date" not in r.text:
            return pd.Series(dtype=float, name=ticker)
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), parse_dates=["Date"])
        df = df.set_index("Date").sort_index()
        if "Volume" not in df.columns:
            return pd.Series(dtype=float, name=ticker)
        s = df["Volume"].dropna()
        s.name = ticker
        return s
    except Exception as e:
        print(f"  stooq volume error {ticker}: {e}")
        return pd.Series(dtype=float, name=ticker)


def _fetch_yfinance_volume(ticker: str, start: str = "2014-01-01") -> pd.Series:
    """Fetch daily volume from yfinance (fallback when stooq returns no volume)."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
        if hist.empty or "Volume" not in hist.columns:
            return pd.Series(dtype=float, name=ticker)
        s = hist["Volume"].dropna().astype(float)
        if s.index.tz is not None:
            s.index = s.index.tz_convert(None)
        else:
            s.index = s.index.tz_localize(None)
        s.name = ticker
        return s
    except Exception as e:
        print(f"  yfinance volume error {ticker}: {e}")
        return pd.Series(dtype=float, name=ticker)


def _fetch_yfinance_volume_batch(tickers: list, start: str) -> pd.DataFrame:
    """Batch volume download via yf.download() — one request for all tickers."""
    import yfinance as yf
    if not tickers:
        return pd.DataFrame()
    try:
        raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            if "Volume" not in raw.columns.get_level_values(0):
                return pd.DataFrame()
            vols = raw["Volume"].copy()
            if isinstance(vols, pd.Series):
                vols = vols.to_frame(name=tickers[0])
        else:
            if "Volume" not in raw.columns:
                return pd.DataFrame()
            vols = raw[["Volume"]].rename(columns={"Volume": tickers[0]})
        if vols.index.tz is not None:
            vols.index = vols.index.tz_convert(None)
        else:
            vols.index = vols.index.tz_localize(None)
        return vols.sort_index().astype(float)
    except Exception as e:
        print(f"  yfinance volume batch error: {e}")
        return pd.DataFrame()


def _fetch_volume_batch(tickers: list, fetch_start: str) -> pd.DataFrame:
    """Download volume for a batch via yfinance batch API (stooq banni)."""
    CHUNK = 30
    chunks = [tickers[i:i+CHUNK] for i in range(0, len(tickers), CHUNK)]
    frames = []
    for i, chunk in enumerate(chunks):
        print(f"  Volume batch {i+1}/{len(chunks)}: {len(chunk)} tickers...")
        df_chunk = _fetch_yfinance_volume_batch(chunk, fetch_start)
        frames.append(df_chunk)
        if i < len(chunks) - 1:
            time.sleep(3)

    result = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()

    missing = [t for t in tickers if result.empty or t not in result.columns]
    for t in missing:
        print(f"  Volume batch missed {t} — individual fallback...")
        s = _fetch_yfinance_volume(t, start=fetch_start)
        if not s.empty:
            result[t] = s
        time.sleep(2)

    return result


def load_volume(tickers: list, refresh: bool = False) -> pd.DataFrame:
    """Return a DataFrame of daily volume, columns = tickers.
    Same incremental strategy as load_prices.
    Volume only needs ~2 years of history for swing charts.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = os.path.join(DATA_DIR, "_volume.csv")
    # 2 years is enough for volume display — never download since 2014
    vol_start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")

    existing_df = None
    if os.path.exists(cache_path):
        _tmp = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if not _tmp.empty:
            existing_df = _tmp

    # ── Fast path ─────────────────────────────────────────────────────────────
    if existing_df is not None and not refresh:
        missing = [t for t in tickers if t not in existing_df.columns]
        if not missing:
            print(f"  Volume loaded from cache (up to {existing_df.index.max().date()})")
            return existing_df[tickers].sort_index()
        # New tickers — 2-year history only
        new_df = _fetch_volume_batch(missing, vol_start)
        if not new_df.empty:
            df = existing_df.join(new_df, how="outer").sort_index()
            df.to_csv(cache_path)
            return df[tickers].sort_index()
        # fetch failed — add missing columns as NaN so slice doesn't crash
        for t in missing:
            existing_df[t] = float("nan")
        return existing_df[tickers].sort_index()

    # ── Incremental refresh ───────────────────────────────────────────────────
    if existing_df is not None and not existing_df.empty:
        last_date = existing_df.index.max()
        fetch_start = (last_date - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        fetch_start = vol_start  # first time: 2 years, never full history

    new_df = _fetch_volume_batch(tickers, fetch_start)

    if new_df.empty:
        return existing_df if existing_df is not None else new_df

    if existing_df is not None:
        df = _merge(existing_df, new_df)
    else:
        df = new_df

    df.to_csv(cache_path)
    return df[tickers].sort_index() if all(t in df.columns for t in tickers) else df.sort_index()


if __name__ == "__main__":
    df = load_prices(refresh=True)
    print(f"Shape : {df.shape}")
    print(f"Period: {df.index.min().date()} to {df.index.max().date()}")
    print(df.tail(3).to_string())

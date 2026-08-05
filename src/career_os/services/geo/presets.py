"""Shipped GeoProfile presets — pure configuration data, no logic.

Everything in this module is geographic VOCABULARY, not code: the engine in
``career_os.services.geo.classifier`` never sees these names. Swapping the
profile swaps the geography.

- ``FRANKFURT_PROFILE`` — the reference preset. Its pattern strings are copied
  character-for-character from the measured source engine (93.6% recall /
  74.6% precision on a 277-item human-judged blind set); they ARE the measured
  artifact, so do not "clean them up".
- ``US_REMOTE_PROFILE`` — an ILLUSTRATIVE contrast preset for a US-based
  remote worker. It exists to prove the engine is config-driven (same input,
  different profile, different verdict). It is demonstration data, not legal
  or immigration advice.
- ``PUBLIC_GEOGRAPHY_TOKENS`` — the shared world-geography token list used by
  :meth:`career_os.services.geo.profile.GeoProfile.from_home_tokens` as the
  base ``foreign`` vocabulary (home/visa-required tokens are subtracted).
"""

from __future__ import annotations

from career_os.services.geo.profile import build_profile

# ---------------------------------------------------------------------------
# Reference preset: Frankfurt-based candidate (EU freedom of movement).
# Pattern strings are verbatim copies of the measured source engine.
# ---------------------------------------------------------------------------

FRANKFURT_PROFILE = build_profile(
    "frankfurt",
    # Home country + its cities.
    home_country=(
        r"\b(germany|german|deutschland|berlin|m(ü|u)nchen|munich|frankfurt|hamburg|"
        r"cologne|k(ö|o)ln|stuttgart|d(ü|u)sseldorf|darmstadt|leipzig|n(ü|u)rnberg|"
        r"nuremberg|karlsruhe|mannheim|bremen|hannover|dresden|essen|dortmund|bonn|"
        r"m(ü|u)nster|augsburg|freiburg|heidelberg|potsdam|kiel|mainz|wiesbaden|"
        r"walldorf|ingolstadt)"
    ),
    # Commuting belt — reachable without moving house. Ranking only.
    home_local=(
        r"\b(frankfurt|offenbach|darmstadt|wiesbaden|mainz|hanau|r(ü|u)sselsheim|"
        r"bad homburg|oberursel|eschborn|neu[- ]isenburg|langen|dreieich|friedberg|"
        r"gie(ß|ss)en|aschaffenburg|mannheim|heidelberg|walldorf|ingelheim|worms|"
        r"limburg|marburg|fulda|w(ü|u)rzburg)\b"
    ),
    # Onsite reachable without a work visa (EU freedom of movement).
    visa_free_region=(
        r"\b(amsterdam|netherlands|dutch|paris|france|french|madrid|barcelona|spain|"
        r"lisbon|porto|portugal|dublin|ireland|vienna|austria|zurich|zug|geneva|"
        r"switzerland|stockholm|sweden|swedish|copenhagen|denmark|danish|nordic|oslo|"
        r"norway|helsinki|finland|warsaw|poland|krakow|wroclaw|prague|czech|budapest|"
        r"hungary|bucharest|romania|milan|rome|italy|brussels|belgium|luxembourg|"
        r"athens|greece|sofia|bulgaria|zagreb|croatia|tallinn|estonia|riga|latvia|"
        r"vilnius|lithuania|ljubljana|slovenia|bratislava|slovakia|malta|cyprus|"
        r"iceland)\b"
    ),
    # Bare pan-region / global location strings, eligible on their own.
    visa_free_wide=(
        r"\b(europe|european|emea|dach|global(ly)?|worldwide|anywhere|eu[\s\-]?wide|eu)\b"
    ),
    # "remote - europe" / "anywhere in europe" phrasings.
    visa_free_remote_phrase=(
        r"(remote[ ,\-]*(europe|eu\b)|europe[ ,\-]*remote|\beu[ \-]wide|"
        r"anywhere in europe|across europe|emea remote|remote[ ,\-]*emea|"
        r"european union|europe/|/europe)"
    ),
    # The UK is outside EU freedom of movement: onsite needs a Skilled Worker
    # visa. Distinct class so the burden stays visible.
    visa_required=(
        r"\b(united kingdom|\buk\b|england|scotland|wales|london|manchester|"
        r"edinburgh|bristol|cambridge|oxford|glasgow|leeds|birmingham)\b"
    ),
    # Explicit ineligible places.
    foreign=(
        r"\b(united states|\busa?\b|u\.s\.?a?\b|america(s|n)?|new york|nyc|"
        r"san francisco|bay area|california|seattle|austin|boston|chicago|denver|"
        r"atlanta|texas|florida|washington|toronto|vancouver|montreal|canada|mexico|"
        r"colombia|uruguay|argentina|brazil|chile|peru|ecuador|venezuela|bolivia|"
        r"paraguay|costa rica|panama|guatemala|latam|india|bangalore|bengaluru|"
        r"hyderabad|mumbai|delhi|pune|chennai|gurgaon|noida|pakistan|bangladesh|"
        r"sri lanka|nepal|china|beijing|shanghai|shenzhen|hong kong|taiwan|singapore|"
        r"japan|tokyo|osaka|korea|seoul|australia|sydney|melbourne|brisbane|"
        r"new zealand|auckland|philippines|manila|indonesia|jakarta|vietnam|hanoi|"
        r"thailand|bangkok|malaysia|kuala lumpur|cambodia|myanmar|mongolia|"
        r"kazakhstan|uzbekistan|dubai|abu dhabi|united arab emirates|\buae\b|qatar|"
        r"doha|kuwait|bahrain|oman|saudi|riyadh|jordan|lebanon|israel|tel aviv|"
        r"turkey|istanbul|egypt|cairo|morocco|tunisia|algeria|nigeria|lagos|kenya|"
        r"nairobi|ghana|tanzania|uganda|ethiopia|south africa|johannesburg|"
        r"cape town|russia|moscow|belarus|serbia|belgrade|bosnia|albania|moldova|"
        r"macedonia|montenegro|armenia|azerbaijan|\bapac\b|\bamer\b|\bnam\b|"
        r"\bceur\b|middle east|africa|asia)\b"
    ),
    # A multi-region posting naming an eligible region is open to home:
    # "(EMEA/AMER)" qualifies, "(AMER)" alone does not.
    eligible_region=r"\b(emea|europe|european|eu)\b",
    # Region tokens in the TITLE are as binding as the location.
    title_region_foreign=(
        r"[,(\-]\s*(east|west|central|amer|apac|latam|nam|anz|us|usa|india|korea|"
        r"japan|mexico|brazil|canada|middle east|emea east)\b"
    ),
)

# ---------------------------------------------------------------------------
# Contrast preset: US-based remote worker (SF Bay Area home).
# ILLUSTRATIVE ONLY — demonstration data proving the engine is config-driven,
# not a researched mobility ruleset and not legal/immigration advice.
# ---------------------------------------------------------------------------

US_REMOTE_PROFILE = build_profile(
    "us-remote",
    # SF Bay Area commute belt.
    home_local=(
        r"\b(san francisco|bay area|oakland|san jose|berkeley|palo alto|"
        r"mountain view|sunnyvale|menlo park|redwood city|cupertino|fremont)\b"
    ),
    # US states and major cities.
    home_country=(
        r"\b(united states|usa|us|u\.s\.|america|american|california|new york|nyc|"
        r"texas|florida|washington|colorado|illinois|georgia|massachusetts|oregon|"
        r"arizona|nevada|utah|virginia|pennsylvania|ohio|michigan|minnesota|"
        r"seattle|austin|boston|chicago|denver|atlanta|los angeles|san diego|"
        r"portland|miami|philadelphia|phoenix|dallas|houston|nashville|"
        r"san francisco|bay area|oakland|san jose|berkeley|palo alto|"
        r"mountain view|sunnyvale|menlo park|redwood city|cupertino|fremont)\b"
    ),
    # USMCA mobility: onsite reachable without a traditional work visa.
    visa_free_region=(
        r"\b(canada|toronto|vancouver|montreal|ottawa|calgary|"
        r"mexico|mexico city|guadalajara|monterrey)\b"
    ),
    # Pan-region / Americas-wide tokens, eligible on their own.
    visa_free_wide=r"\b(americas|nam|global(ly)?|worldwide|anywhere)\b",
    # "remote - americas" phrasings.
    visa_free_remote_phrase=(
        r"(remote[ ,\-]*(americas|amer|nam)|americas[ ,\-]*remote|"
        r"anywhere in the (us|americas))"
    ),
    # Onsite needs a work visa (illustrative: UK/Ireland).
    visa_required=(
        r"\b(united kingdom|uk|england|scotland|wales|london|manchester|"
        r"edinburgh|ireland|dublin)\b"
    ),
    # Explicit ineligible places: Europe + Asia + EMEA tokens.
    foreign=(
        r"\b(germany|deutschland|frankfurt|berlin|munich|hamburg|cologne|"
        r"france|paris|spain|madrid|barcelona|portugal|lisbon|netherlands|"
        r"amsterdam|italy|milan|rome|poland|warsaw|sweden|stockholm|denmark|"
        r"copenhagen|norway|oslo|finland|helsinki|switzerland|zurich|geneva|"
        r"austria|vienna|belgium|brussels|czech|prague|hungary|budapest|"
        r"romania|bucharest|greece|athens|emea|europe|european|eu|"
        r"india|bangalore|bengaluru|mumbai|delhi|pune|china|beijing|shanghai|"
        r"japan|tokyo|korea|seoul|singapore|hong kong|taiwan|vietnam|thailand|"
        r"indonesia|philippines|australia|sydney|melbourne|new zealand|"
        r"dubai|israel|tel aviv|turkey|istanbul|apac|asia|middle east|africa)\b"
    ),
    # Tokens that rescue a multi-region posting for a US candidate.
    eligible_region=r"\b(amer|americas|nam|us)\b",
    # Market-naming tokens in a title that foreclose a US candidate.
    title_region_foreign=(
        r"[,(\-]\s*(emea|europe|apac|latam|india|korea|japan|china|dach|uk|anz)\b"
    ),
)

# ---------------------------------------------------------------------------
# Shared public geography vocabulary for GeoProfile.from_home_tokens.
# Plain word tokens only (they are re.escape-d before compilation). The
# builder subtracts any token claimed by the caller's home/local/visa-required
# vocabularies, then ORs in the caller's extra_foreign_tokens.
# ---------------------------------------------------------------------------

PUBLIC_GEOGRAPHY_TOKENS: tuple[str, ...] = (
    # North America
    "united states",
    "usa",
    "america",
    "american",
    "north america",
    "new york",
    "nyc",
    "san francisco",
    "bay area",
    "california",
    "los angeles",
    "san diego",
    "san jose",
    "seattle",
    "austin",
    "boston",
    "chicago",
    "denver",
    "atlanta",
    "miami",
    "dallas",
    "houston",
    "phoenix",
    "texas",
    "florida",
    "washington",
    "canada",
    "toronto",
    "vancouver",
    "montreal",
    "mexico",
    # Latin America
    "colombia",
    "uruguay",
    "argentina",
    "brazil",
    "chile",
    "peru",
    "ecuador",
    "venezuela",
    "bolivia",
    "paraguay",
    "costa rica",
    "panama",
    "guatemala",
    "latam",
    # Europe
    "germany",
    "deutschland",
    "berlin",
    "munich",
    "frankfurt",
    "hamburg",
    "cologne",
    "stuttgart",
    "france",
    "paris",
    "spain",
    "madrid",
    "barcelona",
    "portugal",
    "lisbon",
    "porto",
    "netherlands",
    "amsterdam",
    "italy",
    "milan",
    "rome",
    "poland",
    "warsaw",
    "krakow",
    "sweden",
    "stockholm",
    "denmark",
    "copenhagen",
    "norway",
    "oslo",
    "finland",
    "helsinki",
    "switzerland",
    "zurich",
    "geneva",
    "austria",
    "vienna",
    "belgium",
    "brussels",
    "luxembourg",
    "czech",
    "prague",
    "hungary",
    "budapest",
    "romania",
    "bucharest",
    "greece",
    "athens",
    "bulgaria",
    "croatia",
    "estonia",
    "latvia",
    "lithuania",
    "slovenia",
    "slovakia",
    "malta",
    "cyprus",
    "iceland",
    "united kingdom",
    "england",
    "scotland",
    "wales",
    "london",
    "manchester",
    "edinburgh",
    "dublin",
    "ireland",
    # Eastern Europe / Caucasus
    "russia",
    "moscow",
    "belarus",
    "ukraine",
    "serbia",
    "belgrade",
    "bosnia",
    "albania",
    "moldova",
    "macedonia",
    "montenegro",
    "armenia",
    "azerbaijan",
    # Middle East
    "dubai",
    "abu dhabi",
    "united arab emirates",
    "qatar",
    "doha",
    "kuwait",
    "bahrain",
    "oman",
    "saudi",
    "riyadh",
    "jordan",
    "lebanon",
    "israel",
    "tel aviv",
    "turkey",
    "istanbul",
    "middle east",
    # Africa
    "egypt",
    "cairo",
    "morocco",
    "tunisia",
    "algeria",
    "nigeria",
    "lagos",
    "kenya",
    "nairobi",
    "ghana",
    "tanzania",
    "uganda",
    "ethiopia",
    "south africa",
    "johannesburg",
    "cape town",
    "africa",
    # South / Southeast / East Asia + Oceania
    "india",
    "bangalore",
    "bengaluru",
    "hyderabad",
    "mumbai",
    "delhi",
    "pune",
    "chennai",
    "pakistan",
    "bangladesh",
    "sri lanka",
    "nepal",
    "china",
    "beijing",
    "shanghai",
    "shenzhen",
    "hong kong",
    "taiwan",
    "singapore",
    "japan",
    "tokyo",
    "osaka",
    "korea",
    "seoul",
    "australia",
    "sydney",
    "melbourne",
    "brisbane",
    "new zealand",
    "auckland",
    "philippines",
    "manila",
    "indonesia",
    "jakarta",
    "vietnam",
    "hanoi",
    "thailand",
    "bangkok",
    "malaysia",
    "kuala lumpur",
    "cambodia",
    "myanmar",
    "mongolia",
    "kazakhstan",
    "uzbekistan",
    "asia",
    "apac",
)

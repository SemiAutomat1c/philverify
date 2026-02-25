"""
PhilVerify — Labeled Dataset for XLM-RoBERTa Fine-tuning (Phase 10)

100 labeled PH-news samples across three classes:
  0 = Credible    (verifiable, sourced reporting)
  1 = Unverified  (unconfirmed claims, speculation)
  2 = Likely Fake (disinformation, hoaxes, satire misread as fact)

Languages: English, Filipino/Tagalog, Taglish (code-switched)
"""

from __future__ import annotations
from dataclasses import dataclass

LABEL_NAMES = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}
LABEL_IDS   = {v: k for k, v in LABEL_NAMES.items()}
NUM_LABELS  = 3


@dataclass
class Sample:
    text: str
    label: int  # 0 | 1 | 2


# ── Full dataset ──────────────────────────────────────────────────────────────
# fmt: off
DATASET: list[Sample] = [

    # ── CREDIBLE (0) ──────────────────────────────────────────────────────────

    # English, sourced
    Sample("DOH reports 500 new COVID-19 cases as vaccination drive continues in Metro Manila", 0),
    Sample("Rappler: Supreme Court upholds Comelec ruling on disqualification case", 0),
    Sample("GMA News: PNP arrests 12 suspects in Bulacan drug bust", 0),
    Sample("Philippine Star: GDP growth slows to 5.3% in Q3 says BSP", 0),
    Sample("Inquirer: Senate passes revised anti-terrorism bill on third reading", 0),
    Sample("Manila Bulletin: Typhoon Carina leaves P2B damage in Isabela province", 0),
    Sample("ABS-CBN News: Marcos signs executive order on agricultural modernization", 0),
    Sample("DOF confirms revenue collection targets met for fiscal year 2025", 0),
    Sample("DSWD distributes relief packs to 10,000 families in Cotabato", 0),
    Sample("PhilStar: Meralco rate hike of P0.18 per kilowatt-hour approved by ERC", 0),
    Sample("PSA reports Philippine population grows to 115 million as of 2025 census", 0),
    Sample("Bangko Sentral ng Pilipinas keeps key policy rate at 6.50 percent", 0),
    Sample("DepEd announces K-12 curriculum review following PISA 2024 results", 0),
    Sample("PAGASA: Tropical storm Maring to make landfall in Quezon on Tuesday", 0),
    Sample("CHED approves 12 new state university programs in Mindanao", 0),
    Sample("LTO records 50,000 new vehicle registrations in January 2026", 0),
    Sample("PH army recovers high-powered weapons in Sulu operation", 0),
    Sample("BIR exceeds tax collection goal by P12 billion in first quarter", 0),
    Sample("Phivolcs raises alert level 2 over Mayon Volcano amid increased activity", 0),
    Sample("DOTr opens three new MRT-3 stations after P4.8B rehabilitation", 0),

    # Filipino/Tagalog sourced news
    Sample("Ayon sa DOH, 200 bata ang nagpabakuna laban sa tigdas ngayong linggo sa Maynila", 0),
    Sample("Inihayag ng PNP na 15 suspek ang nahuli sa operasyon laban sa droga sa Cavite", 0),
    Sample("Inaprubahan ng Senado ang panukalang batas para sa universal healthcare expansion", 0),
    Sample("Sinabi ng PAGASA na mula Lunes hanggang Miyerkules ay uulan sa buong Visayas", 0),
    Sample("Nakapag-ani ng P3 bilyon ang BIR mula sa drive laban sa tax evasion", 0),
    Sample("Nagbigay ng tulong ang DSWD sa 5,000 pamilya na tinamaan ng bagyo sa Leyte", 0),
    Sample("Ipinagutos ng Pangulo ang pagreview ng lahat ng kontrata ng DPWH sa mga probinsya", 0),
    Sample("Natuklasan ng NBI ang network ng mga pekeng lisensya sa Davao City", 0),
    Sample("Naglunsad ng libreng konsultasyon ang DOH para sa mga magsasaka sa Bukidnon", 0),
    Sample("Naipasa ng Kamara ang panukalang batas para sa dagdag na benepisyo ng SSS members", 0),

    # Taglish
    Sample("Sinabi ng BSP governor na ang inflation ay bumaba sa 3.2 percent ngayong Setyembre", 0),
    Sample("Ayon sa GMA News, naaprubahan na ng LGU ang P200M budget para sa road repair sa QC", 0),
    Sample("Inanunsyo ng DepEd na magkakaroon ng face-to-face classes sa lahat ng public schools", 0),
    Sample("Kinumpirma ng Malacañang na pumirma na ang Pangulo sa bagong minimum wage law", 0),

    # ── UNVERIFIED (1) ────────────────────────────────────────────────────────

    # English speculation / unconfirmed
    Sample("SHOCKING: Politician caught taking selfie during Senate hearing", 1),
    Sample("VIRAL: Celebrity spotted at secret meeting with government official", 1),
    Sample("BREAKING: 'Anonymous source' says president planning cabinet reshuffle", 1),
    Sample("Rumor has it: New tax policy to affect OFW remittances starting 2026", 1),
    Sample("CLAIM: Government hiding true COVID-19 death count from public", 1),
    Sample("Unconfirmed: Military says there are 500 rebels still in Mindanao", 1),
    Sample("REPORT: Certain barangay officials accepting bribes according to residents", 1),
    Sample("Alleged: Shipment of smuggled goods found in Manila port last week", 1),
    Sample("CLAIM: New mandatory vaccine policy for all government employees", 1),
    Sample("Source says: Manila Water to increase rates by 20% next month", 1),
    Sample("Tipster tells media: NBI raid on Binondo warehouse reportedly yielded millions", 1),
    Sample("Insiders claim: President to appoint new DILG secretary within the week", 1),
    Sample("Leaked memo allegedly shows plans to raise electricity rates next quarter", 1),
    Sample("Unverified claim: Bulk of calamity funds in Batangas unaccounted for", 1),
    Sample("Social media post alleges senator accepted donations from known oligarch", 1),
    Sample("Image circulating online claims to show bribe being given to traffic enforcer", 1),
    Sample("Reports suggest government may backtrack on jeepney modernization program", 1),
    Sample("Alleged screenshot shows lawmaker voting against bill they publicly supported", 1),
    Sample("Claims circulating that MMDA is planning total private vehicle ban in CBD", 1),
    Sample("Text messages spreading claim that LBC will suspend operations nationwide", 1),

    # Filipino/Tagalog unverified
    Sample("AYON SA ISANG PINAGMUMULAN: Magkakaroon daw ng dagdag na lockdown sa Maynila bukas", 1),
    Sample("HINDI KUMPIRMADO: Sinasabing mag-aanunsyo ang gobyerno ng bagong curfew sa lahat ng lungsod", 1),
    Sample("Di pa totoo? May nagsasabing babalik na daw ang face shields sa lahat ng opisina", 1),
    Sample("Mayroon daw nakitang anomalya sa bilangan ng botante sa tatlong lalawigan na ito", 1),
    Sample("Alegasyon: Kilalang pulitiko raw ay may kinalaman sa smuggling sa pantalan ng Batangas", 1),
    Sample("Kumakalat na mensahe: Daw ipinapatigil ng gobyerno ang distribution ng ayuda", 1),
    Sample("Walang kumpirmasyon: Sinasabing may bagong buwis na ipapataw sa social media users", 1),

    # Taglish unverified
    Sample("May rumor na lumabas na mag-iimpose ng bagong quarantine ang gobyerno ngayong December", 1),
    Sample("Allegedly, may senator na caught on camera na nagbibigay ng pera sa opisyal", 1),
    Sample("Hindi pa confirmed pero may claim na plano nang ipasara ang ilang major highways", 1),

    # ── LIKELY FAKE (2) ───────────────────────────────────────────────────────

    # English clear disinformation
    Sample("SHOCKING TRUTH: Bill Gates microchip found in COVID vaccine in Cebu!", 2),
    Sample("WATCH: Senator caught stealing money in Senate vault - full video", 2),
    Sample("CONFIRMED: Philippines to become 51st state of the United States in 2026!", 2),
    Sample("KATOTOHANAN: DOH secretly poisoning water supply to control population", 2),
    Sample("EXPOSED: Duterte has secret family in Davao that government is hiding", 2),
    Sample("100% TRUE: Garlic cures COVID-19, doctors don't want you to know this!", 2),
    Sample("Filipino scientist discovers cure for cancer suppressed by big pharma", 2),
    Sample("BREAKING: Entire Luzon to experience 3-day total blackout next week", 2),
    Sample("MUST SHARE! Government will confiscate all gold and silver from citizens!", 2),
    Sample("PROOF: COVID vaccines contain human embryo DNA, Vatican confirms", 2),
    Sample("Senator caught on camera eating P500,000 in taxpayer money - PROOF HERE!", 2),
    Sample("BIGO ANG GOBYERNO: Pres. Marcos secretly meeting foreign agents to sell Mindanao", 2),
    Sample("Doctors silenced after discovering that drinking bleach cures hypertension", 2),
    Sample("Vatican secret document shows Philippines is plan to be New World Order hub", 2),
    Sample("ALERT: New 5G towers releasing mind-control signals in Metro Manila!", 2),
    Sample("Exclusive: Deep state operatives running shadow government from Makati", 2),
    Sample("LEAKED VIDEO: General orders troops to shoot civilians in Marawi!", 2),
    Sample("FREE ELECTRICITY: Meralco ordered to give free power to all household starting March", 2),
    Sample("COVID SECRET: Hospitals paid P200,000 per death certificate listing COVID-19", 2),
    Sample("The moon landing was planned in a studio in Manila - Filipino whistleblower reveals", 2),

    # Filipino/Tagalog fake
    Sample("GRABE! Namatay daw ang tatlong tao sa bagong sakit na kumakalat sa Pilipinas!", 2),
    Sample("TOTOO BA? Marcos nagsabi na libreng kuryente na simula bukas!", 2),
    Sample("PANLOLOKO NG GOBYERNO: Nagtatago raw ng tunay na bilang ng patay sa COVID ang DOH!", 2),
    Sample("KATOTOHANAN NA TINATAGO: Ang tubig sa Maynila ay may lason na galing sa gobyerno!", 2),
    Sample("PANGANIB: Ang bagong bakuna ay may microchip na para subaybayan ang mga Pilipino!", 2),
    Sample("PILIPINAS IBEBENTA! Umabot na sa kasunduan ang gobyerno para ibigay ang Palawan sa China!", 2),
    Sample("LUMALABAS NA ANG KATOTOHANAN: Walang tunay na COVID sa ating bansa, ginawa lang ito!", 2),
    Sample("SIGURADONG TOTOO: Ang pagkain ng sibuyas ay lunas sa sakit na kanser!", 2),
    Sample("BIGLANG BALITA: Bukas ay walang pasok sa lahat ng opisina dahil sa bagong utos!", 2),
    Sample("EXPOSED NA SILA: Mga nangungunang Pilipino ay miyembro ng secret na illuminati!", 2),

    # Taglish clickbait / disinformation
    Sample("OMG! Natuklasan ng mga scientist na ang COVID vaccine pa-DAGA ka sa 5 taon, paki-share!", 2),
    Sample("LIBRE NA ANG KURYENTE: Pinagawa na raw ng Pangulo ang Meralco na magbigay ng libre power sa lahat!", 2),
    Sample("HINDI SASABIHIN NG GMA AT ABS-CBN: Ang tunay na cure sa COVID ay nasa ating kusina na lang!", 2),
    Sample("BIGLANG ANUNSYO: P100,000 para sa bawat mamamayan, pinirmahan na ng Pangulo ang check!", 2),
    Sample("VIRAL: Ang tubig sa bote ng Wilkins ay nasubok na may nanalalason na sangkap!", 2),
    Sample("NAGISING NA AKO: Ang mga doktor ay tinatago ang katotohanang ang suka ay lunas sa dengue!", 2),
]
# fmt: on


def get_dataset() -> list[Sample]:
    """Return the full dataset."""
    return DATASET


def get_split(
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[Sample], list[Sample]]:
    """
    Split dataset into train / validation sets.
    Stratified by label to preserve class balance.
    """
    import random
    rng = random.Random(seed)

    by_label: dict[int, list[Sample]] = {0: [], 1: [], 2: []}
    for s in DATASET:
        by_label[s.label].append(s)

    train, val = [], []
    for label_samples in by_label.values():
        shuffled = label_samples[:]
        rng.shuffle(shuffled)
        split_idx = max(1, int(len(shuffled) * train_ratio))
        train.extend(shuffled[:split_idx])
        val.extend(shuffled[split_idx:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def class_weights(samples: list[Sample]) -> list[float]:
    """
    Compute inverse-frequency class weights for imbalanced training.
    Returns a list of length NUM_LABELS.
    """
    from collections import Counter
    counts = Counter(s.label for s in samples)
    total = len(samples)
    weights = []
    for i in range(NUM_LABELS):
        weights.append(total / (NUM_LABELS * max(counts[i], 1)))
    return weights

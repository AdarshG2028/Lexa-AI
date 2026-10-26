from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpokenLanguage:
    """A language a learner can speak to the app in instead of English.

    Each language is its own entry rather than a parameter of a shared
    template: the ways they go wrong differ (how much English is mixed in,
    how far speech drifts from the written form, how well recognition copes),
    and what the model is told about each should be able to differ with them.
    """

    code: str  # ISO 639-1; also the code speech recognition is pinned to
    name: str
    native_name: str
    script: str
    # What the language model is told about how this language is spoken and
    # how its transcripts tend to look. Written for the model, not the user.
    speech_notes: str
    # What the learner is told about transcription quality, when it is worth
    # saying. Empty when recognition is reliable enough not to need a caveat.
    accuracy_note: str = ""
    # The Unicode block this language is written in. Used by the alternatives
    # report to reject an "original" that is really an English word, or a span
    # that mixes scripts: the model occasionally tidies a loanword into Latin
    # letters.
    script_range: tuple[int, int] = (0x0000, 0x007F)
    # English words that everyday speech mixes in, written in this script.
    # The script check cannot catch these - they are native letters spelling an
    # English word - so they are listed and dropped before the learner sees
    # them. Kept high-frequency rather than exhaustive.
    loanwords: frozenset[str] = field(default_factory=frozenset)
    # Words common enough that their English is worth surfacing. Used only to
    # order the report, never to hide an item that the provider proposed.
    common_words: frozenset[str] = field(default_factory=frozenset)
    # Grammar-only words (postpositions, particles, pronouns). Ignored when
    # deciding whether a span is entirely a loanword, so "मीटिंग में" is
    # recognised as the loanword "मीटिंग".
    function_words: frozenset[str] = field(default_factory=frozenset)


# Everyday Hindi words that are already English by another name. A learner who
# says "मीटिंग" does not need to be told it means "meeting".
HINDI_LOANWORDS = frozenset(
    {
        "ऑफिस", "ऑफ़िस", "मीटिंग", "टाइम", "फोन", "फ़ोन", "प्रॉब्लम", "प्रोब्लम",
        "स्कूल", "कॉलेज", "कालेज", "बस", "ट्रेन", "टिकट", "कंप्यूटर", "लैपटॉप",
        "मोबाइल", "इंटरनेट", "ईमेल", "इमेल", "मैसेज", "चैट", "डेटा", "सिस्टम",
        "वीडियो", "फोटो", "कैमरा", "बैंक", "बैटरी", "चार्जर", "मशीन", "प्रोजेक्ट",
        "इंटरव्यू", "जॉब", "सैलरी", "मार्केट", "शॉप", "होटल", "ट्रैफिक", "पुलिस",
        "डॉक्टर", "हॉस्पिटल", "कंपनी", "मैनेजर", "बॉस", "टीम", "डेडलाइन",
        "रिपोर्ट", "अकाउंट", "पासवर्ड", "लॉगिन", "अपडेट", "डाउनलोड", "अपलोड",
        "ऑर्डर", "बिल", "पेमेंट", "डिलीवरी", "एड्रेस", "नंबर", "फैमिली", "फ्रेंड",
        "पार्टी", "गिफ्ट", "कैश", "ऑनलाइन", "ऑफलाइन", "क्रिकेट", "फुटबॉल",
        "फिल्म", "मूवी", "प्रोग्राम", "क्लास", "टीचर", "स्टूडेंट", "न्यूज़", "टीवी",
    }
)

# Common enough that an English equivalent is useful to most learners. This is
# a ranking aid, not a whitelist: a provider's item is shown either way.
HINDI_COMMON_WORDS = frozenset(
    {
        "काम", "पैसा", "पैसे", "समय", "घर", "बात", "आदमी", "औरत", "बच्चा", "बच्चे",
        "दोस्त", "परिवार", "ज़रूरत", "जरूरत", "मदद", "सवाल", "जवाब", "सच", "झूठ",
        "खुशी", "गुस्सा", "डर", "उम्मीद", "फ़ैसला", "फैसला", "मौका", "मौक़ा",
        "तरीका", "वजह", "नतीजा", "हालत", "फ़र्क", "फर्क", "इंतज़ार", "इंतजार",
        "शुरू", "खत्म", "जल्दी", "धीरे", "अच्छा", "बुरा", "बड़ा", "छोटा", "नया",
        "पुराना", "मुश्किल", "आसान", "सही", "गलत", "ज़्यादा", "ज्यादा", "कम",
        "बहुत", "थोड़ा", "सब", "कुछ", "कोई", "हमेशा", "कभी", "अब", "बाद", "पहले",
        "आज", "कल", "हफ्ता", "हफ़्ता", "महीना", "साल", "सुबह", "शाम", "रात",
        "खाना", "पानी", "नींद", "बीमार", "सेहत", "शादी", "नौकरी", "तनख्वाह",
        "मेहनत", "आराम", "सफर", "रास्ता", "देश", "शहर", "गांव", "गाँव", "बाजार",
        "दुकान", "किताब", "पढ़ाई", "अपना", "अपनी", "लोग", "बातें", "सोच", "मन",
    }
)


HINDI_FUNCTION_WORDS = frozenset(
    {
        "का", "की", "के", "को", "में", "पर", "से", "और", "या", "ही", "भी", "तो",
        "ना", "नहीं", "है", "हैं", "था", "थी", "थे", "हो", "होगा", "होगी", "कर",
        "करके", "करना", "वाला", "वाली", "वाले", "लिए", "साथ", "बिना", "जैसा",
        "जैसी", "जैसे", "कि", "जो", "वह", "यह", "मैं", "हम", "तुम", "आप",
    }
)


HINDI = SpokenLanguage(
    code="hi",
    name="Hindi",
    native_name="हिन्दी",
    script="Devanagari",
    speech_notes=(
        "Everyday Hindi speech is full of English words (office, meeting, "
        "phone, time, problem), usually written in Devanagari. Those are "
        "already English, so they are never vocabulary worth translating. "
        "Sentences end with a verb and mark politeness through pronoun and "
        "verb endings."
    ),
    script_range=(0x0900, 0x097F),
    loanwords=HINDI_LOANWORDS,
    common_words=HINDI_COMMON_WORDS,
    function_words=HINDI_FUNCTION_WORDS,
)

KANNADA_LOANWORDS = frozenset(
    {
        "ಆಫೀಸ್", "ಮೀಟಿಂಗ್", "ಟೈಮ್", "ಫೋನ್", "ಪ್ರಾಬ್ಲಮ್", "ಸ್ಕೂಲ್", "ಕಾಲೇಜ್",
        "ಬಸ್", "ಟ್ರೇನ್", "ಟಿಕೆಟ್", "ಕಂಪ್ಯೂಟರ್", "ಲ್ಯಾಪ್ಟಾಪ್", "ಮೊಬೈಲ್",
        "ಇಂಟರ್ನೆಟ್", "ಇಮೇಲ್", "ಮೆಸೇಜ್", "ಡೇಟಾ", "ಸಿಸ್ಟಮ್", "ವಿಡಿಯೋ", "ಫೋಟೋ",
        "ಕ್ಯಾಮೆರಾ", "ಬ್ಯಾಂಕ್", "ಬ್ಯಾಟರಿ", "ಚಾರ್ಜರ್", "ಮೆಷಿನ್", "ಪ್ರಾಜೆಕ್ಟ್",
        "ಇಂಟರ್ವ್ಯೂ", "ಜಾಬ್", "ಸ್ಯಾಲರಿ", "ಮಾರ್ಕೆಟ್", "ಶಾಪ್", "ಹೋಟೆಲ್",
        "ಟ್ರಾಫಿಕ್", "ಪೊಲೀಸ್", "ಡಾಕ್ಟರ್", "ಹಾಸ್ಪಿಟಲ್", "ಕಂಪನಿ", "ಮ್ಯಾನೇಜರ್",
        "ಬಾಸ್", "ಟೀಮ್", "ಡೆಡ್ಲೈನ್", "ರಿಪೋರ್ಟ್", "ಅಕೌಂಟ್", "ಪಾಸ್ವರ್ಡ್",
        "ಲಾಗಿನ್", "ಅಪ್ಡೇಟ್", "ಡೌನ್ಲೋಡ್", "ಅಪ್ಲೋಡ್", "ಆರ್ಡರ್", "ಬಿಲ್",
        "ಪೇಮೆಂಟ್", "ಡೆಲಿವರಿ", "ಅಡ್ರೆಸ್", "ನಂಬರ್", "ಫ್ಯಾಮಿಲಿ", "ಫ್ರೆಂಡ್",
        "ಪಾರ್ಟಿ", "ಗಿಫ್ಟ್", "ಕ್ಯಾಶ್", "ಆನ್ಲೈನ್", "ಆಫ್ಲೈನ್", "ಕ್ರಿಕೆಟ್",
        "ಫುಟ್ಬಾಲ್", "ಸಿನಿಮಾ", "ಮೂವಿ", "ಪ್ರೋಗ್ರಾಂ", "ಕ್ಲಾಸ್", "ಟೀಚರ್",
        "ಸ್ಟೂಡೆಂಟ್", "ನ್ಯೂಸ್", "ಟಿವಿ",
    }
)

KANNADA_COMMON_WORDS = frozenset(
    {
        "ಕೆಲಸ", "ಹಣ", "ಸಮಯ", "ಮನೆ", "ಮಾತು", "ಮನುಷ್ಯ", "ಹೆಂಗಸು", "ಮಗು",
        "ಸ್ನೇಹಿತ", "ಕುಟುಂಬ", "ಅವಶ್ಯಕತೆ", "ಸಹಾಯ", "ಪ್ರಶ್ನೆ", "ಉತ್ತರ", "ಸತ್ಯ",
        "ಸುಳ್ಳು", "ಸಂತೋಷ", "ಕೋಪ", "ಭಯ", "ಆಸೆ", "ನಿರ್ಧಾರ", "ಅವಕಾಶ", "ದಾರಿ",
        "ಕಾರಣ", "ಫಲಿತಾಂಶ", "ಸ್ಥಿತಿ", "ವ್ಯತ್ಯಾಸ", "ಕಾಯುವುದು", "ಆರಂಭ", "ಮುಗಿತ",
        "ಬೇಗ", "ನಿಧಾನ", "ಒಳ್ಳೆಯ", "ಕೆಟ್ಟ", "ದೊಡ್ಡ", "ಚಿಕ್ಕ", "ಹೊಸ", "ಹಳೆಯ",
        "ಕಷ್ಟ", "ಸುಲಭ", "ಸರಿ", "ತಪ್ಪು", "ಜಾಸ್ತಿ", "ಕಮ್ಮಿ", "ತುಂಬಾ", "ಸ್ವಲ್ಪ",
        "ಎಲ್ಲ", "ಏನೋ", "ಯಾರೋ", "ಯಾವಾಗಲೂ", "ಎಂದಾದರೂ", "ಈಗ", "ನಂತರ", "ಮೊದಲು",
        "ಇವತ್ತು", "ನಾಳೆ", "ನಿನ್ನೆ", "ವಾರ", "ತಿಂಗಳು", "ವರ್ಷ", "ಬೆಳಿಗ್ಗೆ", "ಸಂಜೆ",
        "ರಾತ್ರಿ", "ಊಟ", "ನೀರು", "ನಿದ್ದೆ", "ಅನಾರೋಗ್ಯ", "ಆರೋಗ್ಯ", "ಮದುವೆ",
        "ಸಂಬಳ", "ಶ್ರಮ", "ವಿಶ್ರಾಂತಿ", "ಪ್ರಯಾಣ", "ದೇಶ", "ನಗರ", "ಹಳ್ಳಿ",
        "ಮಾರುಕಟ್ಟೆ", "ಅಂಗಡಿ", "ಪುಸ್ತಕ", "ಓದು", "ನಮ್ಮ", "ಜನ", "ಆಲೋಚನೆ", "ಮನಸ್ಸು",
    }
)

KANNADA_FUNCTION_WORDS = frozenset(
    {
        "ಮತ್ತು", "ಅಥವಾ", "ಆದರೆ", "ಎಂದು", "ಇದು", "ಅದು", "ನಾನು", "ನಾವು", "ನೀವು",
        "ಅವರು", "ಇಲ್ಲಿ", "ಅಲ್ಲಿ", "ನಲ್ಲಿ", "ಗೆ", "ಅನ್ನು", "ಅಿಂದ", "ಜೊತೆ", "ಬಗ್ಗೆ",
        "ಮೇಲೆ", "ಕೆಳಗೆ", "ಮುಂದೆ", "ನಂತರ", "ಹಾಗೂ", "ಇಲ್ಲ", "ಅಲ್ಲ", "ಆಗ", "ಈಗ",
        "ಏಕೆ", "ಏನು", "ಯಾರು", "ಎಲ್ಲಿ", "ಹೇಗೆ",
    }
)


KANNADA = SpokenLanguage(
    code="kn",
    name="Kannada",
    native_name="ಕನ್ನಡ",
    script="Kannada",
    speech_notes=(
        "Spoken Kannada differs from the literary written form, so colloquial "
        "verb endings and contractions are normal. Words carry long chains of "
        "suffixes: treat a word with its suffixes as one unit and give the "
        "English for its meaning in context, not for the bare root. English "
        "words are often mixed in."
    ),
    accuracy_note=(
        "Speech recognition for Kannada is imperfect, so some words may be "
        "spelled differently from how you said them."
    ),
    script_range=(0x0C80, 0x0CFF),
    loanwords=KANNADA_LOANWORDS,
    common_words=KANNADA_COMMON_WORDS,
    function_words=KANNADA_FUNCTION_WORDS,
)

TAMIL_LOANWORDS = frozenset(
    {
        "ஆபீஸ்", "மீட்டிங்", "டைம்", "போன்", "பிராப்ளம்", "ஸ்கூல்", "காலேஜ்",
        "பஸ்", "ட்ரெயின்", "டிக்கெட்", "கம்ப்யூட்டர்", "லேப்டாப்", "மொபைல்",
        "இன்டர்நெட்", "ஈமெயில்", "மெசேஜ்", "டேட்டா", "சிஸ்டம்", "வீடியோ",
        "போட்டோ", "கேமரா", "பேங்க்", "பேட்டரி", "சார்ஜர்", "மெஷின்",
        "ப்ராஜெக்ட்", "இன்டர்வியூ", "ஜாப்", "மார்க்கெட்", "ஷாப்", "ஹோட்டல்",
        "டிராஃபிக்", "போலீஸ்", "டாக்டர்", "ஹாஸ்பிடல்", "கம்பெனி", "மேனேஜர்",
        "பாஸ்", "டீம்", "டெட்லைன்", "ரிப்போர்ட்", "அக்கவுண்ட்", "பாஸ்வேர்ட்",
        "லாகின்", "அப்டேட்", "டவுன்லோட்", "அப்லோட்", "ஆர்டர்", "பில்",
        "பேமெண்ட்", "டெலிவரி", "அட்ரஸ்", "நம்பர்", "ஃபேமிலி", "ஃப்ரெண்ட்",
        "பார்ட்டி", "கிஃப்ட்", "கேஷ்", "ஆன்லைன்", "ஆஃப்லைன்", "கிரிக்கெட்",
        "ஃபுட்பால்", "சினிமா", "மூவி", "புரோகிராம்", "கிளாஸ்", "டீச்சர்",
        "ஸ்டூடண்ட்", "நியூஸ்", "டிவி",
    }
)

TAMIL_COMMON_WORDS = frozenset(
    {
        "வேலை", "பணம்", "நேரம்", "வீடு", "பேச்சு", "மனிதன்", "பெண்", "குழந்தை",
        "நண்பன்", "குடும்பம்", "தேவை", "உதவி", "கேள்வி", "பதில்", "உண்மை",
        "பொய்", "சந்தோஷம்", "கோபம்", "பயம்", "நம்பிக்கை", "முடிவு", "வாய்ப்பு",
        "வழி", "காரணம்", "விளைவு", "நிலை", "வித்தியாசம்", "காத்திருப்பு",
        "தொடக்கம்", "சீக்கிரம்", "மெதுவாக", "நல்ல", "மோசமான", "பெரிய", "சிறிய",
        "புதிய", "பழைய", "கஷ்டம்", "எளிது", "சரி", "தப்பு", "அதிகம்", "குறைவு",
        "மிகவும்", "கொஞ்சம்", "எல்லாம்", "ஏதோ", "யாரோ", "எப்போதும்", "எப்போதாவது",
        "இப்போது", "பிறகு", "முன்பு", "இன்று", "நாளை", "நேற்று", "வாரம்",
        "மாதம்", "வருடம்", "காலை", "மாலை", "இரவு", "சாப்பாடு", "தண்ணீர்",
        "தூக்கம்", "நோய்", "உடல்நலம்", "கல்யாணம்", "சம்பளம்", "முயற்சி", "ஓய்வு",
        "பயணம்", "பாதை", "நாடு", "நகரம்", "கிராமம்", "சந்தை", "கடை", "புத்தகம்",
        "படிப்பு", "நம்", "மக்கள்", "எண்ணம்", "மனம்",
    }
)

TAMIL_FUNCTION_WORDS = frozenset(
    {
        "மற்றும்", "அல்லது", "ஆனால்", "என்று", "இது", "அது", "நான்", "நாங்கள்",
        "நீங்கள்", "அவர்கள்", "இங்கே", "அங்கே", "இல்", "க்கு", "ஐ", "இருந்து",
        "உடன்", "பற்றி", "மேல்", "கீழ்", "முன்", "பின்", "இல்லை", "அல்ல", "ஆக",
        "ஏன்", "என்ன", "யார்", "எங்கே", "எப்படி",
    }
)


TAMIL = SpokenLanguage(
    code="ta",
    name="Tamil",
    native_name="தமிழ்",
    script="Tamil",
    speech_notes=(
        "Spoken Tamil differs substantially from literary Tamil: colloquial "
        "forms, dropped endings and merged words are normal, not mistakes. "
        "Words take long chains of suffixes, so treat a word with its "
        "suffixes as one unit and give the English for its meaning in "
        "context. English words are often mixed in."
    ),
    script_range=(0x0B80, 0x0BFF),
    loanwords=TAMIL_LOANWORDS,
    common_words=TAMIL_COMMON_WORDS,
    function_words=TAMIL_FUNCTION_WORDS,
)

TELUGU_LOANWORDS = frozenset(
    {
        "ఆఫీస్", "మీటింగ్", "టైమ్", "ఫోన్", "ప్రాబ్లమ్", "స్కూల్", "కాలేజ్",
        "బస్", "ట్రెయిన్", "టికెట్", "కంప్యూటర్", "ల్యాప్టాప్", "మొబైల్",
        "ఇంటర్నెట్", "ఈమెయిల్", "మెసేజ్", "డేటా", "సిస్టమ్", "వీడియో", "ఫోటో",
        "కెమెరా", "బ్యాంక్", "బ్యాటరీ", "చార్జర్", "మెషిన్", "ప్రాజెక్ట్",
        "ఇంటర్వ్యూ", "జాబ్", "సాలరీ", "మార్కెట్", "షాప్", "హోటల్",
        "ట్రాఫిక్", "పోలీస్", "డాక్టర్", "హాస్పిటల్", "కంపెనీ", "మేనేజర్",
        "బాస్", "టీమ్", "డెడ్లైన్", "రిపోర్ట్", "అకౌంట్", "పాస్వర్డ్",
        "లాగిన్", "అప్డేట్", "డౌన్లోడ్", "అప్లోడ్", "ఆర్డర్", "బిల్",
        "పేమెంట్", "డెలివరీ", "అడ్రస్", "నంబర్", "ఫ్యామిలీ", "ఫ్రెండ్",
        "పార్టీ", "గిఫ్ట్", "క్యాష్", "ఆన్లైన్", "ఆఫ్లైన్", "క్రికెట్",
        "ఫుట్బాల్", "సినిమా", "మూవీ", "ప్రోగ్రామ్", "క్లాస్", "టీచర్",
        "స్టూడెంట్", "న్యూస్", "టీవీ",
    }
)

TELUGU_COMMON_WORDS = frozenset(
    {
        "పని", "డబ్బు", "సమయం", "ఇల్లు", "మాట", "మనిషి", "స్త్రీ", "పిల్లవాడు",
        "స్నేహితుడు", "కుటుంబం", "అవసరం", "సహాయం", "ప్రశ్న", "జవాబు", "నిజం",
        "అబద్ధం", "సంతోషం", "కోపం", "భయం", "ఆశ", "నిర్ణయం", "అవకాశం", "మార్గం",
        "కారణం", "ఫలితం", "పరిస్థితి", "తేడా", "ఎదురుచూపు", "ప్రారంభం", "ముగింపు",
        "త్వరగా", "నెమ్మదిగా", "మంచి", "చెడు", "పెద్ద", "చిన్న", "కొత్త", "పాత",
        "కష్టం", "సులభం", "సరి", "తప్పు", "ఎక్కువ", "తక్కువ", "చాలా", "కొంచెం",
        "అన్నీ", "ఏదో", "ఎవరో", "ఎప్పుడూ", "ఎప్పుడైనా", "ఇప్పుడు", "తర్వాత",
        "ముందు", "ఈరోజు", "రేపు", "నిన్న", "వారం", "నెల", "సంవత్సరం", "ఉదయం",
        "సాయంత్రం", "రాత్రి", "భోజనం", "నీళ్ళు", "నిద్ర", "అనారోగ్యం", "ఆరోగ్యం",
        "పెళ్లి", "జీతం", "శ్రమ", "విశ్రాంతి", "ప్రయాణం", "దేశం", "నగరం",
        "గ్రామం", "సంత", "దుకాణం", "పుస్తకం", "చదువు", "మన", "ప్రజలు",
        "ఆలోచన", "మనసు",
    }
)

TELUGU_FUNCTION_WORDS = frozenset(
    {
        "మరియు", "లేదా", "కానీ", "అని", "ఇది", "అది", "నేను", "మేము", "మీరు",
        "వారు", "ఇక్కడ", "అక్కడ", "లో", "కు", "ను", "నుంచి", "తో", "గురించి",
        "మీద", "కింద", "ముందు", "తర్వాత", "లేదు", "కాదు", "అప్పుడు", "ఎందుకు",
        "ఏమి", "ఎవరు", "ఎక్కడ", "ఎలా",
    }
)


TELUGU = SpokenLanguage(
    code="te",
    name="Telugu",
    native_name="తెలుగు",
    script="Telugu",
    speech_notes=(
        "Spoken Telugu differs from the literary form and words carry long "
        "chains of suffixes: treat a word with its suffixes as one unit and "
        "give the English for its meaning in context. Recognition is "
        "imperfect, so a transcript may contain odd spellings; infer "
        "the intended word from how it would sound, but always quote exactly "
        "what is written. English words are often mixed in."
    ),
    accuracy_note=(
        "Speech recognition for Telugu is imperfect, so some words may be "
        "spelled differently from how you said them."
    ),
    script_range=(0x0C00, 0x0C7F),
    loanwords=TELUGU_LOANWORDS,
    common_words=TELUGU_COMMON_WORDS,
    function_words=TELUGU_FUNCTION_WORDS,
)

# Order is the order a learner sees them in.
SUPPORTED_LANGUAGES: tuple[SpokenLanguage, ...] = (HINDI, KANNADA, TAMIL, TELUGU)

_BY_CODE = {language.code: language for language in SUPPORTED_LANGUAGES}


def get_language(code: str | None) -> SpokenLanguage | None:
    """The language for a code, or None when it is not supported."""
    if not code:
        return None
    return _BY_CODE.get(code.strip().lower())

// Report content, part 2: Methodology, Algorithms, Diagrams.
module.exports = [
  { t: "h1", x: "4. PROPOSED METHODOLOGY AND WORK DESCRIPTION" },
  { t: "h2", x: "4.1 Design Approach" },
  {
    t: "p",
    x: "The system was designed around four principles, each of which resolved a specific risk. The first is separation of concerns along a one-directional dependency chain: the HTTP layer parses and serialises, the service layer orchestrates a turn, provider adapters speak to vendors, and repositories persist state. Nothing above the adapter layer imports a vendor SDK, so a change of provider does not reach business logic.",
  },
  {
    t: "p",
    x: "The second principle is that judgement and invariants are separated. A language model is well suited to deciding which sentence contains a tense error or which native word is worth translating, and poorly suited to counting occurrences, summing scores or guaranteeing that a quotation exists in the transcript. Model output is therefore treated as a proposal, and deterministic code decides what is allowed into a report and what score is displayed. This is the single most important design decision in the project, and it is visible in every analysis.",
  },
  {
    t: "p",
    x: "The third principle is graceful degradation. A missing optional key, an exhausted voice quota or an absent Sarvam subscription must reduce capability rather than break a session. Speech synthesis therefore has an ordered fallback chain, the bridge languages fall back to the default recogniser when Sarvam is unconfigured, and pronunciation can be switched off entirely. Each degradation is visible in the health endpoint or in the response, so a downgrade is never silent.",
  },
  {
    t: "p",
    x: "The fourth principle is that the system should be demonstrable and testable without network access. Offline implementations exist for every provider role, and setting the providers to their mock values runs the entire pipeline deterministically. This choice supports the automated test suite, but it also proves that the abstractions are real rather than nominal.",
  },
  { t: "h2", x: "4.2 Overall Architecture" },
  {
    t: "p",
    x: "Figure 1 shows the layered architecture. The browser client captures audio and performs voice-activity detection locally, then communicates with the API over HTTPS using JSON and multipart uploads. The API layer exposes session, turn, analysis, video and health routes. The domain services implement conversation orchestration, video ingestion and the five analyses. Persistence is provided by a relational database and an audio store. Provider adapters isolate Groq, Sarvam and Deepgram, while the pronunciation model runs locally.",
  },
  {
    t: "fig",
    n: 1,
    file: "fig01_architecture.png",
    caption: "Layered architecture of the system",
  },
  {
    t: "p",
    x: "Two properties of the diagram deserve emphasis. First, the boundaries between layers are logical rather than process boundaries: the API, services and adapters run in one Python process, and the dashed regions indicate responsibility, not deployment. Second, the conversation service depends on interfaces, not on vendor SDKs. The registry chooses a concrete adapter at start-up from configuration, and the service receives the resulting object through dependency injection.",
  },
  { t: "h2", x: "4.3 Provider Abstraction and Registry" },
  {
    t: "p",
    x: "Seven provider roles are defined as Python protocols: speech-to-text, language model, text-to-speech, grammar analysis, vocabulary analysis, pronunciation and English alternatives. Each role has at least one hosted implementation and one offline implementation. The registry is the only place that maps a configured name, such as “groq” or “wav2vec2”, to a class. This keeps configuration knowledge in one file and makes the addition of a provider a local change.",
  },
  {
    t: "p",
    x: "Speech-to-text has a second dimension because the bridge requires per-language routing. A routing adapter holds a default provider and a dictionary from language code to provider. The registry constructs the router only when the default provider is not the mock, the routed-language list is non-empty and the Sarvam key is present; otherwise the default serves every language and a warning is logged at start-up. The conversation service is unaware of the routing; it passes the session's spoken language to a single interface.",
  },
  {
    t: "p",
    x: "Text-to-speech uses an ordered fallback chain rather than a single provider. The primary is tried first; if it fails with a provider error, the next configured provider is attempted, and the response records which provider actually served the audio. Providers without credentials are skipped rather than treated as failures, so listing an unconfigured fallback is safe. This mechanism was added after observing that free-tier voice quotas are the most likely cause of a failed demonstration.",
  },
  { t: "h2", x: "4.4 Lifecycle of a Conversational Turn" },
  {
    t: "p",
    x: "A turn begins when the browser posts a recorded audio segment. The backend validates the declared type and the actual byte size, normalises the audio to 16 kHz mono WAV with FFmpeg [17], stores the normalised file, and sends it to the configured speech-to-text provider with the session's language explicitly pinned [18]. The resulting transcript and word timings are stored on the turn. The service then loads a bounded window of previous exchanges, constructs the message list, and requests a reply from the language model [19]. The reply text is synthesised, the audio is stored, and the complete exchange is persisted as one turn. The HTTP response carries the transcript, the reply text, the reply audio URL, the provider that served the audio, the number of history messages sent, and a breakdown of timings.",
  },
  {
    t: "p",
    x: "Figure 2 expresses this as a sequence diagram. The numbering makes the critical path explicit: recognition, history construction, generation and synthesis are sequential, and persistence follows synthesis so that a turn is never stored without its reply. The figure also shows that the model sees only the bounded history window; the complete transcript remains in storage for the analyses.",
  },
  {
    t: "fig",
    n: 2,
    file: "fig02_sequence.png",
    caption: "Sequence of messages for one conversational turn",
  },
  {
    t: "p",
    x: "Two design details are worth recording. Transcription pins the language on every request instead of relying on auto-detection, because auto-detection mislabelled Kannada as Tamil and Telugu as Hindi during development. And the normalisation step is executed in a worker thread, because a blocking FFmpeg subprocess would otherwise stall the event loop for every concurrent request.",
  },
  { t: "h2", x: "4.5 Conversation Context Management" },
  {
    t: "p",
    x: "A five-to-eight-minute conversation can contain dozens of exchanges. Replaying all of them on every turn would grow cost and latency without bound, so two limits apply: at most twelve recent exchanges and at most eight thousand characters. When the character budget is exceeded, the oldest exchanges are dropped until the history fits. Trimming always removes a complete exchange, never half of one, so the model is never shown a reply whose question has disappeared. Each turn response reports the number of messages actually sent, which makes the context window observable rather than assumed.",
  },
  {
    t: "p",
    x: "The partner is instructed to reply briefly, to end with a follow-up question and not to correct the learner's mistakes during the conversation. Correction is the job of the analyses. That separation keeps the conversation natural and prevents the partner from turning every turn into a lesson, while ensuring that the report, not the dialogue, carries the diagnosis.",
  },
  { t: "h2", x: "4.6 Session Lifecycle" },
  {
    t: "p",
    x: "A session begins in the active state. It becomes completed when the learner ends it, an operation that is idempotent, and becomes expired when no turn has been received for thirty minutes. Idleness is measured from the last turn rather than from session start, so a long conversation never times out while it is in progress. Only an active session accepts new turns; a completed session returns a conflict error and an expired session returns a gone error. Both remain fully readable, because the transcript is the input to every later analysis and ending a conversation must not make it inaccessible.",
  },
  { t: "h2", x: "4.7 Audio Ingestion and Normalisation" },
  {
    t: "p",
    x: "Every audio path converges on the same normalisation routine. The uploaded file is written to a temporary location while its size is checked against a 25 MB limit, its duration is probed with FFprobe, and FFmpeg converts it to a single-channel 16 kHz signed 16-bit PCM WAV, discarding any video stream [17]. Audio that exceeds five minutes is rejected. Browser recordings sometimes arrive without a declared duration because MediaRecorder writes a streaming container; such files are accepted and measured after conversion rather than rejected on a missing header. The normalised file is what the speech recogniser receives, what the pronunciation model receives, and what the learner can download later.",
  },
  {
    t: "p",
    x: "Nine container formats are accepted for audio and six for video, which covers the formats produced by common browsers, phones and presentation software. A mislabelled file is detected during probing and reported as invalid audio rather than being passed to a provider.",
  },
  { t: "h2", x: "4.8 Language Bridge" },
  {
    t: "p",
    x: "The bridge reuses the conversation machinery with three differences. The session is created with the bridge mode and an explicit spoken language; the recognition request is pinned to that language; and the partner is instructed to answer in simple English only, never in the learner's language and never in mixed script. The reply is therefore immediately useful as a model of how the learner's meaning could be expressed in English, and it is also played as speech.",
  },
  {
    t: "p",
    x: "Kannada, Tamil and Telugu are transcribed by Sarvam's saaras:v4 model, which takes a BCP-47 language code as an explicit input and is trained with Indian languages at the centre of its distribution [20]. Hindi and English remain on Whisper, because Whisper is strong on both and there was no measured reason to move Hindi [18]. The routing is configuration-driven: adding or removing a language code changes the route without a code change, and an absent Sarvam key leaves all languages on the default provider.",
  },
  {
    t: "p",
    x: "At the end of a bridge session, the alternatives analysis asks the language model for English equivalents of native-language words and phrases the learner used. Every proposal then passes a deterministic validation pipeline: the English side must be non-empty and written in Latin script; the native side must occur in the transcript within a similarity of 0.8 and must not exceed six words; it must contain at least one character from the language's Unicode block and no Latin letter; it must not consist entirely of known English loanwords; and duplicates and self-translations are removed. Survivors are ranked so that common native words come first and are capped at twelve. The reported native side is always replaced by the exact transcribed span, so the learner never sees a tidied or invented spelling. The result is unscored and presented with a short recognition caveat.",
  },
  { t: "h2", x: "4.9 Video Review" },
  {
    t: "p",
    x: "Video review accepts files up to 200 MB and five minutes. The upload is streamed to a temporary file one megabyte at a time while the received byte count is enforced, rather than trusting a declared content length. The first audio track is extracted and normalised, transcribed with English pinned, and the transcript is checked for speech. A successful ingestion produces a completed session in the video mode with one learner turn and no assistant reply; the video file is deleted, and only the normalised audio, transcript and timings are retained. Ingestion makes no language-model or synthesis call, so a slow provider does not hold the upload open longer than transcription requires.",
  },
  { t: "h2", x: "4.10 Reliability, Limits and Error Handling" },
  {
    t: "p",
    x: "Provider failures are translated at the adapter boundary into a small set of application errors, so that no vendor-shaped payload or HTTP status reaches the service layer. The API returns a single error envelope containing a stable code, a human-readable message and optional details. Codes distinguish invalid or oversized input, missing or inactive sessions, inapplicable analyses, provider unavailability, timeouts, configuration errors and internal failures. A catch-all handler ensures that an unexpected exception never leaks internal detail to the client. Synthesis failures are contained by the ordered fallback chain described in Section 4.3; in the deployed configuration Deepgram provides the primary voice and Groq the first fallback [21].",
  },
  {
    t: "p",
    x: "Rate limiting is implemented as a pure ASGI middleware with a sliding sixty-second window and three buckets: twenty turns per minute, ten analyses per minute and one hundred and twenty general requests per minute. Health checks and preflight requests are exempt. The client address is taken from the forwarded header using a configurable number of trusted proxy hops, reading from the right-hand end, because the left-hand end can be forged. A limited request receives a 429 response with a retry hint and with CORS headers intact, which required adding the limiter before the CORS middleware so that it is the inner layer.",
  },
  {
    t: "p",
    x: "Cross-origin access is restricted to configured front-end origins, with an optional regular expression for preview deployments. Credentials are not allowed, because the application uses no cookies and no authentication headers.",
  },
  { t: "h2", x: "4.11 Data Storage Approach" },
  {
    t: "p",
    x: "A session is stored as one row, its turns as child rows, and its analysis as a single row with one nullable section per analysis. Findings are stored as child rows so that they can be queried later, for example to ask which filler words recur. Audio is not stored in the database: turn rows hold the storage key, format, duration and size, while the bytes live behind a storage interface that writes to local disk in the current deployment. This keeps the database small and allows the audio store to be replaced by object storage without a schema change.",
  },
  {
    t: "p",
    x: "The repository interface has two implementations, an in-memory store and a SQL store, and both are verified against the same contract test suite. The SQL implementation uses SQLAlchemy's asynchronous engine and, in production, a managed PostgreSQL instance. Because SQLite does not preserve time zones, a custom column type normalises timestamps to UTC on write and restores them on read; without it, the idle-expiry check would compare naive and aware datetimes.",
  },

  { t: "h1", x: "5. PROPOSED ALGORITHMS" },
  { t: "h2", x: "5.1 Principle: Model Proposes, Code Decides" },
  {
    t: "p",
    x: "All five analyses follow the same pattern. The language model or acoustic model produces candidate findings or measurements; deterministic code then validates, filters, aggregates and scores them. The pattern is not stylistic. Language models vary between runs, miscount, and occasionally quote text that was never said; acoustic models produce spurious substitutions at accents and word boundaries. Placing scoring and evidence checks in code makes the output reproducible for a given input and makes every number explainable to the learner.",
  },
  { t: "h2", x: "5.2 Grammar Analysis" },
  {
    t: "p",
    x: "Only learner turns are analysed; the partner's replies are excluded. The learner's text is split into sentences at sentence-final punctuation, and each sentence is sent to the configured grammar provider, which returns issues with a category, a quotation, a correction, an explanation and a confidence. Eight categories are used: tense, articles, prepositions, subject-verb agreement, plurals, word form, sentence structure and other. Because the input is transcribed speech, the provider is instructed not to report punctuation or capitalisation.",
  },
  {
    t: "p",
    x: "The returned issues are filtered before display. Findings below a confidence of 0.4 are discarded, duplicates are removed, and no more than twenty-five are reported. A reduction step then removes a finding whose quotation contains an already-reported narrower quotation of the same category, and removes a broad finding that merely restates two or more findings already made. This handles the observed tendency of a model to report both “I go to college yesterday” and the narrower “go” for the same tense error.",
  },
  {
    t: "p",
    x: "Scoring is performed in code and groups issues by sentence, so that a sentence containing three mistakes counts once as a flawed sentence rather than three times. Each flawed sentence costs the confidence of its strongest finding, and the score is",
  },
  { t: "eq", x: "score = 100 − min(1, Σ w(s) / S) × 100" },
  {
    t: "p",
    x: "where S is the number of analysed sentences and w(s) is the worst confidence among the findings attached to sentence s. A conversation with no findings scores 100, because absence of evidence of error is not evidence of poor grammar. The transcript itself is never rewritten; every issue carries its own copy of the quoted sentence, and a test asserts that the stored transcript is byte-identical before and after analysis.",
  },
  { t: "h2", x: "5.3 Vocabulary Analysis" },
  {
    t: "p",
    x: "Counting is performed in code, and the provider is asked only for suggestions. This division follows from the observation that “you said this phrase four times” is arithmetic, and that a model asked to count will sometimes be wrong. The analysis detects four issue types: repeated words, repeated phrases, over-used basic words, and expressions that are grammatical but unnatural.",
  },
  {
    t: "p",
    x: "Tokens are lower-cased and stripped of surrounding punctuation. Stop words are excluded from repetition counts. The repetition threshold scales with conversation length as max(3, round(W / 60)), where W is the number of analysed words, so that three occurrences in eighty words count as a habit while three in eight hundred do not. Phrases of two and three words are counted after trimming stop words from both ends, so the learner is told about “very good” rather than “was very good”; a three-word phrase that recurs at least twice suppresses the two-word phrases it contains, so the same habit is not reported twice. A list of twenty-one basic words, including “good”, “bad”, “nice”, “thing”, “stuff”, “very” and “really”, is flagged at three occurrences. Suggestions are capped at four per issue and issues at twelve.",
  },
  {
    t: "p",
    x: "The vocabulary score charges only repetition beyond the threshold, because using a word up to its threshold is normal speech. When the excess reaches fifteen per cent of all words spoken, the score reaches zero. Lexical diversity, measured as the type-token ratio, is reported but deliberately not scored: the ratio falls as any text grows longer, so scoring it would penalise a learner for speaking more.",
  },
  { t: "h2", x: "5.4 Fluency Analysis" },
  {
    t: "p",
    x: "Fluency is measured rather than judged. It consumes the word timings that the recogniser returns with the transcript, which are stored on the turn at transcription time; re-transcribing later would spend another provider call on data already held. All timings are accumulated per learner turn, never across turns, so that silence while the partner is speaking is not attributed to the learner.",
  },
  {
    t: "p",
    x: "A gap of at least 0.5 seconds between consecutive words is counted as a pause and a gap of at least 1.0 second as a long pause. Speaking rate is the number of words divided by the analysed seconds, expressed in words per minute, and articulation rate excludes pause time. The comfortable band is 110 to 160 words per minute. Filled pauses are counted from a list of single tokens, including “um”, “uh”, “erm”, “er”, “ah”, “hmm”, “mm” and “eh”, and from multi-word phrases such as “you know”, “I mean”, “sort of”, “kind of” and “what do you call it”; a small set of soft markers, including “like”, “actually”, “basically” and “literally”, is counted separately. An immediate repetition of the same word is counted once, and a restart is identified when the same two-word pair recurs within six tokens in the same turn, with overlapping hits counted once. At most fifteen findings are reported.",
  },
  {
    t: "p",
    x: "The score has four equally weighted parts, each capped at twenty-five points: rate outside the comfortable band, long pauses per minute, fillers per hundred words and disfluencies per hundred words. No single habit can therefore sink the score alone, and the arithmetic remains explainable. A typed conversation returns a null fluency score with an explanation rather than a fabricated number.",
  },
  { t: "h2", x: "5.5 Pronunciation Analysis" },
  {
    t: "p",
    x: "Pronunciation analysis compares the sounds a speaker produced with the sounds their words require. Two sequences are built independently, as shown in Figure 3. On the reference path, the transcript is converted to phonemes by g2p_en, which uses the CMU Pronouncing Dictionary where possible and a neural model otherwise; ARPAbet symbols are then mapped to IPA through a thirty-nine-entry table. On the acoustic path, the normalised 16 kHz audio is passed to a wav2vec2 model fine-tuned for phoneme recognition, which emits IPA symbols directly. The tokenizer is loaded with phonemisation disabled, so no espeak installation is required.",
  },
  {
    t: "fig",
    n: 3,
    file: "fig03_pronunciation.png",
    caption: "Pronunciation analysis pipeline: acoustic and reference paths, alignment and evidence filters",
  },
  {
    t: "p",
    x: "The acoustic model classifies every twenty milliseconds and produces a posterior distribution over phonemes. The decoder takes the most probable label per frame, collapses runs of identical labels and removes blanks, in the standard CTC manner, and records the mean posterior probability of each surviving phoneme as its confidence. The two sequences are then aligned globally with the Needleman-Wunsch algorithm using unit substitution and gap costs, which yields the minimum-cost edit script between them. Alignment, rather than position-by-position comparison, prevents a single insertion or deletion from shifting every subsequent phoneme and producing a cascade of false errors.",
  },
  {
    t: "p",
    x: "Mismatches from the alignment are candidate substitutions. Before aggregation, two corrections are applied. Notation folding treats transcription differences as equivalent, for example /ʌ/ and /ɐ/, /ɜː/ and /ɚ/, and flapped or glottal variants of /t/ and /ɹ/; these are properties of the dictionaries and the acoustic model, not mispronunciations. Reduced vowels in a list of forty-one function words are not judged, because nobody pronounces “and” with the vowel a dictionary gives it; consonants in those words are still assessed, otherwise almost all evidence for /ð/ would disappear.",
  },
  {
    t: "p",
    x: "The surviving substitutions are aggregated per phoneme pair across the whole conversation. Four evidence filters then decide what may be reported: a pattern must occur at least three times, its mean confidence must be at least 0.55, it must appear in at least two different words, and at most eight findings may be shown, each with at most six example words. Findings are ordered by occurrence count and then by confidence.",
  },
  {
    t: "p",
    x: "The score is",
  },
  { t: "eq", x: "score = 100 − min(1, (Σ occurrences × confidence / W) / 0.25) × 100" },
  {
    t: "p",
    x: "where W is the number of analysed words and the inner sum runs over reported patterns. A learner whose speech produces no trustworthy pattern therefore scores 100, and a pattern that affects a quarter of all words drives the score to zero. Practice suggestions are drawn from a small hand-written list of drill words for twenty-seven phonemes, for example “think, three, thank, path, birthday” for /θ/. The wording is deliberately advisory, describing a sound as worth practising rather than declaring it wrong.",
  },
  { t: "h2", x: "5.6 English Alternatives Validation" },
  {
    t: "p",
    x: "The alternatives analysis is the clearest example of the propose-and-verify pattern. The model is given the learner's utterances, the language name and script, speech notes and a sample of known loanwords, and is asked for a JSON list of native-language expressions with English equivalents. Each proposal is then subjected to six checks in order: the English side must be non-empty and written in Latin script; the native side must match a real transcribed span within a similarity of 0.8 using a sliding window of the quoted length plus or minus one word; it must contain no Latin letter and at least one letter from the language's Unicode block; it must not consist entirely of loanwords, ignoring function words so that a loanword carrying a postposition is still recognised; it must not duplicate an earlier item or translate to itself; and it must not exceed six words. Survivors are ranked by whether they contain a common native word, and the list is capped at twelve. The matched span replaces the model's quotation, so the report shows what was heard.",
  },
  { t: "h2", x: "5.7 Thresholds and Constants" },
  {
    t: "p",
    x: "Table 3 collects the thresholds that determine behaviour. They are defined as named constants in the source and covered by tests, so that a change is deliberate rather than accidental.",
  },
  {
    t: "tbl",
    n: 3,
    caption: "Principal analysis thresholds and limits",
    widths: [2500, 2350, 3850],
    head: ["Analysis", "Constant", "Value and effect"],
    rows: [
      ["Grammar", "Minimum confidence", "0.4; findings below this are discarded"],
      ["Grammar", "Maximum issues", "25 per conversation"],
      ["Vocabulary", "Repetition threshold", "max(3, round(words / 60)) occurrences"],
      ["Vocabulary", "Basic-word threshold", "3 occurrences before flagging"],
      ["Vocabulary", "Excess for zero score", "15 per cent of all words"],
      ["Fluency", "Pause / long pause", "0.5 s / 1.0 s"],
      ["Fluency", "Comfortable rate", "110–160 words per minute"],
      ["Fluency", "Maximum findings", "15"],
      ["Pronunciation", "Minimum occurrences", "3 per phoneme pattern"],
      ["Pronunciation", "Minimum mean confidence", "0.55"],
      ["Pronunciation", "Minimum distinct words", "2"],
      ["Pronunciation", "Maximum issues", "8"],
      ["Alternatives", "Transcript match similarity", "0.8 (difflib ratio)"],
      ["Alternatives", "Maximum span length", "6 words; at most 12 items reported"],
    ],
  },
  { t: "h2", x: "5.8 Computational Cost" },
  {
    t: "p",
    x: "The deterministic parts are inexpensive relative to the provider calls. Grammar and vocabulary processing are linear in the number of words apart from phrase counting, which is linear in the number of phrase positions with a small constant for lengths two and three. Fluency is a single pass over word timings. Pronunciation is dominated by the acoustic model, not by the algorithms: alignment is O(mn) in the lengths of the expected and observed phoneme sequences, which for a sentence of twenty words is a few hundred symbols and therefore negligible. The model itself runs at roughly 1.35 times real time on four CPU threads in the reported configuration, and its weights are loaded once and held for the life of the process.",
  },

  { t: "h1", x: "6. PROPOSED FLOWCHART, BLOCK DIAGRAM AND DATA-FLOW DIAGRAMS" },
  {
    t: "p",
    x: "This chapter presents the data-flow and workflow views of the system. The layered block diagram appears as Figure 1 in Chapter 4, where it supports the architectural discussion; the diagrams here show the same system from the perspectives of data movement and user workflow.",
  },
  { t: "h2", x: "6.1 Context Diagram (Level 0)" },
  {
    t: "p",
    x: "Figure 4 is the level-0 data-flow diagram. The learner is the only human actor. The system exchanges audio, control information and reports with the learner's browser; requests and responses with external speech and language providers; and records with the database and the audio store. An uploaded video is shown as a separate external input because it enters the system without a microphone and without a live conversation.",
  },
  {
    t: "fig",
    n: 4,
    file: "fig05_context_dfd.png",
    caption: "Level-0 data-flow diagram (context diagram)",
  },
  {
    t: "p",
    x: "The diagram makes an important boundary explicit: the providers are external systems, not parts of the application. The application owns the orchestration, the validation and the stored record; the providers own recognition, generation and synthesis. That separation is what allows a provider to be replaced without changing the flows that the learner experiences.",
  },
  { t: "h2", x: "6.2 Level-1 Data-Flow Diagram" },
  {
    t: "p",
    x: "Figure 5 decomposes the system into six processes and three data stores. Process 1 captures and validates incoming audio. Process 2 transcribes it and generates the reply. Process 3 persists the turn and its audio. Process 4 analyses English speech. Process 5 builds the language bridge. Process 6 ingests a video. The stores hold the session and turn records (D1), the analysis records (D2) and the audio files (D3).",
  },
  {
    t: "fig",
    n: 5,
    file: "fig06_level1_dfd.png",
    caption: "Level-1 data-flow diagram",
  },
  {
    t: "p",
    x: "Two flows in the diagram are easy to miss but matter for correctness. The analysis processes read stored turns rather than the original upload, which means that a report can be regenerated without the learner repeating the conversation; only pronunciation re-reads the stored audio, because it is the only analysis that needs the signal itself. And video ingestion writes a completed session, after which the ordinary analysis processes run unchanged. The dashed annotations clarify that rounded boxes are processes and open-ended rectangles are data stores, following the usual convention.",
  },
  { t: "h2", x: "6.3 Video Review Workflow" },
  {
    t: "p",
    x: "Figure 6 is a flowchart of video review. The file's extension and size are checked before it is streamed to a temporary file; the duration is checked after probing; FFmpeg extracts a 16 kHz mono track; recognition is attempted with English pinned; and an empty transcript is rejected as containing no speech. A successful path ends in a completed session with one learner turn, from which the client can run grammar, vocabulary and fluency analyses. The rejection paths carry distinct status codes so that the interface can explain what was wrong rather than showing a generic failure.",
  },
  {
    t: "fig",
    n: 6,
    file: "fig07_video_workflow.png",
    caption: "Video review workflow",
  },
  {
    t: "p",
    x: "The flowchart also records a privacy-relevant decision: the uploaded video is deleted after extraction, and only the normalised audio, the transcript and the word timings are retained. The system therefore stores what the analyses need, which is not the video.",
  },
  { t: "h2", x: "6.4 Language-Bridge Workflow" },
  {
    t: "p",
    x: "Figure 7 shows the bridge workflow from the learner's choice of language to the final alternatives report. The language determines the recogniser: Kannada, Tamil and Telugu are routed to Sarvam, while Hindi and English use Whisper. The recognised text is sent to the language model with a bridge-specific prompt that requires an English-only reply, and the reply is synthesised and played. The native-language alternatives are produced separately at the end of the session and pass through the validation and ranking stages described in Chapter 5.",
  },
  {
    t: "fig",
    n: 7,
    file: "fig08_language_bridge.png",
    caption: "Language-bridge workflow, including deterministic validation of alternatives",
  },
  {
    t: "p",
    x: "The figure groups the validation checks into a single stage because they are applied as a pipeline to every candidate. This is deliberate: the model's output is one input to the stage, not the stage's authority. The checks are what guarantee that the left-hand side of every reported pair is really the learner's language and really appeared in the transcript.",
  },
  {
    t: "p",
    x: "Taken together, the diagrams describe a system in which the learner's speech is normalised once, stored once, and then analysed from several independent perspectives. The next chapter documents how that design is realised in code, in the database, in the browser and in the deployment.",
  },
];

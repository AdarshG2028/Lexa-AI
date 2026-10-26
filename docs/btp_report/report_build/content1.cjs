// Report content, part 1: Abstract, Introduction, Literature Review,
// Problem Definition and Objectives.
module.exports = [
  { t: "h1", x: "ABSTRACT" },
  {
    t: "p",
    x: "Speaking a second language is a composite skill, and a learner who wants to improve it needs feedback on several different things at once: whether a sentence was grammatical, whether the words were varied and natural, whether the delivery was fluent, and whether individual sounds were articulated clearly. Human coaching supplies this feedback, but it is expensive, episodic and difficult to obtain at the frequency that sustained practice requires. Existing language applications usually address one of these dimensions in isolation, and most of them are designed for a single language and a single script.",
  },
  {
    t: "p",
    x: "This report describes Lexa, a web-based voice conversation and speech-coaching system that was designed, implemented and deployed as a B.Tech project. A learner holds a spoken conversation with an artificial-intelligence partner in the browser, and when the conversation ends the system produces a report on four dimensions of the learner's speech: grammar, vocabulary, fluency and phoneme-level pronunciation. The same analyses can be applied to an uploaded English video of up to five minutes, so that a recording made elsewhere can be reviewed without a live call. A separate language-bridge mode allows a learner to speak Hindi, Kannada, Tamil or Telugu, be answered in simple English, and receive a list of English equivalents for the words and phrases actually used.",
  },
  {
    t: "p",
    x: "The system is implemented as a FastAPI backend and a React 19 / TanStack Start frontend. Speech recognition, language modelling and speech synthesis are reached through replaceable provider adapters; the deployed configuration uses Groq for Whisper transcription, an open-weight GPT-OSS model for dialogue and grammar/vocabulary suggestions, Orpheus for synthesis, Sarvam saaras for the three Dravidian languages and Deepgram as a speech-synthesis fallback. Pronunciation analysis is the only component that runs a model locally: a 316-million-parameter wav2vec2 CTC phoneme recogniser, aligned against dictionary-derived phonemes with the Needleman-Wunsch algorithm and filtered so that only recurring, confident patterns are reported. Scores for grammar, vocabulary, fluency and pronunciation are computed in application code rather than requested from a language model, which makes them deterministic and explainable.",
  },
  {
    t: "p",
    x: "The implementation is accompanied by an offline automated test suite of thirty modules, with a recorded run of 454 passing tests. Measured single-turn latency was 1,968 ms for an English turn and 7,599 ms for a Kannada bridge turn, dominated in the second case by the additional speech-recognition and synthesis calls. On generated evaluation audio, the fluency analyser separated a clean sample (score 100, 158.9 words per minute) from a hesitant one (score 19, 83.9 words per minute), and the pronunciation analyser reduced eighteen raw phoneme mismatches to one trustworthy finding while reporting none for correctly articulated speech. The report discusses these results, the design decisions behind them and the limitations that remain, including the absence of a controlled word-error-rate benchmark and the constraints imposed by a free-tier deployment.",
  },

  { t: "h1", x: "1. INTRODUCTION" },
  { t: "h2", x: "1.1 Background and Motivation" },
  {
    t: "p",
    x: "English is the working language of a large part of Indian higher education and professional life, yet most learners acquire it through reading and writing rather than through sustained speaking practice. The gap is not primarily one of vocabulary knowledge. A learner may know the rule for the past tense and still say “I go to college yesterday” under the cognitive load of real conversation; may know the word “improve” and still repeat “very good” four times in a minute; may know how “think” is spelled and still pronounce it with a /t/ rather than a /θ/. These are performance problems, and performance problems are corrected by practice followed by specific, timely feedback.",
  },
  {
    t: "p",
    x: "The feedback loop is the expensive part. A human coach can hear all of these problems at once and can decide which of them matter for a particular learner, but coaching is constrained by cost, scheduling and the availability of trained teachers. Self-study applications remove the scheduling constraint but usually narrow the feedback: a grammar quiz checks grammar, a pronunciation drill checks a fixed inventory of sounds, and a conversational chatbot provides practice without assessment. What is missing is a single artefact that lets a learner speak freely, then shows what was said, how it was said, and what to work on next.",
  },
  {
    t: "p",
    x: "The Common European Framework of Reference for Languages describes spoken proficiency in terms of communicative performance rather than isolated knowledge [1]. That framing motivates the design of the present system: the learner should be assessed while speaking, on multiple dimensions, and the assessment should be tied to what the learner actually produced rather than to a pre-authored exercise. Recent progress in automatic speech recognition, open-weight language models and self-supervised speech representations makes such an assessment feasible on commodity infrastructure, provided that the system is engineered so that model output is checked and scored by deterministic code.",
  },
  { t: "h2", x: "1.2 The System in Brief" },
  {
    t: "p",
    x: "Lexa is a browser application with two entry points. In the first, the learner starts a live conversation with an artificial-intelligence partner. Speech is captured in the browser, transmitted a turn at a time to a backend service, transcribed, answered by a language model, and returned as synthesized speech, so that the interaction is spoken at both ends. The conversation is stored as a session, and when the learner ends it, the report page runs four analyses over the learner's own turns and presents scores, findings and short practice suggestions.",
  },
  {
    t: "p",
    x: "The four analyses are complementary rather than redundant. Grammar analysis identifies errors in tense, articles, prepositions, agreement, plurals, word form and sentence structure, quoting the sentence and offering a correction. Vocabulary analysis reports repeated words and phrases, over-used basic words and expressions that are grammatical but unnatural, with better alternatives. Fluency analysis measures speaking rate, pauses, filler words, immediate repetitions and false starts from the word timings captured during transcription; it deliberately does not ask a language model for an opinion about fluency. Pronunciation analysis compares the sounds that were produced against the sounds the transcribed words require, at phoneme level, and reports only patterns that recur across different words.",
  },
  {
    t: "p",
    x: "The second entry point accepts an uploaded English video of up to five minutes. The backend validates the file, extracts and normalises its audio track, transcribes it, and stores the result as a completed session containing a single learner turn. The report page then runs the same grammar, vocabulary and fluency analyses over that turn. This path exists because much speaking practice happens away from a microphone attached to a web application, and because a recorded presentation or classroom interaction is a natural object of review.",
  },
  {
    t: "p",
    x: "A third mode, the language bridge, serves learners who are not yet ready to hold a whole conversation in English. The learner speaks Hindi, Kannada, Tamil or Telugu; the partner replies in simple English, which the learner can hear and read; and at the end the system reports English equivalents for the native-language words and phrases that were actually used. The bridge is deliberately unscored, because judging a Hindi utterance with English grammar rules would produce a number that means nothing. English coaching remains the core product, and the bridge is an adjacent feature that reuses the same conversation, persistence and reporting machinery.",
  },
  { t: "h2", x: "1.3 Users, Modes and Languages" },
  {
    t: "p",
    x: "The primary user is an individual learner of English, working alone, on a laptop or desktop browser with a microphone. The system keeps no accounts and no personal profile; a session is identified by an opaque identifier, and the learner reaches the report through that identifier. Three session modes exist. English Coach is the core mode: the learner speaks English and is coached on how they said it. Language Bridge is the mode described above. Video Coach is a finished session built from an uploaded video rather than a live call; it holds one learner turn and no assistant reply, and the English analyses run over it exactly as they do for a conversation.",
  },
  {
    t: "p",
    x: "Four spoken languages are supported in the bridge, each with its own script and its own lexical data: Hindi (Devanagari), Kannada (Kannada script), Tamil (Tamil script) and Telugu (Telugu script). English is the coached language and is never offered as a bridge language. The interface exposes the languages before any backend request is made, so that the landing page can present the choice without a network round trip.",
  },
  { t: "h2", x: "1.4 Scope and Boundaries" },
  {
    t: "p",
    x: "The project covers the complete path from browser capture to a persisted report: audio acquisition and voice-activity detection in the browser, upload and normalisation, transcription, dialogue, synthesis, session persistence, four analyses, two alternative report types, and a deployment configuration on managed infrastructure. It is a working system rather than a prototype of a single component: a session can be created, held, ended and reviewed, and the same deployment serves both the application programming interface and the front end.",
  },
  {
    t: "p",
    x: "Several boundaries were drawn deliberately. There is no authentication or user account; the API is rate limited per client address instead. Interaction is turn-based over HTTPS rather than streamed over a persistent socket, so the learner waits for a complete reply rather than hearing it as it is generated. Cross-session progress tracking and a unified report that deduplicates findings across analyses were planned as later phases and are not part of this submission. On the free deployment, pronunciation analysis is disabled because the local phoneme model requires more memory than the instance provides. These are stated as scope decisions, not as oversights, and each is revisited in the discussion of limitations and future work.",
  },
  { t: "h2", x: "1.5 Organisation of the Report" },
  {
    t: "p",
    x: "Chapter 2 reviews the literature that informed the design: spoken-language assessment, self-supervised and weakly supervised speech recognition, transformer language models, pronunciation assessment, fluency research, code-mixing and browser speech capture. Chapter 3 states the problem, the objectives and the scope in precise terms. Chapter 4 describes the methodology and the architecture, including the lifecycle of a conversational turn. Chapter 5 presents the algorithms and the scoring rules. Chapter 6 presents the data-flow diagrams, block diagrams and workflows. Chapter 7 documents the implementation, the technology stack, the database, the front end, the test suite and the deployment. Chapter 8 reports and discusses the results, including measured latencies, evaluation samples, limitations and threats to validity. Chapter 9 concludes and sets out future work.",
  },

  { t: "h1", x: "2. LITERATURE REVIEW" },
  {
    t: "p",
    x: "The system sits at the intersection of four research traditions: the assessment of spoken language proficiency, automatic speech recognition, large language models and pronunciation assessment. This chapter surveys each in turn, together with the smaller bodies of work on fluency measurement, code-mixed speech and browser-based speech capture, and closes by identifying the gaps that the present implementation addresses.",
  },
  { t: "h2", x: "2.1 Assessing Spoken Language Proficiency" },
  {
    t: "p",
    x: "The dominant framework for describing language proficiency is the Common European Framework of Reference for Languages, which defines six levels from A1 to C2 in terms of what a learner can do in reception, production, interaction and mediation [1]. Its descriptors are communicative: a B1 speaker, for example, can sustain a conversation on familiar matters and describe experiences and ambitions, even though errors remain. The framework is explicitly not a marking scheme for individual utterances, and it does not prescribe how to measure the constructs it describes. That gap between a descriptive framework and an operational measurement is where automated assessment has to make design choices.",
  },
  {
    t: "p",
    x: "Human assessment of spontaneous speech typically decomposes into analytic dimensions: grammatical accuracy, lexical range, fluency, pronunciation and coherence. Analytic scoring has the advantage of diagnostic value, because a learner can be told which dimension is weak, but it multiplies the cost of human judgement and introduces rater variability. The practical consequence for an automated system is that it should produce dimension-level evidence rather than a single holistic number, and it should keep the evidence traceable to what the learner said. Lexa adopts this analytic decomposition directly: four dimensions, each with its own findings, and no attempt to collapse them into one proficiency level.",
  },
  { t: "h2", x: "2.2 Self-Supervised Speech Representation Learning" },
  {
    t: "p",
    x: "Speech recognition moved, over the past decade, from pipelines of hand-engineered features and hidden Markov models to end-to-end neural systems trained on large corpora. A pivotal step was self-supervised pre-training. wav2vec 2.0 learns representations from unlabelled audio by masking latent speech representations and solving a contrastive task, and then fine-tunes with a connectionist temporal classification objective on a comparatively small amount of labelled data [2]. The approach reduced the labelled data required for competitive recognition and made it practical to fine-tune a single architecture for many languages.",
  },
  {
    t: "p",
    x: "Cross-lingual pre-training extended the idea to languages with little labelled data. XLSR learns shared representations across dozens of languages from unlabelled speech and then fine-tunes per language, showing that multilingual pre-training transfers useful acoustic structure even when the target language was not the focus of pre-training [3]. Public multilingual corpora such as Common Voice, which collects validated recordings from volunteers in many languages, made such pre-training and evaluation possible at scale [4]. For a project concerned with Indian languages, these results matter twice: they explain why a general multilingual recogniser can be adequate on high-resource languages and weak on low-resource ones, and they make a phoneme-level acoustic model feasible on ordinary hardware, because a fine-tuned wav2vec2 model is small enough to run on a CPU.",
  },
  {
    t: "p",
    x: "The pronunciation component of Lexa uses a wav2vec2 model fine-tuned to emit phonemes rather than characters. The model is loaded locally, performs a frame-level classification every 20 milliseconds, and its output is collapsed with the standard CTC rule. This design follows directly from the self-supervised line of work: the acoustic representation is learned, the phoneme inventory is fixed by the fine-tuning data, and the decoder is a small amount of deterministic code.",
  },
  { t: "h2", x: "2.3 Weakly Supervised Recognition at Scale" },
  {
    t: "p",
    x: "Whisper took a different route. Instead of self-supervision followed by fine-tuning, it trained a sequence-to-sequence transformer on 680,000 hours of weakly supervised audio collected from the web, with multilingual transcription, translation and language identification as joint objectives [5]. The result is a family of models with strong multilingual recognition, robustness to accents and background noise, and word-level timestamps. Whisper also demonstrated that scale and data diversity can substitute, to a degree, for careful in-domain curation.",
  },
  {
    t: "p",
    x: "For a deployed application, Whisper's practical attractions are that it is available behind hosted, OpenAI-compatible APIs and that it returns word-level timings on request. Those timings are the input to any measurement of speaking rate and pausing, which is why fluency analysis in Lexa depends on them. Its limitation is equally relevant: performance is uneven across languages, and the long tail of the training distribution is thin. The project observed this directly, with auto-detection labelling Kannada as Tamil and Telugu as Hindi, and with more spelling noise in the three Dravidian languages than in Hindi. The engineering response was to pin the language on every request and to route the three Dravidian languages to an Indic-first recogniser, a decision discussed in Chapter 4.",
  },
  { t: "h2", x: "2.4 Transformer Language Models" },
  {
    t: "p",
    x: "The transformer architecture replaced recurrence with self-attention, allowing sequence models to be trained in parallel and to capture long-range dependencies [6]. Language modelling then scaled: generative pre-training followed by task-specific fine-tuning produced strong transfer [7], and further scaling showed that a sufficiently large model could perform new tasks from a handful of examples in its prompt, without parameter updates [8]. This few-shot behaviour is the basis of the conversational partner in Lexa: the system prompt defines the role, the constraints and the reply style, and the session history is replayed as context on every turn.",
  },
  {
    t: "p",
    x: "Open-weight models have made this capability available outside a single vendor. The GPT-OSS family, released with published model cards, provides reasoning-capable transformer models that can be served by third-party inference providers [9]. Lexa uses a 120-billion-parameter member of this family through Groq's inference service, with a low reasoning effort setting and a bounded output length, because a conversational reply should be short and should arrive quickly. Two engineering lessons from the literature are reflected in the implementation. First, structured output is best requested explicitly and then validated: the grammar and vocabulary adapters request JSON and still check every field. Second, a language model is a proposal engine, not a measuring instrument. Counting, scoring and thresholding are therefore performed in code, a principle that runs through Chapter 5.",
  },
  { t: "h2", x: "2.5 Pronunciation Assessment and Phoneme Alignment" },
  {
    t: "p",
    x: "Pronunciation assessment compares what a speaker produced with what the target words require. Classical approaches estimate a goodness-of-pronunciation score from the posterior probability of the expected phonemes given the acoustic model, which requires a phoneme recogniser aligned to the expected sequence. More recent work replaces the hand-built pronunciation lexicon and forced alignment with a CTC phoneme recogniser whose output is compared to a dictionary pronunciation, which is simpler to deploy but produces insertion and deletion noise at the sequence level.",
  },
  {
    t: "p",
    x: "Comparing two phoneme sequences position by position is fragile. A single dropped or inserted sound shifts every subsequent position, so a learner who omits one consonant appears to mispronounce the rest of the word. The standard remedy is global sequence alignment. The Needleman-Wunsch algorithm, originally formulated for comparing amino-acid sequences, computes an optimal alignment under a substitution cost and a gap penalty using dynamic programming [10]. Applied to phonemes, it tolerates insertions and deletions while still identifying genuine substitutions. Lexa uses this algorithm, with unit substitution and gap costs, between the expected phoneme sequence and the recognised one.",
  },
  {
    t: "p",
    x: "The expected sequence comes from a pronouncing dictionary. The CMU Pronouncing Dictionary provides ARPAbet transcriptions for a large English vocabulary [11], and the g2p_en package extends coverage to words not in the dictionary through a neural grapheme-to-phoneme model [12]. The recognised sequence comes from the acoustic model in International Phonetic Alphabet (IPA) symbols, so the two alphabets must be mapped onto a common inventory before alignment. This notation gap, and the treatment of reduced vowels in function words, are the main sources of false positives in phoneme-level feedback, and they are addressed explicitly in the filtering stage described in Chapter 5.",
  },
  { t: "h2", x: "2.6 Fluency, Pauses and Disfluencies" },
  {
    t: "p",
    x: "Fluency is not the absence of hesitation. Spontaneous speech contains filled pauses, repetitions and repairs, and psycholinguistic research has shown that “uh” and “um” are not random noise but signals used by speakers to manage planning and turn-taking [13]. An assessment system therefore has to distinguish habitual disfluency from the ordinary management of spontaneous speech, and it has to measure rate and pausing in a way that is not distorted by the interlocutor.",
  },
  {
    t: "p",
    x: "Two measurement decisions follow. First, pauses must be measured within a speaker's own turns, because silence between turns belongs to the other speaker; summing gaps across a dialogue would attribute the partner's thinking time to the learner. Second, speaking rate and articulation rate should be distinguished: the former includes pause time, the latter excludes it, and the difference between them is itself diagnostic. Lexa implements both, together with a comfortable band for rate, and counts filled pauses, immediate word repetitions and restarts as separate finding types so that the report can say which habit is present rather than merely that fluency is poor.",
  },
  { t: "h2", x: "2.7 Code-Mixing, Scripts and Indic Languages" },
  {
    t: "p",
    x: "Everyday speech in Hindi, Kannada, Tamil and Telugu routinely mixes English words into native-language sentences. Recognition may render such words in the native script or in Latin letters, and the choice is not stable across engines or utterances. For a vocabulary report this matters: an English word that the learner already knows should not be presented as new vocabulary, whereas a native word that the learner does not know in English should be. Distinguishing the two requires lexical knowledge, not merely a language identifier, and it requires script-aware validation.",
  },
  {
    t: "p",
    x: "Scripts are formally defined by the Unicode Standard, which assigns each script a block of code points and specifies its character properties [14]. That gives a reliable, language-independent test for whether a string is written in Devanagari, Kannada, Tamil or Telugu, and whether it contains Latin letters. Unicode properties were used in this project as the first line of defence against a class of error in which a language model “translates” an English word the learner already used. The second line is a curated list of common English loanwords in each script, since a loanword written in Devanagari is still an English word.",
  },
  { t: "h2", x: "2.8 Browser Speech Capture and Voice Activity Detection" },
  {
    t: "p",
    x: "The browser has become a viable speech client. The MediaRecorder interface exposes compressed audio encoding from a microphone stream and is supported, with different container preferences, across major browsers [15]. Capture alone is not enough for a conversation: the client must decide when the learner has finished speaking. Voice activity detection can be performed on the server, but doing it in the browser avoids uploading silence and allows the interface to respond immediately. Silero VAD is a small, openly available neural voice-activity detector that runs through ONNX Runtime and is accurate enough for interactive use [16].",
  },
  {
    t: "p",
    x: "Lexa runs Silero VAD in the browser through a WebAssembly build of ONNX Runtime. The model and runtime are several megabytes, so they are loaded from a content-delivery network rather than bundled with the application, and manual recording remains available if the detector fails. The design choice is consistent with the literature: detection close to the audio source reduces bandwidth and latency, while the server still validates and normalises every upload.",
  },
  { t: "h2", x: "2.9 Summary of Gaps Addressed" },
  {
    t: "p",
    x: "The literature supplies strong components but few complete systems that combine them for a learner-facing product. Five gaps are relevant to this project. First, assessment research tends to evaluate a single dimension, whereas a learner needs several dimensions reported together against the same conversation. Second, language-model-based feedback is usually accepted as generated, without deterministic validation of counts, quotations or scores. Third, phoneme-level pronunciation feedback is known to produce false positives on accented speech, and published systems seldom describe the filters that make it usable. Fourth, Indic-language support is usually studied as recognition accuracy, not as a learner-facing bridge from the learner's language to English. Fifth, deployment constraints, such as running a speech pipeline on a free-tier instance, are rarely treated as part of the design.",
  },
  {
    t: "p",
    x: "Lexa addresses these gaps by treating the conversation as the unit of assessment, by separating model judgement from deterministic scoring and validation, by filtering pronunciation evidence before it reaches the learner, by implementing a validated native-language bridge, and by documenting a deployment in which the expensive local model is optional. The following chapter states the resulting problem and objectives precisely.",
  },

  { t: "h1", x: "3. PROBLEM DEFINITION AND OBJECTIVES" },
  { t: "h2", x: "3.1 Problem Statement" },
  {
    t: "p",
    x: "A learner of spoken English who practises alone receives no structured account of what went wrong. Conversational agents provide practice but not assessment; grammar checkers assess written text; pronunciation applications drill a fixed inventory of sounds and do not connect the drill to what the learner actually said. The result is practice without diagnosis: the learner repeats the same tense error, the same limited vocabulary and the same mispronounced phoneme because nothing in the loop makes them visible.",
  },
  {
    t: "p",
    x: "Building the missing loop is not simply a matter of calling a speech recogniser and a language model. Three difficulties have to be solved together. The system must capture and transport speech reliably enough for analysis; it must produce feedback on several dimensions without inventing errors, especially where model output is probabilistic; and it must do so within the latency and memory limits of affordable infrastructure. For learners who are not yet able to converse in English, a fourth difficulty appears: the system must accept their own language without pretending that English-language metrics apply to it.",
  },
  { t: "h2", x: "3.2 Objectives" },
  {
    t: "p",
    x: "The project was guided by the following objectives:",
  },
  {
    t: "ol",
    items: [
      "To build a browser-based spoken conversation system in which a learner can hold a multi-turn conversation with an artificial-intelligence partner, with speech as both input and output.",
      "To persist each conversation as a session with ordered turns, transcripts, word timings and audio references, so that a report can be generated after the call and revisited later.",
      "To implement grammar, vocabulary and fluency analyses that report dimension-level findings and deterministic scores, keeping model judgement separate from measurement and arithmetic.",
      "To implement phoneme-level pronunciation analysis that aligns recognised sounds against dictionary pronunciations and reports only recurring, confident patterns rather than isolated mismatches.",
      "To support review of an uploaded English video of up to five minutes through the same analysis pipeline, without retaining the video itself.",
      "To implement a language-bridge mode for Hindi, Kannada, Tamil and Telugu in which the learner is answered in simple English and receives validated English equivalents for native-language words actually used.",
      "To engineer the system for replaceable providers, graceful degradation, bounded resource use and deployment on managed free-tier infrastructure, and to verify it with an offline automated test suite.",
    ],
  },
  { t: "h2", x: "3.3 Functional Scope" },
  {
    t: "p",
    x: "The functional scope follows from the objectives and is summarised in Tables 1 and 2. Table 1 lists the three session modes and what each produces. Table 2 lists the spoken languages, their scripts and the recogniser that serves each in the deployed configuration.",
  },
  {
    t: "tbl",
    n: 1,
    caption: "Session modes and their outputs",
    widths: [1900, 3100, 3700],
    head: ["Mode", "Input", "Output"],
    rows: [
      ["English Coach", "Live spoken conversation in English", "Conversation report: grammar, vocabulary, fluency and optional pronunciation"],
      ["Language Bridge", "Live spoken conversation in Hindi, Kannada, Tamil or Telugu", "English reply, transcript, and an unscored list of English alternatives for native words used"],
      ["Video Coach", "Uploaded English video, at most five minutes", "Completed session with one learner turn; grammar, vocabulary and fluency report"],
    ],
  },
  {
    t: "p",
    x: "The bridge mode is deliberately not scored. Its report is a vocabulary aid, and applying English grammar or fluency metrics to a Hindi or Tamil transcript would produce numbers without meaning. The Video Coach mode is treated as a finished session rather than a separate analysis pipeline, because the analyses only require a learner turn containing speech.",
  },
  {
    t: "tbl",
    n: 2,
    caption: "Supported spoken languages and speech-recognition routing",
    widths: [1500, 1900, 2100, 3100],
    head: ["Code", "Language", "Script", "Recogniser in deployed configuration"],
    rows: [
      ["hi", "Hindi", "Devanagari", "Groq Whisper large-v3"],
      ["kn", "Kannada", "Kannada", "Sarvam saaras:v4"],
      ["ta", "Tamil", "Tamil", "Sarvam saaras:v4"],
      ["te", "Telugu", "Telugu", "Sarvam saaras:v4"],
      ["en", "English (coached language)", "Latin", "Groq Whisper large-v3-turbo"],
    ],
  },
  { t: "h2", x: "3.4 Assumptions and Constraints" },
  {
    t: "p",
    x: "The design assumes a single learner per session, a browser with microphone permission and an HTTPS origin, and network access to the configured providers. It assumes that the learner speaks one of the supported languages for the whole of a bridge session; switching language mid-session is not modelled. It assumes that the uploaded video contains an audio track and audible English speech, and rejects the upload otherwise. It assumes that provider quotas are finite, and therefore bounds history, upload size, audio duration, analysis frequency and output length.",
  },
  {
    t: "p",
    x: "The principal constraints are memory and latency. The local pronunciation model requires roughly 1.6 GB of memory and about 1.9 GB of weights on disk, which exceeds the free deployment instance and is therefore an optional component. Turn-based interaction over HTTPS adds a full recognition, generation and synthesis round trip to every exchange. Both constraints shaped the architecture described in the next chapter and are revisited in the evaluation.",
  },
];

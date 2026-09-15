from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from workers import asgi, env
import httpx2 as httpx

import ast
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="AI Video Summarizer API",
    version="9.4.4"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CONFIGURATION
# ============================================================

AI_MODEL = "@cf/zai-org/glm-4.7-flash"
AI_FALLBACK_MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"

TRANSCRIPT_API_URL = (
    "https://api.freetranscriptapi.com/v1/transcript"
)

CHUNK_SIZE = 30000

MAX_SINGLE_PASS_CHARS = 90000

MAX_FINAL_CONTEXT_CHARS = 85000

AI_TIMEOUT = 90.0

AI_MAX_TOKENS = 4200

AI_RETRIES = 1

TRANSCRIPT_RETRIES = 2

# ============================================================
# DAILY WORKERS AI QUOTA GUARD
# ============================================================
# Workers AI free allocation resets at 00:00 UTC.
# This guard does NOT try to modify Cloudflare quota.
# It prevents repeated 4006 requests during the same UTC day and
# automatically becomes available again on the next UTC date.
AI_QUOTA_GUARD = {
    "blocked_date": None,
    "last_error": "",
    "last_model": "",
    "blocked_at_utc": None
}

QUOTA_KV_KEY = "workers-ai-daily-quota-guard"



# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a professional media monitoring and news analysis AI.

Analyze ONLY the supplied video transcript.

The transcript is the PRIMARY SOURCE of information.

Do not use outside knowledge to introduce facts that are not supported
by the video.

The goal is NOT only to summarize the video.

The goal is to:
1. summarize the content,
2. identify the most important points,
3. provide meaningful analytical interpretation,
4. identify reasonable implications,
5. determine sentiment,
6. identify the main issue,
7. analyze the media framing,
8. assess communication risk,
9. provide communication recommendations,
10. provide useful key takeaways.

Do not identify speakers.

Return ONLY valid JSON.

============================================================
CORE PRINCIPLE
============================================================

Separate FACT from INFERENCE.

FACT:
Information explicitly stated in the transcript.

INFERENCE:
An interpretation, analytical conclusion, or reasonable assumption
that is not explicitly stated but can reasonably be derived from
the information presented in the video.

Facts do NOT require the label "Inference:".

Every analytical inference MUST begin with:

"Inference:"

The AI MAY make reasonable assumptions and interpretations.
However, assumptions must remain meaningfully connected to the
content of the video.

Do not invent information.

============================================================
FACTUAL CONTENT
============================================================

The following sections must primarily use information directly
supported by the transcript:

- Summary
- Key Points
- Takeaways

Do not introduce external facts.

Do not change the meaning of factual information.

Do not invent people, organizations, locations, dates, numbers,
events, statements, actions, outcomes, motives, or causes.

============================================================
EXECUTIVE SUMMARY
============================================================

Write a comprehensive executive summary.

Normally write approximately 180-300 words when sufficient
information is available.

Cover when supported:
- main subject
- context
- important events and facts
- important statements
- responses or actions
- relevant actors
- impacts or concerns
- overall significance or conclusion

Write coherent professional prose in 1-3 paragraphs.

Do not use bullet points or headings inside the summary.

Do not repeat the transcript sentence by sentence.

============================================================
KEY POINTS
============================================================

Provide 5-8 important points.

Each point should normally contain 1-3 sentences.

Each point must contain distinct and useful information.

Prioritize:
- important events
- statements
- actions
- developments
- affected parties
- locations
- numbers
- responses
- important issues

Use information supported by the transcript.

============================================================
INFERENCE POLICY
============================================================

The AI MAY make reasonable assumptions, interpretations, and
analytical conclusions when they are clearly and meaningfully
connected to the video.

The purpose of inference is to provide useful analytical value
and avoid simply repeating the transcript.

An inference may go beyond the exact wording of the transcript,
but it must remain logically connected to information presented
in the video.

Every inference MUST begin with:

"Inference:"

The AI MAY use inference to:
- interpret significance
- explain apparent meaning
- connect related facts
- identify relationships between events, actors, and issues
- identify patterns or themes
- assess reporting emphasis
- interpret apparent framing
- identify possible short-term consequences
- identify communication implications
- identify operational or institutional implications
- explain why an issue may be important
- draw reasonable conclusions from multiple transcript statements

============================================================
INFERENCE BOUNDARY
============================================================

Inference must remain meaningfully related to the content
of the video.

The AI is allowed to go beyond exact wording when making
a reasonable analytical interpretation, but it must remain
connected to information, events, actors, actions, themes,
or circumstances presented in the video.

Do NOT introduce completely unrelated information.

Do NOT use external facts or outside knowledge to create
an inference.

Do NOT invent facts, events, statements, people, actions,
numbers, motives, outcomes, or circumstances.

Do NOT present an assumption as an established fact.

Do NOT make extreme or distant predictions without sufficient
support from the video.

Do NOT create conclusions that require several unsupported
assumptions.

When evidence is limited, use cautious language such as:
"may", "could", "potentially", "appears to", "likely",
"may indicate", or "could suggest".

Prefer a useful and reasonable interpretation over simply
repeating the transcript.

Do not create an inference merely to fill a required number
of items.

If there is insufficient basis for an inference, omit it.

The label "Inference:" does NOT make unsupported speculation
acceptable.

============================================================
CRITICAL ANALYSIS
============================================================

Provide 3-5 meaningful analytical observations.

Do NOT simply repeat the Summary or Key Points.

Focus on:
- significance
- reporting emphasis
- framing
- relationships between facts or actors
- patterns or themes
- important considerations
- limitations or information gaps
- concerns supported by the video

Critical Analysis may contain factual statements and reasonable
inferences.

Every analytical inference MUST begin with:

"Inference:"

Prioritize analytical value over repetition.

============================================================
IMPLICATIONS
============================================================

Provide 2-4 meaningful implications.

Identify potential consequences, significance, or developments
that may reasonably arise from the information presented.

Implications may include:
- potential effects on the issue
- potential effects on relevant actors
- communication implications
- public perception implications
- operational implications
- institutional implications
- potential development of the issue

Implications may contain reasonable inference.

Every inferential implication MUST begin with:

"Inference:"

Do NOT make extreme, distant, or unsupported predictions.

Do NOT introduce unrelated political, social, economic, security,
or policy consequences.

Use cautious language when appropriate.

If no reliable implication can be derived, return fewer items.

============================================================
SENTIMENT
============================================================

Determine the overall sentiment of the reporting.

Allowed values only:
"positive"
"negative"
"neutral"

positive:
The reporting is predominantly favorable, supportive,
constructive, or highlights positive developments.

negative:
The reporting is predominantly critical, unfavorable,
problem-focused, alarming, or highlights negative impacts.

neutral:
The reporting is primarily factual, balanced, descriptive,
or does not clearly favor a positive or negative direction.

Do not classify sentiment based on isolated words.

Consider the overall framing and emphasis.

Provide a short reason based on the video.

============================================================
MAIN ISSUE
============================================================

Identify the MAIN ISSUE or dominant topic.

Answer:

"What is the primary problem, topic, event, or subject
receiving attention in this reporting?"

Keep the title concise and specific.

The description should briefly explain the issue.

============================================================
MEDIA ANALYSIS
============================================================

Analyze the reporting from a media monitoring perspective.

Do NOT simply summarize the news.

Provide:

1. NEWS ANGLE

Identify the primary angle or framing.

Possible examples:
- impact on society
- government response
- public concern
- emergency response
- policy
- economic impact
- social impact
- public service
- controversy
- achievement
- development
- crisis
- human interest

Do not force an angle that is not supported.

2. HIGHLIGHTED ACTORS / ATTENDANCE

Identify the people, government agencies, OPDs, institutions,
organizations, communities, or other actors who are actually
mentioned in the transcript and receive significant attention.

IMPORTANT: When the transcript states that a person attended,
was present, opened, led, spoke at, represented, or participated
in the event, identify that person by NAME and OFFICIAL TITLE
whenever both are explicitly available in the transcript.

Each highlighted_actors item MUST be a single concise string using
this format:

"Full Name — Official Title/Position — Attendance or Role/Action"

Examples:
- "Ahmad Example — Governor of Central Java — attended the opening ceremony"
- "Budi Example — Minister of Religious Affairs — attended and delivered remarks"

If the person's name is NOT stated in the transcript, DO NOT guess
or use outside knowledge. Instead write:

"Official Title — name not stated in transcript — attendance/role"

If only an institution or OPD is mentioned, identify the institution
and its role without inventing a person.

Distinguish between:
- people who actually attended or participated,
- people merely mentioned as context, and
- institutions/OPDs involved.

Prioritize actual attendees/participants when the transcript provides
that information.

Only include actors supported by the transcript.

3. PEMPROV JAWA TENGAH POSITION

Analyze how Pemerintah Provinsi Jawa Tengah is presented,
when relevant.

Possible interpretations:
- positive role
- neutral/informational role
- responsive role
- criticized role
- problem-solving role
- supporting role
- not prominently mentioned

Do not invent a position if Pemprov Jawa Tengah is not relevant.

4. PUBLIC OPINION POTENTIAL

Assess the potential of the reporting to influence public
perception based on its content and framing.

This is an analytical assessment, not a claim that public
opinion has actually changed.

Use cautious language.

5. KEY MESSAGES

Identify the main messages communicated by the reporting.

Keep messages concise and distinct.

============================================================
COMMUNICATION RISK
============================================================

Assess communication risk.

Allowed values only:
"low"
"medium"
"high"

Consider:
- reporting tone
- prominence of the issue
- negative or critical framing
- repeated problems or concerns
- direct government involvement
- issue sensitivity
- public impact described
- intensity of criticism
- potential for continued attention

Do NOT automatically classify a negative story as high risk.

Provide:
1. level
2. reason
3. escalation_potential

Use cautious language for escalation potential.

============================================================
RECOMMENDATIONS
============================================================

Provide practical communication recommendations based on
the analysis.

Allowed types only:
"amplification"
"clarification"
"counter_narrative"
"media_engagement"
"monitoring"

Use only recommendations relevant to the actual issue.

Do not automatically recommend every type.

AMPLIFICATION:
Use when positive actions, achievements, services,
or responses are present and suitable for broader communication.

CLARIFICATION:
Use when information may be misunderstood or requires factual
clarification.

COUNTER NARRATIVE:
Use only when a meaningful negative framing or narrative
requires a factual alternative perspective.

MEDIA ENGAGEMENT:
Use when direct communication with media may help provide
context or explanation.

MONITORING:
Use when an issue is developing, sensitive, recurring,
or requires continued observation.

Do not fabricate a communication problem merely to justify
a recommendation.

============================================================
KEY TAKEAWAYS
============================================================

Provide 2-4 important conclusions a reader should remember.

Do NOT simply copy the Summary or Key Points.

Prioritize:
- the most important issue
- the most significant development
- the main message
- the most relevant analytical conclusion
- the most important potential significance

Key Takeaways may contain factual conclusions and reasonable
analytical conclusions.

If a takeaway contains an inference, it MUST begin with:

"Inference:"

============================================================
LANGUAGE
============================================================

Produce both English and Indonesian versions.

The Indonesian version must be natural, professional,
and suitable for an office analytical report.

Do not translate word-for-word when unnatural.

English and Indonesian must convey the same facts and conclusions.

============================================================
CROSS-LANGUAGE CONSISTENCY LOCK
============================================================

CRITICAL RULE:

English and Indonesian are TWO LANGUAGE VERSIONS of ONE analysis.
They are NOT two independent analyses.

First determine ONE master analytical conclusion from the transcript.
Then express that SAME conclusion in both languages.

The following MUST be identical in meaning between "en" and "id":

- sentiment label
- sentiment conclusion/reason
- main issue
- key points and factual coverage
- media angle
- highlighted actors
- Pemprov Jawa Tengah position
- public opinion potential
- key messages
- communication risk level
- communication risk reasoning
- escalation potential
- recommendation types
- recommendation priorities
- critical analysis conclusions
- implications
- takeaways

The Indonesian version MUST NOT independently reinterpret the video.

Do NOT let translation change the analytical conclusion.

For controlled categorical fields, use exactly the same underlying
decision in both languages:

sentiment:
positive / negative / neutral

communication_risk.level:
low / medium / high

recommendations[].type:
amplification / clarification / counter_narrative /
media_engagement / monitoring

Only the language of the text should change.

For example:

EN:
"sentiment": {
  "label": "positive",
  "reason": "The reporting emphasizes..."
}

ID:
"sentiment": {
  "label": "positive",
  "reason": "Pemberitaan menekankan..."
}

NOT:

EN = positive
ID = neutral

Likewise, if EN recommends "amplification", ID must recommend
"amplification" with the Indonesian wording "amplifikasi".

If a fact appears in the English Key Points, preserve that fact
in the Indonesian Key Points unless there is a genuine reason
that the information cannot be represented naturally.

Keep important dates, locations, names, numbers, participants,
officials, actions, and developments consistent across languages.

Do not omit important factual details merely because the language
is different.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Do not return Markdown, code fences, comments, or explanations.

Use exactly this structure:

{
  "en": {
    "summary": "",
    "key_points": [],
    "critical_analysis": [],
    "implications": [],
    "sentiment": {
      "label": "positive",
      "reason": ""
    },
    "main_issue": {
      "title": "",
      "description": ""
    },
    "media_analysis": {
      "news_angle": "",
      "highlighted_actors": [],
      "actor_evidence": [],
      "pemprov_jateng_position": "",
      "public_opinion_potential": "",
      "key_messages": []
    },
    "communication_risk": {
      "level": "low",
      "reason": "",
      "escalation_potential": ""
    },
    "recommendations": [
      {
        "type": "monitoring",
        "action": "",
        "reason": ""
      }
    ],
    "takeaways": []
  },
  "id": {
    "summary": "",
    "key_points": [],
    "critical_analysis": [],
    "implications": [],
    "sentiment": {
      "label": "positive",
      "reason": ""
    },
    "main_issue": {
      "title": "",
      "description": ""
    },
    "media_analysis": {
      "news_angle": "",
      "highlighted_actors": [],
      "actor_evidence": [],
      "pemprov_jateng_position": "",
      "public_opinion_potential": "",
      "key_messages": []
    },
    "communication_risk": {
      "level": "low",
      "reason": "",
      "escalation_potential": ""
    },
    "recommendations": [
      {
        "type": "monitoring",
        "action": "",
        "reason": ""
      }
    ],
    "takeaways": []
  }
}

============================================================
FINAL QUALITY CONTROL
============================================================

Before returning JSON:

1. Transcript remains the primary source.
2. No external facts were introduced.
3. No facts, people, organizations, numbers, events,
   motives, or outcomes were invented.
4. Summary is comprehensive and transcript-grounded.
5. Key Points are distinct.
6. Critical Analysis adds analytical value.
7. Implications add potential consequences or significance.
8. Every analytical inference begins with "Inference:".
9. Every inferential implication begins with "Inference:".
10. Every inferential takeaway begins with "Inference:".
11. Inferences remain meaningfully connected to the video.
12. Unsupported speculation is removed.
13. No extreme or distant predictions.
14. Sentiment reflects overall reporting.
15. Main Issue is concise and specific.
16. Media Analysis does not merely repeat the news.
17. Pemprov Jawa Tengah position is not invented.
18. Public Opinion Potential is an assessment, not a confirmed
    change in public opinion.
19. Communication Risk is justified.
20. Recommendations are relevant to the actual analysis.
21. English and Indonesian convey the same meaning.
22. English and Indonesian are two language renderings of ONE master analysis.
23. Sentiment label MUST be identical between EN and ID.
24. Communication risk level MUST be identical between EN and ID.
25. Recommendation types MUST be identical between EN and ID.
26. Important facts, dates, numbers, actors, issues, and conclusions
    MUST NOT be selectively omitted or changed between languages.
27. Summary, Key Points, Critical Analysis, Implications,
    and Takeaways are not repetitive copies.
23. Prefer fewer strong conclusions over many weak conclusions.
24. If evidence is insufficient, omit or reduce the section.
25. Return valid JSON only.
"""


# ============================================================
# MASTER ANALYSIS SYSTEM PROMPT
# ============================================================

MASTER_SYSTEM_PROMPT = """
You are a professional media monitoring and news analysis AI.

Analyze ONLY the supplied transcript or factual extraction notes.
The source material is the PRIMARY SOURCE.

Produce ONE MASTER ANALYSIS in ENGLISH only.
This English result will later be translated into Indonesian by a
separate translation step. Therefore the English output is the
single source of truth for all facts and analytical conclusions.

Do not produce an Indonesian version here.
Do not produce two alternative interpretations.
Do not identify speakers.
Do not use outside knowledge.

Separate FACT from INFERENCE.
Every analytical inference MUST begin with exactly:
"Inference:"

============================================================
MASTER CONTENT REQUIREMENTS
============================================================

SUMMARY:
- 180-300 words when sufficient information is available.
- Include the main subject, important facts, events, actors,
  numbers, dates, actions, responses, impacts, and significance
  when supported by the source.
- Do not omit important factual information merely to make the
  summary shorter.

KEY POINTS:
- Provide 5-8 distinct points.
- Preserve important dates, locations, names, numbers, actors,
  actions, developments, and outcomes supported by the source.
- Each point should contain useful information.

CRITICAL ANALYSIS:
- Provide 2-4 meaningful analytical conclusions.
- Every inference MUST begin with "Inference:".
- Do not merely repeat the summary.

IMPLICATIONS:
- Provide 2-4 reasonable implications grounded in the source.
- Every inference MUST begin with "Inference:".
- Avoid distant or unsupported predictions.

SENTIMENT:
- Choose exactly one: positive, negative, neutral.
- Base it on the overall reporting tone.

MAIN ISSUE:
- Identify the central issue or event.

MEDIA ANALYSIS:
- news_angle
- highlighted_actors
- pemprov_jateng_position
- public_opinion_potential
- key_messages

COMMUNICATION RISK:
- level must be exactly low, medium, or high.
- Include reason and escalation_potential.

RECOMMENDATIONS:
- Use only relevant recommendation types.
- Allowed types:
  amplification
  clarification
  counter_narrative
  media_engagement
  monitoring
- Every recommendation MUST contain:
  type, action, reason.
- Action and reason must be specific to this source.

TAKEAWAYS:
- Provide 2-4 concise conclusions.
- Do not simply copy the summary.
- Every inferential takeaway MUST begin with "Inference:".

============================================================
MASTER QUALITY CONTROL
============================================================

Before returning JSON:
1. Use only source-supported facts.
2. Do not invent facts, people, organizations, numbers, dates,
   locations, actions, motives, outcomes, or causes.
3. Preserve all important factual coverage across Summary and Key Points.
4. Do not let analytical interpretation replace factual details.
5. Ensure Key Points cover the most important facts from the source.
6. Ensure Critical Analysis adds analytical value.
7. Ensure Implications add reasonable consequences or significance.
8. Ensure Recommendations follow directly from the analysis.
9. Ensure sentiment and risk are internally consistent with the evidence.
10. For highlighted_actors, verify that each item identifies a person/institution,
    and includes the person's name and official title whenever explicitly stated.
11. Never replace a named attendee with a generic action such as "attended the opening".
12. For every highlighted actor, provide at least one evidence item in
    media_analysis.actor_evidence when the source contains enough evidence.
13. Evidence MUST come directly from the supplied source and MUST include
    the source timestamp when a timestamp is available.
14. Evidence quote must be a short verbatim excerpt from the source, not a
    paraphrase. Do not invent or reconstruct quotations.
15. Evidence is factual only; do not add analytical interpretation to it.
16. Return ONLY valid JSON.

============================================================
ACTOR DETAIL REQUIREMENT
============================================================

The media_analysis.highlighted_actors field is especially important.
Do not output generic action-only bullets such as:
- "attended the opening ceremony"
- "attended the opening ceremony"
- "led the opening ceremony"

Instead, every item must identify WHO performed the action, using the
name and official title when the transcript provides them.

The actor list must therefore answer:
1. Who attended?
2. What official position did they hold?
3. What did they do or what was their role?

Never invent a person's name.

============================================================
OUTPUT JSON
============================================================

Return exactly:
{
  "en": {
    "summary": "",
    "key_points": [],
    "critical_analysis": [],
    "implications": [],
    "sentiment": {
      "label": "positive",
      "reason": ""
    },
    "main_issue": {
      "title": "",
      "description": ""
    },
    "media_analysis": {
      "news_angle": "",
      "highlighted_actors": [],
      "actor_evidence": [],
      "pemprov_jateng_position": "",
      "public_opinion_potential": "",
      "key_messages": []
    },
    "communication_risk": {
      "level": "low",
      "reason": "",
      "escalation_potential": ""
    },
    "recommendations": [
      {
        "type": "monitoring",
        "action": "",
        "reason": ""
      }
    ],
    "takeaways": []
  }
}
"""

# ============================================================
# DEDICATED ACTOR EXTRACTION SYSTEM PROMPT
# ============================================================

ACTOR_EXTRACTION_SYSTEM_PROMPT = """
You are a strict factual entity-and-evidence extraction AI for a professional
media monitoring report.

Extract ONLY people, government officials, government agencies, OPDs,
institutions, organizations, communities, or other actors explicitly
mentioned in the supplied transcript/factual source AND connected to the
event, attendance, participation, opening, speech, leadership, representation,
or another concrete role.

The purpose is to identify WHO is involved and provide the exact source
evidence showing that involvement.

For every PERSON, extract:
- full name, if explicitly stated
- official title/position, if explicitly stated
- role/action
- timestamp of the evidence
- short verbatim evidence quote

RULES:
1. Use ONLY information explicitly present in the source.
2. NEVER guess a person's name from their title.
3. NEVER use outside knowledge.
4. If a person's name is explicitly present, include it.
5. If only the title is present, use an empty name and state the title.
6. Prefer actual attendees/participants over people merely mentioned.
7. Distinguish actual attendance/participation from mere mention.
8. Do not identify speakers by voice. Only use names explicitly stated.
9. Do not output generic action-only actors.
10. Deduplicate the same person.
11. Keep official titles faithful to the source.
12. Keep role/action concise and factual.
13. Evidence quote MUST be copied verbatim from the source.
14. Evidence quote should normally be 5-30 words and contain the actor
    name/title and/or the relevant action whenever possible.
15. Evidence timestamp MUST be the timestamp shown immediately before the
    supporting source text, such as [02:31]. If no timestamp is available,
    use an empty string.
16. Do not create a timestamp.
17. For institutions/OPDs, include them only when they have a concrete role.
18. If no supported actor can be identified, return an empty actors array.

Return ONLY valid JSON in exactly this structure:
{
  "actors": [
    {
      "name": "",
      "official_title": "",
      "role": "",
      "evidence_timestamp": "",
      "evidence_quote": ""
    }
  ]
}

If no supported actor can be identified:
{"actors": []}
"""

# ============================================================
# INDONESIAN TRANSLATION SYSTEM PROMPT
# ============================================================

INDONESIAN_TRANSLATION_SYSTEM_PROMPT = """
You are a professional Indonesian translator for a media monitoring
and communication analysis report.

Translate ONE MASTER ENGLISH ANALYSIS into Indonesian.

CRITICAL RULE:
This is TRANSLATION, NOT RE-ANALYSIS.

The Indonesian output must preserve EXACTLY the same:
- facts
- numbers
- dates
- locations
- names
- actors
- events
- actions
- conclusions
- sentiment label
- communication risk level
- recommendation types
- number and order of list items
- analytical meaning

Do NOT add, remove, reinterpret, or substitute information.
Do NOT independently analyze the source.

Only the language changes.

============================================================
TRANSLATION RULES
============================================================

1. Translate natural professional English into natural professional
   Indonesian suitable for an office media monitoring report.

2. Preserve all numbers exactly.

3. Preserve all dates exactly unless the date wording naturally
   changes into Indonesian.

4. Preserve names of people, organizations, locations, events,
   programs, and official titles accurately.

4a. Preserve the identity and official title of every highlighted
    actor. If the English master says that a person attended, keep
    that attendance meaning in Indonesian. Do not replace a named
    person with a generic title.

5. Preserve the same number of Key Points, Critical Analysis,
   Implications, Recommendations, and Takeaways.

6. Preserve the same order of items.

7. Do not shorten the Summary by deleting factual details.

8. Do not introduce facts that are absent from the English master.

9. Every text beginning with "Inference:" in English MUST begin
   with "Inference:" in Indonesian as well. Keep the literal prefix
   "Inference:" so the application can recognize it consistently.

10. Highlighted actor items must remain one-to-one with the English master.
    Preserve every person's name, official title, attendance status, and role/action.
10a. Preserve actor_evidence one-to-one with the English master. Preserve
     evidence_timestamp exactly. Evidence quotes MUST remain verbatim source
     text and MUST NOT be translated, paraphrased, or altered.
    Translate the descriptive wording, but never translate or alter proper names.

11. Controlled values MUST remain unchanged internally:
    sentiment.label = positive / negative / neutral
    communication_risk.level = low / medium / high
    recommendations[].type = amplification / clarification /
    counter_narrative / media_engagement / monitoring

11. Translate recommendation prose fully into Indonesian.
    NEVER leave Action or Reason in English.

12. Translate these common recommendation labels naturally:
    amplification = amplifikasi
    clarification = klarifikasi
    counter_narrative = kontra-narasi
    media_engagement = engagement media
    monitoring = monitoring

============================================================
FINAL CHECK
============================================================

Before returning JSON, compare the Indonesian output against the
English master field-by-field.

The Indonesian version must be a faithful translation of the master,
not a new interpretation.

Return ONLY valid JSON.

OUTPUT:
{
  "id": {
    "summary": "",
    "key_points": [],
    "critical_analysis": [],
    "implications": [],
    "sentiment": {
      "label": "positive",
      "reason": ""
    },
    "main_issue": {
      "title": "",
      "description": ""
    },
    "media_analysis": {
      "news_angle": "",
      "highlighted_actors": [],
      "pemprov_jateng_position": "",
      "public_opinion_potential": "",
      "key_messages": []
    },
    "communication_risk": {
      "level": "low",
      "reason": "",
      "escalation_potential": ""
    },
    "recommendations": [
      {
        "type": "monitoring",
        "action": "",
        "reason": ""
      }
    ],
    "takeaways": []
  }
}
"""


# ============================================================
# CHUNK SYSTEM PROMPT
# ============================================================

CHUNK_SYSTEM_PROMPT = """
You are a transcript extraction assistant.

Extract only important factual information from the supplied
transcript section.

Do not analyze, speculate, infer, or add outside knowledge.

Do not identify speakers.

Return ONLY valid JSON with this structure:

{
  "facts": [],
  "events": [],
  "actors": [],
  "issues": [],
  "locations": [],
  "numbers": [],
  "responses": [],
  "concerns": [],
  "developments": []
}
"""


# ============================================================
# MONITORING REPORT SYSTEM PROMPT
# ============================================================

MONITORING_SYSTEM_PROMPT = """
You are a professional media monitoring and communication
analysis AI.

Your task is to aggregate multiple previously analyzed
news/video items into ONE professional media monitoring report.

IMPORTANT:

Use ONLY the supplied analysis records.

Do not use outside knowledge.

Do not invent facts, exposure counts, stations, actors,
issues, locations, sentiment, or events.

The analysis records are the source dataset.

The purpose is to identify patterns across multiple reports,
not to repeat each individual report.

============================================================
REPORT OBJECTIVE
============================================================

Produce a professional monitoring report covering:

- total exposure
- number of news items
- number of TV stations
- Pemprov Jawa Tengah exposure
- sentiment distribution
- dominant issues
- affected regions
- highlighted actors
- media angles
- Pemprov Jawa Tengah position
- public opinion potential
- key messages
- communication risk
- news trend
- recommendations
- conclusion

============================================================
AGGREGATION RULES
============================================================

Count and group information across all supplied records.

Dominant issues should be based on recurrence and prominence.

Do not merge unrelated issues merely because they are similar.

Affected regions should only include regions explicitly present
in the supplied records.

Highlighted actors should reflect actors repeatedly or
prominently appearing across the records.

Media angles should identify the dominant framing across
the reporting set.

============================================================
SENTIMENT
============================================================

Use the sentiment labels already assigned to the individual
records.

Allowed values:

"positive"
"negative"
"neutral"

Calculate the distribution from the supplied records.

Do not invent counts.

Overall sentiment should reflect the distribution and
dominant reporting tone.

============================================================
PEMPROV JAWA TENGAH
============================================================

Assess how Pemprov Jawa Tengah is positioned across the
reporting set.

Possible positions include:
- positive
- neutral
- responsive
- criticized
- mixed
- limited visibility
- not prominently mentioned

Do not invent involvement.

============================================================
PUBLIC OPINION POTENTIAL
============================================================

Assess the potential for the reporting to shape public
attention or perception.

This is an analytical assessment.

Do not claim that public opinion actually changed unless
the supplied records explicitly support that conclusion.

Use cautious language.

============================================================
COMMUNICATION RISK
============================================================

Assess overall communication risk:

"low"
"medium"
"high"

Consider:
- volume
- sentiment
- issue sensitivity
- prominence
- criticism
- government involvement
- repeated concerns
- potential continuation of coverage

Do not automatically classify a negative issue as high risk.

Provide:
- level
- reason
- escalation_potential

============================================================
NEWS TREND
============================================================

Identify how the dominant issue or coverage develops across
the reporting set when the supplied records provide enough
information.

Do not force a three-stage trend if the data does not support it.

Use the smallest useful number of stages.

============================================================
RECOMMENDATIONS
============================================================

Recommendations must be based on the aggregated analysis.

Allowed types:

"amplification"
"clarification"
"counter_narrative"
"media_engagement"
"monitoring"

Do not automatically include all types.

Recommendations should be practical and relevant.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{
  "report": {
    "title": "",
    "period": {
      "start": "",
      "end": ""
    }
  },
  "statistics": {
    "total_exposure": 0,
    "total_news": 0,
    "total_tv_stations": 0,
    "pemprov_jateng_exposure": 0
  },
  "sentiment": {
    "overall": "neutral",
    "distribution": {
      "positive": 0,
      "negative": 0,
      "neutral": 0
    }
  },
  "dominant_issues": [],
  "affected_regions": [],
  "media_analysis": {
    "dominant_angle": "",
    "highlighted_actors": [],
    "pemprov_jateng_position": "",
    "public_opinion_potential": "",
    "key_messages": []
  },
  "communication_risk": {
    "level": "low",
    "reason": "",
    "escalation_potential": ""
  },
  "news_trend": {
    "stages": []
  },
  "recommendations": [],
  "conclusion": "",
  "sources": []
}
"""

# ============================================================
# CHUNK PROMPT
# ============================================================

CHUNK_PROMPT = """
Extract the important factual information from this transcript
section for later synthesis.

Return JSON with:
{
  "facts": [],
  "events": [],
  "actors": [],
  "issues": [],
  "locations": [],
  "numbers": [],
  "responses": [],
  "concerns": [],
  "developments": []
}

Use ONLY information contained in the transcript section.

Do not invent facts.

TRANSCRIPT SECTION:
"""


# ============================================================
# ERROR RESPONSE
# ============================================================

def error_response(
    message,
    error_type="server_error",
    status=500
):
    return {
        "status": "error",
        "message": message,
        "error": message,
        "error_type": error_type,
        "http_status": status
    }


# ============================================================
# YOUTUBE URL NORMALIZATION
# ============================================================

def normalize_youtube_url(
    url
):
    if not isinstance(
        url,
        str
    ):
        return ""

    url = url.strip()

    if not url:
        return ""

    url = re.sub(
        r"\s+",
        "",
        url
    )

    patterns = [
        r"youtube\.com/watch\?[^#]*v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url,
            re.IGNORECASE
        )

        if match:

            video_id = match.group(
                1
            )

            return (
                "https://www.youtube.com/watch?v="
                + video_id
            )

    return ""


# ============================================================
# EXTRACT VIDEO ID
# ============================================================

def extract_video_id(
    url
):
    normalized = normalize_youtube_url(
        url
    )

    if not normalized:
        return ""

    match = re.search(
        r"[?&]v=([A-Za-z0-9_-]{11})",
        normalized
    )

    if match:
        return match.group(
            1
        )

    return ""


# ============================================================
# FORMAT TIMESTAMP
# ============================================================

def format_timestamp(
    seconds
):
    try:
        total_seconds = int(
            float(seconds)
        )
    except Exception:
        total_seconds = 0

    if total_seconds < 0:
        total_seconds = 0

    hours = total_seconds // 3600

    minutes = (
        total_seconds % 3600
    ) // 60

    secs = (
        total_seconds % 60
    )

    if hours > 0:

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


# ============================================================
# BUILD TRANSCRIPT TEXT
# ============================================================

def build_transcript_text(
    segments
):
    lines = []

    if not isinstance(
        segments,
        list
    ):
        return ""

    for segment in segments:

        if not isinstance(
            segment,
            dict
        ):
            continue

        text = str(
            segment.get(
                "text",
                ""
            )
        ).strip()

        if not text:
            continue

        start = segment.get(
            "start",
            0
        )

        timestamp = format_timestamp(
            start
        )

        lines.append(
            f"[{timestamp}] {text}"
        )

    return "\n".join(
        lines
    )


# ============================================================
# TRANSCRIPT HASH
# ============================================================

def create_transcript_hash(
    text
):
    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# CHUNK TEXT
# ============================================================

def chunk_text(
    text,
    chunk_size=CHUNK_SIZE
):
    if not text:
        return []

    chunks = []

    start = 0

    text_length = len(
        text
    )

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length
        )

        if end < text_length:

            split_position = text.rfind(
                "\n",
                start,
                end
            )

            minimum_split = (
                start +
                int(
                    chunk_size *
                    0.65
                )
            )

            if (
                split_position >
                minimum_split
            ):
                end = split_position

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        start = end

    return chunks


# ============================================================
# RUN AI
# ============================================================

def is_ai_quota_error(message):
    text = str(message or "").lower()

    markers = [
        "4006",
        "3036",
        "daily free allocation",
        "10,000 neurons",
        "10000 neurons",
        "account limited",
        "rate limit",
        "too many requests"
    ]

    return any(marker in text for marker in markers)


def utc_now():
    return datetime.now(timezone.utc)


def utc_date_key(now=None):
    now = now or utc_now()
    return now.strftime("%Y-%m-%d")


def next_quota_reset_utc(now=None):
    now = now or utc_now()
    next_day = (now + timedelta(days=1)).date()
    return datetime(
        next_day.year,
        next_day.month,
        next_day.day,
        0,
        0,
        0,
        tzinfo=timezone.utc
    )


def quota_reset_iso(now=None):
    return next_quota_reset_utc(now).isoformat().replace("+00:00", "Z")


async def load_quota_guard():
    """Load persistent quota state from Cloudflare KV.

    KV is the persistent source for the application-side circuit breaker.
    The actual Workers AI quota remains controlled by Cloudflare.
    """
    try:
        raw = await env.QUOTA_KV.get(QUOTA_KV_KEY)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                AI_QUOTA_GUARD.update({
                    "blocked_date": data.get("blocked_date"),
                    "last_error": data.get("last_error", ""),
                    "last_model": data.get("last_model", ""),
                    "blocked_at_utc": data.get("blocked_at_utc")
                })
    except Exception:
        # Keep the Worker functional if KV has a temporary read problem.
        # Cloudflare remains the authority for the real AI quota.
        pass


async def save_quota_guard():
    """Persist the current quota guard state to Cloudflare KV."""
    data = {
        "blocked_date": AI_QUOTA_GUARD.get("blocked_date"),
        "last_error": AI_QUOTA_GUARD.get("last_error", ""),
        "last_model": AI_QUOTA_GUARD.get("last_model", ""),
        "blocked_at_utc": AI_QUOTA_GUARD.get("blocked_at_utc")
    }

    try:
        await env.QUOTA_KV.put(
            QUOTA_KV_KEY,
            json.dumps(data),
            expiration_ttl=172800
        )
    except Exception:
        # The AI request result must not be hidden by a KV write failure.
        pass


async def refresh_quota_guard():
    """
    Load the persistent guard and clear it automatically when the UTC date changes.
    """
    await load_quota_guard()

    today = utc_date_key()
    blocked_date = AI_QUOTA_GUARD.get("blocked_date")

    if blocked_date and blocked_date != today:
        AI_QUOTA_GUARD["blocked_date"] = None
        AI_QUOTA_GUARD["last_error"] = ""
        AI_QUOTA_GUARD["last_model"] = ""
        AI_QUOTA_GUARD["blocked_at_utc"] = None
        await save_quota_guard()
        return True

    return False


async def is_quota_guard_blocked():
    await refresh_quota_guard()
    return AI_QUOTA_GUARD.get("blocked_date") == utc_date_key()


async def set_quota_guard_block(model, message):
    now = utc_now()
    AI_QUOTA_GUARD["blocked_date"] = utc_date_key(now)
    AI_QUOTA_GUARD["last_error"] = str(message)
    AI_QUOTA_GUARD["last_model"] = str(model or "")
    AI_QUOTA_GUARD["blocked_at_utc"] = now.isoformat().replace("+00:00", "Z")
    await save_quota_guard()


async def quota_status():
    now = utc_now()
    await refresh_quota_guard()
    blocked = await is_quota_guard_blocked()

    return {
        "status": "quota_exhausted" if blocked else "available_or_not_checked",
        "daily_limit_neurons": 10000,
        "timezone": "UTC",
        "current_utc": now.isoformat().replace("+00:00", "Z"),
        "next_reset_utc": quota_reset_iso(now),
        "automatic_daily_reset": True,
        "persistent_guard": True,
        "storage": "Cloudflare Workers KV",
        "guard_blocked": blocked,
        "blocked_date_utc": AI_QUOTA_GUARD.get("blocked_date"),
        "last_model": AI_QUOTA_GUARD.get("last_model", ""),
        "blocked_at_utc": AI_QUOTA_GUARD.get("blocked_at_utc"),
        "last_error": AI_QUOTA_GUARD.get("last_error", "")
    }


class AIQuotaError(RuntimeError):
    """Workers AI daily quota is unavailable for the current UTC day."""


async def run_ai(
    system_prompt,
    user_prompt,
    max_tokens=AI_MAX_TOKENS
):
    """
    Stable Workers AI runner with an automatic daily quota guard.

    Free Workers AI quota resets at 00:00 UTC. When Cloudflare returns
    a quota/account-limit error, the guard blocks further AI calls for
    the current UTC date. The guard is automatically cleared on the next
    UTC date, so the first request after reset can try Workers AI again.

    Quota errors do NOT trigger the fallback model because both models
    consume the same account-level Workers AI allocation. This avoids
    wasting additional requests when the account is quota-limited.
    """

    await refresh_quota_guard()

    if await is_quota_guard_blocked():
        raise AIQuotaError(
            "Workers AI daily free quota is currently unavailable. "
            "Automatic retry is enabled after the Cloudflare daily reset "
            "at " + quota_reset_iso() + "."
        )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens
    }

    models = [
        AI_MODEL,
        AI_FALLBACK_MODEL
    ]

    errors = []

    for model in models:

        if not model:
            continue

        for attempt in range(AI_RETRIES + 1):

            try:
                return await env.AI.run(
                    model,
                    payload
                )

            except Exception as error:

                message = str(error)

                errors.append(
                    model
                    + " -> "
                    + message
                )

                if is_ai_quota_error(message):
                    await set_quota_guard_block(model, message)

                    raise AIQuotaError(
                        "Workers AI daily free quota is currently unavailable. "
                        "Cloudflare returned a quota/account-limit error. "
                        "Automatic retry is enabled after the daily reset at "
                        + quota_reset_iso()
                        + "."
                    )

                if attempt < AI_RETRIES:
                    await asyncio.sleep(
                        0.8 * (attempt + 1)
                    )

    raise RuntimeError(
        "AI model request failed. "
        + " | ".join(errors)
    )


async def run_ai_json(
    system_prompt,
    user_prompt,
    max_tokens=AI_MAX_TOKENS
):
    """
    Run Workers AI and require a valid JSON object.

    One repair attempt is allowed for malformed JSON.
    Account/quota errors are not repeatedly re-requested.
    """

    last_error = None

    for attempt in range(2):

        prompt = user_prompt

        if attempt:
            prompt += (
                "\n\nIMPORTANT RETRY: Return ONLY a valid JSON object. "
                "Do not include markdown fences, explanations, or commentary."
            )

        try:

            result = await run_ai(
                system_prompt,
                prompt,
                max_tokens
            )

            return parse_ai_json(result)

        except Exception as error:

            last_error = error

            if is_ai_quota_error(
                str(error)
            ):
                break

    raise RuntimeError(
        "AI returned invalid or unusable JSON: "
        + str(last_error)
    )


# ============================================================
# DEDICATED ACTOR EXTRACTION
# ============================================================

async def extract_highlighted_actors(source_text):

    if not isinstance(source_text, str):
        return [], []

    source_text = source_text.strip()

    if not source_text:
        return [], []

    # Evidence extraction must use the timestamped transcript itself, not
    # synthesized chunk notes, so the timestamp and quote can be traced back
    # to the original source.
    source_text = source_text[:MAX_FINAL_CONTEXT_CHARS]

    prompt = (
        "Extract highlighted actors AND their source evidence from the "
        "following timestamped transcript/source.\n\n"
        "SOURCE:\n\n"
        + source_text
    )

    try:
        parsed = await run_ai_json(
            ACTOR_EXTRACTION_SYSTEM_PROMPT,
            prompt,
            3000
        )

        actors = parsed.get("actors", []) if isinstance(parsed, dict) else []

        if not isinstance(actors, list):
            return [], []

        highlighted = []
        evidence = []
        seen = set()

        for item in actors:
            if not isinstance(item, dict):
                continue

            name = normalize_text(item.get("name", ""))
            title = normalize_text(
                item.get("official_title", item.get("title", ""))
            )
            role = normalize_text(
                item.get("role", item.get("action", ""))
            )
            timestamp = normalize_text(
                item.get("evidence_timestamp", item.get("timestamp", ""))
            )
            quote = normalize_text(
                item.get("evidence_quote", item.get("quote", ""))
            )

            if not title and not name:
                continue

            if name and title and role:
                actor_text = f"{name} — {title} — {role}"
            elif name and role:
                actor_text = f"{name} — {role}"
            elif title and role:
                actor_text = (
                    f"{title} — name not stated in transcript — {role}"
                )
            elif name and title:
                actor_text = f"{name} — {title}"
            elif title:
                actor_text = f"{title} — name not stated in transcript"
            else:
                continue

            generic = re.sub(r"\s+", " ", actor_text.lower()).strip()
            if generic in {
                "attended the opening ceremony",
                "attended the opening",
                "led the opening ceremony",
                "menghadiri upacara pembukaan",
                "menghadiri acara pembukaan",
                "memimpin upacara pembukaan"
            }:
                continue

            key = actor_text.lower()
            if key in seen:
                continue

            seen.add(key)
            highlighted.append(actor_text)

            evidence.append({
                "actor": actor_text,
                "name": name,
                "official_title": title,
                "role": role,
                "evidence_timestamp": timestamp,
                "evidence_quote": quote
            })

        return highlighted[:12], evidence[:12]

    except Exception:
        # Main analysis remains usable if the evidence extractor fails.
        return [], []


# ============================================================
# EXTRACT AI TEXT
# ============================================================

def extract_ai_text(
    result
):

    if isinstance(
        result,
        str
    ):
        return result

    if isinstance(
        result,
        dict
    ):

        if "response" in result:

            response = result[
                "response"
            ]

            if isinstance(
                response,
                str
            ):
                return response

            if isinstance(
                response,
                dict
            ):
                return json.dumps(
                    response,
                    ensure_ascii=False
                )

        if "result" in result:

            nested = result[
                "result"
            ]

            if isinstance(
                nested,
                str
            ):
                return nested

            if isinstance(
                nested,
                dict
            ):
                return json.dumps(
                    nested,
                    ensure_ascii=False
                )

        return json.dumps(
            result,
            ensure_ascii=False
        )

    return str(
        result
    )


# ============================================================
# CLEAN JSON
# ============================================================

def clean_json_text(
    text
):

    if not text:
        return ""

    text = str(
        text
    ).strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    first = text.find(
        "{"
    )

    last = text.rfind(
        "}"
    )

    if (
        first >= 0 and
        last > first
    ):

        text = text[
            first:last + 1
        ]

    return text.strip()


# ============================================================
# PARSE AI JSON
# ============================================================

def parse_ai_json(
    result
):

    text = extract_ai_text(
        result
    )

    text = clean_json_text(
        text
    )

    if not text:

        raise ValueError(
            "AI returned an empty response."
        )

    try:

        parsed = json.loads(
            text
        )

        if isinstance(
            parsed,
            dict
        ):
            return parsed

    except Exception:
        pass

    try:

        parsed = ast.literal_eval(
            text
        )

        if isinstance(
            parsed,
            dict
        ):
            return parsed

    except Exception:
        pass

    raise ValueError(
        "AI returned invalid JSON."
    )


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        parts = []
        for item in value:
            text = normalize_text(item)
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    if isinstance(value, dict):
        preferred_keys = [
            "issue",
            "reason",
            "evidence",
            "observation",
            "analysis",
            "text",
            "content",
            "description",
            "action",
            "escalation_potential",
            "news_angle"
        ]

        parts = []

        for key in preferred_keys:
            if key in value:
                text = normalize_text(value[key])
                if text:
                    parts.append(text)

        if parts:
            return " ".join(parts).strip()

        values = []
        for item in value.values():
            text = normalize_text(item)
            if text:
                values.append(text)

        return " ".join(values).strip()

    return str(value).strip()


# ============================================================
# NORMALIZE LIST
# ============================================================

def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        output = []

        for item in value:
            text = normalize_text(item)

            if text:
                output.append(text)

        return output

    text = normalize_text(value)

    if text:
        return [text]

    return []


# ============================================================
# NORMALIZE RECOMMENDATIONS
# ============================================================

def normalize_recommendations(value):
    if not isinstance(value, list):
        return []

    allowed_types = {
        "amplification",
        "clarification",
        "counter_narrative",
        "media_engagement",
        "monitoring"
    }

    output = []

    for item in value:
        if isinstance(item, dict):
            recommendation_type = str(
                item.get("type", "monitoring")
            ).strip().lower()

            if recommendation_type not in allowed_types:
                recommendation_type = "monitoring"

            action = normalize_text(
                item.get("action", "")
            )

            reason = normalize_text(
                item.get("reason", "")
            )

            if action:
                output.append({
                    "type": recommendation_type,
                    "action": action,
                    "reason": reason
                })

        else:
            action = normalize_text(item)

            if action:
                output.append({
                    "type": "monitoring",
                    "action": action,
                    "reason": ""
                })

    return output


# ============================================================
# NORMALIZE SENTIMENT
# ============================================================

def normalize_sentiment(value):
    if isinstance(value, dict):
        label = str(
            value.get("label", "neutral")
        ).strip().lower()

        reason = normalize_text(
            value.get("reason", "")
        )
    else:
        label = str(
            value or "neutral"
        ).strip().lower()

        reason = ""

    if label not in {
        "positive",
        "negative",
        "neutral"
    }:
        label = "neutral"

    return {
        "label": label,
        "reason": reason
    }


# ============================================================
# NORMALIZE COMMUNICATION RISK
# ============================================================

def normalize_communication_risk(value):
    if not isinstance(value, dict):
        value = {}

    level = str(
        value.get("level", "low")
    ).strip().lower()

    if level not in {
        "low",
        "medium",
        "high"
    }:
        level = "low"

    return {
        "level": level,
        "reason": normalize_text(
            value.get("reason", "")
        ),
        "escalation_potential": normalize_text(
            value.get("escalation_potential", "")
        )
    }


# ============================================================
# NORMALIZE ACTOR EVIDENCE
# ============================================================

def normalize_actor_evidence(value):
    if not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        if not isinstance(item, dict):
            continue

        actor = normalize_text(
            item.get("actor", "")
        )
        name = normalize_text(
            item.get("name", "")
        )
        official_title = normalize_text(
            item.get("official_title", item.get("title", ""))
        )
        role = normalize_text(
            item.get("role", item.get("action", ""))
        )
        timestamp = normalize_text(
            item.get("evidence_timestamp", item.get("timestamp", ""))
        )
        quote = normalize_text(
            item.get("evidence_quote", item.get("quote", ""))
        )

        if not (actor or name or official_title or quote):
            continue

        cleaned.append({
            "actor": actor,
            "name": name,
            "official_title": official_title,
            "role": role,
            "evidence_timestamp": timestamp,
            "evidence_quote": quote
        })

    return cleaned[:12]


# ============================================================
# NORMALIZE MEDIA ANALYSIS
# ============================================================

def normalize_media_analysis(value):
    if not isinstance(value, dict):
        value = {}

    return {
        "news_angle": normalize_text(
            value.get("news_angle", "")
        ),

        "highlighted_actors": normalize_list(
            value.get("highlighted_actors", [])
        ),

        "actor_evidence": normalize_actor_evidence(
            value.get("actor_evidence", [])
        ),

        "pemprov_jateng_position": normalize_text(
            value.get(
                "pemprov_jateng_position",
                ""
            )
        ),

        "public_opinion_potential": normalize_text(
            value.get(
                "public_opinion_potential",
                ""
            )
        ),

        "key_messages": normalize_list(
            value.get("key_messages", [])
        )
    }


# ============================================================
# ENFORCE INFERENCE LABELS
# ============================================================

def enforce_inference_labels(analysis):
    if not isinstance(analysis, dict):
        return analysis

    for language in ["en", "id"]:
        section = analysis.get(language)

        if not isinstance(section, dict):
            continue

        for field in [
            "critical_analysis",
            "implications"
        ]:
            items = section.get(field, [])

            if not isinstance(items, list):
                continue

            normalized = []

            for item in items:
                text = normalize_text(item)

                if not text:
                    continue

                if not text.lower().startswith(
                    "inference:"
                ):
                    text = "Inference: " + text

                normalized.append(text)

            section[field] = normalized

    return analysis


# ============================================================
# NORMALIZE LANGUAGE BLOCK
# ============================================================

def normalize_language_block(block):
    if not isinstance(block, dict):
        block = {}

    result = {
        "summary": normalize_text(
            block.get("summary", "")
        ),

        "key_points": normalize_list(
            block.get("key_points", [])
        ),

        "critical_analysis": normalize_list(
            block.get("critical_analysis", [])
        ),

        "implications": normalize_list(
            block.get("implications", [])
        ),

        "sentiment": normalize_sentiment(
            block.get("sentiment", {})
        ),

        "main_issue": {
            "title": normalize_text(
                (
                    block.get(
                        "main_issue",
                        {}
                    )
                    if isinstance(
                        block.get(
                            "main_issue",
                            {}
                        ),
                        dict
                    )
                    else {}
                ).get("title", "")
            ),

            "description": normalize_text(
                (
                    block.get(
                        "main_issue",
                        {}
                    )
                    if isinstance(
                        block.get(
                            "main_issue",
                            {}
                        ),
                        dict
                    )
                    else {}
                ).get("description", "")
            )
        },

        "media_analysis": normalize_media_analysis(
            block.get("media_analysis", {})
        ),

        "communication_risk": normalize_communication_risk(
            block.get("communication_risk", {})
        ),

        "recommendations": normalize_recommendations(
            block.get("recommendations", [])
        ),

        "takeaways": normalize_list(
            block.get("takeaways", [])
        )
    }

    return result


# ============================================================
# NORMALIZE FINAL ANALYSIS
# ============================================================

def synchronize_language_analysis(result):
    """
    Enforce analytical consistency between EN and ID.

    EN and ID remain separate language blocks, but controlled
    analytical decisions are locked to the same master result.
    This prevents translation from changing sentiment, risk,
    or recommendation strategy.
    """

    if not isinstance(result, dict):
        return result

    en = result.get("en")
    id_block = result.get("id")

    if not isinstance(en, dict) or not isinstance(id_block, dict):
        return result

    # --------------------------------------------------------
    # SENTIMENT LABEL
    # --------------------------------------------------------
    en_sentiment = en.get("sentiment", {})
    id_sentiment = id_block.get("sentiment", {})

    if not isinstance(en_sentiment, dict):
        en_sentiment = {}

    if not isinstance(id_sentiment, dict):
        id_sentiment = {}

    canonical_sentiment = (
        str(
            en_sentiment.get("label", "neutral")
        )
        .strip()
        .lower()
    )

    if canonical_sentiment not in {
        "positive",
        "negative",
        "neutral"
    }:
        canonical_sentiment = "neutral"

    id_sentiment["label"] = canonical_sentiment

    # Keep the Indonesian reason generated by the model,
    # but never allow it to alter the categorical decision.
    # Do not copy English prose into Indonesian.
    # Translation output remains the source of Indonesian wording.

    en["sentiment"] = en_sentiment
    id_block["sentiment"] = id_sentiment

    # --------------------------------------------------------
    # COMMUNICATION RISK LEVEL
    # --------------------------------------------------------
    en_risk = en.get("communication_risk", {})
    id_risk = id_block.get("communication_risk", {})

    if not isinstance(en_risk, dict):
        en_risk = {}

    if not isinstance(id_risk, dict):
        id_risk = {}

    canonical_risk = (
        str(
            en_risk.get("level", "low")
        )
        .strip()
        .lower()
    )

    if canonical_risk not in {
        "low",
        "medium",
        "high"
    }:
        canonical_risk = "low"

    id_risk["level"] = canonical_risk

    # Do not copy English prose into Indonesian.
    # Translation output remains the source of Indonesian wording.

    en["communication_risk"] = en_risk
    id_block["communication_risk"] = id_risk

    # --------------------------------------------------------
    # RECOMMENDATION TYPES
    # --------------------------------------------------------
    en_recommendations = en.get(
        "recommendations",
        []
    )
    id_recommendations = id_block.get(
        "recommendations",
        []
    )

    if not isinstance(en_recommendations, list):
        en_recommendations = []

    if not isinstance(id_recommendations, list):
        id_recommendations = []

    allowed_types = {
        "amplification",
        "clarification",
        "counter_narrative",
        "media_engagement",
        "monitoring"
    }

    canonical_types = []

    for item in en_recommendations:
        if not isinstance(item, dict):
            continue

        recommendation_type = str(
            item.get("type", "")
        ).strip().lower()

        if recommendation_type in allowed_types:
            canonical_types.append(
                recommendation_type
            )

    # Remove duplicates while preserving order.
    canonical_types = list(
        dict.fromkeys(
            canonical_types
        )
    )

    # Rebuild ID recommendations so strategic types cannot diverge.
    id_by_type = {}

    for item in id_recommendations:
        if not isinstance(item, dict):
            continue

        recommendation_type = str(
            item.get("type", "")
        ).strip().lower()

        if recommendation_type in allowed_types:
            id_by_type[recommendation_type] = item

    synced_id_recommendations = []

    for recommendation_type in canonical_types:

        id_item = id_by_type.get(
            recommendation_type,
            {}
        )

        en_item = next(
            (
                item
                for item in en_recommendations
                if isinstance(item, dict)
                and str(
                    item.get("type", "")
                ).strip().lower()
                == recommendation_type
            ),
            {}
        )

        synced_id_recommendations.append({
            "type": recommendation_type,
            "action": normalize_text(
                id_item.get(
                    "action",
                    ""
                )
            ),
            "reason": normalize_text(
                id_item.get(
                    "reason",
                    ""
                )
            )
        })

    id_block["recommendations"] = (
        synced_id_recommendations
    )

    result["en"] = en
    result["id"] = id_block

    return result


def synchronize_factual_coverage(result):
    """
    Keep the two language versions structurally aligned.

    This does not copy English prose into Indonesian. It only
    ensures that important list sections are populated from the
    master EN result if the model accidentally leaves the ID
    version empty.
    """

    if not isinstance(result, dict):
        return result

    en = result.get("en")
    id_block = result.get("id")

    if not isinstance(en, dict) or not isinstance(id_block, dict):
        return result

    list_fields = [
        "key_points",
        "critical_analysis",
        "implications",
        "takeaways"
    ]

    for field_name in list_fields:

        en_items = en.get(
            field_name,
            []
        )

        id_items = id_block.get(
            field_name,
            []
        )

        if not isinstance(en_items, list):
            en_items = []

        if not isinstance(id_items, list):
            id_items = []

        # If ID is accidentally empty, use the EN content as a
        # fallback rather than returning an incomplete analysis.
        # The normal case remains the model-generated Indonesian text.
        if en_items and not id_items:
            id_block[field_name] = en_items.copy()

    # Main issue fallback if one language is accidentally empty.
    en_issue = en.get(
        "main_issue",
        {}
    )

    id_issue = id_block.get(
        "main_issue",
        {}
    )

    if not isinstance(en_issue, dict):
        en_issue = {}

    if not isinstance(id_issue, dict):
        id_issue = {}

    if not id_issue.get("title"):
        id_issue["title"] = en_issue.get(
            "title",
            ""
        )

    if not id_issue.get("description"):
        id_issue["description"] = en_issue.get(
            "description",
            ""
        )

    id_block["main_issue"] = id_issue

    result["en"] = en
    result["id"] = id_block

    return result


def normalize_analysis(data):
    if not isinstance(data, dict):
        data = {}

    result = {
        "en": normalize_language_block(
            data.get("en", {})
        ),
        "id": normalize_language_block(
            data.get("id", {})
        )
    }

    result = enforce_inference_labels(
        result
    )

    result = synchronize_language_analysis(
        result
    )

    result = synchronize_factual_coverage(
        result
    )

    return result


# ============================================================
# NORMALIZE MONITORING REPORT
# ============================================================

def normalize_monitoring_report(data):
    if not isinstance(data, dict):
        data = {}

    report = data.get("report", {})
    if not isinstance(report, dict):
        report = {}

    statistics = data.get("statistics", {})
    if not isinstance(statistics, dict):
        statistics = {}

    sentiment = data.get("sentiment", {})
    if not isinstance(sentiment, dict):
        sentiment = {}

    distribution = sentiment.get("distribution", {})
    if not isinstance(distribution, dict):
        distribution = {}

    dominant_issues = data.get(
        "dominant_issues",
        []
    )
    if not isinstance(dominant_issues, list):
        dominant_issues = []

    normalized_issues = []

    for item in dominant_issues:
        if not isinstance(item, dict):
            continue

        try:
            exposure_count = int(
                item.get("exposure_count", 0)
            )
        except Exception:
            exposure_count = 0

        try:
            percentage = float(
                item.get("percentage", 0)
            )
        except Exception:
            percentage = 0.0

        normalized_issues.append({
            "issue": normalize_text(
                item.get("issue", "")
            ),
            "exposure_count": max(
                exposure_count,
                0
            ),
            "percentage": max(
                percentage,
                0.0
            ),
            "description": normalize_text(
                item.get("description", "")
            )
        })

    affected_regions = data.get(
        "affected_regions",
        []
    )
    if not isinstance(affected_regions, list):
        affected_regions = []

    normalized_regions = []

    for item in affected_regions:
        if not isinstance(item, dict):
            continue

        try:
            count = int(
                item.get("exposure_count", 0)
            )
        except Exception:
            count = 0

        normalized_regions.append({
            "region": normalize_text(
                item.get("region", "")
            ),
            "exposure_count": max(
                count,
                0
            ),
            "issues": normalize_list(
                item.get("issues", [])
            )
        })

    recommendations = normalize_recommendations(
        data.get("recommendations", [])
    )

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        sources = []

    normalized_sources = []

    for item in sources:
        if isinstance(item, dict):
            try:
                count = int(
                    item.get("exposure_count", 0)
                )
            except Exception:
                count = 0

            normalized_sources.append({
                "station": normalize_text(
                    item.get("station", "")
                ),
                "exposure_count": max(
                    count,
                    0
                )
            })

    overall = str(
        sentiment.get(
            "overall",
            "neutral"
        )
    ).strip().lower()

    if overall not in {
        "positive",
        "negative",
        "neutral"
    }:
        overall = "neutral"

    return {
        "report": {
            "title": normalize_text(
                report.get("title", "")
            ),
            "period": {
                "start": normalize_text(
                    (
                        report.get(
                            "period",
                            {}
                        )
                        if isinstance(
                            report.get(
                                "period",
                                {}
                            ),
                            dict
                        )
                        else {}
                    ).get("start", "")
                ),
                "end": normalize_text(
                    (
                        report.get(
                            "period",
                            {}
                        )
                        if isinstance(
                            report.get(
                                "period",
                                {}
                            ),
                            dict
                        )
                        else {}
                    ).get("end", "")
                )
            }
        },

        "statistics": {
            "total_exposure": max(
                int(
                    statistics.get(
                        "total_exposure",
                        0
                    ) or 0
                ),
                0
            ),
            "total_news": max(
                int(
                    statistics.get(
                        "total_news",
                        0
                    ) or 0
                ),
                0
            ),
            "total_tv_stations": max(
                int(
                    statistics.get(
                        "total_tv_stations",
                        0
                    ) or 0
                ),
                0
            ),
            "pemprov_jateng_exposure": max(
                int(
                    statistics.get(
                        "pemprov_jateng_exposure",
                        0
                    ) or 0
                ),
                0
            )
        },

        "sentiment": {
            "overall": overall,
            "distribution": {
                "positive": max(
                    int(
                        distribution.get(
                            "positive",
                            0
                        ) or 0
                    ),
                    0
                ),
                "negative": max(
                    int(
                        distribution.get(
                            "negative",
                            0
                        ) or 0
                    ),
                    0
                ),
                "neutral": max(
                    int(
                        distribution.get(
                            "neutral",
                            0
                        ) or 0
                    ),
                    0
                )
            }
        },

        "dominant_issues": normalized_issues,
        "affected_regions": normalized_regions,

        "media_analysis": normalize_media_analysis(
            data.get(
                "media_analysis",
                {}
            )
        ),

        "communication_risk": normalize_communication_risk(
            data.get(
                "communication_risk",
                {}
            )
        ),

        "news_trend": {
            "stages": normalize_list(
                (
                    data.get(
                        "news_trend",
                        {}
                    )
                    if isinstance(
                        data.get(
                            "news_trend",
                            {}
                        ),
                        dict
                    )
                    else {}
                ).get("stages", [])
            )
        },

        "recommendations": recommendations,

        "conclusion": normalize_text(
            data.get("conclusion", "")
        ),

        "sources": normalized_sources
    }


# ============================================================
# FETCH TRANSCRIPT
# ============================================================

async def fetch_transcript(
    video_url
):

    normalized_url = normalize_youtube_url(
        video_url
    )

    if not normalized_url:

        raise ValueError(
            "Invalid YouTube URL."
        )

    response = None
    last_error = None

    for attempt in range(TRANSCRIPT_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=AI_TIMEOUT,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    TRANSCRIPT_API_URL,
                    params={
                        "video_url": normalized_url
                    }
                )

            if response.status_code == 200:
                break

            last_error = RuntimeError(
                "Transcript service returned HTTP "
                + str(response.status_code)
            )

        except Exception as error:
            last_error = error

        if attempt < TRANSCRIPT_RETRIES:
            await asyncio.sleep(0.8 * (attempt + 1))

    if response is None:
        raise RuntimeError(
            "Failed to connect to transcript service after retries: "
            + str(last_error)
        )

    if response.status_code != 200:

        try:

            error_data = response.json()

            message = error_data.get(
                "message",
                (
                    "Transcript service returned HTTP "
                    + str(
                        response.status_code
                    )
                )
            )

        except Exception:

            message = (
                response.text
                or (
                    "Transcript service returned HTTP "
                    + str(
                        response.status_code
                    )
                )
            )

        raise RuntimeError(
            message
        )

    try:

        data = response.json()

    except Exception:

        raise RuntimeError(
            "Transcript service returned invalid JSON."
        )

    if not isinstance(
        data,
        dict
    ):

        raise RuntimeError(
            "Transcript service returned invalid data."
        )

    segments = data.get(
        "transcript",
        []
    )

    if not isinstance(
        segments,
        list
    ):
        segments = []

    cleaned = []

    for segment in segments:

        if not isinstance(
            segment,
            dict
        ):
            continue

        text = str(
            segment.get(
                "text",
                ""
            )
        ).strip()

        if not text:
            continue

        try:

            start = float(
                segment.get(
                    "start",
                    0
                )
            )

        except Exception:

            start = 0.0

        try:

            duration = float(
                segment.get(
                    "duration",
                    0
                )
            )

        except Exception:

            duration = 0.0

        cleaned.append(
            {
                "text":
                    text,

                "start":
                    start,

                "duration":
                    duration
            }
        )

    if not cleaned:

        raise RuntimeError(
            "Transcript is empty or unavailable for this video."
        )

    return {
        "title":
            data.get(
                "title",
                "Untitled Video"
            ),

        "language":
            data.get(
                "language",
                "unknown"
            ),

        "transcript":
            cleaned
    }


# ============================================================
# MASTER -> INDONESIAN TRANSLATION
# ============================================================

async def translate_master_to_indonesian(
    master_en
):

    if not isinstance(master_en, dict):
        raise ValueError(
            "Master English analysis is invalid."
        )

    source_json = json.dumps(
        {
            "en": master_en
        },
        ensure_ascii=False,
        indent=2
    )

    prompt = """
Translate the following MASTER ENGLISH ANALYSIS into Indonesian.

IMPORTANT:
- This is translation only, NOT a new analysis.
- Preserve every fact, number, date, actor, issue, conclusion,
  recommendation type, and list-item count.
- Preserve the same order.
- Translate ALL prose, especially recommendation action and reason.
- Do not leave English sentences in the Indonesian result.
- Keep the literal prefix "Inference:" for inferential items.
- Keep controlled internal values unchanged.
- Preserve actor_evidence one-to-one.
- DO NOT translate evidence_quote; it must remain verbatim source text.
- DO NOT change evidence_timestamp.

MASTER ENGLISH ANALYSIS:

""" + source_json

    last_error = None

    for attempt in range(2):
        try:
            parsed = await run_ai_json(
                INDONESIAN_TRANSLATION_SYSTEM_PROMPT,
                prompt,
                4200
            )

            id_block = parsed.get(
                "id",
                parsed
            )

            if not isinstance(id_block, dict):
                raise ValueError(
                    "Indonesian translation returned invalid data."
                )

            id_block = normalize_language_block(id_block)
            validate_indonesian_translation(master_en, id_block)
            return id_block

        except Exception as error:
            last_error = error

            if attempt == 0:
                prompt += (
                    "\n\nRETRY REQUIREMENT: The previous translation was incomplete. "
                    "Translate every field, especially recommendation action/reason "
                    "and actor evidence metadata. Preserve counts and order."
                )

    raise RuntimeError(
        "Indonesian translation failed after retries: "
        + str(last_error)
    )


def validate_indonesian_translation(
    master_en,
    id_block
):

    if not isinstance(master_en, dict):
        raise ValueError(
            "Master English analysis is invalid."
        )

    if not isinstance(id_block, dict):
        raise ValueError(
            "Indonesian analysis is invalid."
        )

    # Required text fields must exist in ID.
    required_text_fields = [
        "summary"
    ]

    for field_name in required_text_fields:
        if not normalize_text(
            id_block.get(field_name, "")
        ):
            raise ValueError(
                "Indonesian translation is incomplete: "
                + field_name
            )

    # List sections must preserve item counts.
    list_fields = [
        "key_points",
        "critical_analysis",
        "implications",
        "takeaways"
    ]

    for field_name in list_fields:

        en_items = master_en.get(
            field_name,
            []
        )
        id_items = id_block.get(
            field_name,
            []
        )

        if not isinstance(en_items, list):
            en_items = []

        if not isinstance(id_items, list):
            id_items = []

        if len(en_items) != len(id_items):
            raise ValueError(
                "Indonesian translation changed item count: "
                + field_name
            )

        for index, en_item in enumerate(en_items):
            id_item = id_items[index]

            en_text = normalize_text(en_item)
            id_text = normalize_text(id_item)

            if en_text and not id_text:
                raise ValueError(
                    "Indonesian translation contains an empty item: "
                    + field_name
                )

    # Main issue must be complete.
    en_issue = master_en.get(
        "main_issue",
        {}
    )
    id_issue = id_block.get(
        "main_issue",
        {}
    )

    if not isinstance(en_issue, dict):
        en_issue = {}
    if not isinstance(id_issue, dict):
        id_issue = {}

    if en_issue.get("title") and not id_issue.get("title"):
        raise ValueError(
            "Indonesian translation is incomplete: main_issue.title"
        )

    if en_issue.get("description") and not id_issue.get("description"):
        raise ValueError(
            "Indonesian translation is incomplete: main_issue.description"
        )

    # Actor evidence must remain one-to-one and traceable.
    en_media = master_en.get("media_analysis", {})
    id_media = id_block.get("media_analysis", {})
    if not isinstance(en_media, dict):
        en_media = {}
    if not isinstance(id_media, dict):
        id_media = {}

    en_evidence = en_media.get("actor_evidence", [])
    id_evidence = id_media.get("actor_evidence", [])
    if not isinstance(en_evidence, list):
        en_evidence = []
    if not isinstance(id_evidence, list):
        id_evidence = []

    if len(en_evidence) != len(id_evidence):
        raise ValueError(
            "Indonesian translation changed actor evidence count."
        )

    for index, en_item in enumerate(en_evidence):
        if not isinstance(en_item, dict):
            continue
        id_item = id_evidence[index]
        if not isinstance(id_item, dict):
            raise ValueError("Indonesian actor evidence item is invalid.")

        if normalize_text(en_item.get("actor", "")) and not normalize_text(id_item.get("actor", "")):
            raise ValueError("Indonesian actor evidence is incomplete: actor")

        if normalize_text(en_item.get("evidence_timestamp", "")) != normalize_text(id_item.get("evidence_timestamp", "")):
            raise ValueError("Indonesian actor evidence timestamp changed.")

        # Evidence quote is source text, so it must remain verbatim.
        if normalize_text(en_item.get("evidence_quote", "")) != normalize_text(id_item.get("evidence_quote", "")):
            raise ValueError("Indonesian actor evidence quote changed.")

    # Recommendation count and prose must be preserved.
    en_recs = master_en.get(
        "recommendations",
        []
    )
    id_recs = id_block.get(
        "recommendations",
        []
    )

    if not isinstance(en_recs, list):
        en_recs = []
    if not isinstance(id_recs, list):
        id_recs = []

    if len(en_recs) != len(id_recs):
        raise ValueError(
            "Indonesian translation changed recommendation count."
        )

    for index, en_rec in enumerate(en_recs):

        if not isinstance(en_rec, dict):
            continue

        id_rec = id_recs[index]
        if not isinstance(id_rec, dict):
            raise ValueError(
                "Indonesian recommendation item is invalid."
            )

        en_type = str(
            en_rec.get("type", "")
        ).strip().lower()
        id_type = str(
            id_rec.get("type", "")
        ).strip().lower()

        if en_type != id_type:
            raise ValueError(
                "Indonesian recommendation type changed."
            )

        for prose_field in [
            "action",
            "reason"
        ]:
            if (
                normalize_text(
                    en_rec.get(prose_field, "")
                )
                and not normalize_text(
                    id_rec.get(prose_field, "")
                )
            ):
                raise ValueError(
                    "Indonesian recommendation is incomplete: "
                    + prose_field
                )

    # Important: if the translation is exactly identical to English
    # for a whole prose field, it is almost certainly untranslated.
    # This specifically catches the current Action/Reason problem.
    if (
        normalize_text(master_en.get("summary", ""))
        and normalize_text(master_en.get("summary", ""))
        == normalize_text(id_block.get("summary", ""))
    ):
        raise ValueError(
            "Indonesian summary appears untranslated."
        )

    for index, en_rec in enumerate(en_recs):
        if not isinstance(en_rec, dict):
            continue

        id_rec = id_recs[index]

        for prose_field in [
            "action",
            "reason"
        ]:
            en_text = normalize_text(
                en_rec.get(prose_field, "")
            )
            id_text = normalize_text(
                id_rec.get(prose_field, "")
            )

            if en_text and id_text and en_text == id_text:
                raise ValueError(
                    "Indonesian recommendation "
                    + prose_field
                    + " appears untranslated."
                )

    return True


async def build_consistent_analysis(
    master_result,
    actor_source=None
):

    if not isinstance(master_result, dict):
        raise ValueError(
            "Master analysis returned invalid data."
        )

    master_en = master_result.get(
        "en",
        master_result
    )

    if not isinstance(master_en, dict):
        raise ValueError(
            "Master English analysis is missing."
        )

    master_en = normalize_language_block(
        master_en
    )

    # Only run the extra actor extraction pass when the master analysis
    # does not already contain useful named actors/evidence. This reduces
    # latency and failure points for normal short videos while preserving
    # the dedicated extractor as a fallback for difficult transcripts.
    if actor_source:
        media = master_en.get("media_analysis", {})
        if not isinstance(media, dict):
            media = {}
            master_en["media_analysis"] = media

        existing_actors = media.get("highlighted_actors", [])
        existing_evidence = media.get("actor_evidence", [])

        if not existing_actors:
            try:
                extracted_actors, actor_evidence = await extract_highlighted_actors(
                    actor_source
                )

                if extracted_actors:
                    media["highlighted_actors"] = extracted_actors

                if actor_evidence:
                    media["actor_evidence"] = actor_evidence

            except Exception:
                # Actor evidence is supplemental. Never let this optional
                # pass destroy an otherwise valid analysis.
                pass

    id_block = await translate_master_to_indonesian(
        master_en
    )

    validate_indonesian_translation(
        master_en,
        id_block
    )

    result = {
        "en": master_en,
        "id": id_block
    }

    # Lock controlled analytical decisions to the master EN result.
    result = synchronize_language_analysis(
        result
    )

    # Do NOT copy English prose into Indonesian as a fallback.
    # The Indonesian block must come from the translation step so
    # that no English text can leak into the ID report.
    return enforce_inference_labels(
        result
    )


# ============================================================
# ANALYZE LARGE TRANSCRIPT
# ============================================================

async def analyze_large_transcript(
    transcript_text
):

    chunks = chunk_text(
        transcript_text
    )

    if not chunks:

        raise ValueError(
            "Transcript could not be divided into chunks."
        )

    notes = []

    for index, chunk in enumerate(
        chunks,
        start=1
    ):

        prompt = (
            CHUNK_PROMPT
            + "\n\nCHUNK "
            + str(index)
            + " OF "
            + str(len(chunks))
            + "\n\n"
            + chunk
        )

        result = await run_ai_json(
            CHUNK_SYSTEM_PROMPT,
            prompt,
            2200
        )

        notes.append(
            json.dumps(
                result,
                ensure_ascii=False
            )
        )

    combined_notes = "\n\n".join(
        notes
    )

    if len(combined_notes) > MAX_FINAL_CONTEXT_CHARS:
        half = MAX_FINAL_CONTEXT_CHARS // 2
        combined_notes = (
            combined_notes[:half]
            + "\n\n[... middle notes omitted for context control ...]\n\n"
            + combined_notes[-half:]
        )

    final_prompt = """
Create the final professional video analysis from the following
factual extraction notes.

IMPORTANT: Produce ONE MASTER ENGLISH analysis only.
The Indonesian version is generated separately by a translation step.
Do not produce an Indonesian analysis in this call.

Use all relevant information.

Follow the required JSON structure.

The executive summary must normally be approximately
180-300 words.

Do not invent facts.

Do not identify speakers.

Return ONLY valid JSON.

ANALYSIS NOTES:

""" + combined_notes

    final_result = await run_ai_json(
        MASTER_SYSTEM_PROMPT,
        final_prompt,
        4200
    )

    analysis = await build_consistent_analysis(
        final_result,
        actor_source=transcript_text
    )

    return (
        analysis,
        "chunked",
        len(chunks)
    )


# ============================================================
# ANALYZE TRANSCRIPT
# ============================================================

async def analyze_transcript(
    transcript_text
):

    if len(
        transcript_text
    ) <= MAX_SINGLE_PASS_CHARS:

        prompt = """
Create the final professional video analysis from
the following transcript.

IMPORTANT: Produce ONE MASTER ENGLISH analysis only.
The Indonesian version is generated separately by a translation step.
Do not produce an Indonesian analysis in this call.

Use ALL relevant information.

The executive summary must normally contain
approximately 180-300 words.

Follow the required JSON structure.

Do not invent facts.

Do not identify speakers.

Return ONLY valid JSON.

TRANSCRIPT:

""" + transcript_text

        result = await run_ai_json(
            MASTER_SYSTEM_PROMPT,
            prompt,
            4200
        )

        analysis = await build_consistent_analysis(
            result,
            actor_source=transcript_text
        )

        return (
            analysis,
            "single_pass",
            1
        )

    return await analyze_large_transcript(
        transcript_text
    )



# ============================================================
# MONITORING REPORT ENDPOINT
# ============================================================

@app.post("/monitoring-report")
async def monitoring_report(
    request: Request
):

    try:

        body = await request.json()

        if not isinstance(body, dict):
            return error_response(
                "Request body must be a JSON object.",
                "invalid_request",
                400
            )

        analyses = (
            body.get("analyses")
            or body.get("items")
            or []
        )

        if not isinstance(analyses, list):
            return error_response(
                "analyses must be an array.",
                "validation_error",
                400
            )

        if not analyses:
            return error_response(
                "At least one analysis record is required.",
                "validation_error",
                400
            )

        if len(analyses) > 100:
            return error_response(
                "Maximum 100 analysis records per monitoring report.",
                "validation_error",
                400
            )

        period = body.get("period", {})
        if not isinstance(period, dict):
            period = {}

        start_date = str(
            period.get("start", "")
        ).strip()

        end_date = str(
            period.get("end", "")
        ).strip()

        # ----------------------------------------------------
        # BUILD AGGREGATION DATA
        # ----------------------------------------------------

        records = []

        for index, item in enumerate(
            analyses,
            start=1
        ):

            if not isinstance(item, dict):
                continue

            video = item.get("video", {})
            if not isinstance(video, dict):
                video = {}

            ai = item.get("ai", {})
            if not isinstance(ai, dict):
                ai = {}

            # Prefer Indonesian analysis for the monitoring layer.
            # Fall back to English if Indonesian is unavailable.
            language_data = ai.get("id")

            if not isinstance(
                language_data,
                dict
            ):
                language_data = ai.get(
                    "en",
                    {}
                )

            if not isinstance(
                language_data,
                dict
            ):
                language_data = {}

            records.append({
                "record_id": index,

                "video": {
                    "id": normalize_text(
                        video.get("id", "")
                    ),
                    "title": normalize_text(
                        video.get("title", "")
                    ),
                    "url": normalize_text(
                        video.get("url", "")
                    ),
                    "station": normalize_text(
                        video.get("station", "")
                    ),
                    "source": normalize_text(
                        video.get("source", "")
                    ),
                    "publication_date": normalize_text(
                        video.get(
                            "publication_date",
                            ""
                        )
                    )
                },

                "analysis": language_data
            })

        if not records:
            return error_response(
                "No valid analysis records were supplied.",
                "validation_error",
                400
            )

        # ----------------------------------------------------
        # DETERMINISTIC STATISTICS
        # ----------------------------------------------------

        total_news = len(records)

        stations = []

        positive = 0
        negative = 0
        neutral = 0

        pemprov_exposure = 0

        for record in records:

            video = record["video"]
            analysis = record["analysis"]

            station = video.get(
                "station",
                ""
            ).strip()

            if station:
                stations.append(
                    station
                )

            sentiment = analysis.get(
                "sentiment",
                {}
            )

            if isinstance(
                sentiment,
                dict
            ):
                label = str(
                    sentiment.get(
                        "label",
                        "neutral"
                    )
                ).strip().lower()
            else:
                label = "neutral"

            if label == "positive":
                positive += 1
            elif label == "negative":
                negative += 1
            else:
                neutral += 1

            media_analysis = analysis.get(
                "media_analysis",
                {}
            )

            if not isinstance(
                media_analysis,
                dict
            ):
                media_analysis = {}

            pemprov_position = normalize_text(
                media_analysis.get(
                    "pemprov_jateng_position",
                    ""
                )
            ).lower()

            if (
                pemprov_position
                and
                "not prominently mentioned"
                not in pemprov_position
                and
                "tidak disebut"
                not in pemprov_position
                and
                "tidak menonjol"
                not in pemprov_position
            ):
                pemprov_exposure += 1

        unique_stations = sorted(
            set(
                item
                for item in stations
                if item
            )
        )

        # ----------------------------------------------------
        # BUILD AI AGGREGATION INPUT
        # ----------------------------------------------------

        aggregation_payload = {
            "period": {
                "start": start_date,
                "end": end_date
            },

            "deterministic_statistics": {
                "total_news": total_news,
                "total_exposure": total_news,
                "total_tv_stations": len(
                    unique_stations
                ),
                "pemprov_jateng_exposure": pemprov_exposure,

                "sentiment_distribution": {
                    "positive": positive,
                    "negative": negative,
                    "neutral": neutral
                },

                "stations": unique_stations
            },

            "records": records
        }

        aggregation_text = json.dumps(
            aggregation_payload,
            ensure_ascii=False
        )

        if len(aggregation_text) > MAX_FINAL_CONTEXT_CHARS:
            aggregation_text = aggregation_text[
                :MAX_FINAL_CONTEXT_CHARS
            ]

        prompt = """
Create the final professional media monitoring report
from the supplied analysis records.

Use the deterministic statistics as authoritative counts
for total news, total exposure, TV stations, and sentiment.

Do not change deterministic counts.

Use the supplied individual analysis records to determine:
- dominant issues
- affected regions
- media angles
- highlighted actors
- Pemprov Jawa Tengah position
- public opinion potential
- key messages
- communication risk
- news trend
- recommendations
- conclusion

Return ONLY valid JSON.

PERIOD:
""" + json.dumps(
            {
                "start": start_date,
                "end": end_date
            },
            ensure_ascii=False
        ) + """

AGGREGATION DATA:

""" + aggregation_text

        result = await run_ai(
            MONITORING_SYSTEM_PROMPT,
            prompt,
            5000
        )

        report = normalize_monitoring_report(
            parse_ai_json(result)
        )

        # Force authoritative deterministic statistics.
        report["report"]["period"]["start"] = start_date
        report["report"]["period"]["end"] = end_date

        report["statistics"]["total_news"] = total_news
        report["statistics"]["total_exposure"] = total_news
        report["statistics"]["total_tv_stations"] = len(
            unique_stations
        )
        report["statistics"]["pemprov_jateng_exposure"] = (
            pemprov_exposure
        )

        report["sentiment"]["distribution"] = {
            "positive": positive,
            "negative": negative,
            "neutral": neutral
        }

        sentiment_counts = {
            "positive": positive,
            "negative": negative,
            "neutral": neutral
        }

        report["sentiment"]["overall"] = max(
            sentiment_counts,
            key=sentiment_counts.get
        )

        # Build deterministic source list when station metadata exists.
        station_counts = {}

        for station in stations:
            station_counts[station] = (
                station_counts.get(
                    station,
                    0
                ) + 1
            )

        report["sources"] = [
            {
                "station": station,
                "exposure_count": count
            }
            for station, count
            in sorted(
                station_counts.items(),
                key=lambda item: (
                    -item[1],
                    item[0]
                )
            )
        ]

        return {
            "status": "success",
            "report": report,
            "processing": {
                "total_records": total_news,
                "total_tv_stations": len(
                    unique_stations
                ),
                "sentiment_distribution": {
                    "positive": positive,
                    "negative": negative,
                    "neutral": neutral
                }
            }
        }

    except ValueError as error:

        return error_response(
            str(error),
            "validation_error",
            400
        )

    except RuntimeError as error:

        return error_response(
            str(error),
            "processing_error",
            502
        )

    except Exception as error:

        return error_response(
            "Unexpected server error: "
            + str(error),
            "server_error",
            500
        )


# ============================================================
# DAILY QUOTA STATUS
# ============================================================

@app.get("/quota-status")
async def quota_status_endpoint():
    return {
        "version": "9.4.4",
        "provider": "Cloudflare Workers AI",
        "primary_model": AI_MODEL,
        "fallback_model": AI_FALLBACK_MODEL,
        "quota": await quota_status()
    }


# ============================================================
# AI DIAGNOSTIC TEST
# ============================================================

@app.get("/ai-test")
async def ai_test():

    try:

        result = await run_ai(
            "Return ONLY a valid JSON object.",
            '{"status":"ok"}',
            80
        )

        parsed = parse_ai_json(
            result
        )

        return {
            "status":
                "ok",

            "version":
                "9.4.3",

            "ai":
                parsed,

            "quota":
                await quota_status(),

            "primary_model":
                AI_MODEL,

            "fallback_model":
                AI_FALLBACK_MODEL
        }

    except Exception as error:

        message = str(error)

        return {
            "status":
                "error",

            "version":
                "9.4.3",

            "primary_model":
                AI_MODEL,

            "fallback_model":
                AI_FALLBACK_MODEL,

            "quota_error":
                isinstance(error, AIQuotaError)
                or is_ai_quota_error(
                    message
                ),

            "quota":
                await quota_status(),

            "error":
                message
        }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "status":
            "ok",

        "service":
            "AI Video Summarizer API",

        "version":
            "9.4.3"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return {
        "status":
            "ok",

        "version":
            "9.4.3"
    }


# ============================================================
# ANALYZE ENDPOINT
# ============================================================

@app.post("/analyze")
async def analyze(
    request: Request
):

    try:

        # ----------------------------------------------------
        # READ JSON
        # ----------------------------------------------------

        try:

            body = await request.json()

        except Exception:

            return error_response(
                "Invalid JSON request body.",
                "invalid_json",
                400
            )

        if not isinstance(
            body,
            dict
        ):

            return error_response(
                "Request body must be a JSON object.",
                "invalid_request",
                400
            )

        # ----------------------------------------------------
        # READ URL
        # ----------------------------------------------------

        video_url = (
            body.get(
                "video_url"
            )
            or body.get(
                "youtube_url"
            )
            or body.get(
                "url"
            )
            or ""
        )

        if not isinstance(
            video_url,
            str
        ):

            video_url = str(
                video_url
            )

        video_url = video_url.strip()

        # ----------------------------------------------------
        # VALIDATE URL
        # ----------------------------------------------------

        if not video_url:

            return error_response(
                "YouTube URL is required.",
                "validation_error",
                400
            )

        normalized_url = normalize_youtube_url(
            video_url
        )

        if not normalized_url:

            return error_response(
                "Invalid YouTube URL.",
                "validation_error",
                400
            )

        video_id = extract_video_id(
            normalized_url
        )

        if not video_id:

            return error_response(
                "Could not extract YouTube video ID.",
                "validation_error",
                400
            )

        # Optional media-monitoring metadata.
        # Existing frontend requests remain fully compatible.
        station = str(
            body.get("station", "")
            or body.get("tv_station", "")
            or ""
        ).strip()

        source = str(
            body.get("source", "")
            or ""
        ).strip()

        publication_date = str(
            body.get("publication_date", "")
            or body.get("date", "")
            or ""
        ).strip()

        # ----------------------------------------------------
        # GET TRANSCRIPT
        # ----------------------------------------------------

        transcript_data = await fetch_transcript(
            normalized_url
        )

        transcript_segments = (
            transcript_data[
                "transcript"
            ]
        )

        # ----------------------------------------------------
        # BUILD TRANSCRIPT TEXT
        # ----------------------------------------------------

        transcript_text = build_transcript_text(
            transcript_segments
        )

        if not transcript_text:

            return error_response(
                "Transcript is empty.",
                "transcript_error",
                422
            )

        # ----------------------------------------------------
        # HASH
        # ----------------------------------------------------

        transcript_hash = create_transcript_hash(
            transcript_text
        )

        # ----------------------------------------------------
        # AI ANALYSIS
        # ----------------------------------------------------

        (
            analysis,
            analysis_mode,
            total_chunks
        ) = await analyze_transcript(
            transcript_text
        )

        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        return {
            "status":
                "success",

            "video": {
                "id":
                    video_id,

                "url":
                    normalized_url,

                "title":
                    transcript_data[
                        "title"
                    ],

                "station":
                    station,

                "source":
                    source,

                "publication_date":
                    publication_date
            },

            "transcript": {
                "title":
                    transcript_data[
                        "title"
                    ],

                "language":
                    transcript_data[
                        "language"
                    ],

                "transcript":
                    transcript_segments
            },

            "ai":
                analysis,

            "processing": {
                "mode":
                    analysis_mode,

                "total_segments":
                    len(
                        transcript_segments
                    ),

                "total_chunks":
                    total_chunks,

                "transcript_characters":
                    len(
                        transcript_text
                    ),

                "transcript_hash":
                    transcript_hash
            }
        }

    except ValueError as error:

        return error_response(
            str(error),
            "validation_error",
            400
        )

    except AIQuotaError as error:

        return {
            "status": "error",
            "message": str(error),
            "error": str(error),
            "error_type": "ai_quota_exhausted",
            "http_status": 429,
            "quota": await quota_status()
        }

    except RuntimeError as error:

        return error_response(
            str(error),
            "processing_error",
            502
        )

    except Exception as error:

        return error_response(
            "Unexpected server error: "
            + str(error),
            "server_error",
            500
        )


# ============================================================
# CLOUDFLARE ASGI
# ============================================================

Default = asgi.entrypoint(app)

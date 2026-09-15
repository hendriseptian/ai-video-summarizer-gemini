function isValidYouTubeUrl(value) {
    if (!value) return false;
    try {
        const url = new URL(value.trim());
        const hostname = url.hostname.toLowerCase();
        if (
            hostname === "youtube.com" ||
            hostname === "www.youtube.com" ||
            hostname === "m.youtube.com" ||
            hostname === "youtu.be" ||
            hostname === "www.youtu.be"
        ) {
            return true;
        }
        return false;
    } catch (error) {
        return false;
    }
}

const API_URL =
    "https://ai-video-summarizer.hendriseptian25.workers.dev/analyze";

let currentData = null;
let currentAIRoot = null;
let currentLanguage = "en";

window.addEventListener("DOMContentLoaded", function () {

    const analyzeButton =
        document.getElementById("analyzeButton");

    const videoUrl =
        document.getElementById("videoUrl");

    if (!analyzeButton) {
        console.error("ANALYZE button not found.");
        return;
    }

    analyzeButton.addEventListener(
        "click",
        analyzeVideo
    );

    if (videoUrl) {

        videoUrl.addEventListener(
            "keydown",
            function (event) {

                if (event.key === "Enter") {
                    analyzeVideo();
                }

            }
        );

    }

});


async function analyzeVideo() {

    const videoUrlInput =
        document.getElementById("videoUrl");

    const analyzeButton =
        document.getElementById("analyzeButton");

    const status =
        document.getElementById("status");

    const videoInfo =
        document.getElementById("videoInfo");

    const transcript =
        document.getElementById("transcript");

    const aiResult =
        document.getElementById("aiResult");


    const url =
        videoUrlInput
            ? videoUrlInput.value.trim()
            : "";


    if (!url) {

        setStatus(
            status,
            "Please enter a YouTube URL.",
            "error"
        );

        return;

    }


    if (!isYouTubeUrl(url)) {

        setStatus(
            status,
            "Please enter a valid YouTube URL.",
            "error"
        );

        return;

    }


    analyzeButton.disabled = true;

    analyzeButton.dataset.oldText =
        analyzeButton.textContent;

    analyzeButton.textContent =
        "ANALYZING...";


    setStatus(
        status,
        "Analyzing video. Please wait...",
        "loading"
    );


    if (videoInfo) {

        videoInfo.innerHTML =
            `<div class="empty-state">
                Loading video information...
            </div>`;

    }


    if (transcript) {

        transcript.innerHTML =
            `<div class="empty-state">
                Loading transcript...
            </div>`;

    }


    if (aiResult) {

        aiResult.innerHTML = "";

    }


    try {

        const response =
            await fetch(
                API_URL,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        video_url: url
                    })
                }
            );


        const text =
            await response.text();


        let data;


        try {

            data =
                JSON.parse(text);

        } catch (error) {

            console.error(
                "Server response:",
                text
            );

            throw new Error(
                "Server returned invalid JSON."
            );

        }


        if (!response.ok) {

            throw new Error(
                getErrorMessage(
                    data,
                    response.status
                )
            );

        }


        currentData =
            data;


        currentAIRoot =
            findAIRoot(data);


        if (!currentAIRoot) {

            console.error(
                "AI data not found:",
                data
            );

            const serverMessage =
                getErrorMessage(
                    data,
                    response.status
                );

            throw new Error(
                serverMessage &&
                serverMessage !==
                    "Request failed (HTTP " +
                    response.status +
                    ")."
                    ? serverMessage
                    : "Server returned no AI analysis data."
            );

        }


        renderVideoInfo(
            data
        );


        renderTranscript(
            data
        );


        renderAI(
            getLanguageData(
                currentAIRoot
            )
        );


        setStatus(
            status,
            "Analysis completed successfully.",
            "success"
        );


    } catch (error) {

        console.error(
            "Analyze error:",
            error
        );


        setStatus(
            status,
            error.message ||
                "Failed to analyze video.",
            "error"
        );


        if (videoInfo) {

            videoInfo.innerHTML = `
                <div class="error-box">
                    ${escapeHTML(
                        error.message ||
                        "Failed to analyze video."
                    )}
                </div>
            `;

        }


    } finally {

        analyzeButton.disabled =
            false;

        analyzeButton.textContent =
            analyzeButton.dataset.oldText ||
            "ANALYZE";

    }

}


function findAIRoot(data) {

    if (!data) {
        return null;
    }


    if (
        data.ai &&
        typeof data.ai === "object"
    ) {

        return data.ai;

    }


    if (
        data.analysis &&
        typeof data.analysis === "object"
    ) {

        return data.analysis;

    }


    if (
        data.result &&
        typeof data.result === "object"
    ) {

        return data.result;

    }


    if (
        data.ai_result &&
        typeof data.ai_result === "object"
    ) {

        return data.ai_result;

    }


    if (
        data.summary ||
        data.key_points ||
        data.sentiment
    ) {

        return data;

    }


    return recursiveAI(
        data
    );

}


function recursiveAI(
    object,
    depth = 0
) {

    if (
        !object ||
        typeof object !== "object"
    ) {

        return null;

    }


    if (depth > 8) {
        return null;
    }


    if (
        object.en &&
        object.id
    ) {

        return object;

    }


    if (
        object.summary ||
        object.key_points ||
        object.sentiment ||
        object.main_issue
    ) {

        return object;

    }


    for (
        const key in object
    ) {

        if (
            !Object.prototype
                .hasOwnProperty
                .call(object, key)
        ) {
            continue;
        }


        const value =
            object[key];


        if (
            value &&
            typeof value === "object"
        ) {

            const result =
                recursiveAI(
                    value,
                    depth + 1
                );


            if (result) {
                return result;
            }

        }

    }


    return null;

}


function getLanguageData(
    root
) {

    if (
        !root ||
        typeof root !== "object"
    ) {

        return root;

    }


    if (
        root.en ||
        root.id
    ) {

        if (
            currentLanguage === "id" &&
            root.id
        ) {

            return root.id;

        }


        if (
            currentLanguage === "en" &&
            root.en
        ) {

            return root.en;

        }


        return (
            root.en ||
            root.id
        );

    }


    return root;

}


function field(
    object,
    keys
) {

    if (
        !object ||
        typeof object !== "object"
    ) {

        return null;

    }


    for (
        const key of keys
    ) {

        if (
            object[key] !== undefined &&
            object[key] !== null
        ) {

            return object[key];

        }

    }


    return null;

}


function renderVideoInfo(
    data
) {

    const box =
        document.getElementById(
            "videoInfo"
        );


    if (!box) {
        return;
    }


    const video =
        data.video ||
        {};


    const transcript =
        data.transcript ||
        {};


    const title =
        video.title ||
        transcript.title ||
        data.title ||
        "Untitled Video";


    const language =
        transcript.language ||
        video.language ||
        data.language ||
        "-";


    const id =
        video.id ||
        data.video_id ||
        extractYouTubeId(
            video.url ||
            data.url ||
            document.getElementById(
                "videoUrl"
            ).value
        );


    const url =
        video.url ||
        data.url ||
        document.getElementById(
            "videoUrl"
        ).value;


    box.innerHTML = `

        <div class="meta-grid">

            <div class="meta-item">

                <strong>
                    Title
                </strong>

                <span>
                    ${escapeHTML(
                        title
                    )}
                </span>

            </div>


            <div class="meta-item">

                <strong>
                    Video ID
                </strong>

                <span>
                    ${escapeHTML(
                        id || "-"
                    )}
                </span>

            </div>


            <div class="meta-item">

                <strong>
                    Language
                </strong>

                <span>
                    ${escapeHTML(
                        language
                    )}
                </span>

            </div>


            <div class="meta-item">

                <strong>
                    URL
                </strong>

                <span>
                    ${escapeHTML(
                        url
                    )}
                </span>

            </div>

        </div>

    `;

}


function renderAI(
    ai
) {

    const box =
        document.getElementById(
            "aiResult"
        );


    if (!box) {
        return;
    }


    if (
        !ai ||
        typeof ai !== "object"
    ) {

        box.innerHTML =
            `<div class="error-box">
                AI analysis data is empty.
            </div>`;

        return;

    }


    const summary =
        field(
            ai,
            [
                "summary",
                "executive_summary"
            ]
        );


    const sentiment =
        field(
            ai,
            [
                "sentiment"
            ]
        );


    const mainIssue =
        field(
            ai,
            [
                "main_issue",
                "mainIssue",
                "isu_utama"
            ]
        );


    const keyPoints =
        field(
            ai,
            [
                "key_points",
                "keyPoints"
            ]
        );


    const mediaAnalysis =
        field(
            ai,
            [
                "media_analysis",
                "mediaAnalysis",
                "analisis_media"
            ]
        );


    const risk =
        field(
            ai,
            [
                "communication_risk",
                "communicationRisk",
                "risiko_komunikasi"
            ]
        );


    const recommendations =
        field(
            ai,
            [
                "recommendations",
                "recommendation",
                "rekomendasi"
            ]
        );


    const critical =
        field(
            ai,
            [
                "critical_analysis",
                "criticalAnalysis"
            ]
        );


    const implications =
        field(
            ai,
            [
                "implications",
                "implication"
            ]
        );


    const takeaways =
        field(
            ai,
            [
                "takeaways",
                "key_takeaways"
            ]
        );


    box.innerHTML = `

        <div class="result-toolbar">

            <div class="toolbar-actions">

                <button
                    id="languageEn"
                    class="lang-btn ${
                        currentLanguage === "en"
                            ? "active"
                            : ""
                    }"
                    type="button">
                    EN
                </button>

                <button
                    id="languageId"
                    class="lang-btn ${
                        currentLanguage === "id"
                            ? "active"
                            : ""
                    }"
                    type="button">
                    ID
                </button>

                <button
                    id="exportPdfButton"
                    class="export-btn"
                    type="button">
                    Export PDF
                </button>

            </div>

        </div>


        <div class="analysis-grid">

            ${summaryCard(
                summary
            )}

            ${sentimentCard(
                sentiment
            )}

            ${issueCard(
                mainIssue
            )}

            ${keyPointCard(
                keyPoints
            )}

            ${mediaCard(
                mediaAnalysis
            )}

            ${riskCard(
                risk
            )}

            ${recommendationCard(
                recommendations
            )}

            ${textCard(
                "Critical Analysis",
                critical
            )}

            ${textCard(
                "Implications",
                implications
            )}

            ${textCard(
                "Takeaways",
                takeaways
            )}

        </div>

    `;

}


function summaryCard(
    value
) {

    if (!value) {
        return "";
    }


    return `

        <article class="
            analysis-card
            full-width
        ">

            <h3>
                Summary
            </h3>

            <div class="summary-text">

                ${renderValue(
                    value
                )}

            </div>

        </article>

    `;

}


function sentimentCard(
    value
) {

    if (!value) {
        return "";
    }


    let text =
        value;


    if (
        typeof value === "object"
    ) {

        text =
            value.label ||
            value.value ||
            value.result ||
            value.sentiment ||
            "";

    }


    text =
        String(text);


    const lower =
        text.toLowerCase();


    let css =
        "sentiment-neutral";


    if (
        lower.includes(
            "positive"
        ) ||
        lower.includes(
            "positif"
        )
    ) {

        css =
            "sentiment-positive";

    }


    if (
        lower.includes(
            "negative"
        ) ||
        lower.includes(
            "negatif"
        )
    ) {

        css =
            "sentiment-negative";

    }


    return `

        <article class="
            analysis-card
        ">

            <h3>
                Sentiment
            </h3>

            <span class="
                sentiment-badge
                ${css}
            ">

                ${escapeHTML(
                    text
                )}

            </span>

        </article>

    `;

}


function issueCard(
    value
) {

    if (!value) {
        return "";
    }


    return `

        <article class="
            analysis-card
        ">

            <h3>
                Isu Utama
            </h3>

            <div class="main-issue">

                ${renderValue(
                    value
                )}

            </div>

        </article>

    `;

}


function keyPointCard(
    value
) {

    if (!value) {
        return "";
    }


    const items =
        normalizeList(
            value
        );


    return `

        <article class="
            analysis-card
        ">

            <h3>
                Key Points
            </h3>

            <ul class="
                key-points-list
            ">

                ${items
                    .map(
                        item => `
                            <li>
                                ${renderValue(
                                    item
                                )}
                            </li>
                        `
                    )
                    .join("")}

            </ul>

        </article>

    `;

}


function renderActorEvidence(
    actors,
    evidence
) {

    const actorList =
        Array.isArray(actors)
            ? actors
            : [];


    const evidenceList =
        Array.isArray(evidence)
            ? evidence
            : [];


    if (!actorList.length) {
        return "";
    }


    function actorKey(
        value
    ) {

        return String(
            value || ""
        )
        .trim()
        .toLowerCase();

    }


    return `

        <ul class="actor-evidence-list">

            ${actorList
                .map(
                    (
                        actor,
                        index
                    ) => {

                        const actorText =
                            typeof actor ===
                                "object"
                                ? (
                                    actor.actor ||
                                    actor.name ||
                                    ""
                                )
                                : String(
                                    actor || ""
                                );


                        const match =
                            evidenceList.find(
                                item =>
                                    item &&
                                    actorKey(
                                        item.actor
                                    ) ===
                                    actorKey(
                                        actorText
                                    )
                            ) ||
                            evidenceList[index] ||
                            null;


                        let evidenceHTML =
                            "";


                        if (
                            match &&
                            typeof match ===
                                "object"
                        ) {

                            const timestamp =
                                match.evidence_timestamp ||
                                match.timestamp ||
                                "";


                            const quote =
                                match.evidence_quote ||
                                match.quote ||
                                "";


                            if (
                                timestamp ||
                                quote
                            ) {

                                evidenceHTML = `

                                    <div class="
                                        actor-evidence
                                    ">

                                        <strong>
                                            Evidence
                                        </strong>

                                        ${
                                            timestamp
                                                ? `
                                                    <span class="
                                                        actor-evidence-time
                                                    ">
                                                        [
                                                        ${escapeHTML(
                                                            timestamp
                                                        )}
                                                        ]
                                                    </span>
                                                `
                                                : ""
                                        }

                                        ${
                                            quote
                                                ? `
                                                    <span class="
                                                        actor-evidence-quote
                                                    ">
                                                        ${escapeHTML(
                                                            quote
                                                        )}
                                                    </span>
                                                `
                                                : ""
                                        }

                                    </div>

                                `;

                            }

                        }


                        return `

                            <li class="actor-item">

                                <div class="
                                    actor-main
                                ">
                                    ${escapeHTML(
                                        actorText
                                    )}
                                </div>

                                ${evidenceHTML}

                            </li>

                        `;

                    }
                )
                .join("")}

        </ul>

    `;

}


function mediaCard(
    value
) {

    if (!value) {
        return "";
    }


    if (
        typeof value !== "object" ||
        Array.isArray(value)
    ) {

        return `

            <article class="
                analysis-card
                full-width
            ">

                <h3>
                    Analisis Media
                </h3>

                ${renderValue(
                    value
                )}

            </article>

        `;

    }


    const items = [

        [
            "Angle Pemberitaan",
            [
                "angle",
                "news_angle",
                "media_angle"
            ]
        ],

        [
            "Aktor / OPD yang Mendapat Sorotan",
            [
                "actors",
                "actors_opd",
                "highlighted_actors",
                "aktor",
                "opd"
            ]
        ],

        [
            "Posisi Pemprov Jawa Tengah",
            [
                "pemprov_position",
                "government_position",
                "position_of_pemprov"
            ]
        ],

        [
            "Potensi Pembentukan Opini Publik",
            [
                "public_opinion",
                "public_opinion_potential"
            ]
        ],

        [
            "Key Message",
            [
                "key_message",
                "key_messages",
                "message"
            ]
        ]

    ];


    let html =
        "";


    items.forEach(
        function (item) {

            const valueFound =
                field(
                    value,
                    item[1]
                );


            if (
                valueFound !== null
            ) {

                const fieldName =
                    item[1].find(
                        key =>
                            Object.prototype
                                .hasOwnProperty
                                .call(
                                    value,
                                    key
                                )
                    );


                let renderedValue =
                    renderValue(
                        valueFound
                    );


                if (
                    fieldName ===
                        "highlighted_actors" ||
                    fieldName ===
                        "actors" ||
                    fieldName ===
                        "actors_opd"
                ) {

                    const evidence =
                        field(
                            value,
                            [
                                "actor_evidence",
                                "actors_evidence",
                                "evidence_actors"
                            ]
                        ) || [];


                    renderedValue =
                        renderActorEvidence(
                            valueFound,
                            evidence
                        );


                    if (!renderedValue) {

                        renderedValue =
                            renderValue(
                                valueFound
                            );

                    }

                }


                html += `

                    <div class="
                        media-analysis-item
                    ">

                        <strong>
                            ${item[0]}
                        </strong>

                        ${renderedValue}

                    </div>

                `;

            }

        }
    );


    if (!html) {

        html =
            renderObject(
                value
            );

    }


    return `

        <article class="
            analysis-card
            full-width
        ">

            <h3>
                Analisis Media
            </h3>

            <div class="
                media-analysis
            ">

                ${html}

            </div>

        </article>

    `;

}
/* ============================================================
   RISK
   ============================================================ */

function riskCard(
    value
) {

    if (!value) {
        return "";
    }


    let level =
        value;


    let reason =
        null;


    let escalation =
        null;


    if (
        typeof value === "object"
    ) {

        level =
            field(
                value,
                [
                    "level",
                    "risk_level",
                    "risk",
                    "tingkat"
                ]
            );


        reason =
            field(
                value,
                [
                    "reason",
                    "alasan"
                ]
            );


        escalation =
            field(
                value,
                [
                    "escalation",
                    "potential_escalation",
                    "potensi_eskalasi"
                ]
            );

    }


    const text =
        String(
            level || "-"
        );


    const lower =
        text.toLowerCase();


    let css =
        "risk-low";


    if (
        lower.includes(
            "high"
        ) ||
        lower.includes(
            "tinggi"
        )
    ) {

        css =
            "risk-high";

    } else if (
        lower.includes(
            "medium"
        ) ||
        lower.includes(
            "sedang"
        ) ||
        lower.includes(
            "moderate"
        )
    ) {

        css =
            "risk-medium";

    }


    return `

        <article class="
            analysis-card
        ">

            <h3>
                Risiko Komunikasi
            </h3>


            <span class="
                risk-badge
                ${css}
            ">

                ${escapeHTML(
                    text
                )}

            </span>


            ${
                reason
                    ? `
                        <div
                            style="
                                margin-top:10px;
                            "
                        >

                            <strong>
                                Alasan
                            </strong>

                            ${renderValue(
                                reason
                            )}

                        </div>
                    `
                    : ""
            }


            ${
                escalation
                    ? `
                        <div
                            style="
                                margin-top:10px;
                            "
                        >

                            <strong>
                                Potensi Eskalasi
                            </strong>

                            ${renderValue(
                                escalation
                            )}

                        </div>
                    `
                    : ""
            }

        </article>

    `;

}


/* ============================================================
   RECOMMENDATION
   ============================================================ */

function recommendationCard(
    value
) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "";

    }


    const typeLabels = {

        amplification:
            currentLanguage === "id"
                ? "Amplifikasi"
                : "Amplification",

        amplification_media:
            currentLanguage === "id"
                ? "Amplifikasi Media"
                : "Media Amplification",

        clarification:
            currentLanguage === "id"
                ? "Klarifikasi"
                : "Clarification",

        counter_narrative:
            currentLanguage === "id"
                ? "Counter Narrative"
                : "Counter Narrative",

        media_engagement:
            currentLanguage === "id"
                ? "Engagement Media"
                : "Media Engagement",

        monitoring:
            currentLanguage === "id"
                ? "Monitoring Lanjutan"
                : "Continued Monitoring",

        continued_monitoring:
            currentLanguage === "id"
                ? "Monitoring Lanjutan"
                : "Continued Monitoring",

        monitoring_lanjutan:
            currentLanguage === "id"
                ? "Monitoring Lanjutan"
                : "Continued Monitoring",

        follow_up_monitoring:
            currentLanguage === "id"
                ? "Monitoring Lanjutan"
                : "Continued Monitoring"

    };


    const labels =
        currentLanguage === "id"

            ? {
                type:
                    "Tipe",

                action:
                    "Tindakan",

                reason:
                    "Alasan",

                recommendation:
                    "Rekomendasi"
            }

            : {
                type:
                    "Type",

                action:
                    "Action",

                reason:
                    "Reason",

                recommendation:
                    "Recommendation"
            };


    function normalizeType(
        type
    ) {

        return String(
            type === null ||
            type === undefined
                ? ""
                : type
        )
            .trim()
            .toLowerCase()
            .replace(
                /\s+/g,
                "_"
            )
            .replace(
                /-/g,
                "_"
            );

    }


    function renderRecommendationItem(
        item
    ) {

        if (
            !item ||
            typeof item !== "object"
        ) {

            return "";

        }


        const rawType =
            item.type ||
            item.Type ||
            item.TYPE ||
            "";


        const type =
            normalizeType(
                rawType
            );


        const displayedType =
            typeLabels[type] ||
            String(
                rawType || "-"
            );


        const action =
            item.action ||
            item.Action ||
            item.ACTION ||
            item.aksi ||
            "";


        const reason =
            item.reason ||
            item.Reason ||
            item.REASON ||
            item.alasan ||
            "";


        return `

            <div class="
                recommendation-item
            ">

                <div class="
                    recommendation-field
                ">

                    <strong>
                        ${escapeHTML(
                            labels.type
                        )}
                    </strong>

                    <span>
                        ${escapeHTML(
                            displayedType
                        )}
                    </span>

                </div>


                ${
                    action
                        ? `
                            <div class="
                                recommendation-field
                            ">

                                <strong>
                                    ${escapeHTML(
                                        labels.action
                                    )}
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        valueToPlainText(
                                            action
                                        )
                                    )}
                                </span>

                            </div>
                        `
                        : ""
                }


                ${
                    reason
                        ? `
                            <div class="
                                recommendation-field
                            ">

                                <strong>
                                    ${escapeHTML(
                                        labels.reason
                                    )}
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        valueToPlainText(
                                            reason
                                        )
                                    )}
                                </span>

                            </div>
                        `
                        : ""
                }

            </div>

        `;

    }


    let html =
        "";


    if (
        Array.isArray(
            value
        )
    ) {

        html =
            value
                .map(
                    renderRecommendationItem
                )
                .join("");

    } else if (
        typeof value === "object"
    ) {

        html =
            renderRecommendationItem(
                value
            );

    }


    if (!html) {

        const legacyItems = [

            [
                "Amplifikasi",
                [
                    "amplification",
                    "amplifikasi"
                ]
            ],

            [
                "Klarifikasi",
                [
                    "clarification",
                    "klarifikasi"
                ]
            ],

            [
                "Counter Narrative",
                [
                    "counter_narrative",
                    "counterNarrative"
                ]
            ],

            [
                "Engagement Media",
                [
                    "media_engagement",
                    "engagement_media"
                ]
            ],

            [
                "Monitoring Lanjutan",
                [
                    "monitoring",
                    "continued_monitoring",
                    "monitoring_lanjutan",
                    "follow_up_monitoring"
                ]
            ]

        ];


        legacyItems.forEach(
            function (
                item
            ) {

                const found =
                    field(
                        value,
                        item[1]
                    );


                if (
                    found !== null &&
                    found !== undefined
                ) {

                    html += `

                        <div class="
                            recommendation-item
                        ">

                            <div class="
                                recommendation-field
                            ">

                                <strong>
                                    ${escapeHTML(
                                        labels.recommendation
                                    )}
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        currentLanguage === "id"
                                            ? item[0]
                                            : (
                                                item[0] ===
                                                    "Amplifikasi"

                                                    ? "Amplification"

                                                    : item[0]
                                            )
                                    )}
                                </span>

                            </div>


                            <div class="
                                recommendation-field
                            ">

                                <span>
                                    ${escapeHTML(
                                        valueToPlainText(
                                            found
                                        )
                                    )}
                                </span>

                            </div>

                        </div>

                    `;

                }

            }
        );

    }


    if (!html) {

        html =
            renderObject(
                value
            );

    }


    return `

        <article class="
            analysis-card
            full-width
        ">

            <h3>
                ${escapeHTML(
                    labels.recommendation
                )}
            </h3>


            <div class="
                recommendations
            ">

                ${html}

            </div>

        </article>

    `;

}


/* ============================================================
   TEXT CARD
   ============================================================ */

function textCard(
    title,
    value
) {

    if (!value) {
        return "";
    }


    return `

        <article class="
            analysis-card
        ">

            <h3>
                ${escapeHTML(
                    title
                )}
            </h3>


            ${renderValue(
                value
            )}

        </article>

    `;

}


/* ============================================================
   RENDER VALUE
   ============================================================ */

function renderValue(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";

    }


    if (
        Array.isArray(
            value
        )
    ) {

        return `

            <ul>

                ${value
                    .map(
                        item => `

                            <li>

                                ${renderValue(
                                    item
                                )}

                            </li>

                        `
                    )
                    .join("")}

            </ul>

        `;

    }


    if (
        typeof value === "object"
    ) {

        return renderObject(
            value
        );

    }


    const text =
        String(
            value
        );


    if (
        /^Inference:/i.test(
            text
        )
    ) {

        return `

            <div class="
                inference
            ">

                <span class="
                    inference-label
                ">

                    Inference:

                </span>


                ${escapeHTML(
                    text.replace(
                        /^Inference:\s*/i,
                        ""
                    )
                )}

            </div>

        `;

    }


    return escapeHTML(
        text
    ).replace(
        /\n/g,
        "<br>"
    );

}


/* ============================================================
   VALUE TO PLAIN TEXT
   ============================================================ */

function valueToPlainText(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";

    }


    if (
        Array.isArray(
            value
        )
    ) {

        return value
            .map(
                item =>
                    valueToPlainText(
                        item
                    )
            )
            .join("\n");

    }


    if (
        typeof value === "object"
    ) {

        return Object.entries(
            value
        )
        .map(
            function ([
                key,
                item
            ]) {

                return (
                    formatLabel(
                        key
                    ) +
                    ": " +
                    valueToPlainText(
                        item
                    )
                );

            }
        )
        .join("\n");

    }


    return String(
        value
    );

}


/* ============================================================
   RENDER OBJECT
   ============================================================ */

function renderObject(
    object
) {

    if (
        !object ||
        typeof object !== "object"
    ) {

        return "";

    }


    let html =
        "";


    Object.entries(
        object
    ).forEach(
        function ([
            key,
            value
        ]) {

            html += `

                <div class="
                    media-analysis-item
                ">

                    <strong>
                        ${escapeHTML(
                            formatLabel(
                                key
                            )
                        )}
                    </strong>


                    ${renderValue(
                        value
                    )}

                </div>

            `;

        }
    );


    return html;

}


/* ============================================================
   NORMALIZE LIST
   ============================================================ */

function normalizeList(
    value
) {

    if (
        Array.isArray(
            value
        )
    ) {

        return value;

    }


    if (
        typeof value === "object" &&
        value !== null
    ) {

        const list =
            value.items ||
            value.points ||
            value.list ||
            value.values;


        if (
            Array.isArray(
                list
            )
        ) {

            return list;

        }

    }


    if (
        typeof value === "string"
    ) {

        return value
            .split(
                "\n"
            )
            .map(
                item =>
                    item
                        .replace(
                            /^\s*[-•*]\s*/,
                            ""
                        )
                        .trim()
            )
            .filter(
                Boolean
            );

    }


    return [
        value
    ];

}


/* ============================================================
   FORMAT LABEL
   ============================================================ */

function formatLabel(
    value
) {

    return String(
        value
    )
        .replace(
            /_/g,
            " "
        )
        .replace(
            /([a-z])([A-Z])/g,
            "$1 $2"
        )
        .replace(
            /\b\w/g,
            function (
                char
            ) {

                return char.toUpperCase();

            }
        );

}
/* ============================================================
   YOUTUBE URL HELPERS
   ============================================================ */

function isYouTubeUrl(
    value
) {

    return isValidYouTubeUrl(
        value
    );

}


function extractYouTubeId(
    value
) {

    if (!value) {
        return "";
    }


    try {

        const url =
            new URL(
                value.trim()
            );


        const hostname =
            url.hostname.toLowerCase();


        if (
            hostname ===
                "youtu.be" ||
            hostname ===
                "www.youtu.be"
        ) {

            return (
                url.pathname
                    .replace(
                        /^\//,
                        ""
                    )
                    .split(
                        "/"
                    )[0] ||
                ""
            );

        }


        if (
            hostname ===
                "youtube.com" ||
            hostname ===
                "www.youtube.com" ||
            hostname ===
                "m.youtube.com"
        ) {

            const watchId =
                url.searchParams.get(
                    "v"
                );


            if (watchId) {
                return watchId;
            }


            const parts =
                url.pathname
                    .split("/")
                    .filter(
                        Boolean
                    );


            if (
                parts[0] ===
                    "shorts" &&
                parts[1]
            ) {

                return parts[1];

            }


            if (
                parts[0] ===
                    "embed" &&
                parts[1]
            ) {

                return parts[1];

            }

        }

    } catch (
        error
    ) {

        console.warn(
            "Unable to extract YouTube ID.",
            error
        );

    }


    return "";

}


/* ============================================================
   STATUS
   ============================================================ */

function setStatus(
    element,
    message,
    type = ""
) {

    if (!element) {
        return;
    }


    element.className =
        "status";


    if (type) {

        element.classList.add(
            type
        );

    }


    element.textContent =
        message || "";

}


/* ============================================================
   ERROR HANDLING
   ============================================================ */

function getErrorMessage(
    data,
    status
) {

    /* --------------------------------------------------------
       CLOUDFLARE WORKERS AI DAILY QUOTA
       -------------------------------------------------------- */

    if (
        data &&
        data.error_type ===
            "ai_quota_exhausted"
    ) {

        const quota =
            data.quota || {};

        if (
            quota.next_reset_utc
        ) {

            const resetDate =
                new Date(
                    quota.next_reset_utc
                );

            const localReset =
                resetDate.toLocaleString(
                    undefined,
                    {
                        dateStyle: "medium",
                        timeStyle: "short"
                    }
                );

            return (
                "AI quota sementara habis. " +
                "Sistem akan otomatis mencoba kembali setelah reset Cloudflare pada " +
                localReset +
                "."
            );

        }

        return (
            "AI quota sementara habis. " +
            "Sistem akan otomatis mencoba kembali setelah reset harian Cloudflare."
        );

    }


    /* --------------------------------------------------------
       CLOUDFLARE QUOTA ERROR DIRECT
       -------------------------------------------------------- */

    const rawError =
        data &&
        (
            data.error ||
            data.detail ||
            data.message ||
            ""
        );


    const errorText =
        String(
            rawError
        ).toLowerCase();


    if (
        errorText.includes("4006") ||
        errorText.includes("3036") ||
        errorText.includes("10,000 neurons") ||
        errorText.includes("10000 neurons") ||
        errorText.includes("daily free allocation") ||
        errorText.includes("account limited")
    ) {

        return (
            "AI quota Cloudflare sedang mencapai batas harian. " +
            "Aplikasi akan menunggu reset quota harian Cloudflare " +
            "dan dapat digunakan kembali setelah reset."
        );

    }


    /* --------------------------------------------------------
       STANDARD SERVER ERROR
       -------------------------------------------------------- */

    if (
        data &&
        typeof data.detail ===
            "string"
    ) {

        return data.detail;

    }


    if (
        data &&
        typeof data.error ===
            "string"
    ) {

        return data.error;

    }


    if (
        data &&
        typeof data.message ===
            "string"
    ) {

        return data.message;

    }


    return (
        "Server error (" +
        status +
        ")."
    );

}

/* ============================================================
   ESCAPE HTML
   ============================================================ */

function escapeHTML(
    value
) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";

    }


    return String(
        value
    )
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}


/* ============================================================
   TRANSCRIPT RENDERING
   ============================================================ */

function renderTranscript(
    data
) {

    const box =
        document.getElementById(
            "transcript"
        );


    if (!box) {
        return;
    }


    const transcriptObject =
        data &&
        data.transcript
            ? data.transcript
            : data || {};


    const segments =
        transcriptObject.transcript ||
        transcriptObject.segments ||
        data.transcript_segments ||
        [];


    if (
        !Array.isArray(
            segments
        ) ||
        !segments.length
    ) {

        box.innerHTML =
            `<div class="empty-state">
                Transcript tidak tersedia.
            </div>`;

        return;

    }


    box.innerHTML = `

        <div class="
            transcript-list
        ">

            ${segments
                .map(
                    function (
                        segment
                    ) {

                        const start =
                            segment.start ??
                            segment.timestamp ??
                            segment.time ??
                            0;


                        const text =
                            segment.text ||
                            segment.content ||
                            "";


                        return `

                            <div class="
                                transcript-row
                            ">

                                <span class="
                                    transcript-time
                                ">

                                    ${escapeHTML(
                                        formatTimestamp(
                                            start
                                        )
                                    )}

                                </span>


                                <span class="
                                    transcript-text
                                ">

                                    ${escapeHTML(
                                        text
                                    )}

                                </span>

                            </div>

                        `;

                    }
                )
                .join("")}

        </div>

    `;

}


/* ============================================================
   TIMESTAMP
   ============================================================ */

function formatTimestamp(
    seconds
) {

    let totalSeconds =
        Number(
            seconds
        );


    if (
        !Number.isFinite(
            totalSeconds
        )
    ) {

        totalSeconds =
            0;

    }


    totalSeconds =
        Math.max(
            0,
            Math.floor(
                totalSeconds
            )
        );


    const hours =
        Math.floor(
            totalSeconds /
            3600
        );


    const minutes =
        Math.floor(
            (
                totalSeconds %
                3600
            ) /
            60
        );


    const secs =
        totalSeconds %
        60;


    if (
        hours > 0
    ) {

        return [
            String(
                hours
            ).padStart(
                2,
                "0"
            ),

            String(
                minutes
            ).padStart(
                2,
                "0"
            ),

            String(
                secs
            ).padStart(
                2,
                "0"
            )

        ].join(":");

    }


    return [

        String(
            minutes
        ).padStart(
            2,
            "0"
        ),

        String(
            secs
        ).padStart(
            2,
            "0"
        )

    ].join(":");

}


/* ============================================================
   LANGUAGE SWITCHING
   ============================================================ */

document.addEventListener(
    "click",
    function (
        event
    ) {

        const button =
            event.target.closest(
                "[data-language]"
            );


        if (!button) {
            return;
        }


        const language =
            button.dataset.language;


        if (
            language !== "en" &&
            language !== "id"
        ) {

            return;

        }


        switchLanguage(
            language
        );

    }
);


function switchLanguage(
    language
) {

    if (
        !currentAIRoot
    ) {

        return;

    }


    if (
        language !== "en" &&
        language !== "id"
    ) {

        return;

    }


    currentLanguage =
        language;


    const ai =
        getLanguageData(
            currentAIRoot
        );


    renderAI(
        ai
    );

}


/* ============================================================
   FALLBACK LANGUAGE BUTTON SUPPORT
   ============================================================ */

document.addEventListener(
    "click",
    function (
        event
    ) {

        const target =
            event.target;


        if (
            target &&
            target.id ===
                "languageEn"
        ) {

            switchLanguage(
                "en"
            );

            return;

        }


        if (
            target &&
            target.id ===
                "languageId"
        ) {

            switchLanguage(
                "id"
            );

            return;

        }

    }
);


/* ============================================================
   EXPORT PDF
   ============================================================ */

document.addEventListener(
    "click",
    function (
        event
    ) {

        const button =
            event.target.closest(
                "#exportPdfButton"
            );


        if (!button) {
            return;
        }


        exportPDF();

    }
);


async function exportPDF() {

    if (
        !currentData ||
        !currentAIRoot
    ) {

        alert(
            "Tidak ada hasil analisis untuk diekspor."
        );

        return;

    }


    if (
        typeof window.jspdf ===
            "undefined"
    ) {

        alert(
            "PDF library belum tersedia. Silakan refresh halaman."
        );

        return;

    }


    const {
        jsPDF
    } =
        window.jspdf;


    const doc =
        new jsPDF({
            unit: "mm",
            format: "a4"
        });


    const ai =
        getLanguageData(
            currentAIRoot
        );


    const video =
        currentData.video ||
        {};


    const transcriptObject =
        currentData.transcript ||
        {};


    const title =
        video.title ||
        transcriptObject.title ||
        "AI Video Analysis";


    let y =
        18;


    const margin =
        15;


    const pageWidth =
        doc.internal.pageSize
            .getWidth();


    const usableWidth =
        pageWidth -
        margin * 2;


    function addPageIfNeeded(
        height = 8
    ) {

        const pageHeight =
            doc.internal.pageSize
                .getHeight();


        if (
            y + height >
            pageHeight - 15
        ) {

            doc.addPage();

            y = 18;

        }

    }


    function addTitle(
        text
    ) {

        addPageIfNeeded(
            12
        );


        doc.setFontSize(
            16
        );


        doc.setFont(
            "helvetica",
            "bold"
        );


        const lines =
            doc.splitTextToSize(
                String(
                    text || ""
                ),
                usableWidth
            );


        doc.text(
            lines,
            margin,
            y
        );


        y +=
            lines.length *
            7 +
            5;

    }


    function addHeading(
        text
    ) {

        addPageIfNeeded(
            12
        );


        doc.setFontSize(
            12
        );


        doc.setFont(
            "helvetica",
            "bold"
        );


        doc.text(
            String(
                text || ""
            ),
            margin,
            y
        );


        y += 7;

    }


    function addText(
        text,
        size = 9
    ) {

        if (
            text === null ||
            text === undefined
        ) {

            return;

        }


        const plain =
            valueToPlainText(
                text
            );


        if (
            !plain.trim()
        ) {

            return;

        }


        doc.setFontSize(
            size
        );


        doc.setFont(
            "helvetica",
            "normal"
        );


        const lines =
            doc.splitTextToSize(
                plain,
                usableWidth
            );


        const lineHeight =
            size === 9
                ? 4.8
                : 5.5;


        for (
            const line of
                lines
        ) {

            addPageIfNeeded(
                lineHeight
            );


            doc.text(
                line,
                margin,
                y
            );


            y +=
                lineHeight;

        }


        y += 2;

    }


    addTitle(
        "AI Video Analysis"
    );


    addText(
        title,
        11
    );


    addHeading(
        "Video Information"
    );


    addText(
        "Video ID: " +
        (
            video.id ||
            extractYouTubeId(
                video.url ||
                ""
            ) ||
            "-"
        )
    );


    addText(
        "Language: " +
        (
            transcriptObject.language ||
            "-"
        )
    );


    addText(
        "URL: " +
        (
            video.url ||
            "-"
        )
    );


    const sections = [

        [
            "Summary",
            field(
                ai,
                [
                    "summary",
                    "executive_summary"
                ]
            )
        ],

        [
            "Sentiment",
            field(
                ai,
                [
                    "sentiment"
                ]
            )
        ],

        [
            "Isu Utama",
            field(
                ai,
                [
                    "main_issue",
                    "mainIssue",
                    "isu_utama"
                ]
            )
        ],

        [
            "Key Points",
            field(
                ai,
                [
                    "key_points",
                    "keyPoints"
                ]
            )
        ],

        [
            "Analisis Media",
            field(
                ai,
                [
                    "media_analysis",
                    "mediaAnalysis",
                    "analisis_media"
                ]
            )
        ],

        [
            "Risiko Komunikasi",
            field(
                ai,
                [
                    "communication_risk",
                    "communicationRisk",
                    "risiko_komunikasi"
                ]
            )
        ],

        [
            currentLanguage === "id"
                ? "Rekomendasi"
                : "Recommendations",

            field(
                ai,
                [
                    "recommendations",
                    "recommendation",
                    "rekomendasi"
                ]
            )
        ],

        [
            "Critical Analysis",
            field(
                ai,
                [
                    "critical_analysis",
                    "criticalAnalysis"
                ]
            )
        ],

        [
            "Implications",
            field(
                ai,
                [
                    "implications",
                    "implication"
                ]
            )
        ],

        [
            "Takeaways",
            field(
                ai,
                [
                    "takeaways",
                    "key_takeaways"
                ]
            )
        ]

    ];


    sections.forEach(
        function ([
            heading,
            content
        ]) {

            if (
                content === null ||
                content === undefined ||
                content === ""
            ) {

                return;

            }


            addHeading(
                heading
            );


            addText(
                content
            );

        }
    );


    const filename =
        sanitizeFilename(
            title
        ) +
        "_" +
        currentLanguage +
        "_AI_Analysis.pdf";


    doc.save(
        filename
    );

}


/* ============================================================
   SANITIZE FILE NAME
   ============================================================ */

function sanitizeFilename(
    value
) {

    return String(
        value ||
        "video"
    )
        .replace(
            /[<>:"/\\|?*\x00-\x1F]/g,
            ""
        )
        .replace(
            /\s+/g,
            "_"
        )
        .substring(
            0,
            120
        );

}


/* ============================================================
   INITIAL STATE
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const videoUrl =
            document.getElementById(
                "videoUrl"
            );


        if (videoUrl) {

            videoUrl.focus();

        }


        const aiResult =
            document.getElementById(
                "aiResult"
            );


        if (aiResult) {

            aiResult.addEventListener(
                "click",
                function (
                    event
                ) {

                    const languageButton =
                        event.target.closest(
                            ".lang-btn"
                        );


                    if (
                        !languageButton
                    ) {

                        return;

                    }


                    const language =
                        languageButton.dataset
                            .language;


                    if (
                        language === "en" ||
                        language === "id"
                    ) {

                        switchLanguage(
                            language
                        );

                    }

                }
            );

        }

    }
);

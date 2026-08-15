let systemAvailabilityChart = null;
let fuelAvailabilityChart = null;
let fuelShareChart = null;
let fuelRevisionChart = null;
let revisionDirectionChart = null;

/* =========================================================
   DASHBOARD VALUE LABELS
   ========================================================= */

const dashboardValueLabelsPlugin = {
    id: "dashboardValueLabels",

    afterDatasetsDraw(chart) {
        const canvasId =
            chart.canvas.id;

        const supportedCharts = [
            "system-availability-chart",
            "fuel-availability-chart",
            "fuel-revision-chart"
        ];

        if (!supportedCharts.includes(canvasId)) {
            return;
        }

        const ctx =
            chart.ctx;

        const dataset =
            chart.data.datasets[0];

        const meta =
            chart.getDatasetMeta(0);

        if (!dataset || !meta) {
            return;
        }

        ctx.save();


        /* =====================================================
           SYSTEM AVAILABILITY POINT LABELS
           ===================================================== */

        if (
            canvasId ===
            "system-availability-chart"
        ) {
            meta.data.forEach(
                (point, index) => {
                    const value =
                        Number(
                            dataset.data[index]
                        );

                    const label =
                        `${formatNumber(value)} MW`;

                    ctx.font =
                        "700 9px sans-serif";

                    const textWidth =
                        ctx.measureText(label).width;

                    const paddingX =
                        4;

                    const boxHeight =
                        15;

                    let labelY =
                        point.y - 15;

                    /*
                     * If the point is close to the top
                     * of the chart, move its label below.
                     */
                    if (
                        labelY
                        <
                        chart.chartArea.top + 10
                    ) {
                        labelY =
                            point.y + 17;
                    }

                    let boxLeft =
                        point.x
                        - textWidth / 2
                        - paddingX;

                    const boxWidth =
                        textWidth
                        + paddingX * 2;

                    /*
                     * Keep first and last labels inside
                     * the plotting area.
                     */
                    boxLeft =
                        Math.max(
                            chart.chartArea.left,
                            Math.min(
                                boxLeft,
                                chart.chartArea.right
                                - boxWidth
                            )
                        );

                    ctx.fillStyle =
                        "rgba(255, 255, 255, 0.90)";

                    ctx.fillRect(
                        boxLeft,
                        labelY
                        - boxHeight / 2,
                        boxWidth,
                        boxHeight
                    );

                    ctx.fillStyle =
                        "#334155";

                    ctx.textAlign =
                        "center";

                    ctx.textBaseline =
                        "middle";

                    ctx.fillText(
                        label,
                        boxLeft
                        + boxWidth / 2,
                        labelY
                    );
                }
            );

            ctx.restore();
            return;
        }


        /* =====================================================
           HORIZONTAL BAR VALUE LABELS
           ===================================================== */

        meta.data.forEach(
            (bar, index) => {
                const value =
                    Number(
                        dataset.data[index]
                    );

                const isRevision =
                    canvasId ===
                    "fuel-revision-chart";

                const sign =
                    (
                        isRevision
                        && value > 0
                    )
                        ? "+"
                        : "";

                const label =
                    `${sign}${formatNumber(value)} MW`;

                ctx.font =
                    "700 9px sans-serif";

                const textWidth =
                    ctx.measureText(label).width;

                const barWidth =
                    Math.abs(
                        bar.x - bar.base
                    );

                const positive =
                    value >= 0;

                /*
                 * Large bars get their labels inside.
                 * Small bars get their labels immediately
                 * outside so the number remains readable.
                 */
                const placeInside =
                    barWidth
                    >
                    textWidth + 18;

                let labelX;

                if (placeInside) {
                    ctx.fillStyle =
                        "#ffffff";

                    if (positive) {
                        labelX =
                            bar.x - 7;

                        ctx.textAlign =
                            "right";
                    }
                    else {
                        labelX =
                            bar.x + 7;

                        ctx.textAlign =
                            "left";
                    }
                }
                else {
                    ctx.fillStyle =
                        "#334155";

                    if (positive) {
                        labelX =
                            bar.x + 7;

                        ctx.textAlign =
                            "left";

                        if (
                            labelX
                            + textWidth
                            >
                            chart.chartArea.right
                        ) {
                            labelX =
                                chart.chartArea.right
                                - 3;

                            ctx.textAlign =
                                "right";
                        }
                    }
                    else {
                        labelX =
                            bar.x - 7;

                        ctx.textAlign =
                            "right";

                        if (
                            labelX
                            - textWidth
                            <
                            chart.chartArea.left
                        ) {
                            labelX =
                                chart.chartArea.left
                                + 3;

                            ctx.textAlign =
                                "left";
                        }
                    }
                }

                ctx.textBaseline =
                    "middle";

                ctx.fillText(
                    label,
                    labelX,
                    bar.y
                );
            }
        );

        ctx.restore();
    }
};


if (typeof Chart !== "undefined") {
    Chart.register(
        dashboardValueLabelsPlugin
    );
}




/* =========================================================
   FORMATTERS
   ========================================================= */

function formatNumber(value) {
    if (value === null || value === undefined) {
        return "N/A";
    }

    return new Intl.NumberFormat(
        "en-GB",
        {
            maximumFractionDigits: 0
        }
    ).format(value);
}


function normaliseUtcTimestamp(value) {
    if (!value) {
        return value;
    }

    const hasTimezone =
        /Z$|[+-]\d{2}:\d{2}$/.test(value);

    return hasTimezone
        ? value
        : `${value}Z`;
}


function formatPublication(value) {
    if (!value) {
        return "N/A";
    }

    const date =
        new Date(
            normaliseUtcTimestamp(value)
        );

    return new Intl.DateTimeFormat(
        "en-GB",
        {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "UTC",
            timeZoneName: "short"
        }
    ).format(date);
}


function formatForecastDate(value) {
    const date =
        new Date(
            normaliseUtcTimestamp(value)
        );

    return new Intl.DateTimeFormat(
        "en-GB",
        {
            day: "2-digit",
            month: "short",
            timeZone: "UTC"
        }
    ).format(date);
}


function setText(id, value) {
    const element =
        document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}


/* =========================================================
   KPI DATA
   ========================================================= */

async function loadKPIs() {
    const status =
        document.getElementById(
            "refresh-status"
        );

    try {
        if (status) {
            status.textContent =
                "Refreshing live Databricks data...";
        }

        const response =
            await fetch(
                "/api/kpis",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const data =
            await response.json();

        const publication =
            formatPublication(
                data.latest_publication
            );

        const systemMW =
            `${formatNumber(
                data.system_available_mw
            )} MW`;


        setText(
            "latest-publication",
            publication
        );

        setText(
            "system-available-mw",
            systemMW
        );

        setText(
            "publications-loaded",
            formatNumber(
                data.publications_loaded
            )
        );

        setText(
            "fuel-types-tracked",
            formatNumber(
                data.fuel_types_tracked
            )
        );


        setText(
            "hero-publication",
            publication
        );

        setText(
            "hero-system-mw",
            systemMW
        );

        setText(
            "current-system-mw",
            systemMW
        );

        setText(
            "current-publication",
            publication
        );


        if (status) {
            const now =
                new Intl.DateTimeFormat(
                    "en-GB",
                    {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit"
                    }
                ).format(
                    new Date()
                );

            status.textContent =
                `Live · refreshed ${now}`;
        }
    }
    catch (error) {
        console.error(
            "Dashboard KPI refresh failed:",
            error
        );

        if (status) {
            status.textContent =
                "Live data temporarily unavailable";
        }
    }
}


/* =========================================================
   SYSTEM AVAILABILITY CHART
   ========================================================= */

async function loadSystemAvailability() {
    const canvas =
        document.getElementById(
            "system-availability-chart"
        );

    const message =
        document.getElementById(
            "system-chart-message"
        );

    if (!canvas) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/system-availability",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const rows =
            await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            throw new Error(
                "No system availability data returned"
            );
        }


        const labels =
            rows.map(
                row =>
                    formatForecastDate(
                        row.forecast_date
                    )
            );


        const values =
            rows.map(
                row =>
                    row.available_mw
            );


        if (message) {
            message.classList.add(
                "hidden"
            );
        }


        if (systemAvailabilityChart) {
            systemAvailabilityChart.destroy();
        }


        const context =
            canvas.getContext("2d");


        const gradient =
            context.createLinearGradient(
                0,
                0,
                0,
                380
            );

        gradient.addColorStop(
            0,
            "rgba(37, 137, 255, 0.24)"
        );

        gradient.addColorStop(
            0.6,
            "rgba(22, 184, 166, 0.08)"
        );

        gradient.addColorStop(
            1,
            "rgba(255, 255, 255, 0)"
        );


        systemAvailabilityChart =
            new Chart(
                context,
                {
                    type: "line",

                    data: {
                        labels: labels,

                        datasets: [
                            {
                                label:
                                    "Available MW",

                                data:
                                    values,

                                borderColor:
                                    "#2589ff",

                                backgroundColor:
                                    gradient,

                                borderWidth:
                                    3,

                                fill:
                                    true,

                                tension:
                                    0.32,

                                pointRadius:
                                    4,

                                pointHoverRadius:
                                    7,

                                pointBackgroundColor:
                                    "#ffffff",

                                pointBorderColor:
                                    "#2589ff",

                                pointBorderWidth:
                                    2
                            }
                        ]
                    },


                    options: {
                        responsive:
                            false,

                        maintainAspectRatio:
                            false,

                        interaction: {
                            intersect:
                                false,

                            mode:
                                "index"
                        },


                        plugins: {
                            legend: {
                                display:
                                    false
                            },

                            tooltip: {
                                displayColors:
                                    false,

                                padding:
                                    12,

                                callbacks: {
                                    label:
                                        function(context) {
                                            return (
                                                `${formatNumber(
                                                    context.raw
                                                )} MW available`
                                            );
                                        }
                                }
                            }
                        },


                        scales: {
                            x: {
                                grid: {
                                    display:
                                        false
                                },

                                border: {
                                    display:
                                        false
                                },

                                ticks: {
                                    color:
                                        "#69788d",

                                    font: {
                                        size:
                                            11
                                    },

                                    maxRotation:
                                        0,

                                    autoSkip:
                                        true,

                                    maxTicksLimit:
                                        8
                                }
                            },


                            y: {
                                suggestedMin:
                                    40000,

                                grid: {
                                    color:
                                        "rgba(148, 163, 184, 0.15)"
                                },

                                border: {
                                    display:
                                        false
                                },

                                ticks: {
                                    color:
                                        "#69788d",

                                    padding:
                                        8,

                                    callback:
                                        function(value) {
                                            return (
                                                `${Math.round(
                                                    value / 1000
                                                )}k`
                                            );
                                        }
                                },

                                title: {
                                    display:
                                        true,

                                    text:
                                        "Available MW",

                                    color:
                                        "#69788d",

                                    font: {
                                        size:
                                            11,
                                        weight:
                                            "600"
                                    }
                                }
                            }
                        }
                    }
                }
            );
    }
    catch (error) {
        console.error(
            "System availability chart failed:",
            error
        );

        if (message) {
            message.textContent =
                "Unable to load live forecast data";
        }
    }
}



/* =========================================================
   FUEL AVAILABILITY CHART
   ========================================================= */

async function loadFuelAvailability() {
    const canvas =
        document.getElementById(
            "fuel-availability-chart"
        );

    const message =
        document.getElementById(
            "fuel-chart-message"
        );

    if (!canvas) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/fuel-availability",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const rows =
            await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            throw new Error(
                "No fuel availability data returned"
            );
        }

        const labels =
            rows.map(
                row => row.fuel_label || row.fuel_type
            );

        const values =
            rows.map(
                row => row.available_mw
            );

        if (message) {
            message.classList.add("hidden");
        }

        if (fuelAvailabilityChart) {
            fuelAvailabilityChart.destroy();
        }

        const context =
            canvas.getContext("2d");

        fuelAvailabilityChart =
            new Chart(
                context,
                {
                    type: "bar",

                    data: {
                        labels: labels,

                        datasets: [
                            {
                                label:
                                    "Available MW",

                                data:
                                    values,

                                backgroundColor:
                                    "rgba(37, 137, 255, 0.78)",

                                borderColor:
                                    "#2589ff",

                                borderWidth:
                                    1,

                                borderRadius:
                                    5,

                                barPercentage:
                                    0.74,

                                categoryPercentage:
                                    0.86
                            }
                        ]
                    },

                    options: {
                        responsive:
                            false,

                        maintainAspectRatio:
                            false,

                        indexAxis:
                            "y",

                        interaction: {
                            intersect:
                                false,

                            mode:
                                "nearest"
                        },

                        plugins: {
                            legend: {
                                display:
                                    false
                            },

                            tooltip: {
                                displayColors:
                                    false,

                                padding:
                                    12,

                                callbacks: {
                                    label:
                                        function(context) {
                                            return (
                                                `${formatNumber(
                                                    context.raw
                                                )} MW available`
                                            );
                                        }
                                }
                            }
                        },

                        scales: {
                            y: {
                                grid: {
                                    display:
                                        false
                                },

                                border: {
                                    display:
                                        false
                                },

                                ticks: {
                                    color:
                                        "#52647b",

                                    font: {
                                        size:
                                            10,
                                        weight:
                                            "600"
                                    }
                                }
                            },

                            x: {
                                beginAtZero:
                                    true,

                                border: {
                                    display:
                                        false
                                },

                                grid: {
                                    color:
                                        "rgba(148, 163, 184, 0.14)"
                                },

                                ticks: {
                                    color:
                                        "#69788d",

                                    callback:
                                        function(value) {
                                            if (value >= 1000) {
                                                return (
                                                    `${value / 1000}k`
                                                );
                                            }

                                            return value;
                                        }
                                },

                                title: {
                                    display:
                                        true,

                                    text:
                                        "Available MW",

                                    color:
                                        "#69788d",

                                    font: {
                                        size:
                                            11,
                                        weight:
                                            "600"
                                    }
                                }
                            }
                        }
                    }
                }
            );
    }
    catch (error) {
        console.error(
            "Fuel availability chart failed:",
            error
        );

        if (message) {
            message.textContent =
                "Unable to load fuel availability";
        }
    }
}



/* =========================================================
   CAPACITY MIX SHARE
   ========================================================= */

async function loadFuelShare() {
    const canvas =
        document.getElementById(
            "fuel-share-chart"
        );

    const message =
        document.getElementById(
            "fuel-share-message"
        );

    if (!canvas) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/fuel-availability",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const rows =
            await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            throw new Error(
                "No fuel availability data returned"
            );
        }

        const SHORT_LABELS = {
            "CCGT": "CCGT",
            "NUCLEAR": "Nuclear",
            "WIND": "Wind",
            "BIOMASS": "Biomass",
            "OTHER": "Other",
            "PS": "Pumped Storage",
            "NPSHYD": "Hydro",
            "OCGT": "OCGT",
            "INTFR": "France",
            "INTIFA2": "IFA2",
            "INTELEC": "ElecLink",
            "INTIRL": "Ireland",
            "INTEW": "East-West",
            "INTGRNL": "Greenlink",
            "INTNED": "Netherlands",
            "INTNEM": "Belgium",
            "INTNSL": "Norway",
            "INTVKL": "Denmark"
        };

        const sortedRows =
            [...rows].sort(
                (a, b) =>
                    Number(b.available_mw)
                    - Number(a.available_mw)
            );

        const primaryRows =
            sortedRows.slice(0, 7);

        const remainingRows =
            sortedRows.slice(7);

        const chartRows =
            primaryRows.map(
                row => ({
                    fuelType:
                        row.fuel_type,

                    shortLabel:
                        SHORT_LABELS[row.fuel_type]
                        || row.fuel_type,

                    fullLabel:
                        row.fuel_label
                        || row.fuel_type,

                    value:
                        Number(row.available_mw)
                })
            );

        const remainingMW =
            remainingRows.reduce(
                (total, row) =>
                    total
                    + Number(row.available_mw),
                0
            );

        if (remainingMW > 0) {
            chartRows.push({
                fuelType:
                    "REMAINING",

                shortLabel:
                    "Other categories",

                fullLabel:
                    "Remaining fuel and interconnector categories",

                value:
                    remainingMW
            });
        }

        const totalMW =
            chartRows.reduce(
                (total, row) =>
                    total + row.value,
                0
            );

        const colours = [
            "#2589ff",
            "#16a765",
            "#f59e0b",
            "#7c5ce7",
            "#0891b2",
            "#ef5350",
            "#14a394",
            "#94a3b8"
        ];

        if (message) {
            message.classList.add("hidden");
            message.hidden = true;
        }

        if (fuelShareChart) {
            fuelShareChart.destroy();
        }


        /*
         * Total MW in donut centre.
         */
        const centreTextPlugin = {
            id:
                "fuelShareCentreText",

            afterDraw(chart) {
                const {
                    ctx,
                    chartArea
                } = chart;

                if (!chartArea) {
                    return;
                }

                const centreX =
                    (
                        chartArea.left
                        + chartArea.right
                    ) / 2;

                const centreY =
                    (
                        chartArea.top
                        + chartArea.bottom
                    ) / 2 - 8;

                ctx.save();

                ctx.textAlign =
                    "center";

                ctx.textBaseline =
                    "middle";

                ctx.fillStyle =
                    "#152238";

                ctx.font =
                    "700 20px sans-serif";

                ctx.fillText(
                    `${formatNumber(totalMW)} MW`,
                    centreX,
                    centreY
                );

                ctx.fillStyle =
                    "#718096";

                ctx.font =
                    "600 10px sans-serif";

                ctx.fillText(
                    "AVAILABLE CAPACITY",
                    centreX,
                    centreY + 22
                );

                ctx.restore();
            }
        };


        /*
         * Percentage labels drawn directly on donut slices.
         */
        const arcLabelPlugin = {
            id:
                "fuelShareArcLabels",

            afterDatasetsDraw(chart) {
                const ctx =
                    chart.ctx;

                const dataset =
                    chart.data.datasets[0];

                const meta =
                    chart.getDatasetMeta(0);

                meta.data.forEach(
                    (arc, index) => {
                        const value =
                            Number(
                                dataset.data[index]
                            );

                        const share =
                            totalMW > 0
                                ? (
                                    value
                                    / totalMW
                                    * 100
                                )
                                : 0;

                        /*
                         * Avoid overcrowding very small slices.
                         */
                        if (share < 3) {
                            return;
                        }

                        const position =
                            arc.tooltipPosition();

                        const fontSize =
                            share >= 10
                                ? 12
                                : 10;

                        ctx.save();

                        ctx.textAlign =
                            "center";

                        ctx.textBaseline =
                            "middle";

                        ctx.fillStyle =
                            "#ffffff";

                        ctx.font =
                            `700 ${fontSize}px sans-serif`;

                        ctx.fillText(
                            `${share.toFixed(1)}%`,
                            position.x,
                            position.y
                        );

                        ctx.restore();
                    }
                );
            }
        };


        fuelShareChart =
            new Chart(
                canvas.getContext("2d"),
                {
                    type:
                        "doughnut",

                    plugins: [
                        centreTextPlugin,
                        arcLabelPlugin
                    ],

                    data: {
                        labels:
                            chartRows.map(
                                row =>
                                    row.shortLabel
                            ),

                        datasets: [
                            {
                                data:
                                    chartRows.map(
                                        row =>
                                            row.value
                                    ),

                                backgroundColor:
                                    colours,

                                borderColor:
                                    "#ffffff",

                                borderWidth:
                                    3,

                                hoverBorderWidth:
                                    4,

                                hoverOffset:
                                    7,

                                spacing:
                                    1
                            }
                        ]
                    },

                    options: {
                        responsive:
                            false,

                        maintainAspectRatio:
                            false,

                        cutout:
                            "64%",

                        plugins: {
                            legend: {
                                position:
                                    "bottom",

                                labels: {
                                    usePointStyle:
                                        true,

                                    pointStyle:
                                        "circle",

                                    boxWidth:
                                        8,

                                    boxHeight:
                                        8,

                                    padding:
                                        12,

                                    color:
                                        "#52647b",

                                    font: {
                                        size:
                                            10,
                                        weight:
                                            "600"
                                    }
                                }
                            },

                            tooltip: {
                                padding:
                                    12,

                                callbacks: {
                                    title:
                                        function(items) {
                                            const index =
                                                items[0].dataIndex;

                                            return (
                                                chartRows[index]
                                                    .fullLabel
                                            );
                                        },

                                    label:
                                        function(context) {
                                            const value =
                                                Number(
                                                    context.raw
                                                );

                                            const share =
                                                totalMW > 0
                                                    ? (
                                                        value
                                                        / totalMW
                                                        * 100
                                                    )
                                                    : 0;

                                            return (
                                                `${formatNumber(value)} MW `
                                                + `(${share.toFixed(1)}%)`
                                            );
                                        }
                                }
                            }
                        }
                    }
                }
            );
    }
    catch (error) {
        console.error(
            "Fuel share chart failed:",
            error
        );

        if (message) {
            message.hidden = false;

            message.classList.remove(
                "hidden"
            );

            message.textContent =
                "Unable to load capacity mix";
        }
    }
}



/* =========================================================
   REVISION INTELLIGENCE
   ========================================================= */

async function loadFuelRevisions() {
    const canvas =
        document.getElementById("fuel-revision-chart");

    const message =
        document.getElementById("fuel-revision-message");

    if (!canvas) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/fuel-revisions",
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const rows =
            await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            throw new Error(
                "No fuel revision data returned"
            );
        }

        const sortedRows =
            [...rows].sort(
                (a, b) =>
                    Math.abs(b.net_revision_mw)
                    - Math.abs(a.net_revision_mw)
            );

        const labels =
            sortedRows.map(
                row =>
                    row.fuel_label
                    || row.fuel_type
            );

        const values =
            sortedRows.map(
                row =>
                    Number(row.net_revision_mw)
            );

        const colours =
            values.map(
                value =>
                    value >= 0
                        ? "#16a765"
                        : "#ef5350"
            );

        if (message) {
            message.classList.add("hidden");
            message.hidden = true;
        }

        if (fuelRevisionChart) {
            fuelRevisionChart.destroy();
        }

        fuelRevisionChart =
            new Chart(
                canvas.getContext("2d"),
                {
                    type: "bar",

                    data: {
                        labels: labels,

                        datasets: [
                            {
                                label:
                                    "Net revision MW",

                                data:
                                    values,

                                backgroundColor:
                                    colours,

                                borderRadius:
                                    5,

                                borderWidth:
                                    0
                            }
                        ]
                    },

                    options: {
                        responsive:
                            false,

                        maintainAspectRatio:
                            false,

                        indexAxis:
                            "y",

                        plugins: {
                            legend: {
                                display:
                                    false
                            },

                            tooltip: {
                                displayColors:
                                    false,

                                callbacks: {
                                    label:
                                        function(context) {
                                            const value =
                                                Number(
                                                    context.raw
                                                );

                                            const prefix =
                                                value > 0
                                                    ? "+"
                                                    : "";

                                            return (
                                                `${prefix}${formatNumber(value)} MW`
                                            );
                                        }
                                }
                            }
                        },

                        scales: {
                            y: {
                                grid: {
                                    display:
                                        false
                                },

                                border: {
                                    display:
                                        false
                                },

                                ticks: {
                                    color:
                                        "#52647b",

                                    font: {
                                        size:
                                            10,
                                        weight:
                                            "600"
                                    }
                                }
                            },

                            x: {
                                border: {
                                    display:
                                        false
                                },

                                grid: {
                                    color:
                                        "rgba(148, 163, 184, 0.14)"
                                },

                                ticks: {
                                    color:
                                        "#69788d",

                                    callback:
                                        function(value) {
                                            if (
                                                Math.abs(value)
                                                >= 1000
                                            ) {
                                                return (
                                                    `${value / 1000}k`
                                                );
                                            }

                                            return value;
                                        }
                                },

                                title: {
                                    display:
                                        true,

                                    text:
                                        "Net revision MW",

                                    color:
                                        "#69788d"
                                }
                            }
                        }
                    }
                }
            );
    }
    catch (error) {
        console.error(
            "Fuel revisions failed:",
            error
        );

        if (message) {
            message.hidden = false;
            message.classList.remove("hidden");
            message.textContent =
                "Unable to load revision intelligence";
        }
    }
}


/* =========================================================
   REVISION DIRECTION COUNT
   ========================================================= */

async function loadRevisionDirections() {
    const canvas =
        document.getElementById(
            "revision-direction-chart"
        );

    const message =
        document.getElementById(
            "revision-direction-message"
        );

    if (!canvas) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/revision-directions",
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const rows =
            await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            throw new Error(
                "No revision direction data returned"
            );
        }

        const order = {
            up: 1,
            down: 2,
            unchanged: 3
        };

        const labelsMap = {
            up: "Upward",
            down: "Downward",
            unchanged: "Unchanged"
        };

        const colourMap = {
            up: "#16a765",
            down: "#ef5350",
            unchanged: "#94a3b8"
        };

        const sortedRows =
            [...rows].sort(
                (a, b) =>
                    order[a.direction]
                    - order[b.direction]
            );

        const labels =
            sortedRows.map(
                row =>
                    labelsMap[row.direction]
                    || row.direction
            );

        const values =
            sortedRows.map(
                row =>
                    Number(row.count)
            );

        const colours =
            sortedRows.map(
                row =>
                    colourMap[row.direction]
                    || "#64748b"
            );

        if (message) {
            message.classList.add("hidden");
            message.hidden = true;
        }

        if (revisionDirectionChart) {
            revisionDirectionChart.destroy();
        }

        const directionLabelsPlugin = {
            id:
                "revisionDirectionLabels",

            afterDatasetsDraw(chart) {
                const ctx =
                    chart.ctx;

                const meta =
                    chart.getDatasetMeta(0);

                meta.data.forEach(
                    (bar, index) => {
                        const row =
                            sortedRows[index];

                        const label =
                            `${formatNumber(row.count)} · `
                            + `${Number(row.share_pct).toFixed(2)}%`;

                        ctx.save();

                        ctx.fillStyle =
                            "#52647b";

                        ctx.font =
                            "600 10px sans-serif";

                        ctx.textAlign =
                            "left";

                        ctx.textBaseline =
                            "middle";

                        ctx.fillText(
                            label,
                            bar.x + 8,
                            bar.y
                        );

                        ctx.restore();
                    }
                );
            }
        };

        revisionDirectionChart =
            new Chart(
                canvas.getContext("2d"),
                {
                    type:
                        "bar",

                    plugins: [
                        directionLabelsPlugin
                    ],

                    data: {
                        labels:
                            labels,

                        datasets: [
                            {
                                label:
                                    "Revision count",

                                data:
                                    values,

                                backgroundColor:
                                    colours,

                                borderRadius:
                                    5
                            }
                        ]
                    },

                    options: {
                        responsive:
                            false,

                        maintainAspectRatio:
                            false,

                        indexAxis:
                            "y",

                        layout: {
                            padding: {
                                right:
                                    105
                            }
                        },

                        plugins: {
                            legend: {
                                display:
                                    false
                            },

                            tooltip: {
                                displayColors:
                                    false,

                                callbacks: {
                                    label:
                                        function(context) {
                                            const row =
                                                sortedRows[
                                                    context.dataIndex
                                                ];

                                            return (
                                                `${formatNumber(row.count)} revisions `
                                                + `(${Number(row.share_pct).toFixed(2)}%)`
                                            );
                                        }
                                }
                            }
                        },

                        scales: {
                            y: {
                                grid: {
                                    display:
                                        false
                                },

                                border: {
                                    display:
                                        false
                                },

                                ticks: {
                                    color:
                                        "#52647b",

                                    font: {
                                        size:
                                            10,
                                        weight:
                                            "600"
                                    }
                                }
                            },

                            x: {
                                beginAtZero:
                                    true,

                                border: {
                                    display:
                                        false
                                },

                                grid: {
                                    color:
                                        "rgba(148, 163, 184, 0.14)"
                                },

                                ticks: {
                                    color:
                                        "#69788d",

                                    callback:
                                        function(value) {
                                            if (value >= 1000) {
                                                return (
                                                    `${Math.round(
                                                        value / 1000
                                                    )}k`
                                                );
                                            }

                                            return value;
                                        }
                                }
                            }
                        }
                    }
                }
            );
    }
    catch (error) {
        console.error(
            "Revision directions failed:",
            error
        );

        if (message) {
            message.hidden = false;
            message.classList.remove("hidden");
            message.textContent =
                "Unable to load revision direction history";
        }
    }
}


/* =========================================================
   REVISION SIGNALS
   ========================================================= */

async function loadRevisionSignals() {
    try {
        const response =
            await fetch(
                "/api/revision-signals",
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const data =
            await response.json();

        const upward =
            data.largest_upward;

        const downward =
            data.largest_downward;

        const fuel =
            data.most_revised_fuel;


        if (upward) {
            setText(
                "largest-upward-value",
                `+${formatNumber(
                    upward.revision_mw
                )} MW`
            );

            setText(
                "largest-upward-detail",
                `${upward.unit} · `
                + `${upward.fuel_label || upward.fuel_type}`
            );
        }


        if (downward) {
            setText(
                "largest-downward-value",
                `${formatNumber(
                    downward.revision_mw
                )} MW`
            );

            setText(
                "largest-downward-detail",
                `${downward.unit} · `
                + `${downward.fuel_label || downward.fuel_type}`
            );
        }


        if (fuel) {
            setText(
                "most-revised-fuel-value",
                fuel.fuel_label
                || fuel.fuel_type
            );

            const net =
                Number(
                    fuel.net_revision_mw
                );

            const prefix =
                net > 0
                    ? "+"
                    : "";

            setText(
                "most-revised-fuel-detail",
                `${formatNumber(
                    fuel.absolute_revision_mw
                )} MW absolute · `
                + `${prefix}${formatNumber(net)} MW net`
            );
        }
    }
    catch (error) {
        console.error(
            "Revision signals failed:",
            error
        );

        setText(
            "largest-upward-value",
            "Unavailable"
        );

        setText(
            "largest-downward-value",
            "Unavailable"
        );

        setText(
            "most-revised-fuel-value",
            "Unavailable"
        );
    }
}


/* =========================================================
   TOP UNIT REVISIONS
   ========================================================= */

async function loadTopUnitRevisions() {
    const body =
        document.getElementById(
            "top-unit-revisions-body"
        );

    if (!body) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/top-unit-revisions",
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const rows =
            await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            throw new Error(
                "No unit revision data returned"
            );
        }

        body.innerHTML = "";

        rows.forEach(
            row => {
                const tr =
                    document.createElement("tr");

                const revision =
                    Number(
                        row.revision_mw
                    );

                const revisionPrefix =
                    revision > 0
                        ? "+"
                        : "";

                const directionLabel =
                    row.direction === "up"
                        ? "Upward"
                        : row.direction === "down"
                            ? "Downward"
                            : "Unchanged";

                tr.innerHTML = `
                    <td>
                        <strong>${row.unit}</strong>
                    </td>

                    <td>
                        ${row.fuel_label || row.fuel_type}
                    </td>

                    <td>
                        <span class="${
                            row.direction === "up"
                                ? "revision-up"
                                : row.direction === "down"
                                    ? "revision-down"
                                    : "revision-unchanged"
                        }">
                            ${directionLabel}
                        </span>
                    </td>

                    <td>
                        <strong class="${
                            revision > 0
                                ? "revision-up"
                                : revision < 0
                                    ? "revision-down"
                                    : "revision-unchanged"
                        }">
                            ${revisionPrefix}${formatNumber(revision)} MW
                        </strong>
                    </td>

                    <td>
                        ${formatForecastDate(
                            row.forecast_date
                        )}
                    </td>

                    <td>
                        ${formatPublication(
                            row.publication_time
                        )}
                    </td>
                `;

                body.appendChild(tr);
            }
        );
    }
    catch (error) {
        console.error(
            "Top unit revisions failed:",
            error
        );

        body.innerHTML = `
            <tr>
                <td colspan="6">
                    Unable to load unit revision intelligence
                </td>
            </tr>
        `;
    }
}



/* =========================================================
   AVAILABILITY STABILITY & EARLY WARNING
   ========================================================= */

async function loadStabilityIntelligence() {

    try {
        const response =
            await fetch(
                "/api/stability-intelligence",
                {
                    cache:
                        "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `API returned ${response.status}`
            );
        }

        const data =
            await response.json();


        const score =
            Number(
                data.stability_score
                || 0
            );


        setText(
            "stability-score",
            score.toFixed(1)
        );


        setText(
            "stability-band",
            data.stability_band
            || "Unavailable"
        );


        setText(
            "stability-change-share",
            `${Number(
                data.changed_revision_share_pct
                || 0
            ).toFixed(2)}% of historical revision records changed MW`
        );


        const scoreFill =
            document.getElementById(
                "stability-score-fill"
            );

        if (scoreFill) {
            scoreFill.style.width =
                `${Math.max(
                    0,
                    Math.min(
                        100,
                        score
                    )
                )}%`;
        }


        const netRevision =
            Number(
                data.net_revision_mw_24h
                || 0
            );


        const netRevisionElement =
            document.getElementById(
                "stability-net-revision"
            );


        if (netRevisionElement) {

            const prefix =
                netRevision > 0
                    ? "+"
                    : "";

            netRevisionElement.textContent =
                `${prefix}${formatNumber(
                    netRevision
                )} MW`;


            netRevisionElement.classList.remove(
                "positive",
                "negative",
                "neutral"
            );


            if (netRevision > 0) {
                netRevisionElement.classList.add(
                    "positive"
                );
            }

            else if (netRevision < 0) {
                netRevisionElement.classList.add(
                    "negative"
                );
            }

            else {
                netRevisionElement.classList.add(
                    "neutral"
                );
            }
        }


        const watchElement =
            document.getElementById(
                "stability-watch-status"
            );


        if (watchElement) {

            watchElement.textContent =
                data.watch_status
                || "Unavailable";


            watchElement.classList.remove(
                "positive",
                "negative",
                "neutral"
            );


            watchElement.classList.add(
                data.watch_tone
                || "neutral"
            );
        }


        setText(
            "stability-watch-detail",
            data.watch_detail
            || "Revision watch unavailable"
        );


        setText(
            "stability-most-revised-fuel",
            data.most_revised_fuel
            || "Unavailable"
        );


        setText(
            "stability-most-revised-detail",
            `${formatNumber(
                data.most_revised_fuel_abs_mw
                || 0
            )} MW absolute revision activity`
        );

    }

    catch (error) {

        console.error(
            "Stability intelligence failed:",
            error
        );


        setText(
            "stability-score",
            "Unavailable"
        );


        setText(
            "stability-band",
            "Unable to calculate stability"
        );


        setText(
            "stability-net-revision",
            "Unavailable"
        );


        setText(
            "stability-watch-status",
            "Unavailable"
        );


        setText(
            "stability-most-revised-fuel",
            "Unavailable"
        );
    }
}


/* =========================================================
   NAVIGATION
   ========================================================= */

const navigationLinks =
    document.querySelectorAll(
        ".nav-link"
    );


navigationLinks.forEach(
    link => {
        link.addEventListener(
            "click",
            () => {
                navigationLinks.forEach(
                    item =>
                        item.classList.remove(
                            "active"
                        )
                );

                link.classList.add(
                    "active"
                );
            }
        );
    }
);


/* =========================================================
   INITIAL LOAD
   ========================================================= */

async function refreshDashboard() {
    await Promise.all([
        loadKPIs(),
        loadSystemAvailability(),
        loadFuelAvailability(),
        loadFuelShare(),
        loadFuelRevisions(),
        loadRevisionDirections(),
        loadRevisionSignals(),
        loadTopUnitRevisions(),
        loadStabilityIntelligence()
    ]);
}


refreshDashboard();


/*
 * Refresh the web presentation every five minutes.
 * Databricks ingestion remains independently scheduled.
 */

setInterval(
    refreshDashboard,
    5 * 60 * 1000
);

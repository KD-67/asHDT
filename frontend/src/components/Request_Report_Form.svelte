<script>
    import { gql, subscribe } from "../lib/gql.js";

    let textColor = '#422800';
    let borderColor = '#422800';
    let cardColor = '#d0e8ff';
    let cardSectionColor = 'aliceblue';
    let addBtnColor = 'rgb(114, 231, 114)';

    let loading = $state(false);
    let submitting = $state(false);
    let submitStatus = $state("");

    let subjects = $state([]);
    let subject_profile = $state({});
    let profile_visible = $state(false);
    let subject_names = $state({});
    let modules = $state([]);
    let markers = $state([]);
    let analysis_methods = $state([]);
    let markerset_instances = $state([]);

    let selected_subject = $state("nothing");
    let selected_method_id = $state("trajectory");
    let input_mode = $state("single");     // "single" | "markerset"
    let selected_markerset_id = $state("");
    let selected_module = $state("nothing");
    let selected_marker = $state("nothing");
    let selected_start_time = $state("2026-01-01T00:00");
    let selected_end_time = $state("2026-03-31T00:00");
    let selected_polynomial_degree = $state(2);
    let selected_healthy_min = $state(0);
    let selected_healthy_max = $state(1);
    let selected_vulnerability_margin = $state(0.1);
    let zone_reference_note = $state(null);

    // ── Derived: selected method info ──────────────────────────────────────────
    let selected_method = $derived(
        analysis_methods.find(m => m.method_id === selected_method_id) ?? null
    );

    async function loadSubjects() {
        loading = true;
        try {
            const data = await gql(`query { subjects { subjectId firstName lastName } }`);
            subjects = data.subjects.map(s => s.subjectId);
            subject_names = {};
            for (const s of data.subjects) {
                if (s.firstName && s.lastName) {
                    subject_names[s.subjectId] = `${s.firstName} ${s.lastName} // ID: (${s.subjectId})`;
                }
            }
        } catch (e) {
            console.error("Failed to load subjects:", e);
        } finally {
            loading = false;
        }
    }

    async function loadSubjectProfile(subjectID) {
        loading = true;
        try {
            const data = await gql(
                `query($id: String!) { subject(subjectId: $id) { subjectId firstName lastName sex dob email phone notes createdAt } }`,
                { id: subjectID }
            );
            const s = data.subject;
            subject_profile = {
                subject_id: s.subjectId,
                first_name: s.firstName,
                last_name:  s.lastName,
                sex:        s.sex,
                dob:        s.dob,
                email:      s.email,
                phone:      s.phone,
                notes:      s.notes,
                created_at: s.createdAt,
            };
        } catch (error) {
            console.error("Failed to fetch profile:", error);
        } finally {
            loading = false;
        }
    }

    async function loadModules() {
        loading = true;
        try {
            const data = await gql(`query { modules { moduleId moduleName markers { markerId markerName } } }`);
            modules = data.modules.map(m => ({
                module_id:   m.moduleId,
                module_name: m.moduleName,
                markers:     m.markers.map(mk => ({ marker_id: mk.markerId, marker_name: mk.markerName })),
            }));
        } catch (e) {
            console.error("Failed to load modules:", e);
        } finally {
            loading = false;
        }
    }

    async function loadAnalysisMethods() {
        try {
            const data = await gql(`query {
                analysisMethods {
                    methodId methodName description status
                    acceptsSingleMarker acceptsMarkerset
                    minMarkers maxMarkers paramsSchema outputType
                }
            }`);
            analysis_methods = data.analysisMethods.map(m => ({
                method_id:             m.methodId,
                method_name:           m.methodName,
                description:           m.description,
                status:                m.status,
                accepts_single_marker: m.acceptsSingleMarker,
                accepts_markerset:     m.acceptsMarkerset,
                params_schema:         m.paramsSchema,
            }));
        } catch (e) {
            console.error("Failed to load analysis methods:", e);
            // Fallback so the form stays functional
            analysis_methods = [{
                method_id:             "trajectory",
                method_name:           "Trajectory Analysis",
                description:           "Polynomial fit + 27-state classification.",
                status:                "implemented",
                accepts_single_marker: true,
                accepts_markerset:     true,
                params_schema:         "trajectory",
            }];
        }
    }

    async function loadMarkersetInstances(subjectId) {
        if (!subjectId || subjectId === "nothing") { markerset_instances = []; return; }
        try {
            const data = await gql(
                `query($s: String!) { markersetInstances(subjectId: $s) { instanceId name } }`,
                { s: subjectId }
            );
            markerset_instances = data.markersetInstances.map(i => ({
                instance_id: i.instanceId,
                name:        i.name,
            }));
        } catch (e) {
            console.error("Failed to load markerset instances:", e);
            markerset_instances = [];
        }
    }

    function onModuleChange() {
        const module = modules.find(m => m.module_id === selected_module);
        markers = module ? module.markers : [];
        selected_marker = "";
    }

    function onSubjectChange() {
        selected_module = "nothing";
        selected_marker = "nothing";
        selected_markerset_id = "";
        zone_reference_note = null;
        loadMarkersetInstances(selected_subject);
    }

    async function loadZoneReference() {
        if (!selected_subject || !selected_module || !selected_marker) return;
        try {
            const data = await gql(
                `query($s: String!, $mo: String!, $ma: String!) {
                    zoneReference(subjectId: $s, moduleId: $mo, markerId: $ma) {
                        healthyMin healthyMax vulnerabilityMargin note
                    }
                }`,
                { s: selected_subject, mo: selected_module, ma: selected_marker }
            );
            const ref = data.zoneReference;
            if (!ref) { zone_reference_note = null; return; }
            selected_healthy_min          = ref.healthyMin;
            selected_healthy_max          = ref.healthyMax;
            selected_vulnerability_margin = ref.vulnerabilityMargin;
            zone_reference_note           = ref.note;
        } catch (error) {
            console.error("Failed to fetch zone reference:", error);
        }
    }

    async function submitTimegraphRequest() {
        submitting   = true;
        submitStatus = "Submitting analysis job...";
        try {
            // Build the analysis input based on selected mode
            let analysisInput;

            if (input_mode === "markerset") {
                if (!selected_markerset_id) throw new Error("Select a markerset.");
                analysisInput = {
                    subjectId:   selected_subject,
                    method:      "TRAJECTORY",
                    timeframe: {
                        startTime: new Date(selected_start_time).toISOString(),
                        endTime:   new Date(selected_end_time).toISOString(),
                    },
                    markersetId: selected_markerset_id,
                    trajectoryParams: {
                        polynomialDegree:    selected_polynomial_degree,
                        // zone boundaries ignored for composite (resolved per-marker from DB)
                        healthyMin:          0.0,
                        healthyMax:          1.0,
                        vulnerabilityMargin: selected_vulnerability_margin,
                    },
                };
            } else {
                // Single-marker mode
                if (!selected_module || !selected_marker) throw new Error("Select a module and marker.");
                analysisInput = {
                    subjectId:  selected_subject,
                    method:     "TRAJECTORY",
                    timeframe: {
                        startTime: new Date(selected_start_time).toISOString(),
                        endTime:   new Date(selected_end_time).toISOString(),
                    },
                    markerRefs: [{ moduleId: selected_module, markerId: selected_marker }],
                    trajectoryParams: {
                        polynomialDegree:    selected_polynomial_degree,
                        healthyMin:          selected_healthy_min,
                        healthyMax:          selected_healthy_max,
                        vulnerabilityMargin: selected_vulnerability_margin,
                    },
                };
            }

            // 1. Enqueue the job
            const mutData = await gql(
                `mutation($input: AnalysisInput!) { submitAnalysis(input: $input) { jobId status } }`,
                { input: analysisInput }
            );

            const jobId = mutData.submitAnalysis.jobId;
            submitStatus = "Analysis running...";

            // 2. Stream job status via WebSocket subscription
            await new Promise((resolve, reject) => {
                let unsub;
                unsub = subscribe(
                    `subscription($jobId: String!) {
                        jobStatus(jobId: $jobId) {
                            status progress errorMessage
                            result {
                                ... on TrajectoryReport {
                                    reportId
                                    datapoints {
                                        timestamp xHours rawValue dataQuality
                                        healthScore fittedValue zone
                                        fPrime fDoublePrime trajectoryState timeToTransitionHours
                                    }
                                    fitMetadata {
                                        coefficients t0Iso
                                        zoneBoundaries { vulnerabilityMargin }
                                    }
                                }
                            }
                        }
                    }`,
                    { jobId },
                    (payload) => {
                        const job = payload.jobStatus;
                        if (job.progress != null) {
                            submitStatus = `Analysis running... ${Math.round(job.progress * 100)}%`;
                        }
                        if (job.status === "COMPLETED") {
                            const r = job.result;
                            // Transform camelCase GQL response to snake_case for localStorage
                            const report = {
                                report_id:  r.reportId,
                                datapoints: r.datapoints.map(dp => ({
                                    timestamp:                dp.timestamp,
                                    x_hours:                  dp.xHours,
                                    raw_value:                dp.rawValue,
                                    data_quality:             dp.dataQuality,
                                    health_score:             dp.healthScore,
                                    fitted_value:             dp.fittedValue,
                                    zone:                     dp.zone,
                                    f_prime:                  dp.fPrime,
                                    f_double_prime:           dp.fDoublePrime,
                                    trajectory_state:         dp.trajectoryState,
                                    time_to_transition_hours: dp.timeToTransitionHours,
                                })),
                                fit_metadata: {
                                    coefficients:    r.fitMetadata.coefficients,
                                    t0_iso:          r.fitMetadata.t0Iso,
                                    zone_boundaries: { vulnerability_margin: r.fitMetadata.zoneBoundaries.vulnerabilityMargin },
                                },
                            };
                            localStorage.setItem("timegraph_report", JSON.stringify(report));
                            window.open("http://localhost:5173/#timegraph", "_blank");
                            unsub();
                            resolve();
                        } else if (job.status === "FAILED") {
                            unsub();
                            reject(new Error(job.errorMessage ?? "Analysis failed"));
                        }
                    },
                    (err) => { unsub?.(); reject(err); }
                );
            });

            submitStatus = "";
        } catch (error) {
            console.error("Failed to submit timegraph request:", error);
            submitStatus = `Error: ${error.message}`;
        } finally {
            submitting = false;
        }
    }

    loadSubjects();
    loadModules();
    loadAnalysisMethods();
</script>

<main style="--textColor: {textColor}; --borderColor: {borderColor}">
    <div id="main_container">

        <h2 id="form_header">Report Request Form</h2>

        <div id="report_form">

            <!-- Row 0: Method selector -->
            <div id="row_method">
                <label>Analysis Method
                    <select bind:value={selected_method_id}>
                        {#each analysis_methods as m}
                            <option
                                value={m.method_id}
                                disabled={m.status !== "implemented"}
                                title={m.status !== "implemented" ? "Not yet implemented" : m.description}
                            >
                                {m.method_name}{m.status !== "implemented" ? " (coming soon)" : ""}
                            </option>
                        {/each}
                    </select>
                </label>
                {#if selected_method}
                    <p id="method_desc">{selected_method.description}</p>
                {/if}
            </div>

            <!-- Row 1: Subject + input mode + marker/markerset selectors -->
            <div id="row_selectors">
                <label>Subject
                    <select bind:value={selected_subject} onchange={onSubjectChange}>
                        <option value="nothing">-- select subject --</option>
                        {#each subjects as subject}
                            <option value={subject}>{subject_names[subject] ?? subject}</option>
                        {/each}
                    </select>
                </label>

                {#if selected_method?.accepts_markerset && selected_method?.accepts_single_marker}
                    <label>Input mode
                        <select bind:value={input_mode}>
                            <option value="single">Single marker</option>
                            <option value="markerset">Saved markerset</option>
                        </select>
                    </label>
                {:else if selected_method?.accepts_markerset && !selected_method?.accepts_single_marker}
                    <!-- Force markerset mode -->
                    {#if input_mode !== "markerset"}{input_mode = "markerset"}{/if}
                {/if}

                {#if input_mode === "markerset"}
                    <label>Markerset
                        <select bind:value={selected_markerset_id} disabled={!selected_subject || selected_subject === "nothing"}>
                            <option value="">-- select markerset --</option>
                            {#each markerset_instances as ms}
                                <option value={ms.instance_id}>{ms.name}</option>
                            {/each}
                        </select>
                    </label>
                {:else}
                    <label>Module
                        <select bind:value={selected_module} disabled={!selected_subject || selected_subject === "nothing"} onchange={onModuleChange}>
                            <option value="">-- select module --</option>
                            {#each modules as module}
                                <option value={module.module_id}>{module.module_name || module.module_id}</option>
                            {/each}
                        </select>
                    </label>

                    <label>Marker
                        <select bind:value={selected_marker} disabled={!selected_module} onchange={loadZoneReference}>
                            <option value="">-- select marker --</option>
                            {#each markers as marker}
                                <option value={marker.marker_id}>{marker.marker_name || marker.marker_id}</option>
                            {/each}
                        </select>
                    </label>
                {/if}
            </div>

            <!-- Row 2: Timeframe + polynomial degree -->
            <div id="row_timeframe">
                <label>From
                    <input type="datetime-local" bind:value={selected_start_time} required />
                </label>
                <label>To
                    <input type="datetime-local" bind:value={selected_end_time} required />
                </label>
                <label>Polynomial Degree — {selected_polynomial_degree}
                    <input type="range" min="1" max="5" step="1" bind:value={selected_polynomial_degree} />
                </label>
            </div>

            <!-- Row 3: Trajectory params (zone boundaries) -->
            {#if selected_method?.params_schema === "trajectory"}
                <div id="row_zones">
                    <span id="zone_label">
                        {input_mode === "markerset"
                            ? "Trajectory Parameters (zone boundaries resolved per-marker from DB)"
                            : "Zone Boundaries"}
                    </span>
                    {#if zone_reference_note && input_mode === "single"}
                        <p id="zone_reference_note">{zone_reference_note}</p>
                    {/if}

                    {#if input_mode === "single"}
                        <label>Healthy minimum
                            <input type="number" bind:value={selected_healthy_min} required />
                        </label>
                        <label>Healthy maximum
                            <input type="number" bind:value={selected_healthy_max} required />
                        </label>
                    {/if}

                    <label>Vulnerability margin
                        <input type="number" bind:value={selected_vulnerability_margin} required />
                    </label>
                </div>
            {/if}

            <!-- Row 4: Actions -->
            <div id="row_submit">
                <button type="button" onclick={async () => {
                    if (profile_visible) { profile_visible = false; return; }
                    if (!selected_subject || selected_subject === "nothing") return;
                    await loadSubjectProfile(selected_subject);
                    profile_visible = true;
                }}>{profile_visible ? "Hide profile" : "Show profile"}</button>
                <button style="--addBtnColor: {addBtnColor}" class="add_btn" type="button" onclick={submitTimegraphRequest} disabled={submitting}>
                    {submitting ? "Working..." : "Request report"}
                </button>
                {#if submitStatus}<p id="submit_status">{submitStatus}</p>{/if}
            </div>

        </div>

        {#if profile_visible && Object.keys(subject_profile).length > 0}
        <div id="profile_display">
            <h4>Selected profile</h4>
            {#each Object.entries(subject_profile) as [key, value]}
                <div class="profile_row">
                    <span class="profile_key">{key.replace(/_/g, ' ')}</span>
                    <span class="profile_val">{value ?? '—'}</span>
                </div>
            {/each}
        </div>
        {/if}

    </div>
</main>

<style>

    * {
        color: var(--textColor);
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    /* BUTTONS */

    button {
        border-radius: 30px;
        margin: 0.75rem 0.25rem;
        padding: 0.25rem 0.75rem;
        box-shadow: 5px 5px 0px var(--borderColor);
        cursor: pointer;
        font-size: 14px;
        border: 1px solid var(--borderColor);
        background-color: #fbeee0;
    }

    button:hover {
        transform: scale(102%);
        font-weight: 550;
        border: 2px solid var(--borderColor);
    }

    button:active {
        box-shadow: var(--borderColor) 2px 2px 0 0;
        transform: translate(2px, 2px);
    }

    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
    }

    .add_btn {
        background-color: var(--addBtnColor);
    }

    /* LAYOUT */

    #main_container {
        border: 1px solid var(--borderColor);
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px;
    }

    #form_header {
        padding: 0.5rem 0;
    }

    #report_form {
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px var(--borderColor);
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    #report_form label {
        display: grid;
        font-size: 0.85em;
        gap: 4px;
    }

    #report_form input,
    #report_form select {
        padding: 5px;
        border: 1px solid var(--borderColor);
        border-radius: 3px;
        background: white;
        font-size: 0.9em;
        width: 100%;
    }

    input:focus, select:focus {
        background-color: aqua;
        outline: none;
    }

    input[type="range"] {
        padding: 0;
        border: none;
        background: transparent;
    }

    #row_method {
        display: flex;
        align-items: center;
        gap: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--borderColor);
    }

    #row_method label {
        flex-shrink: 0;
        min-width: 200px;
    }

    #method_desc {
        font-size: 0.8em;
        color: #555;
        font-style: italic;
        flex: 1;
    }

    #row_selectors {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
    }

    #row_timeframe {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        padding-top: 10px;
        border-top: 1px solid var(--borderColor);
    }

    #row_zones {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        padding-top: 10px;
        border-top: 1px solid var(--borderColor);
        align-items: start;
    }

    #zone_label {
        grid-column: 1 / 4;
        font-weight: bold;
        font-size: 0.9em;
    }

    #row_submit {
        display: flex;
        align-items: center;
        gap: 10px;
        padding-top: 10px;
        border-top: 1px solid var(--borderColor);
    }

    #zone_reference_note {
        grid-column: 1 / 4;
        font-style: italic;
        font-size: 0.85em;
        color: #555;
    }

    #submit_status {
        font-weight: bold;
        font-size: 0.9em;
    }

    /* PROFILE DISPLAY */

    #profile_display {
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: aliceblue;
        box-shadow: 5px 5px 0px var(--borderColor);
        padding: 10px;
        display: grid;
        gap: 4px;
    }

    #profile_display h4 {
        border-bottom: 1px solid var(--borderColor);
        padding-bottom: 4px;
        margin-bottom: 4px;
    }

    .profile_row {
        display: flex;
        gap: 10px;
        font-size: 0.9em;
    }

    .profile_key {
        font-weight: bold;
        min-width: 120px;
        text-transform: capitalize;
    }

    .profile_val {
        color: #444;
    }

</style>

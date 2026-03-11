<script>
    import { gql, subscribe } from "../lib/gql.js";

    let loading = $state(false);
    let submitting = $state(false);
    let submitStatus = $state("");

    let subjects = $state([]);
    let subject_profile = $state({});
    let subject_names = $state({});
    let modules = $state([]);
    let markers = $state([]);

    let selected_subject = $state("nothing");
    let selected_module = $state("nothing");
    let selected_marker = $state("nothing");
    let selected_start_time = $state("2026-01-01T00:00");
    let selected_end_time = $state("2026-03-31T00:00");
    let selected_polynomial_degree = $state(2);
    let selected_healthy_min = $state(0);
    let selected_healthy_max = $state(1);
    let selected_vulnerability_margin = $state(0.1);
    let zone_reference_note = $state(null);

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

    function onModuleChange() {
        const module = modules.find(m => m.module_id === selected_module);
        markers = module ? module.markers : [];
        selected_marker = "";
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
            // 1. Enqueue the job
            const mutData = await gql(
                `mutation($input: AnalysisInput!) { submitAnalysis(input: $input) { jobId status } }`,
                {
                    input: {
                        subjectId:  selected_subject,
                        moduleId:   selected_module,
                        markerIds:  [selected_marker],
                        method:     "TRAJECTORY",
                        timeframe: {
                            startTime: new Date(selected_start_time).toISOString(),
                            endTime:   new Date(selected_end_time).toISOString(),
                        },
                        trajectoryParams: {
                            polynomialDegree:    selected_polynomial_degree,
                            healthyMin:          selected_healthy_min,
                            healthyMax:          selected_healthy_max,
                            vulnerabilityMargin: selected_vulnerability_margin,
                        },
                    },
                }
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
</script>

<h2>Report Request Form</h2>

<form id="generate_report_form">
        <fieldset id="generate_timegraph_from_existing_data" class="input_form" style='background:lightgreen'>
        <legend style="font-size: large;">Select existing user</legend>
            <fieldset id="subject_selector">
                <legend>Select Subject</legend>
                <select bind:value={selected_subject}>
                    {#each subjects as subject}
                        <option value={subject}>{subject_names[subject] ?? subject}</option>
                    {/each}
                </select>
                <p>(Selected: {selected_subject})</p>
                <button type='button' onclick={() => loadSubjectProfile(selected_subject)}>Show selected user profile</button>
            </fieldset>

            <fieldset id="module_selector">
                <legend>Select Module</legend>
                <select bind:value={selected_module} disabled={!selected_subject} onchange={onModuleChange}>
                    <option value="">-- select module --</option>
                    {#each modules as module}
                        <option value={module.module_id}>{module.module_name || module.module_id}</option>
                    {/each}
                </select>
                <p>(Selected: {selected_module})</p>
            </fieldset>

            <fieldset id="marker_selector">
                <legend>Select Marker</legend>
                <select bind:value={selected_marker} disabled={!selected_module} onchange={loadZoneReference}>
                    <option value="">-- select marker --</option>
                    {#each markers as marker}
                        <option value={marker.marker_id}>{marker.marker_name || marker.marker_id}</option>
                    {/each}
                </select>
                <p>(Selected: {selected_marker})</p>
            </fieldset>

            <fieldset id="timeframe_selector">
                <legend>Select timeframe</legend>
                <div>
                    <label for="starttime">From:</label>
                    <input id="starttime" type="datetime-local" bind:value={selected_start_time} required />
                    <p>(Selected: {selected_start_time})</p>
                </div>
                <div>
                    <label for="endtime">To:</label>
                    <input id="endtime" type="datetime-local" bind:value={selected_end_time} required />
                    <p>(Selected: {selected_end_time})</p>
                </div>
            </fieldset>

            <fieldset name="polynomial_degree_selector">
                <legend>Select polynomial degree</legend>
                <label for="polynomial_degree_selector"></label>
                <input id="polynomial_degree_selector" type="range" min="1" max="5" step="1" bind:value={selected_polynomial_degree}/>
                <p>(Selected: {selected_polynomial_degree})</p>
            </fieldset>

            <fieldset class="zone_boundaries_input">
                <legend>Select zone boundaries</legend>

                <fieldset>
                    <label for="healthy_min_selector">Healthy minimum:</label>
                    <input id="healthy_min_selector" type="number" bind:value={selected_healthy_min} required/>
                    <p>(Selected: {selected_healthy_min})</p>
                </fieldset>

                <fieldset>
                    <label for="healthy_max_selector">Healthy maximum:</label>
                    <input id="healthy_max_selector" type="number" bind:value={selected_healthy_max} required/>
                    <p>(Selected: {selected_healthy_max})</p>
                </fieldset>

                <fieldset>
                    <label for="vulnerability_margin_selector">Vulnerability margin:</label>
                    <input id="vulnerability_margin_selector" type="number" bind:value={selected_vulnerability_margin} required/>
                    <p>(Selected: {selected_vulnerability_margin})</p>
                </fieldset>
                {#if zone_reference_note}<p id="zone_reference_note">{zone_reference_note}</p>{/if}
            </fieldset>

            <button type="button" onclick={submitTimegraphRequest} disabled={submitting}>
                {submitting ? "Working..." : "Request report"}
            </button>
            {#if submitStatus}<p>{submitStatus}</p>{/if}
        </fieldset>
</form>

<br>

<div style="border: 1px solid black; background:lightyellow">
  <h4>Selected profile:</h4>
    {JSON.stringify(subject_profile)}
 </div>  

<style>
    .input_form {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        align-items: start;
    }

    .zone_boundaries_input {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        align-items: start;
    }

    input:focus, select:focus {
        background-color: aqua;
    }

    #timeframe_selector {
        display:grid;
    }
</style>
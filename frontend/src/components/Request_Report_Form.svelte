<script>
    let loading = false;

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
        const response = await fetch("http://localhost:8000/subjects");
        subjects = await response.json();
        // fetch profile of each subject
        for (const subject of subjects) {
            const res = await fetch(`http://localhost:8000/subjects/${subject}/profile`);
            const profile = await res.json();
            if (profile.first_name && profile.last_name){
                subject_names[subject] = profile.first_name + " " + profile.last_name + " // ID: (" + profile.subject_id + ")";
            }          
        }
        loading = false;
    }

    async function loadSubjectProfile(subjectID) {
        loading = true;
        try {
            const response = await fetch(`http://localhost:8000/subjects/${subjectID}/profile`);
            subject_profile = await response.json();
        } catch (error) {
            console.error("Failed to fetch profile:", error);
        } finally {
            loading = false
        }
    }

    async function loadModules() {
        loading = true;
        const response = await fetch("http://localhost:8000/modules");
        const data = await response.json();
        modules = data.modules;                                                 // registry returns { modules: [...] }
        loading = false;
    }

    function onModuleChange() {
        const module = modules.find(m => m.module_id === selected_module);
        markers = module ? module.markers : [];                                 // update available markers when module changes
        selected_marker = "";
    }

    async function loadZoneReference() {
        if (!selected_subject || !selected_module || !selected_marker) return;
        try {
            const res = await fetch(`http://localhost:8000/subjects/${selected_subject}/zone-reference/${selected_module}/${selected_marker}`);
            if (!res.ok) { zone_reference_note = null; return; }
            const data = await res.json();
            selected_healthy_min = data.healthy_min;
            selected_healthy_max = data.healthy_max;
            selected_vulnerability_margin = data.vulnerability_margin;
            zone_reference_note = data.note;
        } catch (error) {
            console.error("Failed to fetch zone reference:", error);
        }
    }

    async function submitTimegraphRequest() {
        const payload = {                                                       // matches the pydantic request model from routes.py
            subject_id: selected_subject,
            module_id: selected_module,
            marker_id: selected_marker,
            timeframe: {
                start_time: new Date(selected_start_time).toISOString(),
                end_time: new Date(selected_end_time).toISOString()
            },
            zone_boundaries: {
                healthy_min: selected_healthy_min,
                healthy_max: selected_healthy_max,
                vulnerability_margin: selected_vulnerability_margin
            },
            fitting: {
                polynomial_degree: selected_polynomial_degree
            }
        };
        try {
            const response = await fetch("http://localhost:8000/timegraph", {   // sends the payload to the backend
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify(payload)
            });
            const report = await response.json();

            localStorage.setItem("timegraph_report", JSON.stringify(report));
            window.open("http://localhost:5173/#timegraph", "_blank");
        } catch (error) {
            console.error("Failed to submit timegraph request:", error);
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
                        <option value={module.module_id}>{module.module_id}</option>
                    {/each}
                </select>
                <p>(Selected: {selected_module})</p>
            </fieldset>

            <fieldset id="marker_selector">
                <legend>Select Marker</legend>
                <select bind:value={selected_marker} disabled={!selected_module} onchange={loadZoneReference}>
                    <option value="">-- select marker --</option>
                    {#each markers as marker}
                        <option value={marker.marker_id}>{marker.marker_id}</option>
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

            <button type="button" onclick={submitTimegraphRequest}>Request report</button>
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
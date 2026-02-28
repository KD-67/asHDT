<script>
    import { createEventDispatcher } from "svelte";
    const dispatch = createEventDispatcher();

    let loading = false;

    let subjects = [];
    let subject_profile = {};
    let subject_names = {};
    let modules = [];
    let markers = [];



    let selected_subject = "subject_001";
    let selected_module = "fitness";
    let selected_marker = "vo2max";
    let selected_start_time = "2026-01-01T00:00";
    let selected_end_time = "2026-03-31T00:00";
    let selected_polynomial_degree = 2;
    let selected_healthy_min = 0;
    let selected_healthy_max = 1;
    let selected_vulnerability_margin = 1;

    let new_last_name = "";
    let new_first_name = "";
    let new_sex = "";
    let new_dob = [];
    let new_email = "";
    let new_phone = "";
    let new_notes = "";

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
        modules = data.modules;                  // registry returns { modules: [...] }
        loading = false;
    }

    function onModuleChange() {
        const module = modules.find(m => m.module_id === selected_module);
        markers = module ? module.markers : [];  // update markers when module changes
        selected_marker = "";
    }

    async function submitTimegraphRequest() {
        const payload = {
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
            const response = await fetch("http://localhost:8000/timegraph", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify(payload)
            });
            const report = await response.json();

            console.log("Report:", report);
            sessionStorage.setItem("timegraph_report", JSON.stringify(report));
            dispatch("reportSubmitted");  // This triggers the navigation in App.svelte
        } catch (error) {
            console.error("Failed to submit timegraph request:", error);
        }
    }

    loadSubjects();
    loadModules();
</script>

<form id="generate_report_form">
    <fieldset id="generate_timegraph_from_existing_data" style='background:lightgreen'>
    <legend style="font-size: large;">Select existing user</legend>
        <fieldset id="subject_selector">
            <legend>Select Subject</legend>
            <select bind:value={selected_subject}>
                {#each subjects as subject}
                    <option value={subject}>{subject_names[subject] ?? subject}</option>
                {/each}
            </select>
            <button type='button' on:click={() => loadSubjectProfile(selected_subject)}>Show selected user profile</button>
        </fieldset>

        <fieldset id="module_selector">
            <legend>Select Module</legend>
            <select bind:value={selected_module} disabled={!selected_subject} on:change={onModuleChange}>
                <option value="">-- select module --</option>
                {#each modules as module}
                    <option value={module.module_id}>{module.module_id}</option>
                {/each}
            </select>
        </fieldset>

        <fieldset id="marker_selector">
            <legend>Select Marker</legend>
            <select bind:value={selected_marker} disabled={!selected_module}>
                <option value="">-- select marker --</option>
                {#each markers as marker}
                    <option value={marker.marker_id}>{marker.marker_id}</option>
                {/each}
            </select>
        </fieldset>

        <fieldset id="timeframe_selector">
            <legend>Select timeframe</legend>
            <label for="starttime">From</label>
            <input id="starttime" type="datetime-local" bind:value={selected_start_time} required />
            <label for="endtime">To</label>
            <input id="endtime" type="datetime-local" bind:value={selected_end_time} required />
        </fieldset>

        <fieldset name="polynomial_degree_selector">
            <legend>Select polynomial degree</legend>
            <label for="polynomial_degree_selector"></label>
            <input id="polynomial_degree_selector" type="range" min="1" max="5" step="1" bind:value={selected_polynomial_degree}/>
            <p>{selected_polynomial_degree}</p>
        </fieldset>

        <fieldset>
            <legend>Select zone boundaries</legend>
            <label for="healthy_min_selector">Healthy minimum:</label>
            <input id="healthy_min_selector" type="number" bind:value={selected_healthy_min} required/>

            <label for="healthy_max_selector">Healthy maximum:</label>
            <input id="healthy_max_selector" type="number" bind:value={selected_healthy_max} required/>

            <label for="vulnerability_margin_selector">Vulnerability margin:</label>
            <input id="vulnerability_margin_selector" type="number" bind:value={selected_vulnerability_margin} required/>
        </fieldset>

        <button type="button" on:click={submitTimegraphRequest}>Request report</button>
    </fieldset>
</form>

<br>

<div style="border: 1px solid black; background:lightyellow">
  <h4>Selected profile:</h4>
    {JSON.stringify(subject_profile)}
 </div>  

  <br>

<form id="generate_new_subject_form">

    <fieldset style='background:lightblue'>
        <legend style="font-size: large;">New user</legend>
        
        <label for="last_name">Last name</label>
        <input type="text" id="last_name" bind:value={new_last_name}>
        
        <label for="first_name">First name</label>
        <input type="text" id="first_name" bind:value={new_first_name}>
       
        <fieldset name="sex_declarer">
            <legend>Sex</legend>

            <label for="sex_f">Female</label>
            <input type="radio" name="sex" id="sex_f" value="F" bind:group={new_sex}>
                <br>
            <label for="sex_m">Male</label>
            <input type="radio" name="sex" id="sex_m" value="M" bind:group={new_sex}>
                <br>
            <label for="sex_u">Undeclared</label>
            <input type="radio" name="sex" id="sex_u" value="Undeclared" bind:group={new_sex}>
        </fieldset>

        <label for="dob">Date of birth</label>
        <input type="date" id="dob" bind:value={new_dob}>

        <label for="email">Email address</label>
        <input type="text" id="email" bind:value={new_email}>
        
        <label for="phone">Phone number</label>
        <input type="number" id="phone" bind:value={new_phone}>

        <label for="notes">Notes</label>
        <input type="textarea" id="notes" bind:value={new_notes}>
        
        <button type="button">Create new user</button>
    </fieldset>

</form>

<style>
    
</style>
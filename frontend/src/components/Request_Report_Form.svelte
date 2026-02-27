<script>
    let loading = false;

    let subjects = [];
    let subject_profile = {};
    let subject_names = {};
    let modules = [];
    let markers = [];

    let selected_subject = "";
    let selected_module = "";
    let selected_marker = "";

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



    loadSubjects();
    loadModules();

    loadSubjectProfile("subject_001");
</script>

<form>
    <fieldset>
        <legend>New user</legend>
        
        <label for="last_name">Last name</label>
        <input type="text" name="last_name">
        
        <label for="first_name">First name</label>
        <input type="text" name="first_name">
       
        <fieldset>
            <legend>Sex</legend>

            <label for="sex_f">Female</label>
            <input type="radio" name="sex_f">

            <label for="sex_m">Male</label>
            <input type="radio" name="sex_m">
        </fieldset>

        <label for="dob_name">Date of birth</label>
        <input type="date" name="dob">

        <label for="email">Email address</label>
        <input type="text" name="email">
        
        <label for="tel">Phone number</label>
        <input type="number" name="phone">

        <label for="notes">Notes</label>
        <input type="textarea" name="notes">
        
        <button>Create new user</button>
    </fieldset>


    <fieldset>
    <legend>Select existing user</legend>
        <fieldset>
            <legend>Select Subject</legend>
            <select bind:value={selected_subject}>
                {#each subjects as subject}
                    <option value={subject}>{subject_names[subject] ?? subject}</option>
                {/each}
            </select>
        </fieldset>

        <fieldset>
            <legend>Select Module</legend>
            <select bind:value={selected_module} on:change={onModuleChange}>
                <option value="">-- select module --</option>
                {#each modules as module}
                    <option value={module.module_id}>{module.module_id}</option>
                {/each}
            </select>
        </fieldset>

        <fieldset>
            <legend>Select Marker</legend>
            <select bind:value={selected_marker} disabled={!selected_module}>
                <option value="">-- select marker --</option>
                {#each markers as marker}
                    <option value={marker.marker_id}>{marker.marker_id}</option>
                {/each}
            </select>
        </fieldset>
    </fieldset>
</form>

  <div>{JSON.stringify(subject_profile)}</div>  

<style>
    
</style>
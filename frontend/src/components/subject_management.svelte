<script>
    import { onMount } from "svelte";

    const BASE_URL = "http://localhost:8000";

    // Mode: "create" or "edit"
    let mode = $state("create");

    // Subject list for edit mode
    let subjects = $state([]);
    let selectedSubject = $state("");

    // Form fields
    let first_name = $state("");
    let last_name = $state("");
    let sex = $state("");
    let dob = $state("");
    let email = $state("");
    let phone = $state("");
    let notes = $state("");

    let statusMessage = $state("");
    let statusOk = $state(true);

    onMount(async () => {
        const res = await fetch(`${BASE_URL}/subjects`);
        subjects = await res.json();
    });

    async function loadProfile(subject_id) {
        const res = await fetch(`${BASE_URL}/subjects/${subject_id}/profile`);
        if (!res.ok) { statusMessage = "Failed to load profile."; statusOk = false; return; }
        const p = await res.json();
        first_name = p.first_name ?? "";
        last_name  = p.last_name  ?? "";
        sex        = p.sex        ?? "";
        dob        = p.dob        ?? "";
        email      = p.email      ?? "";
        phone      = p.phone      ?? "";
        notes      = p.notes      ?? "";
        statusMessage = "";
    }

    function clearFields() {
        first_name = ""; last_name = ""; sex = ""; dob = "";
        email = ""; phone = ""; notes = ""; statusMessage = "";
    }

    function switchMode(newMode) {
        mode = newMode;
        selectedSubject = "";
        clearFields();
    }

    async function handleCreate() {
        const res = await fetch(`${BASE_URL}/subjects`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ first_name, last_name, sex, dob, email, phone, notes }),
        });
        if (res.ok) {
            const data = await res.json();
            statusMessage = `Subject created: ${data.subject_id}`;
            statusOk = true;
            clearFields();
            const updated = await fetch(`${BASE_URL}/subjects`);
            subjects = await updated.json();
        } else {
            const err = await res.json();
            statusMessage = `Error: ${err.detail ?? res.statusText}`;
            statusOk = false;
        }
    }

    async function handleEdit() {
        const res = await fetch(`${BASE_URL}/subjects/${selectedSubject}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ first_name, last_name, sex, dob, email, phone, notes }),
        });
        if (res.ok) {
            statusMessage = "Profile updated.";
            statusOk = true;
        } else {
            const err = await res.json();
            statusMessage = `Error: ${err.detail ?? res.statusText}`;
            statusOk = false;
        }
    }

    async function handleDelete() {
        if (!confirm(`Delete ${selectedSubject}? Their data will be moved to deleted_subjects/.`)) return;
        const res = await fetch(`${BASE_URL}/subjects/${selectedSubject}`, { method: "DELETE" });
        if (res.ok) {
            statusMessage = `${selectedSubject} deleted.`;
            statusOk = true;
            selectedSubject = "";
            clearFields();
            const updated = await fetch(`${BASE_URL}/subjects`);
            subjects = await updated.json();
        } else {
            const err = await res.json();
            statusMessage = `Error: ${err.detail ?? res.statusText}`;
            statusOk = false;
        }
    }
</script>

<main>
    <div id="main_container">

        <div id="mode_toggle">
            <button type="button" class:active={mode === "create"} onclick={() => switchMode("create")}>Create new</button>
            <button type="button" class:active={mode === "edit"}   onclick={() => switchMode("edit")}>Edit existing</button>
        </div>

        {#if mode === "edit"}
        <div id="subject_selector">
            <label for="subject_select">Select subject:</label>
            <select id="subject_select" bind:value={selectedSubject} onchange={() => loadProfile(selectedSubject)}>
                <option value="">-- select --</option>
                {#each subjects as s}
                    <option value={s}>{s}</option>
                {/each}
            </select>
        </div>
        {/if}

        <form id="subject_form">
            <h2>{mode === "create" ? "Create new user:" : "Edit user:"}</h2>

            <label for="last_name">Last name</label>
            <input type="text" id="last_name" bind:value={last_name}>

            <label for="first_name">First name</label>
            <input type="text" id="first_name" bind:value={first_name}>

            <fieldset name="sex_declarer">
                <legend>Sex</legend>
                <input type="radio" name="sex" id="sex_f" value="F" bind:group={sex}>
                <label for="sex_f">Female</label>
                    <br>
                <input type="radio" name="sex" id="sex_m" value="M" bind:group={sex}>
                <label for="sex_m">Male</label>
                    <br>
                <input type="radio" name="sex" id="sex_u" value="Undeclared" bind:group={sex}>
                <label for="sex_u">Undeclared</label>
            </fieldset>

            <label for="dob">Date of birth</label>
            <input type="date" id="dob" bind:value={dob}>

            <label for="email">Email address</label>
            <input type="text" id="email" bind:value={email}>

            <label for="phone">Phone number</label>
            <input type="text" id="phone" bind:value={phone}>

            <label for="notes">Notes</label>
            <input type="textarea" id="notes" bind:value={notes}>
        </form>

        <div id="preview_container">
            <h4>Preview:</h4>
            <p>Name: {last_name} {first_name}</p>
            <p>Sex: {sex}</p>
            <p>DOB: {dob}</p>
            <p>Email: {email}</p>
            <p>Phone: {phone}</p>
            <p>Notes: {notes}</p>

            {#if mode === "create"}
                <button type="button" onclick={handleCreate}>Create new user</button>
            {:else}
                <button type="button" onclick={handleEdit}  disabled={!selectedSubject}>Save changes</button>
                <button type="button" onclick={handleDelete} disabled={!selectedSubject} id="delete_btn">Delete subject</button>
            {/if}

            {#if statusMessage}
                <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
            {/if}
        </div>

    </div>
</main>

<style>
    #main_container {
        border: 1px solid black;
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        padding: 5px;
    }

    #mode_toggle {
        width: 100%;
        display: flex;
        gap: 5px;
    }

    #mode_toggle button.active {
        font-weight: bold;
        text-decoration: underline;
    }

    #subject_selector {
        width: 100%;
    }

    form {
        background-color: lightblue;
        padding: 15px 10px;
        border: 1px solid black;
    }

    fieldset {
        border: 1px solid black;
    }

    #preview_container {
        border: 1px solid black;
        margin: 5px;
        padding: 3px;
    }

    #delete_btn {
        background-color: rgb(255, 180, 180);
        margin-top: 5px;
        display: block;
    }

    #status_msg {
        margin-top: 8px;
        font-weight: bold;
    }

    #status_msg.error {
        color: red;
    }
</style>

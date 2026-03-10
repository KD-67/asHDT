<script>
    let cardColor = '#d0e8ff';
    let markerRowColor = 'aliceblue';
    let addBtnColor = 'rgb(114, 231, 114)';
    let viewBtnColor = 'rgb(209, 162, 252)';
    let editBtnColor = 'aqua';
    let deleteBtnColor = 'rgb(255, 180, 180)';
    let zoneRefBtnColor = 'rgb(252, 217, 18)';

    import ViewIcon from "../assets/view_icon.svg?raw";
    import AddIcon from "../assets/add_icon.svg?raw";
    import EditIcon from "../assets/edit_icon.svg?raw";
    import DeleteIcon from "../assets/delete_icon.svg?raw";
    import LevelsIcon from "../assets/levels_icon.svg?raw";

    import { onMount } from "svelte";

    const BASE_URL = "http://localhost:8000";

    // Mode: "view" or "add"
    let mode = $state("view");

    // Subject list for view mode (array of objects)
    let subjects = $state([]);

    // Inline edit state
    let editingSubject = $state(null);
    let editSubject = $state({});

    // Add mode form fields
    let first_name = $state("");
    let last_name = $state("");
    let sex = $state("");
    let dob = $state("");
    let email = $state("");
    let phone = $state("");
    let notes = $state("");

    let statusMessage = $state("");
    let statusOk = $state(true);

    onMount(loadSubjects);

    async function loadSubjects() {
        const res = await fetch(`${BASE_URL}/subjects`);
        if (!res.ok) return;
        const ids = await res.json();

        // Fetch each subject's profile and merge into objects
        const subjectObjects = [];
        for (const id of ids) {
            const profileRes = await fetch(`${BASE_URL}/subjects/${id}/profile`);
            if (profileRes.ok) {
                const profile = await profileRes.json();
                subjectObjects.push({
                    subject_id: id,
                    first_name: profile.first_name ?? "",
                    last_name: profile.last_name ?? "",
                    sex: profile.sex ?? "",
                    dob: profile.dob ?? "",
                    email: profile.email ?? "",
                    phone: profile.phone ?? "",
                    notes: profile.notes ?? "",
                });
            }
        }
        subjects = subjectObjects;
    }

    function setStatus(msg, ok = true) {
        statusMessage = msg;
        statusOk = ok;
    }

    function toggleEditSubject(s) {
        if (editingSubject === s.subject_id) {
            editingSubject = null;
            editSubject = {};
        } else {
            editingSubject = s.subject_id;
            editSubject = { ...s };
        }
        statusMessage = "";
    }

    async function handleEditSubject(subject_id) {
        const res = await fetch(`${BASE_URL}/subjects/${subject_id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                first_name: editSubject.first_name,
                last_name: editSubject.last_name,
                sex: editSubject.sex,
                dob: editSubject.dob,
                email: editSubject.email,
                phone: editSubject.phone,
                notes: editSubject.notes,
            }),
        });
        if (res.ok) {
            setStatus(`Subject "${subject_id}" updated.`);
            editingSubject = null;
            await loadSubjects();
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }

    async function handleDeleteSubject(subject_id) {
        if (!confirm(`Delete ${subject_id}? Their data will be moved to deleted_subjects/.`)) return;
        const res = await fetch(`${BASE_URL}/subjects/${subject_id}`, { method: "DELETE" });
        if (res.ok) {
            setStatus(`Subject "${subject_id}" deleted.`);
            await loadSubjects();
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }

    async function handleCreate() {
        const res = await fetch(`${BASE_URL}/subjects`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ first_name, last_name, sex, dob, email, phone, notes }),
        });
        if (res.ok) {
            const data = await res.json();
            setStatus(`Subject created: ${data.subject_id}`);
            first_name = ""; last_name = ""; sex = ""; dob = "";
            email = ""; phone = ""; notes = "";
            mode = "view";
            await loadSubjects();
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }
</script>

<main>
    <div id="main_container">

        <div id="mode_toggle">
            <button type="button" style="--viewBtnColor: {viewBtnColor}" class:active={mode === "view"} onclick={() => { mode = "view"; statusMessage = ""; }} id="viewedit_sub_btn">{@html ViewIcon}</button>
            <button type="button" style="--addBtnColor: {addBtnColor}" class:active={mode === "add"} onclick={() => { mode = "add"; statusMessage = ""; }} id="add_sub_btn">{@html AddIcon}</button>

            {#if statusMessage}
                <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
            {/if}
        </div>

        <div id="viewbox">
            <!-- VIEW MODE: Subject cards -->
            {#if mode === "view"}
                {#if subjects.length === 0}
                    <p>No subjects found.</p>
                {/if}
                {#each subjects as s}
                    <div class="module_card" style="--cardColor: {cardColor}">
                        <div id="card_header_container">
                            <h2 class="card_header">{s.last_name}, {s.first_name}</h2>
                        </div>

                        <div id="card_actions">
                            <button style="--editBtnColor: {editBtnColor}" type="button" id="edit_btn" onclick={(e) => { e.stopPropagation(); toggleEditSubject(s); }}>
                                {@html EditIcon}
                            </button>
                            <button style="--deleteBtnColor: {deleteBtnColor}" type="button" id="delete_btn" onclick={(e) => { e.stopPropagation(); handleDeleteSubject(s.subject_id); }}>
                                {@html DeleteIcon}
                            </button>
                        </div>

                        <span class="card_description">{s.sex} · DOB: {s.dob}</span>

                        {#if editingSubject === s.subject_id}
                            <div class="inline_form subject_edit_form" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
                                <label>Last name <input type="text" bind:value={editSubject.last_name}></label>
                                <label>First name <input type="text" bind:value={editSubject.first_name}></label>
                                <label>Sex
                                    <select bind:value={editSubject.sex}>
                                        <option value="F">F</option>
                                        <option value="M">M</option>
                                        <option value="Undeclared">Undeclared</option>
                                    </select>
                                </label>
                                <label>DOB <input type="date" bind:value={editSubject.dob}></label>
                                <label>Email <input type="text" bind:value={editSubject.email}></label>
                                <label>Phone <input type="text" bind:value={editSubject.phone}></label>
                                <label>Notes <input type="text" bind:value={editSubject.notes}></label>
                                <button type="button" onclick={() => handleEditSubject(s.subject_id)}>Save</button>
                                <button type="button" onclick={() => toggleEditSubject(s)}>Cancel</button>
                            </div>
                        {/if}
                    </div>
                {/each}
            {/if}

            <!-- ADD MODE: Form + Preview -->
            {#if mode === "add"}
                <form id="new_subject_form">
                    <h2>Add new subject</h2>
                    <label for="add_last_name">Last name</label>
                    <input type="text" id="add_last_name" bind:value={last_name}>

                    <label for="add_first_name">First name</label>
                    <input type="text" id="add_first_name" bind:value={first_name}>

                    <label for="add_sex">Sex</label>
                    <select id="add_sex" bind:value={sex}>
                        <option value="">-- select --</option>
                        <option value="F">Female</option>
                        <option value="M">Male</option>
                        <option value="Undeclared">Undeclared</option>
                    </select>

                    <label for="add_dob">Date of birth</label>
                    <input type="date" id="add_dob" bind:value={dob}>

                    <label for="add_email">Email address</label>
                    <input type="text" id="add_email" bind:value={email}>

                    <label for="add_phone">Phone number</label>
                    <input type="text" id="add_phone" bind:value={phone}>

                    <label for="add_notes">Notes</label>
                    <input type="text" id="add_notes" bind:value={notes}>

                    <button style="--addBtnColor: {addBtnColor}" type="button" id="add_new_subject_btn" onclick={handleCreate}>{@html AddIcon}</button>
                </form>

                <div id="preview_container">
                    <h4>Preview:</h4>
                    <p>Name: {last_name} {first_name}</p>
                    <p>Sex: {sex}</p>
                    <p>DOB: {dob}</p>
                    <p>Email: {email}</p>
                    <p>Phone: {phone}</p>
                    <p>Notes: {notes}</p>
                </div>
            {/if}
        </div>

    </div>
</main>

<style>

    * {
        color: #422800;
        margin: 0;
        padding: 0;
    }

    /* BUTTONS */
    button {
        border-radius: 30px;
        margin: 0.75rem 0.25rem;
        padding: 0.25rem 0.75rem;
        box-shadow: 5px 5px 0px #422800;
        cursor: pointer;
        font-size: 10px;
        color: #422800;
    }

    button :global(svg) {
        overflow: visible;
        width: 20px;
        height: 20px;
        color: #422800;
    }

    button:hover {
        transform: scale(102%);
        font-weight: 550;
        border: 2px solid black;
    }

    button:active {
        box-shadow: #422800 2px 2px 0 0;
        transform: translate(2px, 2px);
    }

    #viewedit_sub_btn {
        background-color: var(--viewBtnColor);
    }

    #add_sub_btn {
        background-color: var(--addBtnColor);
    }

    #delete_btn {
        background-color: var(--deleteBtnColor);
    }

    #edit_btn {
        background-color: var(--editBtnColor);
    }

    /* MAIN DIV */
    #main_container {
        border: 1px solid black;
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        gap: 5px;
        padding: 5px;
    }

    #mode_toggle {
        width: 100%;
        display: flex;
        gap: 5px;
        align-items: center;
    }

    #mode_toggle button.active {
        font-weight: bold;
        text-decoration: underline;
    }

    #status_msg {
        width: 100%;
        font-weight: bold;
    }

    #status_msg.error {
        color: red;
    }

    /* VIEW MODE */
    #viewbox {
        width: 50vw;
        display: flex;
        flex-direction: column;
    }

    .module_card {
        display: grid;
        border: 2px solid #422800;
        border-radius: 0.5rem;
        background-color: var(--cardColor);
        box-shadow: 5px 5px 0px #422800;
        margin: 5px;
        padding: 8px;
        grid-template-rows: auto auto auto auto;
        grid-template-columns: 50% 50%;
    }

    .module_card:hover {
        transform: scale(1.02);
        cursor: pointer;
    }

    #card_header_container {
        grid-area: 1 / 1 / 2 / 2;
        padding: 0.7rem 0;
    }

    .card_header {
        margin: 0;
        padding: 0;
    }

    .card_description {
        grid-area: 2 / 1 / 3 / 3;
        color: #444;
        padding: 0.25rem 0;
        font-size: 18px;
    }

    #card_actions {
        grid-area: 1 / 2 / 2 / 3;
        display: flex;
        justify-content: flex-end;
        gap: 5px;
    }

    /* INLINE FORM */
    .inline_form {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 5px;
        border: 2px solid #422800;
        border-radius: 0.5rem;
        background-color: lightyellow;
        padding: 8px;
        margin: 5px 0;
        box-shadow: 5px 5px 0px #422800;
        grid-area: 3 / 1 / 4 / 3;
    }

    .subject_edit_form {
        flex-direction: column;
        align-items: flex-start;
    }

    .subject_edit_form label {
        display: flex;
        flex-direction: column;
        margin-bottom: 5px;
    }

    .subject_edit_form input,
    .subject_edit_form select {
        margin-top: 3px;
        padding: 4px;
        border: 1px solid #422800;
        border-radius: 3px;
    }

    /* ADD MODE */
    form {
        display: grid;
        border: 2px solid #422800;
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px #422800;
        margin: 5px;
        padding: 15px;
        gap: 10px;
        grid-template-columns: 1fr 1fr;
    }

    form h2 {
        grid-column: 1 / -1;
    }

    form label {
        display: flex;
        flex-direction: column;
    }

    form input,
    form select {
        margin-top: 5px;
        padding: 5px;
        border: 1px solid #422800;
        border-radius: 3px;
    }

    #add_new_subject_btn {
        grid-column: 1 / -1;
        justify-self: end;
    }

    #preview_container {
        border: 2px solid #422800;
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px #422800;
        margin: 5px;
        padding: 15px;
    }

</style>

<script>
    let textColor = '#422800';
    let borderColor = '#422800';
    let cardColor = '#d0e8ff';
    let cardSectionColor = 'aliceblue';
    let addBtnColor = 'rgb(114, 231, 114)';
    let viewBtnColor = 'rgb(209, 162, 252)';
    let editBtnColor = '#4CF3FC';
    let deleteBtnColor = 'rgb(255, 180, 180)';

    import ViewIcon from "../assets/view_icon.svg?raw";
    import AddIcon from "../assets/add_icon.svg?raw";
    import EditIcon from "../assets/edit_icon.svg?raw";
    import DeleteIcon from "../assets/delete_icon.svg?raw";
    import GenericUserIcon from "../assets/generic_user_icon.svg?raw";
    import CancelIcon from "../assets/cancel_icon.svg?raw";

    import { onMount } from "svelte";

    const BASE_URL = "http://localhost:8000";

    // Mode: "view" or "add"
    let mode = $state("view");

    // Subject list for view mode (array of objects)
    let subjects = $state([]);

    // Expanded subject (for showing profile details)
    let expandedSubject = $state(null);

    // Inline edit state
    let editingSubject = $state(null);
    let editSubject = $state({ first_name: "", last_name: "", sex: "", dob: "", email: "", phone: "", notes: "", created_at: "" });

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
                    created_at: profile.created_at ?? "",
                });
            }
        }
        subjects = subjectObjects;
    }

    function formatDate(iso) {
        if (!iso) return '—';
        return new Date(iso).toLocaleString(undefined, { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function setStatus(msg, ok = true) {
        statusMessage = msg;
        statusOk = ok;
    }

    function collapseSubject() {
        expandedSubject = null;
        editingSubject = null;
        editSubject = { first_name: "", last_name: "", sex: "", dob: "", email: "", phone: "", notes: "", created_at: "" };
    }

    function toggleEditSubject(s) {
        if (editingSubject === s.subject_id) {
            editingSubject = null;
            editSubject = { first_name: "", last_name: "", sex: "", dob: "", email: "", phone: "", notes: "", created_at: "" };
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

<main style="--textColor: {textColor}; --borderColor: {borderColor}">
    <div id="main_container">

        <div id="mode_toggle">
            <button type="button" style="--viewBtnColor: {viewBtnColor}" class:active={mode === "view"} onclick={() => { mode = "view"; statusMessage = ""; }} class="view_btn">{@html ViewIcon}</button>
            <button type="button" style="--addBtnColor: {addBtnColor}" class:active={mode === "add"} onclick={() => { mode = "add"; statusMessage = ""; }} class="add_btn">{@html AddIcon}</button>

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
                    <div class="module_card" role="button" style="--cardColor: {cardColor}" tabindex="0" onclick={() => expandedSubject === s.subject_id ? collapseSubject() : (collapseSubject(), expandedSubject = s.subject_id)} onkeydown={(e) => e.key === 'Enter' && (expandedSubject === s.subject_id ? collapseSubject() : (collapseSubject(), expandedSubject = s.subject_id))}>
                        <div id="card_header_container">
                            <div class="card_icon_container">
                                <div class="card_icon">{@html GenericUserIcon}</div>
                            </div>
                            <h2 class="card_header">{s.last_name}, {s.first_name}</h2> 
                        </div>

                        <div id="card_actions">
                            <button style="--viewBtnColor: {viewBtnColor}" type="button" class="view_btn" id="view_profile_btn">
                                {@html ViewIcon}
                            </button>
                            <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={(e) => { e.stopPropagation(); toggleEditSubject(s); }}>
                                {@html EditIcon}
                            </button>
                            <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={(e) => { e.stopPropagation(); handleDeleteSubject(s.subject_id); }}>
                                {@html DeleteIcon}
                            </button>
                        </div>

                        <span class="card_description">
                            <p class="card_description_item"><strong>Sex: {s.sex}</strong></p>
                            <p class="card_description_item"><strong>·</strong></p>
                            <p class="card_description_item">Date of Birth: {formatDate(s.dob).slice(0,-12)}</p>
                        </span>

                        {#if expandedSubject === s.subject_id}
                            <div class="profile_section">
                                <p><strong>ID:</strong> {s.subject_id}</p>
                                <p><strong>Email:</strong> {s.email || '—'}</p>
                                <p><strong>Phone:</strong> {s.phone || '—'}</p>
                                <p><strong>Notes:</strong> {s.notes || '—'}</p>
                                <p><strong>Created:</strong> {formatDate(s.created_at)}</p>
                            </div>
                        {/if}

                        {#if editingSubject === s.subject_id}
                            <div class="subject_edit_form" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
                                <h3 class="edit_header">Edit</h3>
                                <label>Last name <input type="text" bind:value={editSubject.last_name}></label>
                                <label>First name <input type="text" bind:value={editSubject.first_name}></label>
                                <label>Sex
                                    <select bind:value={editSubject.sex}>
                                        <option value="F">F</option>
                                        <option value="M">M</option>
                                        <option value="Undeclared">Undeclared</option>
                                    </select>
                                </label>
                                <label>Date of Birth <input type="date" bind:value={editSubject.dob}></label>
                                <label>Email <input type="text" bind:value={editSubject.email}></label>
                                <label>Phone <input type="text" bind:value={editSubject.phone}></label>
                                <label>Notes <textarea class="edit_text" rows=5 bind:value={editSubject.notes}></textarea></label>
                                <div class="edit_btns_container">
                                    <button style="--addBtnColor: {addBtnColor}" class="add_btn" type="button" onclick={() => handleEditSubject(s.subject_id)}>{@html AddIcon}</button>
                                    <button style="--deleteBtnColor: {deleteBtnColor}" class="delete_btn" type="button" onclick={() => toggleEditSubject(s)}>{@html CancelIcon}</button>
                                </div>
                            </div>
                        {/if}
                    </div>
                {/each}
            {/if}

            <!-- ADD MODE: Form + Preview -->
            {#if mode === "add"}
                <form id="new_subject_form">
                    <h2>Add new subject</h2>
                    <label for="add_last_name">Last name
                        <input type="text" id="add_last_name" bind:value={last_name}>
                    </label>
                    
                    <label for="add_first_name">First name
                        <input type="text" id="add_first_name" bind:value={first_name}>
                    </label>
                    
                    <label for="add_sex">Sex
                        <select id="add_sex" bind:value={sex}>
                        <option value="">-- select --</option>
                        <option value="F">Female</option>
                        <option value="M">Male</option>
                        <option value="Undeclared">Undeclared</option>
                    </select>
                    </label>

                    <label for="add_dob">Date of birth
                        <input type="date" id="add_dob" bind:value={dob}>
                    </label>

                    <label for="add_email" >Email address
                        <input type="text" id="add_email" bind:value={email}>
                    </label>
                    
                    <label for="add_phone">Phone number
                        <input type="text" id="add_phone" bind:value={phone}>
                    </label>
                    
                    <label for="add_notes" id="add_notes_container">Notes
                        <textarea id="add_notes" bind:value={notes}></textarea>
                    </label>
                    
                    <div id="add_new_subject_btn_container">
                        <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" onclick={handleCreate}>{@html AddIcon}</button>
                    </div>
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
        color: var(--textColor);
        margin: 0;
        padding: 0;
    }

    /* BUTTONS */
    button {
        border-radius: 30px;
        margin: 0.75rem 0.25rem;
        padding: 0.25rem 0.75rem;
        box-shadow: 5px 5px 0px var(--textColor);
        cursor: pointer;
        font-size: 10px;
        color: var(--textColor);
    }

    button :global(svg) {
        overflow: visible;
        width: 20px;
        height: 20px;
        color: var(--textColor);
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

    .view_btn {
        background-color: var(--viewBtnColor);
    }

    .add_btn {
        background-color: var(--addBtnColor);
    }

    .delete_btn {
        background-color: var(--deleteBtnColor);
    }

    .edit_btn {
        background-color: var(--editBtnColor);
    }

    /* MAIN DIV */
    #main_container {
        border: 1px solid var(--borderColor);
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
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: var(--cardColor);
        box-shadow: 5px 5px 0px var(--borderColor);
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
        display: flex;
        justify-content: flex-start;
        /* align-items: center; */
        padding: 0.5rem 0.5rem;
    }

    .card_header {
        margin: 0 15px;
        padding: 0;
    }

    .card_icon_container {
        border: 2px solid var(--borderColor);
        border-radius: 50%;
        height: 30px;
        background-color: #fcf5ed;
        box-shadow: 5px 5px 0px var(--borderColor);
    }

    .card_icon {
      width: 30px;                                                                                
      height: 30px;
      border-radius: 50%;
      overflow: hidden;
      margin: 1px;
    }

    .card_icon :global(svg) {
        width: 100%;
        height: 100%;
    }

    .card_description {
        grid-area: 2 / 1 / 3 / 3;
        display: flex;
        justify-content: flex-start;
        color: #444;
        padding: 0.25rem 5px;
        font-size: 18px;
        gap: 10px;
    }

    #card_actions {
        grid-area: 1 / 2 / 2 / 3;
        display: flex;
        justify-content: flex-end;
        gap: 5px;
    }

    /* PROFILE SECTION */
    .profile_section {
        grid-area: 3 / 1 / 4 / 3;
        display: grid;
        border-top: 2px solid var(--borderColor);
        margin-top: 10px;
        padding-top: 8px;
        gap: 4px;
    }

    .profile_section p {
        font-size: 0.95em;
        padding: 2px 0;
    }

    /* INLINE FORM */
    .subject_edit_form {
        display: grid;
        grid-template-rows: auto auto auto auto auto;
        grid-template-columns: auto auto auto;
        gap: 5px;
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: lightyellow;
        padding: 8px;
        margin: 5px 0;
        box-shadow: 5px 5px 0px var(--borderColor);
        grid-area: 4 / 1 / 5 / 3;
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
        border: 1px solid var(--borderColor);
        border-radius: 3px;
    }

    .edit_header {
        grid-area: 1 / 1 / 2 / 4;
    }

    .edit_text {
        grid-area: 4 / 1 / 6 / 2;
    }

    .edit_btns_container {
        grid-area: 5 / 3 / 6 / 4;
        display: flex;
        justify-content: flex-end;
    }

    /* ADD MODE */
    #new_subject_form {
        display: grid;
        grid-template-columns: auto auto;
        grid-template-rows: auto auto auto auto auto auto;
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px var(--borderColor);
        margin: 5px;
        padding: 15px;
        gap: 10px;
        grid-template-columns: 1fr 1fr;
    }

    #new_subject_form h2 {
        grid-area: 1 / 1 / 2 / 3;
    }

    #new_subject_form label {
        display: flex;
        flex-direction: column;
    }

    #new_subject_form input,
    #new_subject_form select,
    #new_subject_form textarea {
        margin-top: 5px;
        padding: 5px;
        border: 1px solid var(--borderColor);
        border-radius: 3px;
    }

    #add_notes_container {
        grid-area: 5 / 1 / 6 / 3;
    }

    #add_new_subject_btn_container {
        grid-area: 6 / 2 / 7 / 3;
        display: flex;
        justify-content: flex-end;
    }

    #preview_container {
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px var(--borderColor);
        margin: 5px;
        padding: 15px;
    }

</style>

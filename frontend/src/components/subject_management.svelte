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
    import { createSubject, updateSubject, deleteSubject, fetchDatasets, fetchDatapoints, addDatapoint, updateDatapoint, deleteDatapoint, uploadDatapoint, deleteDataset } from "../lib/api.js";
    import { appState, ensureSubjectsLoaded, ensureModulesLoaded, storeAddSubject, storeUpdateSubject, storeRemoveSubject } from "../lib/stores.svelte.js";

    // Mode: "view" or "add"
    let mode = $state("view");

    // Profile expanded (view button)
    let expandedSubject = $state(null);

    // Inline edit state
    let editingSubject = $state(null);
    let editSubject = $state({ first_name: "", last_name: "", sex: "", dob: "", email: "", phone: "", notes: "", created_at: "" });

    // Dataset panel state (card div click)
    let datasetsSubject = $state(null);
    let datasets = $state([]);
    let selectedDataset = $state(null);
    let datapoints = $state([]);

    // Module selector for "open new dataset"
    let newDsModule = $state("");
    let newDsMarker = $state("");

    // Add datapoint form
    let addTab = $state("form");
    let dpTimestamp = $state("");
    let dpValue = $state("");
    let dpUnit = $state("");
    let dpQuality = $state("good");
    let uploadFile = $state(null);
    let addFormOpen = $state(false);

    // Edit datapoint form
    let editingDp = $state(null);
    let editTs = $state("");
    let editValue = $state("");
    let editUnit = $state("");
    let editQuality = $state("good");

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

    onMount(() => {
        ensureSubjectsLoaded();
        ensureModulesLoaded();
    });

    let availableMarkers = $derived(
        appState.modules.find(m => m.module_id === newDsModule)?.markers ?? []
    );

    $effect(() => {
        newDsModule;
        newDsMarker = "";
    });

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
        datasetsSubject = null;
        editingSubject = null;
        selectedDataset = null;
        datapoints = [];
        datasets = [];
        editingDp = null;
        newDsModule = "";
        newDsMarker = "";
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
        try {
            await updateSubject(subject_id, {
                firstName: editSubject.first_name,
                lastName:  editSubject.last_name,
                sex:       editSubject.sex,
                dob:       editSubject.dob,
                email:     editSubject.email,
                phone:     editSubject.phone,
                notes:     editSubject.notes,
            });
            setStatus(`Subject "${subject_id}" updated.`);
            editingSubject = null;
            storeUpdateSubject(subject_id, {
                first_name: editSubject.first_name,
                last_name:  editSubject.last_name,
                sex:        editSubject.sex,
                dob:        editSubject.dob,
                email:      editSubject.email,
                phone:      editSubject.phone,
                notes:      editSubject.notes,
            });
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function handleDeleteSubject(subject_id) {
        if (!confirm(`Delete ${subject_id}? Their data will be moved to deleted_subjects/.`)) return;
        try {
            await deleteSubject(subject_id);
            setStatus(`Subject "${subject_id}" deleted.`);
            collapseSubject();
            storeRemoveSubject(subject_id);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function handleCreate() {
        try {
            const subjectId = await createSubject({ firstName: first_name, lastName: last_name, sex, dob, email, phone, notes });
            setStatus(`Subject created: ${subjectId}`);
            storeAddSubject({
                subject_id: subjectId,
                first_name, last_name, sex, dob, email, phone, notes,
                created_at: new Date().toISOString(),
            });
            first_name = ""; last_name = ""; sex = ""; dob = "";
            email = ""; phone = ""; notes = "";
            mode = "view";
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    // --- Dataset management ---

    async function loadDatasets(subject_id) {
        datasets = [];
        selectedDataset = null;
        datapoints = [];
        statusMessage = "";
        try {
            datasets = await fetchDatasets(subject_id);
        } catch (e) {
            setStatus("Failed to load datasets.", false);
        }
    }

    async function loadDatapoints(module_id, marker_id) {
        selectedDataset = { module_id, marker_id };
        datapoints = [];
        editingDp = null;
        addFormOpen = false;
        statusMessage = "";
        try {
            datapoints = await fetchDatapoints(datasetsSubject, module_id, marker_id);
            if (datapoints.length > 0) dpUnit = datapoints[0].unit ?? "";
        } catch (e) {
            setStatus(`Failed to load datapoints.`, false);
        }
    }

    function handleOpenDataset() {
        if (!newDsModule || !newDsMarker) {
            setStatus("Select a module and marker first.", false);
            return;
        }
        loadDatapoints(newDsModule, newDsMarker);
        statusMessage = "";
    }

    function handleStartEdit(dp) {
        editingDp   = dp;
        editTs      = dp.measured_at.slice(0, 16);
        editValue   = String(dp.value);
        editUnit    = dp.unit ?? "";
        editQuality = dp.data_quality ?? "good";
        statusMessage = "";
    }

    async function handleEditSave() {
        if (!editTs)        { setStatus("Timestamp is required.", false); return; }
        if (editValue === "") { setStatus("Value is required.", false); return; }
        const mid = selectedDataset.module_id;
        const mkid = selectedDataset.marker_id;
        try {
            await updateDatapoint(datasetsSubject, mid, mkid, editingDp.measured_at, {
                measuredAt:  new Date(editTs).toISOString(),
                value:       parseFloat(editValue),
                unit:        editUnit,
                dataQuality: editQuality,
            });
            setStatus("Datapoint updated.");
            editingDp = null;
            await loadDatasets(datasetsSubject);
            await loadDatapoints(mid, mkid);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function handleAddForm() {
        if (!dpTimestamp)   { setStatus("Timestamp is required.", false); return; }
        if (dpValue === "") { setStatus("Value is required.", false); return; }
        const mid = selectedDataset.module_id;
        const mkid = selectedDataset.marker_id;
        try {
            await addDatapoint(datasetsSubject, mid, mkid, {
                measuredAt:  new Date(dpTimestamp).toISOString(),
                value:       parseFloat(dpValue),
                unit:        dpUnit,
                dataQuality: dpQuality,
            });
            setStatus("Datapoint added.");
            dpTimestamp = ""; dpValue = ""; dpQuality = "good";
            await loadDatasets(datasetsSubject);
            await loadDatapoints(mid, mkid);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function handleUpload() {
        if (!uploadFile) { setStatus("Select a file first.", false); return; }
        const mid = selectedDataset.module_id;
        const mkid = selectedDataset.marker_id;
        try {
            await uploadDatapoint(datasetsSubject, mid, mkid, uploadFile);
            setStatus("File uploaded.");
            uploadFile = null;
            await loadDatasets(datasetsSubject);
            await loadDatapoints(mid, mkid);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function handleDeleteDatapoint(measured_at) {
        if (!confirm(`Delete datapoint at ${measured_at}?`)) return;
        const mid = selectedDataset.module_id;
        const mkid = selectedDataset.marker_id;
        try {
            await deleteDatapoint(datasetsSubject, mid, mkid, measured_at);
            setStatus("Datapoint deleted.");
            await loadDatasets(datasetsSubject);
            await loadDatapoints(mid, mkid);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function handleDeleteDataset(module_id, marker_id) {
        if (!confirm(`Delete entire dataset ${module_id}/${marker_id}? This cannot be undone.`)) return;
        try {
            await deleteDataset(datasetsSubject, module_id, marker_id);
            setStatus(`Dataset ${module_id}/${marker_id} deleted.`);
            selectedDataset = null;
            datapoints = [];
            await loadDatasets(datasetsSubject);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
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
            <div class="main_header_container">
                <h2>Subjects</h2>
            </div>
            <!-- VIEW MODE: Subject cards -->
            {#if mode === "view"}
                {#if appState.subjects.length === 0}
                    <p>No subjects found.</p>
                {/if}
                {#each appState.subjects as s}
                    <div class="module_card" role="button" style="--cardColor: {cardColor}" tabindex="0"
                        onclick={() => {
                            if (datasetsSubject === s.subject_id) {
                                collapseSubject();
                            } else {
                                collapseSubject();
                                datasetsSubject = s.subject_id;
                                loadDatasets(s.subject_id);
                            }
                        }}
                        onkeydown={(e) => {
                            if (e.key === 'Enter') {
                                if (datasetsSubject === s.subject_id) {
                                    collapseSubject();
                                } else {
                                    collapseSubject();
                                    datasetsSubject = s.subject_id;
                                    loadDatasets(s.subject_id);
                                }
                            }
                        }}>

                        <div id="card_header_container">
                            <div class="card_icon_container">
                                <div class="card_icon">{@html GenericUserIcon}</div>
                            </div>
                            <h2 class="card_header">{s.last_name}, {s.first_name}</h2>
                        </div>

                        <div id="card_actions">
                            <button style="--viewBtnColor: {viewBtnColor}" type="button" class="view_btn" id="view_profile_btn"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    if (expandedSubject === s.subject_id) {
                                        expandedSubject = null;
                                    } else {
                                        datasetsSubject = null;
                                        selectedDataset = null;
                                        datasets = [];
                                        datapoints = [];
                                        expandedSubject = s.subject_id;
                                    }
                                }}>
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
                            <div class="profile_section" role="button" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
                                <p><strong>ID:</strong> {s.subject_id}</p>
                                <p><strong>Email:</strong> {s.email || '—'}</p>
                                <p><strong>Phone:</strong> {s.phone || '—'}</p>
                                <p><strong>Notes:</strong> {s.notes || '—'}</p>
                                <p><strong>Created:</strong> {formatDate(s.created_at)}</p>
                            </div>
                        {/if}

                        {#if datasetsSubject === s.subject_id}
                            <div class="datasets_section" role="button" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>

                                <!-- Open new dataset row -->
                                <div class="new_dataset_row">
                                    <select bind:value={newDsModule}>
                                        <option value="">-- module --</option>
                                        {#each appState.modules as m}
                                            <option value={m.module_id}>{m.module_name || m.module_id}</option>
                                        {/each}
                                    </select>
                                    <select bind:value={newDsMarker} disabled={!newDsModule}>
                                        <option value="">-- marker --</option>
                                        {#each availableMarkers as mk}
                                            <option value={mk.marker_id}>{mk.marker_name || mk.marker_id}</option>
                                        {/each}
                                    </select>
                                    <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" onclick={handleOpenDataset}>Open</button>
                                </div>

                                <!-- Dataset list -->
                                {#if datasets.length === 0}
                                    <p class="empty_msg">No datasets found.</p>
                                {:else}
                                    <table class="datapoints_table">
                                        <thead>
                                            <tr>
                                                <th>Module</th>
                                                <th>Marker</th>
                                                <th>Entries</th>
                                                <th></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {#each datasets as ds}
                                                <tr class="dataset_row" class:selected={selectedDataset?.module_id === ds.module_id && selectedDataset?.marker_id === ds.marker_id}
                                                    onclick={() => {
                                                        if (selectedDataset?.module_id === ds.module_id && selectedDataset?.marker_id === ds.marker_id) {
                                                            selectedDataset = null;
                                                            datapoints = [];
                                                            editingDp = null;
                                                        } else {
                                                            loadDatapoints(ds.module_id, ds.marker_id);
                                                        }
                                                    }}>
                                                    <td>{ds.module_id}</td>
                                                    <td>{ds.marker_id}</td>
                                                    <td>{ds.entry_count}</td>
                                                    <td class="delete_dataset_btn_container">
                                                        <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn"
                                                            onclick={(e) => { e.stopPropagation(); handleDeleteDataset(ds.module_id, ds.marker_id); }}>
                                                            {@html DeleteIcon}
                                                        </button>
                                                    </td>
                                                </tr>
                                            {/each}
                                        </tbody>
                                    </table>
                                {/if}

                                <!-- Datapoint detail sub-panel -->
                                {#if selectedDataset}
                                    <div class="datapoint_panel">
                                        <h4 class="dp_panel_header">{selectedDataset.module_id} / {selectedDataset.marker_id}</h4>

                                        {#if datapoints.length === 0}
                                            <p class="empty_msg">No datapoints.</p>
                                        {:else}
                                            <table class="datapoints_table">
                                                <thead>
                                                    <tr>
                                                        <th>Timestamp</th>
                                                        <th>Value</th>
                                                        <th>Unit</th>
                                                        <th>Quality</th>
                                                        <th></th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {#each datapoints as dp}
                                                        <tr class:editing_row={editingDp?.measured_at === dp.measured_at}>
                                                            <td>{dp.measured_at}</td>
                                                            <td>{dp.value}</td>
                                                            <td>{dp.unit}</td>
                                                            <td>{dp.data_quality}</td>
                                                            <td class="datapoints_btns_container">
                                                                <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={() => handleStartEdit(dp)}>
                                                                    {@html EditIcon}
                                                                </button>

                                                                <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={() => handleDeleteDatapoint(dp.measured_at)}>
                                                                    {@html DeleteIcon}
                                                                </button>
                                                            </td>
                                                        </tr>
                                                    {/each}
                                                </tbody>
                                            </table>
                                        {/if}

                                        <!-- Edit datapoint form -->
                                        {#if editingDp}
                                            <div class="add_datapoint_form">
                                                <h4 class="dp_form_header">Edit datapoint</h4>
                                                <label>Timestamp <input type="datetime-local" bind:value={editTs}></label>
                                                <label>Value <input type="number" step="any" bind:value={editValue}></label>
                                                <label>Unit <input type="text" bind:value={editUnit}></label>
                                                <label>Quality
                                                    <select bind:value={editQuality}>
                                                        <option value="good">good</option>
                                                        <option value="suspect">suspect</option>
                                                        <option value="poor">poor</option>
                                                    </select>
                                                </label>
                                                <div class="dp_form_btns">
                                                    <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" onclick={handleEditSave}>{@html AddIcon}</button>
                                                    <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={() => editingDp = null}>{@html CancelIcon}</button>
                                                </div>
                                            </div>
                                        {/if}

                                        <!-- Add datapoint form -->
                                        <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" onclick={() => addFormOpen = !addFormOpen}>
                                            {addFormOpen ? 'Cancel' : 'Add datapoint'}
                                        </button>

                                        {#if addFormOpen}
                                            <div class="add_datapoint_form">
                                                <div class="add_tab_toggle">
                                                    <button type="button" class:active_tab={addTab === "form"} onclick={() => addTab = "form"}>Form</button>
                                                    <button type="button" class:active_tab={addTab === "upload"} onclick={() => addTab = "upload"}>Upload JSON</button>
                                                </div>

                                                {#if addTab === "form"}
                                                    <label>Timestamp <input type="datetime-local" bind:value={dpTimestamp}></label>
                                                    <label>Value <input type="number" step="any" bind:value={dpValue}></label>
                                                    <label>Unit <input type="text" bind:value={dpUnit}></label>
                                                    <label>Quality
                                                        <select bind:value={dpQuality}>
                                                            <option value="good">good</option>
                                                            <option value="suspect">suspect</option>
                                                            <option value="poor">poor</option>
                                                        </select>
                                                    </label>
                                                    <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" onclick={handleAddForm}>{@html AddIcon}</button>
                                                {:else}
                                                    <label>JSON file <input type="file" accept=".json" onchange={(e) => uploadFile = /** @type {HTMLInputElement} */ (e.target).files[0]}></label>
                                                    <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" onclick={handleUpload}>{@html AddIcon}</button>
                                                {/if}
                                            </div>
                                        {/if}

                                    </div>
                                {/if}
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
        grid-template-rows: auto auto auto auto auto;
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

    /* DATASETS SECTION */
    .datasets_section {
        grid-area: 4 / 1 / 5 / 3;
        border-top: 2px solid var(--borderColor);
        margin-top: 10px;
        padding-top: 8px;
        background-color: aliceblue;
        border-radius: 0.25rem;
        padding: 8px;
    }

    .new_dataset_row {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;
        flex-wrap: wrap;
    }

    .new_dataset_row select {
        padding: 4px;
        border: 1px solid var(--borderColor);
        border-radius: 3px;
        background-color: white;
    }

    .datapoints_table {
        border-collapse: collapse;
        width: 100%;
        font-size: 0.85em;
        margin-bottom: 6px;
    }

    .datapoints_table th,
    .datapoints_table td {
        border: 1px solid #ccc;
        padding: 3px 6px;
        text-align: left;
    }

    .datapoints_table th {
        background-color: #e8f4ff;
    }

    .dataset_row {
        cursor: pointer;
    }

    .dataset_row:hover {
        background-color: #cce0ff;
    }

    .dataset_row.selected {
        background-color: #b0d0ff;
    }

    .delete_dataset_btn_container {
        display: flex;
        justify-content: flex-end;
    }

    .editing_row {
        background-color: rgb(255, 250, 210);
    }

    .empty_msg {
        color: #888;
        font-style: italic;
        font-size: 0.9em;
        padding: 4px 0;
    }

    /* DATAPOINT DETAIL PANEL */
    .datapoint_panel {
        margin-top: 8px;
        border-top: 1px solid var(--borderColor);
        padding-top: 8px;
    }

    .dp_panel_header {
        font-size: 0.95em;
        margin-bottom: 6px;
    }

    .datapoints_btns_container {
        display: flex;
        justify-content: flex-end;
    }

    /* ADD/EDIT DATAPOINT FORM */
    .add_datapoint_form {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 6px;
        background-color: lightyellow;
        border: 2px solid var(--borderColor);
        border-radius: 0.25rem;
        padding: 8px;
        margin-top: 8px;
    }

    .add_datapoint_form label {
        display: flex;
        flex-direction: column;
        font-size: 0.85em;
    }

    .add_datapoint_form input,
    .add_datapoint_form select {
        margin-top: 3px;
        padding: 3px;
        border: 1px solid var(--borderColor);
        border-radius: 3px;
        width: 150px;
    }

    .dp_form_header {
        width: 100%;
        font-size: 0.9em;
        margin-bottom: 2px;
    }

    .dp_form_btns {
        display: flex;
        align-items: center;
    }

    .add_tab_toggle {
        width: 100%;
        display: flex;
        gap: 5px;
        margin-bottom: 4px;
    }

    .add_tab_toggle button {
        margin: 0;
    }

    button.active_tab {
        font-weight: bold;
        text-decoration: underline;
    }

    /* INLINE EDIT FORM */
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
        grid-area: 5 / 1 / 6 / 3;
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

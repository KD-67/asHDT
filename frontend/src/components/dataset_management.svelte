<script>                                                                                                  
    import { onMount } from "svelte";

    const BASE_URL = "http://localhost:8000";

    let subjects = $state([]);
    let selectedSubject = $state("");
    let datasets = $state([]);
    let selectedDataset = $state(null); // { module_id, marker_id }
    let datapoints = $state([]);
    let statusMessage = $state("");
    let statusOk = $state(true);
    let modules = $state([]);
    let newDsModule = $state("");
    let newDsMarker = $state("");

    // Edit datapoint
    let editingDp = $state(null); // { measured_at, value, unit, data_quality } — original values
    let editTs = $state("");
    let editValue = $state("");
    let editUnit = $state("");
    let editQuality = $state("good");

    // Add datapoint form
    let addTab = $state("form"); // "form" or "upload"
    let dpTimestamp = $state("");
    let dpValue = $state("");
    let dpUnit = $state("");
    let dpQuality = $state("good");
    let uploadFile = $state(null);

    onMount(async () => {
        const [subRes, modRes] = await Promise.all([
            fetch(`${BASE_URL}/subjects`),
            fetch(`${BASE_URL}/modules`),
        ]);
        subjects = await subRes.json();
        const modData = await modRes.json();
        modules = modData.modules ?? [];
    });

    let availableMarkers = $derived(
        modules.find(m => m.module_id === newDsModule)?.markers ?? []
    );

    $effect(() => {
        newDsModule;
        newDsMarker = "";
    });

    function handleOpenDataset() {
        if (!newDsModule || !newDsMarker) {
            setStatus("Select a module and marker first.", false);
            return;
        }
        loadDatapoints(newDsModule, newDsMarker);
        statusMessage = "";
    }

    function setStatus(msg, ok = true) {
        statusMessage = msg;
        statusOk = ok;
    }

    async function loadDatasets(subject_id) {
        datasets = [];
        selectedDataset = null;
        datapoints = [];
        statusMessage = "";
        const res = await fetch(`${BASE_URL}/subjects/${subject_id}/datasets`);
        if (res.ok) datasets = await res.json();
        else setStatus("Failed to load datasets.", false);
    }

    async function loadDatapoints(module_id, marker_id) {
        selectedDataset = { module_id, marker_id };
        datapoints = [];
        dpUnit = "";
        statusMessage = "";
        const res = await
fetch(`${BASE_URL}/subjects/${selectedSubject}/datasets/${module_id}/${marker_id}`);
        if (res.ok) {
            datapoints = await res.json();
            if (datapoints.length > 0) dpUnit = datapoints[0].unit ?? "";
        } else if (res.status === 404) {
            setStatus("No datapoints found for this dataset.", true);
        } else {
            setStatus(`Failed to load datapoints (${res.status}).`, false);
        }
    }

    function handleStartEdit(dp) {
        editingDp = dp;
        editTs = dp.measured_at.slice(0, 16); // trim to datetime-local format
        editValue = String(dp.value);
        editUnit = dp.unit ?? "";
        editQuality = dp.data_quality ?? "good";
        statusMessage = "";
    }

    async function handleEditSave() {
        if (!editTs) { setStatus("Timestamp is required.", false); return; }
        if (editValue === "") { setStatus("Value is required.", false); return; }
        const res = await fetch(
            `${BASE_URL}/subjects/${selectedSubject}/datasets/${selectedDataset.module_id}/${selectedDataset.marker_id}/${encodeURIComponent(editingDp.measured_at)}`,
            {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    measured_at: new Date(editTs).toISOString(),
                    value: parseFloat(editValue),
                    unit: editUnit,
                    data_quality: editQuality,
                }),
            }
        );
        if (res.ok) {
            setStatus("Datapoint updated.");
            editingDp = null;
            await loadDatasets(selectedSubject);
            await loadDatapoints(selectedDataset.module_id, selectedDataset.marker_id);
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }

    async function handleAddForm() {
        if (!dpTimestamp) { setStatus("Timestamp is required.", false); return; }
        if (dpValue === "") { setStatus("Value is required.", false); return; }
        const res = await fetch(
            `${BASE_URL}/subjects/${selectedSubject}/datasets/${selectedDataset.module_id}/${selectedDataset.marker_id}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    measured_at: new Date(dpTimestamp).toISOString(),
                    value: parseFloat(dpValue),
                    unit: dpUnit,
                    data_quality: dpQuality,
                }),
            }
        );
        if (res.ok) {
            setStatus("Datapoint added.");
            dpTimestamp = ""; dpValue = ""; dpQuality = "good";
            await loadDatasets(selectedSubject);
            await loadDatapoints(selectedDataset.module_id, selectedDataset.marker_id);
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }

    async function handleUpload() {
        if (!uploadFile) { setStatus("Select a file first.", false); return; }
        const form = new FormData();
        form.append("file", uploadFile);
        const res = await fetch(
            `${BASE_URL}/subjects/${selectedSubject}/datasets/${selectedDataset.module_id}/${selectedDataset.marker_id}/upload`,
            { method: "POST", body: form }
        );
        if (res.ok) {
            setStatus("File uploaded.");
            uploadFile = null;
            await loadDatasets(selectedSubject);
            await loadDatapoints(selectedDataset.module_id, selectedDataset.marker_id);
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }

    async function handleDeleteDatapoint(measured_at) {
        if (!confirm(`Delete datapoint at ${measured_at}?`)) return;
        const res = await fetch(
            `${BASE_URL}/subjects/${selectedSubject}/datasets/${selectedDataset.module_id}/${selectedDataset.marker_id}/${encodeURIComponent(measured_at)}`,
            { method: "DELETE" }
        );
        if (res.ok) {
            setStatus("Datapoint deleted.");
            await loadDatasets(selectedSubject);
            await loadDatapoints(selectedDataset.module_id, selectedDataset.marker_id);
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }

    async function handleDeleteDataset(module_id, marker_id) {
        if (!confirm(`Delete entire dataset ${module_id}/${marker_id} for ${selectedSubject}? This cannot 
be undone.`)) return;
        const res = await fetch(
            `${BASE_URL}/subjects/${selectedSubject}/datasets/${module_id}/${marker_id}`,
            { method: "DELETE" }
        );
        if (res.ok) {
            setStatus(`Dataset ${module_id}/${marker_id} deleted.`);
            selectedDataset = null;
            datapoints = [];
            await loadDatasets(selectedSubject);
        } else {
            const err = await res.json();
            setStatus(`Error: ${err.detail ?? res.statusText}`, false);
        }
    }
</script>

<main>
    <div id="main_container">

        <!-- Subject selector -->
        <div id="subject_selector">
            <label for="subject_select">Subject:</label>
            <select id="subject_select" bind:value={selectedSubject} onchange={() =>
loadDatasets(selectedSubject)}>
                <option value="">-- select --</option>
                {#each subjects as s}
                    <option value={s}>{s}</option>
                {/each}
            </select>
        </div>

        {#if selectedSubject}
            <div id="new_dataset_row">
                <label for="nd_module">Module</label>
                <select id="nd_module" bind:value={newDsModule}>
                    <option value="">-- module --</option>
                    {#each modules as m}
                        <option value={m.module_id}>{m.module_id}</option>
                    {/each}
                </select>

                <label for="nd_marker">Marker</label>
                <select id="nd_marker" bind:value={newDsMarker} disabled={!newDsModule}>
                    <option value="">-- marker --</option>
                    {#each availableMarkers as mk}
                        <option value={mk.marker_id}>{mk.marker_id}</option>
                    {/each}
                </select>

                <button type="button" onclick={handleOpenDataset}>Open</button>
            </div>
        {/if}

        {#if statusMessage}
            <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
        {/if}

        <!-- Dataset list -->
        {#if selectedSubject}
            <div id="dataset_list">
                <h3>Datasets for {selectedSubject}</h3>
                {#if datasets.length === 0}
                    <p class="empty_msg">No datasets found.</p>
                {:else}
                    <table>
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
                                <tr class:selected_row={selectedDataset?.module_id === ds.module_id &&
selectedDataset?.marker_id === ds.marker_id}
                                    onclick={() => loadDatapoints(ds.module_id, ds.marker_id)}
                                    style="cursor: pointer;">
                                    <td>{ds.module_id}</td>
                                    <td>{ds.marker_id}</td>
                                    <td>{ds.entry_count}</td>
                                    <td><button type="button" class="delete_btn" onclick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteDataset(ds.module_id, ds.marker_id);
                                    }}>Delete</button></td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                {/if}
            </div>
        {/if}

        <!-- Datapoint detail panel -->
        {#if selectedDataset}
            <div id="detail_panel">
                <h3>{selectedDataset.module_id} / {selectedDataset.marker_id}</h3>

                <!-- Datapoint table -->
                {#if datapoints.length === 0}
                    <p class="empty_msg">No datapoints.</p>
                {:else}
                    <table>
                        <thead>
                            <tr><th>Timestamp</th><th>Value</th><th>Unit</th><th>Quality</th><th></th><th></th></tr>
                        </thead>
                        <tbody>
                            {#each datapoints as dp}
                                <tr class:editing_row={editingDp?.measured_at === dp.measured_at}>
                                    <td>{dp.measured_at}</td>
                                    <td>{dp.value}</td>
                                    <td>{dp.unit}</td>
                                    <td>{dp.data_quality}</td>
                                    <td><button type="button" onclick={() => handleStartEdit(dp)}>Edit</button></td>
                                    <td><button type="button" class="delete_btn" onclick={() =>
handleDeleteDatapoint(dp.measured_at)}>Delete</button></td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                {/if}

                <!-- Edit datapoint -->
                {#if editingDp}
                    <div id="edit_section">
                        <h4>Edit datapoint</h4>
                        <div class="add_form">
                            <label>Timestamp</label>
                            <input type="datetime-local" bind:value={editTs}>

                            <label>Value</label>
                            <input type="number" step="any" bind:value={editValue}>

                            <label>Unit</label>
                            <input type="text" bind:value={editUnit}>

                            <label>Data quality</label>
                            <select bind:value={editQuality}>
                                <option value="good">good</option>
                                <option value="suspect">suspect</option>
                                <option value="poor">poor</option>
                            </select>

                            <button type="button" onclick={handleEditSave}>Save</button>
                            <button type="button" onclick={() => editingDp = null}>Cancel</button>
                        </div>
                    </div>
                {/if}

                <!-- Add datapoint -->
                <div id="add_section">
                    <h4>Add datapoint</h4>
                    <div id="add_tab_toggle">
                        <button type="button" class:active={addTab === "form"} onclick={() => addTab =    
"form"}>Form</button>
                        <button type="button" class:active={addTab === "upload"} onclick={() => addTab =  
"upload"}>Upload JSON</button>
                    </div>

                    {#if addTab === "form"}
                        <div class="add_form">
                            <label>Timestamp</label>
                            <input type="datetime-local" bind:value={dpTimestamp}>

                            <label>Value</label>
                            <input type="number" step="any" bind:value={dpValue}>

                            <label>Unit</label>
                            <input type="text" bind:value={dpUnit}>

                            <label>Data quality</label>
                            <select bind:value={dpQuality}>
                                <option value="good">good</option>
                                <option value="suspect">suspect</option>
                                <option value="poor">poor</option>
                            </select>

                            <button type="button" onclick={handleAddForm}>Add datapoint</button>
                        </div>
                    {:else}
                        <div class="add_form">
                            <label>JSON file</label>
                            <input type="file" accept=".json" onchange={(e) => uploadFile = e.target.files[0]}>
                            <button type="button" onclick={handleUpload}>Upload</button>
                        </div>
                    {/if}
                </div>
            </div>
        {/if}

    </div>
</main>

<style>
    #main_container {
        border: 1px solid black;
        background-color: rgb(255, 216, 216);
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        padding: 5px;
    }

    #subject_selector {
        width: 100%;
    }

    #new_dataset_row {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    #status_msg {
        width: 100%;
        font-weight: bold;
    }

    #status_msg.error { color: red; }

    #dataset_list, #detail_panel {
        border: 1px solid black;
        padding: 8px;
        flex: 1;
        min-width: 300px;
    }

    table {
        border-collapse: collapse;
        width: 100%;
    }

    th, td {
        border: 1px solid #ccc;
        padding: 4px 8px;
        text-align: left;
    }

    th { background-color: #eee; }

    .selected_row { background-color: rgb(220, 235, 255); }

    .delete_btn { background-color: rgb(255, 180, 180); }

    .empty_msg { color: #888; font-style: italic; }

    .editing_row { background-color: rgb(255, 250, 210); }

    #edit_section {
        margin-top: 12px;
        border-top: 1px solid #ccc;
        padding-top: 8px;
    }

    #add_section {
        margin-top: 12px;
        border-top: 1px solid #ccc;
        padding-top: 8px;
    }

    #add_tab_toggle {
        display: flex;
        gap: 5px;
        margin-bottom: 8px;
    }

    #add_tab_toggle button.active {
        font-weight: bold;
        text-decoration: underline;
    }

    .add_form {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        background-color: lightyellow;
        padding: 8px;
        border: 1px solid #ccc;
    }

    .add_form input, .add_form select { width: 160px; }
</style>

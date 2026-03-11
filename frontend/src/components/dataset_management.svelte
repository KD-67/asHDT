<script>
    import { onMount } from "svelte";
    import { gql } from "../lib/gql.js";

    // ── State ──────────────────────────────────────────────────────────────────

    let subjects = $state([]);
    let selectedSubject = $state("");
    let modules = $state([]);

    // Templates
    let templates = $state([]);
    let selectedTemplate = $state(null);   // full template object

    // Instances (per-subject)
    let instances = $state([]);
    let selectedInstance = $state(null);   // full instance object

    // Editor state (shared for template + instance creation/editing)
    let editorMode = $state(null);   // null | "new_template" | "edit_template" | "new_instance" | "edit_instance"
    let editorName = $state("");
    let editorDescription = $state("");
    let editorMarkerset_id = $state("");   // for instance: FK to template (or "" for custom)
    let editorMarkers = $state([]);
    // Each marker: { module_id, marker_id, weight, active, transform_type, transform_window_hours, transform_lag_hours, missing_data }

    let statusMessage = $state("");
    let statusOk = $state(true);

    // Module selector for adding a marker to the editor
    let addMarkerModule = $state("");
    let addMarkerMarker = $state("");

    // ── Derived ────────────────────────────────────────────────────────────────

    let availableMarkersForAdd = $derived(
        modules.find(m => m.module_id === addMarkerModule)?.markers ?? []
    );

    $effect(() => { addMarkerModule; addMarkerMarker = ""; });

    // ── Load on mount ──────────────────────────────────────────────────────────

    onMount(async () => {
        const [subData, modData, tmplData] = await Promise.all([
            gql(`query { subjects { subjectId } }`),
            gql(`query { modules { moduleId moduleName markers { markerId markerName } } }`),
            gql(`query { markersetTemplates { markersetId name description markers {
                    moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
                } createdAt } }`),
        ]);
        subjects  = subData.subjects.map(s => s.subjectId);
        modules   = modData.modules.map(m => ({
            module_id:   m.moduleId,
            module_name: m.moduleName,
            markers:     m.markers.map(mk => ({ marker_id: mk.markerId, marker_name: mk.markerName })),
        }));
        templates = tmplData.markersetTemplates.map(normaliseTemplate);
    });

    // ── Normalise GQL responses ────────────────────────────────────────────────

    function normaliseTemplate(t) {
        return {
            markerset_id: t.markersetId,
            name:         t.name,
            description:  t.description ?? "",
            markers:      t.markers.map(normaliseMarker),
            created_at:   t.createdAt,
        };
    }

    function normaliseInstance(i) {
        return {
            instance_id:  i.instanceId,
            subject_id:   i.subjectId,
            markerset_id: i.markersetId ?? "",
            name:         i.name,
            markers:      i.markers.map(normaliseMarker),
            created_at:   i.createdAt,
        };
    }

    function normaliseMarker(m) {
        return {
            module_id:              m.moduleId,
            marker_id:              m.markerId,
            weight:                 m.weight ?? 1.0,
            active:                 m.active ?? true,
            transform_type:         m.transformType ?? "none",
            transform_window_hours: m.transformWindowHours ?? null,
            transform_lag_hours:    m.transformLagHours ?? null,
            missing_data:           m.missingData ?? "interpolate",
        };
    }

    // ── Helpers ────────────────────────────────────────────────────────────────

    function setStatus(msg, ok = true) { statusMessage = msg; statusOk = ok; }

    function markerToGqlInput(m) {
        return {
            moduleId:    m.module_id,
            markerId:    m.marker_id,
            weight:      m.weight,
            active:      m.active,
            transform: {
                type:        m.transform_type,
                windowHours: m.transform_window_hours ?? null,
                lagHours:    m.transform_lag_hours ?? null,
            },
            missingData: m.missing_data,
        };
    }

    function markerLabel(m) {
        const mod = modules.find(md => md.module_id === m.module_id);
        const mk  = mod?.markers.find(mk => mk.marker_id === m.marker_id);
        return `${mod?.module_name || m.module_id} / ${mk?.marker_name || m.marker_id}`;
    }

    // ── Template actions ───────────────────────────────────────────────────────

    function startNewTemplate() {
        editorMode        = "new_template";
        editorName        = "";
        editorDescription = "";
        editorMarkers     = [];
        statusMessage     = "";
    }

    function startEditTemplate(tmpl) {
        selectedTemplate  = tmpl;
        editorMode        = "edit_template";
        editorName        = tmpl.name;
        editorDescription = tmpl.description;
        editorMarkers     = tmpl.markers.map(m => ({ ...m }));
        statusMessage     = "";
    }

    async function saveTemplate() {
        if (!editorName.trim()) { setStatus("Name is required.", false); return; }
        if (editorMarkers.length === 0) { setStatus("Add at least one marker.", false); return; }

        const markersInput = editorMarkers.map(markerToGqlInput);

        try {
            if (editorMode === "new_template") {
                const data = await gql(
                    `mutation($input: CreateMarkersetTemplateInput!) {
                        createMarkersetTemplate(input: $input) {
                            markersetId name description markers {
                                moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
                            } createdAt
                        }
                    }`,
                    { input: { name: editorName, description: editorDescription, markers: markersInput } }
                );
                templates = [...templates, normaliseTemplate(data.createMarkersetTemplate)];
                setStatus(`Template "${editorName}" created.`);
            } else {
                const data = await gql(
                    `mutation($id: String!, $input: CreateMarkersetTemplateInput!) {
                        updateMarkersetTemplate(markersetId: $id, input: $input) {
                            markersetId name description markers {
                                moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
                            } createdAt
                        }
                    }`,
                    { id: selectedTemplate.markerset_id, input: { name: editorName, description: editorDescription, markers: markersInput } }
                );
                const updated = normaliseTemplate(data.updateMarkersetTemplate);
                templates = templates.map(t => t.markerset_id === updated.markerset_id ? updated : t);
                selectedTemplate = updated;
                setStatus(`Template "${editorName}" updated.`);
            }
            editorMode = null;
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function deleteTemplate(tmpl) {
        if (!confirm(`Delete template "${tmpl.name}"? Instances using it will lose their base.`)) return;
        try {
            await gql(
                `mutation($id: String!) { deleteMarkersetTemplate(markersetId: $id) }`,
                { id: tmpl.markerset_id }
            );
            templates = templates.filter(t => t.markerset_id !== tmpl.markerset_id);
            if (selectedTemplate?.markerset_id === tmpl.markerset_id) selectedTemplate = null;
            setStatus(`Template "${tmpl.name}" deleted.`);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    // ── Instance actions ───────────────────────────────────────────────────────

    async function loadInstances(subjectId) {
        instances = [];
        selectedInstance = null;
        if (!subjectId) return;
        try {
            const data = await gql(
                `query($s: String!) { markersetInstances(subjectId: $s) {
                    instanceId subjectId markersetId name markers {
                        moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
                    } createdAt
                } }`,
                { s: subjectId }
            );
            instances = data.markersetInstances.map(normaliseInstance);
        } catch (e) {
            setStatus("Failed to load instances.", false);
        }
    }

    function startNewInstance(fromTemplate = null) {
        editorMode        = "new_instance";
        editorName        = fromTemplate ? `${fromTemplate.name} (${selectedSubject})` : "";
        editorMarkerset_id = fromTemplate?.markerset_id ?? "";
        editorMarkers     = fromTemplate ? fromTemplate.markers.map(m => ({ ...m })) : [];
        statusMessage     = "";
    }

    function startEditInstance(inst) {
        selectedInstance   = inst;
        editorMode         = "edit_instance";
        editorName         = inst.name;
        editorMarkerset_id = inst.markerset_id;
        editorMarkers      = inst.markers.map(m => ({ ...m }));
        statusMessage      = "";
    }

    async function saveInstance() {
        if (!selectedSubject) { setStatus("Select a subject first.", false); return; }
        if (!editorName.trim()) { setStatus("Name is required.", false); return; }
        if (editorMarkers.length === 0) { setStatus("Add at least one marker.", false); return; }

        const markersInput = editorMarkers.map(markerToGqlInput);
        const instInput = {
            markersetId: editorMarkerset_id || null,
            name:        editorName,
            markers:     markersInput,
        };

        try {
            if (editorMode === "new_instance") {
                const data = await gql(
                    `mutation($s: String!, $input: CreateMarkersetInstanceInput!) {
                        createMarkersetInstance(subjectId: $s, input: $input) {
                            instanceId subjectId markersetId name markers {
                                moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
                            } createdAt
                        }
                    }`,
                    { s: selectedSubject, input: instInput }
                );
                instances = [...instances, normaliseInstance(data.createMarkersetInstance)];
                setStatus(`Instance "${editorName}" created.`);
            } else {
                const data = await gql(
                    `mutation($id: String!, $input: CreateMarkersetInstanceInput!) {
                        updateMarkersetInstance(instanceId: $id, input: $input) {
                            instanceId subjectId markersetId name markers {
                                moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
                            } createdAt
                        }
                    }`,
                    { id: selectedInstance.instance_id, input: instInput }
                );
                const updated = normaliseInstance(data.updateMarkersetInstance);
                instances = instances.map(i => i.instance_id === updated.instance_id ? updated : i);
                selectedInstance = updated;
                setStatus(`Instance "${editorName}" updated.`);
            }
            editorMode = null;
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    async function deleteInstance(inst) {
        if (!confirm(`Delete instance "${inst.name}"?`)) return;
        try {
            await gql(
                `mutation($id: String!) { deleteMarkersetInstance(instanceId: $id) }`,
                { id: inst.instance_id }
            );
            instances = instances.filter(i => i.instance_id !== inst.instance_id);
            if (selectedInstance?.instance_id === inst.instance_id) selectedInstance = null;
            setStatus(`Instance "${inst.name}" deleted.`);
        } catch (e) {
            setStatus(`Error: ${e.message}`, false);
        }
    }

    // ── Editor: marker management ──────────────────────────────────────────────

    function addMarkerToEditor() {
        if (!addMarkerModule || !addMarkerMarker) {
            setStatus("Select a module and marker to add.", false); return;
        }
        if (editorMarkers.some(m => m.module_id === addMarkerModule && m.marker_id === addMarkerMarker)) {
            setStatus("Marker already in list.", false); return;
        }
        editorMarkers = [...editorMarkers, {
            module_id:              addMarkerModule,
            marker_id:              addMarkerMarker,
            weight:                 1.0,
            active:                 true,
            transform_type:         "none",
            transform_window_hours: null,
            transform_lag_hours:    null,
            missing_data:           "interpolate",
        }];
        addMarkerModule = ""; addMarkerMarker = "";
        statusMessage = "";
    }

    function removeMarkerFromEditor(index) {
        editorMarkers = editorMarkers.filter((_, i) => i !== index);
    }

    function cancelEditor() {
        editorMode = null;
        statusMessage = "";
    }
</script>

<main>
    <div id="main_container">

        <h2 id="page_title">Markerset Builder</h2>
        <p id="page_subtitle">Create and manage named compositions of markers with feature-engineering config. Markersets are the primary input for multi-marker analyses.</p>

        {#if statusMessage}
            <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
        {/if}

        <!-- ── Templates + Instances side-by-side ── -->
        <div id="panels">

            <!-- LEFT: Templates -->
            <div class="panel">
                <div class="panel_header">
                    <h3>Markerset Templates</h3>
                    <button type="button" class="small_btn add_btn" onclick={startNewTemplate}>+ New template</button>
                </div>

                {#if templates.length === 0}
                    <p class="empty_msg">No templates yet.</p>
                {:else}
                    <table>
                        <thead><tr><th>Name</th><th>Markers</th><th></th></tr></thead>
                        <tbody>
                            {#each templates as tmpl}
                                <tr class:selected_row={selectedTemplate?.markerset_id === tmpl.markerset_id}
                                    onclick={() => { selectedTemplate = tmpl; statusMessage = ""; }}
                                    style="cursor:pointer">
                                    <td>{tmpl.name}</td>
                                    <td>{tmpl.markers.length}</td>
                                    <td>
                                        <button type="button" class="small_btn" onclick={(e) => { e.stopPropagation(); startEditTemplate(tmpl); }}>Edit</button>
                                        <button type="button" class="small_btn delete_btn" onclick={(e) => { e.stopPropagation(); deleteTemplate(tmpl); }}>Delete</button>
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                {/if}

                <!-- Template detail -->
                {#if selectedTemplate && editorMode !== "edit_template"}
                    <div class="detail_box">
                        <h4>{selectedTemplate.name}</h4>
                        {#if selectedTemplate.description}<p class="desc_text">{selectedTemplate.description}</p>{/if}
                        <table class="marker_table">
                            <thead><tr><th>Marker</th><th>Weight</th><th>Transform</th><th>Missing</th><th>Active</th></tr></thead>
                            <tbody>
                                {#each selectedTemplate.markers as m}
                                    <tr>
                                        <td>{markerLabel(m)}</td>
                                        <td>{m.weight}</td>
                                        <td>{m.transform_type}{m.transform_window_hours ? ` (${m.transform_window_hours}h)` : ""}{m.transform_lag_hours ? ` lag ${m.transform_lag_hours}h` : ""}</td>
                                        <td>{m.missing_data}</td>
                                        <td>{m.active ? "✓" : "—"}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {/if}
            </div>

            <!-- RIGHT: Subject instances -->
            <div class="panel">
                <div class="panel_header">
                    <h3>Subject Instances</h3>
                    <div id="subject_row">
                        <label for="sub_select">Subject</label>
                        <select id="sub_select" bind:value={selectedSubject} onchange={() => loadInstances(selectedSubject)}>
                            <option value="">-- select --</option>
                            {#each subjects as s}
                                <option value={s}>{s}</option>
                            {/each}
                        </select>
                    </div>
                </div>

                {#if selectedSubject}
                    <div id="instance_actions">
                        <button type="button" class="small_btn add_btn" onclick={() => startNewInstance(null)}>+ Custom instance</button>
                        {#if selectedTemplate}
                            <button type="button" class="small_btn add_btn" onclick={() => startNewInstance(selectedTemplate)}>
                                + From "{selectedTemplate.name}"
                            </button>
                        {/if}
                    </div>
                {/if}

                {#if instances.length === 0 && selectedSubject}
                    <p class="empty_msg">No instances for {selectedSubject}.</p>
                {:else if instances.length > 0}
                    <table>
                        <thead><tr><th>Name</th><th>Markers</th><th>Template</th><th></th></tr></thead>
                        <tbody>
                            {#each instances as inst}
                                <tr class:selected_row={selectedInstance?.instance_id === inst.instance_id}
                                    onclick={() => { selectedInstance = inst; statusMessage = ""; }}
                                    style="cursor:pointer">
                                    <td>{inst.name}</td>
                                    <td>{inst.markers.length}</td>
                                    <td>{inst.markerset_id ? "from template" : "custom"}</td>
                                    <td>
                                        <button type="button" class="small_btn" onclick={(e) => { e.stopPropagation(); startEditInstance(inst); }}>Edit</button>
                                        <button type="button" class="small_btn delete_btn" onclick={(e) => { e.stopPropagation(); deleteInstance(inst); }}>Delete</button>
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                {/if}

                <!-- Instance detail -->
                {#if selectedInstance && editorMode !== "edit_instance"}
                    <div class="detail_box">
                        <h4>{selectedInstance.name}</h4>
                        <table class="marker_table">
                            <thead><tr><th>Marker</th><th>Weight</th><th>Transform</th><th>Missing</th><th>Active</th></tr></thead>
                            <tbody>
                                {#each selectedInstance.markers as m}
                                    <tr>
                                        <td>{markerLabel(m)}</td>
                                        <td>{m.weight}</td>
                                        <td>{m.transform_type}{m.transform_window_hours ? ` (${m.transform_window_hours}h)` : ""}{m.transform_lag_hours ? ` lag ${m.transform_lag_hours}h` : ""}</td>
                                        <td>{m.missing_data}</td>
                                        <td>{m.active ? "✓" : "—"}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {/if}
            </div>

        </div>

        <!-- ── Editor panel ── -->
        {#if editorMode !== null}
            <div id="editor_panel">
                <h3 id="editor_title">
                    {editorMode === "new_template" ? "New Template"
                     : editorMode === "edit_template" ? `Edit Template: ${selectedTemplate?.name}`
                     : editorMode === "new_instance" ? "New Instance"
                     : `Edit Instance: ${selectedInstance?.name}`}
                </h3>

                <div id="editor_meta">
                    <label>Name
                        <input type="text" bind:value={editorName} placeholder="e.g. Metabolic Panel" />
                    </label>
                    {#if editorMode === "new_template" || editorMode === "edit_template"}
                        <label>Description
                            <input type="text" bind:value={editorDescription} placeholder="Optional description" />
                        </label>
                    {/if}
                </div>

                <!-- Marker list in editor -->
                <div id="editor_markers">
                    <h4>Markers</h4>
                    {#if editorMarkers.length === 0}
                        <p class="empty_msg">No markers added yet.</p>
                    {:else}
                        <table id="editor_marker_table">
                            <thead>
                                <tr>
                                    <th>Marker</th>
                                    <th>Weight</th>
                                    <th>Transform</th>
                                    <th>Window (h)</th>
                                    <th>Lag (h)</th>
                                    <th>Missing data</th>
                                    <th>Active</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each editorMarkers as m, i}
                                    <tr>
                                        <td>{markerLabel(m)}</td>
                                        <td>
                                            <input type="number" step="0.1" min="0" bind:value={editorMarkers[i].weight} class="narrow_input" />
                                        </td>
                                        <td>
                                            <select bind:value={editorMarkers[i].transform_type} class="narrow_select">
                                                <option value="none">none</option>
                                                <option value="log">log</option>
                                                <option value="rolling_avg">rolling_avg</option>
                                                <option value="normalize">normalize</option>
                                                <option value="lag">lag</option>
                                            </select>
                                        </td>
                                        <td>
                                            {#if m.transform_type === "rolling_avg"}
                                                <input type="number" step="1" min="1" bind:value={editorMarkers[i].transform_window_hours} class="narrow_input" placeholder="24" />
                                            {:else}—{/if}
                                        </td>
                                        <td>
                                            {#if m.transform_type === "lag"}
                                                <input type="number" step="1" bind:value={editorMarkers[i].transform_lag_hours} class="narrow_input" placeholder="0" />
                                            {:else}—{/if}
                                        </td>
                                        <td>
                                            <select bind:value={editorMarkers[i].missing_data} class="narrow_select">
                                                <option value="interpolate">interpolate</option>
                                                <option value="forward_fill">forward_fill</option>
                                                <option value="skip">skip</option>
                                                <option value="zero">zero</option>
                                            </select>
                                        </td>
                                        <td>
                                            <input type="checkbox" bind:checked={editorMarkers[i].active} />
                                        </td>
                                        <td>
                                            <button type="button" class="small_btn delete_btn" onclick={() => removeMarkerFromEditor(i)}>✕</button>
                                        </td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    {/if}

                    <!-- Add marker row -->
                    <div id="add_marker_row">
                        <label>Module
                            <select bind:value={addMarkerModule}>
                                <option value="">-- module --</option>
                                {#each modules as m}
                                    <option value={m.module_id}>{m.module_name || m.module_id}</option>
                                {/each}
                            </select>
                        </label>
                        <label>Marker
                            <select bind:value={addMarkerMarker} disabled={!addMarkerModule}>
                                <option value="">-- marker --</option>
                                {#each availableMarkersForAdd as mk}
                                    <option value={mk.marker_id}>{mk.marker_name || mk.marker_id}</option>
                                {/each}
                            </select>
                        </label>
                        <button type="button" class="small_btn add_btn" onclick={addMarkerToEditor}>+ Add</button>
                    </div>
                </div>

                <!-- Editor actions -->
                <div id="editor_actions">
                    <button type="button" class="save_btn" onclick={editorMode.includes("template") ? saveTemplate : saveInstance}>
                        {editorMode.startsWith("new_") ? "Create" : "Save changes"}
                    </button>
                    <button type="button" onclick={cancelEditor}>Cancel</button>
                </div>

            </div>
        {/if}

    </div>
</main>

<style>
    #main_container {
        border: 1px solid #422800;
        background-color: #f5f0e8;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 12px;
    }

    #page_title {
        font-size: 1.2em;
        color: #422800;
    }

    #page_subtitle {
        font-size: 0.85em;
        color: #666;
        font-style: italic;
    }

    #status_msg { font-weight: bold; color: green; }
    #status_msg.error { color: red; }

    /* Two-column panels */
    #panels {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
    }

    .panel {
        border: 1px solid #422800;
        background: white;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .panel_header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
    }

    .panel_header h3 { font-size: 1em; color: #422800; }

    #subject_row {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.85em;
    }

    #subject_row select { font-size: 0.9em; padding: 3px; }

    #instance_actions {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }

    /* Tables */
    table {
        border-collapse: collapse;
        width: 100%;
        font-size: 0.85em;
    }

    th, td {
        border: 1px solid #ccc;
        padding: 3px 6px;
        text-align: left;
    }

    th { background: #f0e8d8; color: #422800; }

    .selected_row { background-color: #d0e8ff; }

    .detail_box {
        border: 1px solid #ccc;
        background: #fafafa;
        padding: 8px;
        font-size: 0.85em;
    }

    .detail_box h4 { margin-bottom: 6px; color: #422800; }
    .desc_text { color: #666; font-style: italic; margin-bottom: 6px; }

    .marker_table th, .marker_table td { font-size: 0.85em; }

    /* Editor */
    #editor_panel {
        border: 2px solid #422800;
        border-radius: 6px;
        background: #d0e8ff;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    #editor_title { font-size: 1em; color: #422800; }

    #editor_meta {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 10px;
    }

    #editor_meta label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
    }

    #editor_meta input {
        padding: 4px;
        border: 1px solid #422800;
        border-radius: 3px;
        font-size: 0.9em;
    }

    #editor_markers h4 { font-size: 0.9em; color: #422800; margin-bottom: 6px; }

    #editor_marker_table { font-size: 0.8em; }
    #editor_marker_table th { background: #c8dcf5; }

    .narrow_input  { width: 60px; padding: 2px 4px; font-size: 0.85em; }
    .narrow_select { font-size: 0.8em; padding: 2px; }

    #add_marker_row {
        display: flex;
        align-items: flex-end;
        gap: 8px;
        margin-top: 8px;
        padding: 8px;
        background: #e8f4ff;
        border: 1px solid #aac;
        border-radius: 4px;
    }

    #add_marker_row label {
        display: grid;
        gap: 3px;
        font-size: 0.8em;
    }

    #add_marker_row select {
        font-size: 0.85em;
        padding: 3px;
        border: 1px solid #422800;
        border-radius: 3px;
    }

    #editor_actions {
        display: flex;
        gap: 8px;
    }

    /* Buttons */
    button {
        border-radius: 20px;
        padding: 4px 12px;
        cursor: pointer;
        border: 1px solid #422800;
        background: #fbeee0;
        font-size: 0.85em;
        box-shadow: 3px 3px 0 #422800;
    }

    button:hover { font-weight: bold; }
    button:active { box-shadow: 1px 1px 0 #422800; transform: translate(1px, 1px); }

    .small_btn { padding: 2px 8px; font-size: 0.8em; }
    .add_btn   { background: rgb(114, 231, 114); }
    .delete_btn { background: rgb(255, 180, 180); }
    .save_btn  { background: rgb(114, 231, 114); font-weight: bold; }

    .empty_msg { color: #888; font-style: italic; font-size: 0.85em; }
</style>

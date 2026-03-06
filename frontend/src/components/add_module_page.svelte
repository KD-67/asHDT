  <script>                                                                                                  
      import { onMount } from "svelte";

      const BASE_URL = "http://localhost:8000";

      let mode = $state("view");
      let modules = $state([]);
      let statusMessage = $state("");
      let statusOk = $state(true);

      // New module form
      let new_module_id = $state("");
      let new_module_description = $state("");

      // Expanded module (for showing markers)
      let expandedModule = $state("");

      // Inline module edit
      let editingModule = $state("");
      let editModuleDescription = $state("");

      // Inline marker add (per module)
      let addingMarkerTo = $state("");
      let newMarker = $state(emptyMarker());

      // Inline marker edit
      let editingMarker = $state(null); // { module_id, marker_id }
      let editMarker = $state(emptyMarker());

      // Demographic zone refs
      let expandedZoneRef = $state(null); // { module_id, marker_id } or null
      let zoneRefRows = $state([]);
      let addingDemoZone = $state(false);
      let newDemoZone = $state({ sex: "M", age: "", healthy_min: "", healthy_max: "", vulnerability_margin: "" });
      let editingDemoZone = $state(null); // { sex, age } of row being edited
      let editDemoZone = $state({ healthy_min: "", healthy_max: "", vulnerability_margin: "" });

      function emptyMarker() {
          return { marker_id: "", description: "", unit: "", volatility_class: "", healthy_min: "",
  healthy_max: "", vulnerability_margin: "" };
      }

      onMount(loadModules);

      async function loadModules() {
          const res = await fetch(`${BASE_URL}/modules`);
          if (res.ok) {
              const data = await res.json();
              modules = data.modules ?? [];
          }
      }

      function setStatus(msg, ok = true) {
          statusMessage = msg;
          statusOk = ok;
      }

      // --- Module actions ---

      async function handleCreateModule() {
          if (!new_module_id.trim()) { setStatus("Module ID is required.", false); return; }
          const res = await fetch(`${BASE_URL}/modules`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ module_id: new_module_id.trim(), description:
  new_module_description.trim() }),
          });
          if (res.ok) {
              setStatus(`Module "${new_module_id}" created.`);
              new_module_id = ""; new_module_description = "";
              mode = "view";
              await loadModules();
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      function startEditModule(mod) {
          editingModule = mod.module_id;
          editModuleDescription = mod.description;
          statusMessage = "";
      }

      async function handleEditModule(module_id) {
          const res = await fetch(`${BASE_URL}/modules/${module_id}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ description: editModuleDescription }),
          });
          if (res.ok) {
              setStatus(`Module "${module_id}" updated.`);
              editingModule = "";
              await loadModules();
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      async function handleDeleteModule(module_id) {
          if (!confirm(`Delete module "${module_id}"? This cannot be undone.`)) return;
          const res = await fetch(`${BASE_URL}/modules/${module_id}`, { method: "DELETE" });
          if (res.ok) {
              setStatus(`Module "${module_id}" deleted.`);
              if (expandedModule === module_id) expandedModule = "";
              await loadModules();
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      // --- Marker actions ---

      function startAddMarker(module_id) {
          addingMarkerTo = module_id;
          newMarker = emptyMarker();
          statusMessage = "";
      }

      async function handleAddMarker(module_id) {
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  marker_id: newMarker.marker_id.trim(),
                  description: newMarker.description.trim(),
                  unit: newMarker.unit.trim(),
                  volatility_class: newMarker.volatility_class.trim(),
                  healthy_min: parseFloat(newMarker.healthy_min),
                  healthy_max: parseFloat(newMarker.healthy_max),
                  vulnerability_margin: parseFloat(newMarker.vulnerability_margin),
              }),
          });
          if (res.ok) {
              setStatus(`Marker "${newMarker.marker_id}" added to "${module_id}".`);
              addingMarkerTo = "";
              await loadModules();
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      function startEditMarker(module_id, mk) {
          editingMarker = { module_id, marker_id: mk.marker_id };
          editMarker = { ...mk, healthy_min: "", healthy_max: "", vulnerability_margin: "" };
          statusMessage = "";
      }

      async function handleEditMarker(module_id, marker_id) {
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers/${marker_id}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  description: editMarker.description,
                  unit: editMarker.unit,
                  volatility_class: editMarker.volatility_class,
                  healthy_min: parseFloat(editMarker.healthy_min),
                  healthy_max: parseFloat(editMarker.healthy_max),
                  vulnerability_margin: parseFloat(editMarker.vulnerability_margin),
              }),
          });
          if (res.ok) {
              setStatus(`Marker "${marker_id}" updated.`);
              editingMarker = null;
              await loadModules();
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      // --- Demographic zone ref actions ---

      async function toggleZoneRef(module_id, marker_id) {
          if (expandedZoneRef?.module_id === module_id && expandedZoneRef?.marker_id === marker_id) {
              expandedZoneRef = null;
              zoneRefRows = [];
              addingDemoZone = false;
              editingDemoZone = null;
          } else {
              expandedZoneRef = { module_id, marker_id };
              addingDemoZone = false;
              editingDemoZone = null;
              await loadZoneRefs(module_id, marker_id);
          }
      }

      async function loadZoneRefs(module_id, marker_id) {
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers/${marker_id}/zone-references`);
          if (res.ok) {
              zoneRefRows = await res.json();
          } else {
              setStatus("Failed to load zone references.", false);
          }
      }

      async function handleAddDemoZone(module_id, marker_id) {
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers/${marker_id}/zone-references`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  sex: newDemoZone.sex,
                  age: parseInt(newDemoZone.age),
                  healthy_min: parseFloat(newDemoZone.healthy_min),
                  healthy_max: parseFloat(newDemoZone.healthy_max),
                  vulnerability_margin: parseFloat(newDemoZone.vulnerability_margin),
              }),
          });
          if (res.ok) {
              setStatus("Demographic zone row added.");
              addingDemoZone = false;
              newDemoZone = { sex: "M", age: "", healthy_min: "", healthy_max: "", vulnerability_margin: "" };
              await loadZoneRefs(module_id, marker_id);
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      async function handleEditDemoZone(module_id, marker_id, sex, age) {
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers/${marker_id}/zone-references/${sex}/${age}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  healthy_min: parseFloat(editDemoZone.healthy_min),
                  healthy_max: parseFloat(editDemoZone.healthy_max),
                  vulnerability_margin: parseFloat(editDemoZone.vulnerability_margin),
              }),
          });
          if (res.ok) {
              setStatus("Demographic zone row updated.");
              editingDemoZone = null;
              await loadZoneRefs(module_id, marker_id);
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      async function handleDeleteDemoZone(module_id, marker_id, sex, age) {
          if (!confirm(`Delete zone ref ${sex}/${age}?`)) return;
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers/${marker_id}/zone-references/${sex}/${age}`, {
              method: "DELETE",
          });
          if (res.ok) {
              setStatus("Demographic zone row deleted.");
              await loadZoneRefs(module_id, marker_id);
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }

      async function handleDeleteMarker(module_id, marker_id) {
          if (!confirm(`Delete marker "${marker_id}" from "${module_id}"?`)) return;
          const res = await fetch(`${BASE_URL}/modules/${module_id}/markers/${marker_id}`, { method:        
  "DELETE" });
          if (res.ok) {
              setStatus(`Marker "${marker_id}" deleted.`);
              await loadModules();
          } else {
              const err = await res.json();
              setStatus(`Error: ${err.detail ?? res.statusText}`, false);
          }
      }
  </script>

  <main>
      <div id="main_container">

          <div id="mode_toggle">
              <button type="button" class:active={mode === "view"} onclick={() => { mode = "view"; statusMessage = ""; }}>View / Edit</button>
              <button type="button" class:active={mode === "add"}  onclick={() => { mode = "add"; statusMessage = ""; }}>Add New Module</button>
          </div>

          {#if statusMessage}
              <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
          {/if}
            <div id="module_card_holder">
          <!-- VIEW / EDIT MODE -->
          {#if mode === "view"}
              {#if modules.length === 0}
                  <p>No modules found.</p>
              {/if}
              {#each modules as mod}
                <div class="module_card" role="button" tabindex="0" onclick={() => expandedModule = expandedModule === mod.module_id ? "" : mod.module_id} onkeydown={(e) => e.key === 'Enter' && (expandedModule = expandedModule === mod.module_id ? "" : mod.module_id)}>
                    <div id="card_header_container">
                        <h3 class="card_header"> {mod.module_id} </h3>
                    </div>

                    <div id="card_actions">
                        <button type="button" class="CRUD_btn" id="edit_btn" onclick={()=> startEditModule(mod)}>Edit</button>
                        <button type="button" class="CRUD_btn" id="delete_btn" onclick={()=> handleDeleteModule(mod.module_id)}>Delete</button>
                    </div>

                    <span class="card_description"> {mod.description} </span>

                    <div class="card_expand_markers_container">
                        <span>
                          {expandedModule === mod.module_id ? "▼" : "▶"} Markers
                        </span>
                    </div>
                    

                    {#if expandedModule === mod.module_id}
                            <div class="markers_section">
                              {#if mod.markers.length === 0}
                                  <p class="no_markers">No markers.</p>
                              {/if}
                              {#each mod.markers as mk}
                                  <div class="marker_row">
                                      <span class="marker_id">{mk.marker_id}</span>
                                      <span class="marker_meta">{mk.description} — {mk.unit} ({mk.volatility_class})</span>
                                      <button type="button" class="CRUD_btn" id="edit_btn" onclick={() => startEditMarker(mod.module_id, mk)}>Edit</button>
                                      <button type="button" class="CRUD_btn" id="delete_btn" onclick={() => handleDeleteMarker(mod.module_id, mk.marker_id)}>Delete</button>
                                      <button type="button" class="CRUD_btn" id="zone_refs_btn" onclick={() => toggleZoneRef(mod.module_id, mk.marker_id)}>Zones</button>
                                  </div>

                                  {#if expandedZoneRef?.module_id === mod.module_id && expandedZoneRef?.marker_id === mk.marker_id}
                                      <div class="inline_form zone_refs_panel">
                                          <strong style="width:100%">Demographic zone references — {mk.marker_id}</strong>
                                          {#if zoneRefRows.length > 0}
                                              <table class="zone_refs_table">
                                                  <thead>
                                                      <tr>
                                                          <th>Sex</th><th>Age</th><th>Healthy Min</th><th>Healthy Max</th><th>Vulnerability Margin</th><th>Actions</th>
                                                      </tr>
                                                  </thead>
                                                  <tbody>
                                                      {#each zoneRefRows as row}
                                                          {#if editingDemoZone?.sex === row.sex && editingDemoZone?.age === row.age}
                                                              <tr>
                                                                  <td>{row.sex}</td>
                                                                  <td>{row.age}</td>
                                                                  <td><input type="number" bind:value={editDemoZone.healthy_min} style="width:80px"></td>
                                                                  <td><input type="number" bind:value={editDemoZone.healthy_max} style="width:80px"></td>
                                                                  <td><input type="number" bind:value={editDemoZone.vulnerability_margin} style="width:80px"></td>
                                                                  <td>
                                                                      <button type="button" onclick={() => handleEditDemoZone(mod.module_id, mk.marker_id, row.sex, row.age)}>Save</button>
                                                                      <button type="button" onclick={() => editingDemoZone = null}>Cancel</button>
                                                                  </td>
                                                              </tr>
                                                          {:else}
                                                              <tr>
                                                                  <td>{row.sex}</td>
                                                                  <td>{row.age}</td>
                                                                  <td>{row.healthy_min}</td>
                                                                  <td>{row.healthy_max}</td>
                                                                  <td>{row.vulnerability_margin}</td>
                                                                  <td>
                                                                      <button type="button" onclick={() => { editingDemoZone = { sex: row.sex, age: row.age }; editDemoZone = { healthy_min: row.healthy_min, healthy_max: row.healthy_max, vulnerability_margin: row.vulnerability_margin }; }}>✏️</button>
                                                                      <button type="button" class="delete_btn" onclick={() => handleDeleteDemoZone(mod.module_id, mk.marker_id, row.sex, row.age)}>✕</button>
                                                                  </td>
                                                              </tr>
                                                          {/if}
                                                      {/each}
                                                  </tbody>
                                              </table>
                                          {:else}
                                              <p style="color:#888;font-style:italic;width:100%">No demographic zone rows yet.</p>
                                          {/if}

                                          {#if addingDemoZone}
                                              <div class="demo_zone_add_form">
                                                  <label>Sex
                                                      <select bind:value={newDemoZone.sex}>
                                                          <option value="M">M</option>
                                                          <option value="F">F</option>
                                                      </select>
                                                  </label>
                                                  <label>Age <input type="number" bind:value={newDemoZone.age} style="width:60px"></label>
                                                  <label>Healthy min <input type="number" bind:value={newDemoZone.healthy_min} style="width:80px"></label>
                                                  <label>Healthy max <input type="number" bind:value={newDemoZone.healthy_max} style="width:80px"></label>
                                                  <label>Vuln margin <input type="number" bind:value={newDemoZone.vulnerability_margin} style="width:80px"></label>
                                                  <button type="button" onclick={() => handleAddDemoZone(mod.module_id, mk.marker_id)}>Add</button>
                                                  <button type="button" onclick={() => addingDemoZone = false}>Cancel</button>
                                              </div>
                                          {:else}
                                              <button type="button" onclick={() => addingDemoZone = true}>＋ Add row</button>
                                          {/if}
                                      </div>
                                  {/if}

                                  {#if editingMarker?.module_id === mod.module_id && editingMarker?.marker_id === mk.marker_id}
                                      <div class="inline_form marker_edit_form">
                                          <label>Description <input type="text" bind:value={editMarker.description}></label>
                                          <label>Unit <input type="text" bind:value={editMarker.unit}></label>
                                          <label>Volatility class
                                              <select bind:value={editMarker.volatility_class}>
                                                  <option value="short_term">short_term</option>
                                                  <option value="medium_term">medium_term</option>
                                                  <option value="long_term">long_term</option>
                                              </select>
                                          </label>
                                          <label>Healthy min <input type="number" bind:value={editMarker.healthy_min}></label>
                                          <label>Healthy max <input type="number" bind:value={editMarker.healthy_max}></label>
                                          <label>Vulnerability margin <input type="number" bind:value={editMarker.vulnerability_margin}></label>
                                          <button type="button" onclick={() => handleEditMarker(mod.module_id, mk.marker_id)}>Save</button>
                                          <button type="button" onclick={() => editingMarker = null}>Cancel</button>
                                      </div>
                                  {/if}
                              {/each}

                              <!-- Add marker form -->
                                {#if addingMarkerTo === mod.module_id}
                                  <div class="inline_form marker_edit_form">
                                      <strong>New marker</strong>
                                      <label>Marker ID <input type="text" bind:value={newMarker.marker_id}></label>
                                      <label>Description <input type="text" bind:value={newMarker.description}></label>
                                      <label>Unit <input type="text" bind:value={newMarker.unit}></label>
                                      <label>Volatility class
                                          <select bind:value={newMarker.volatility_class}>
                                              <option value="">-- select --</option>
                                              <option value="short_term">short_term</option>
                                              <option value="medium_term">medium_term</option>
                                              <option value="long_term">long_term</option>
                                          </select>
                                      </label>
                                      <label>Healthy min <input type="number" bind:value={newMarker.healthy_min}></label>
                                      <label>Healthy max <input type="number" bind:value={newMarker.healthy_max}></label>
                                      <label>Vulnerability margin <input type="number" bind:value={newMarker.vulnerability_margin}></label>
                                      <button type="button" onclick={() => handleAddMarker(mod.module_id)}>Add marker</button>
                                      <button type="button" onclick={() => addingMarkerTo = ""}>Cancel</button>
                                  </div>
                              {:else}
                                  <button type="button" class="add_marker_btn" onclick={() => startAddMarker(mod.module_id)}>+ Add marker</button>
                              {/if}
                          </div>
                      {/if}

                      {#if editingModule === mod.module_id}
                          <div class="inline_form">
                              <label>Description <input type="text" bind:value={editModuleDescription}></label>
                              <button type="button" onclick={() => handleEditModule(mod.module_id)}>Save</button>
                              <button type="button" onclick={() => editingModule = ""}>Cancel</button>
                          </div>
                      {/if}
                  </div>
              {/each}
          {/if}
          </div>

          <!-- ADD NEW MODULE MODE -->
          {#if mode === "add"}
              <form id="module_form">
                  <h2>Add new module</h2>
                  <label for="new_module_id">Module ID</label>
                  <input type="text" id="new_module_id" bind:value={new_module_id}>
                  <label for="new_module_description">Description</label>
                  <input type="text" id="new_module_description" bind:value={new_module_description}>       
              </form>
              <div id="preview_container">
                  <h4>Preview:</h4>
                  <p>Module ID: {new_module_id}</p>
                  <p>Description: {new_module_description}</p>
                  <button type="button" onclick={handleCreateModule}>Create module</button>
              </div>
          {/if}

      </div>
  </main>

  <style>
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
    }

    #mode_toggle button.active {
        font-weight: bold;
        text-decoration: underline;
    }

    #status_msg {
        width: 100%;
        font-weight: bold;
    }

    #status_msg.error { color: red; }

    #module_card_holder {
        width: 40vw;
        display: flex;
        flex-direction: column;
    }

    .module_card {
        display: grid;
        border: 1px solid white;
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 12px 17px 51px rgba(0, 0, 0, 0.22);
        margin: 5px;
        padding: 5px;
        grid-template-rows: auto auto auto;
        grid-template-columns: 50% 50%;
    }

    .module_card:hover {
        transform: scale(1.01);
        border: 1px solid black;
    }

    #card_header_container {
        grid-row: 1 / 2;
        grid-column: 1 / 2;
    }
    
    .card_header {
        color: rgb(0, 0, 0);
    }

    .card_expand_markers_container {
        grid-area: 3 / 1 / 4 / 3;
    }

    .expand_markers_btn {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 1em;
    }

    #card_actions { 
        grid-area: 1 / 2 / 2 / 3; 
        display: flex; 
        justify-content: flex-end;
        gap: 5px; 
    }

    .CRUD_btn {
        border-radius: 20%;
        width: 15%;
        height: 50%;
        margin: 0.25rem;
        font-size: auto;
    }
    
    #delete_btn { 
        background-color: rgb(255, 180, 180); 
    }

    #edit_btn {
        background-color: aqua;
    }

    .card_description {
        grid-row: 2 / 3;
        grid-column: 1 / 3;
        color: #444; 
    }

    .markers_section {
        margin-top: 5px;
        padding-left: 20px;
        border-left: 2px solid #ccc;
    }

    .marker_row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 3px 0;
    }

    .marker_id { font-weight: bold; min-width: 120px; }
    .marker_meta { flex: 1; color: #555; font-size: 0.9em; }

    .no_markers { color: #888; font-style: italic; }

    .inline_form {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 5px;
        background-color: lightyellow;
        padding: 8px;
        margin: 5px 0;
        border: 1px solid #ccc;
    }

    .marker_edit_form label { font-size: 0.85em; }
    .marker_edit_form input, .marker_edit_form select { width: 120px; }

    .add_marker_btn { margin-top: 5px; }

    #zone_refs_btn { 
        background-color: rgb(252, 217, 18); 
    }

    .zone_refs_panel { flex-direction: column; align-items: flex-start; }

    .zone_refs_table { border-collapse: collapse; font-size: 0.85em; width: 100%; }
    .zone_refs_table th, .zone_refs_table td { border: 1px solid #ccc; padding: 3px 6px; text-align: center; }
    .zone_refs_table th { background: #eee; }

    .demo_zone_add_form { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; font-size: 0.85em; }

    form {
        background-color: lightblue;
        padding: 15px 10px;
        border: 1px solid black;
        display: flex;
        flex-direction: column;
        gap: 5px;
    }

    #preview_container {
        border: 1px solid black;
        margin: 5px;
        padding: 3px;
    }
  </style>
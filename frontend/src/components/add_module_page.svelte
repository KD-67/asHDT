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
              <button type="button" class:active={mode === "view"} onclick={() => { mode = "view";
  statusMessage = ""; }}>View / Edit</button>
              <button type="button" class:active={mode === "add"}  onclick={() => { mode = "add";
  statusMessage = ""; }}>Add New Module</button>
          </div>

          {#if statusMessage}
              <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
          {/if}

          <!-- VIEW / EDIT MODE -->
          {#if mode === "view"}
              {#if modules.length === 0}
                  <p>No modules found.</p>
              {/if}
              {#each modules as mod}
                  <div class="module_card">
                      <div class="module_header">
                          <button type="button" class="expand_btn" onclick={() => expandedModule =
  expandedModule === mod.module_id ? "" : mod.module_id}>
                              {expandedModule === mod.module_id ? "▼" : "▶"}
  <strong>{mod.module_id}</strong>
                          </button>
                          <span class="module_desc">{mod.description}</span>
                          <div class="module_actions">
                              <button type="button" onclick={() => startEditModule(mod)}>Edit</button>      
                              <button type="button" class="delete_btn" onclick={() =>
  handleDeleteModule(mod.module_id)}>Delete</button>
                          </div>
                      </div>

                      {#if editingModule === mod.module_id}
                          <div class="inline_form">
                              <label>Description</label>
                              <input type="text" bind:value={editModuleDescription}>
                              <button type="button" onclick={() =>
  handleEditModule(mod.module_id)}>Save</button>
                              <button type="button" onclick={() => editingModule = ""}>Cancel</button>      
                          </div>
                      {/if}

                      {#if expandedModule === mod.module_id}
                          <div class="markers_section">
                              {#if mod.markers.length === 0}
                                  <p class="no_markers">No markers.</p>
                              {/if}
                              {#each mod.markers as mk}
                                  <div class="marker_row">
                                      <span class="marker_id">{mk.marker_id}</span>
                                      <span class="marker_meta">{mk.description} — {mk.unit}
  ({mk.volatility_class})</span>
                                      <button type="button" onclick={() => startEditMarker(mod.module_id,   
  mk)}>Edit</button>
                                      <button type="button" class="delete_btn" onclick={() =>
  handleDeleteMarker(mod.module_id, mk.marker_id)}>Delete</button>
                                  </div>

                                  {#if editingMarker?.module_id === mod.module_id &&
  editingMarker?.marker_id === mk.marker_id}
                                      <div class="inline_form marker_edit_form">
                                          <label>Description</label><input type="text"
  bind:value={editMarker.description}>
                                          <label>Unit</label><input type="text"
  bind:value={editMarker.unit}>
                                          <label>Volatility class</label>
                                          <select bind:value={editMarker.volatility_class}>
                                              <option value="short_term">short_term</option>
                                              <option value="medium_term">medium_term</option>
                                              <option value="long_term">long_term</option>
                                          </select>
                                          <label>Healthy min</label><input type="number"
  bind:value={editMarker.healthy_min}>
                                          <label>Healthy max</label><input type="number"
  bind:value={editMarker.healthy_max}>
                                          <label>Vulnerability margin</label><input type="number"
  bind:value={editMarker.vulnerability_margin}>
                                          <button type="button" onclick={() =>
  handleEditMarker(mod.module_id, mk.marker_id)}>Save</button>
                                          <button type="button" onclick={() => editingMarker =
  null}>Cancel</button>
                                      </div>
                                  {/if}
                              {/each}

                              <!-- Add marker form -->
                              {#if addingMarkerTo === mod.module_id}
                                  <div class="inline_form marker_edit_form">
                                      <strong>New marker</strong>
                                      <label>Marker ID</label><input type="text"
  bind:value={newMarker.marker_id}>
                                      <label>Description</label><input type="text"
  bind:value={newMarker.description}>
                                      <label>Unit</label><input type="text" bind:value={newMarker.unit}>    
                                      <label>Volatility class</label>
                                      <select bind:value={newMarker.volatility_class}>
                                          <option value="">-- select --</option>
                                          <option value="short_term">short_term</option>
                                          <option value="medium_term">medium_term</option>
                                          <option value="long_term">long_term</option>
                                      </select>
                                      <label>Healthy min</label><input type="number"
  bind:value={newMarker.healthy_min}>
                                      <label>Healthy max</label><input type="number"
  bind:value={newMarker.healthy_max}>
                                      <label>Vulnerability margin</label><input type="number"
  bind:value={newMarker.vulnerability_margin}>
                                      <button type="button" onclick={() =>
  handleAddMarker(mod.module_id)}>Add marker</button>
                                      <button type="button" onclick={() => addingMarkerTo =
  ""}>Cancel</button>
                                  </div>
                              {:else}
                                  <button type="button" class="add_marker_btn" onclick={() =>
  startAddMarker(mod.module_id)}>+ Add marker</button>
                              {/if}
                          </div>
                      {/if}
                  </div>
              {/each}
          {/if}

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

      .module_card {
          width: 100%;
          border: 1px solid black;
          padding: 5px;
      }

      .module_header {
          display: flex;
          align-items: center;
          gap: 10px;
      }

      .expand_btn {
          background: none;
          border: none;
          cursor: pointer;
          font-size: 1em;
      }

      .module_desc { flex: 1; color: #444; }

      .module_actions { display: flex; gap: 5px; }

      .delete_btn { background-color: rgb(255, 180, 180); }

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
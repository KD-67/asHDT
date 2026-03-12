  <script>
      let textColor = '#422800';
      let borderColor = '#422800';
      let cardColor = '#d0e8ff';
      let cardSectionColor = 'aliceblue';
      let addBtnColor = 'rgb(114, 231, 114)';
      let viewBtnColor = 'rgb(209, 162, 252)';
      let editBtnColor = '#4CF3FC';
      let deleteBtnColor = 'rgb(255, 180, 180)';
      let zoneRefBtnColor = 'rgb(252, 217, 18)';
    
      import ViewIcon from "../assets/view_icon.svg?raw";
      import AddIcon from "../assets/add_icon.svg?raw";
      import EditIcon from "../assets/edit_icon.svg?raw";
      import DeleteIcon from "../assets/delete_icon.svg?raw";
      import LevelsIcon from "../assets/levels_icon.svg?raw";

      import { onMount } from "svelte";
      import { fetchDemographicZones, addDemographicZone, updateDemographicZone, deleteDemographicZone } from "../lib/api.js";
      import { createModule, updateModule, deleteModule, createMarker, updateMarker, deleteMarker } from "../lib/services.js";
      import { appState, ensureModulesLoaded } from "../lib/stores.svelte.js";

      let mode = $state("view");
      let statusMessage = $state("");
      let statusOk = $state(true);

      // New module form
      let new_module_name = $state("");
      let new_module_id = $state("");
      let new_module_description = $state("");

      // Expanded module (for showing markers)
      let expandedModule = $state("");

      // Inline module edit
      let editingModule = $state("");
      let editModuleName = $state("");
      let editModuleDescription = $state("");

      // Inline marker add (per module)
      let addingMarkerTo = $state("");
      let newMarker = $state(emptyMarker());

      // Inline marker edit
      let editingMarker = $state(null); // { module_id, marker_id }
      let editMarker = $state(emptyMarker());

      // Expanded marker description
      let expandedMarkerDescription = $state(null); // { module_id, marker_id } or null

      // Demographic zone refs
      let expandedZoneRef = $state(null); // { module_id, marker_id } or null
      let zoneRefRows = $state([]);
      let addingDemoZone = $state(false);
      let newDemoZone = $state({ sex: "M", age: "", healthy_min: "", healthy_max: "", vulnerability_margin: "" });
      let editingDemoZone = $state(null); // { sex, age } of row being edited
      let editDemoZone = $state({ healthy_min: "", healthy_max: "", vulnerability_margin: "" });

      function emptyMarker() {
          return { marker_id: "", marker_name: "", description: "", unit: "", volatility_class: "", healthy_min: "", healthy_max: "", vulnerability_margin: "" };
      }

      onMount(() => ensureModulesLoaded());

      function setStatus(msg, ok = true) {
          statusMessage = msg;
          statusOk = ok;
      }

      // --- Module actions ---

      async function handleCreateModule() {
          if (!new_module_id.trim()) { setStatus("Module ID is required.", false); return; }
          try {
              await createModule({ module_id: new_module_id.trim(), module_name: new_module_name.trim(), description: new_module_description.trim() });
              setStatus(`Module "${new_module_id}" created.`);
              new_module_id = ""; new_module_name = ""; new_module_description = "";
              mode = "view";
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      function toggleEditModule(mod) {
          if (editingModule === mod.module_id) {
              collapseModule();
          } else {
              collapseModule();
              editingModule = mod.module_id;
              editModuleName = mod.module_name ?? "";
              editModuleDescription = mod.description;
          }
          statusMessage = "";
      }

      async function handleEditModule(module_id) {
          try {
              await updateModule(module_id, { module_name: editModuleName, description: editModuleDescription });
              setStatus(`Module "${module_id}" updated.`);
              editingModule = "";
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      async function handleDeleteModule(module_id) {
          if (!confirm(`Delete module "${module_id}"? This cannot be undone.`)) return;
          try {
              await deleteModule(module_id);
              setStatus(`Module "${module_id}" deleted.`);
              if (expandedModule === module_id) collapseModule();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      // --- Marker actions ---

      function startAddMarker(module_id) {
          collapseMarkerPanels();
          addingMarkerTo = module_id;
          statusMessage = "";
      }

      async function handleAddMarker(module_id) {
          if (isNaN(parseFloat(newMarker.healthy_min)) || isNaN(parseFloat(newMarker.healthy_max)) || isNaN(parseFloat(newMarker.vulnerability_margin))) {
              setStatus("Healthy min, max, and vulnerability margin must be numbers.", false);
              return;
          }
          try {
              await createMarker(module_id, newMarker);
              setStatus(`Marker "${newMarker.marker_id}" added to "${module_id}".`);
              addingMarkerTo = "";
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      function toggleEditMarker(module_id, mk) {
          if (editingMarker?.module_id === module_id && editingMarker?.marker_id === mk.marker_id) {
              collapseMarkerPanels();
          } else {
              collapseMarkerPanels();
              editingMarker = { module_id, marker_id: mk.marker_id };
              editMarker = { ...mk };
          }
          statusMessage = "";
      }

      async function handleEditMarker(module_id, marker_id) {
          try {
              await updateMarker(module_id, marker_id, editMarker);
              setStatus(`Marker "${marker_id}" updated.`);
              editingMarker = null;
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      // --- Demographic zone ref actions ---

      async function toggleZoneRef(module_id, marker_id) {
          if (expandedZoneRef?.module_id === module_id && expandedZoneRef?.marker_id === marker_id) {
              collapseMarkerPanels();
          } else {
              collapseMarkerPanels();
              expandedZoneRef = { module_id, marker_id };
              await loadZoneRefs(module_id, marker_id);
          }
      }

      async function loadZoneRefs(module_id, marker_id) {
          try {
              zoneRefRows = await fetchDemographicZones(module_id, marker_id);
          } catch (e) {
              setStatus("Failed to load zone references.", false);
          }
      }

      async function handleAddDemoZone(module_id, marker_id) {
          try {
              await addDemographicZone(module_id, marker_id, {
                  sex:                 newDemoZone.sex,
                  age:                 parseInt(newDemoZone.age),
                  healthyMin:          parseFloat(newDemoZone.healthy_min),
                  healthyMax:          parseFloat(newDemoZone.healthy_max),
                  vulnerabilityMargin: parseFloat(newDemoZone.vulnerability_margin),
              });
              setStatus("Demographic zone row added.");
              addingDemoZone = false;
              newDemoZone = { sex: "M", age: "", healthy_min: "", healthy_max: "", vulnerability_margin: "" };
              await loadZoneRefs(module_id, marker_id);
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      async function handleEditDemoZone(module_id, marker_id, sex, age) {
          try {
              await updateDemographicZone(module_id, marker_id, sex, age, {
                  healthyMin:          parseFloat(editDemoZone.healthy_min),
                  healthyMax:          parseFloat(editDemoZone.healthy_max),
                  vulnerabilityMargin: parseFloat(editDemoZone.vulnerability_margin),
              });
              setStatus("Demographic zone row updated.");
              editingDemoZone = null;
              await loadZoneRefs(module_id, marker_id);
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      async function handleDeleteDemoZone(module_id, marker_id, sex, age) {
          if (!confirm(`Delete zone ref ${sex}/${age}?`)) return;
          try {
              await deleteDemographicZone(module_id, marker_id, sex, age);
              setStatus("Demographic zone row deleted.");
              await loadZoneRefs(module_id, marker_id);
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      async function handleDeleteMarker(module_id, marker_id) {
          if (!confirm(`Delete marker "${marker_id}" from "${module_id}"?`)) return;
          try {
              await deleteMarker(module_id, marker_id);
              setStatus(`Marker "${marker_id}" deleted.`);
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      function collapseMarkerPanels() {
          editingMarker = null;
          editMarker = emptyMarker();
          addingMarkerTo = "";
          newMarker = emptyMarker();
          expandedMarkerDescription = null;
          expandedZoneRef = null;
          zoneRefRows = [];
          addingDemoZone = false;
          newDemoZone = { sex: "M", age: "", healthy_min: "", healthy_max: "", vulnerability_margin: "" };
          editingDemoZone = null;
          editDemoZone = { healthy_min: "", healthy_max: "", vulnerability_margin: "" };
      }

      function collapseModule() {
          expandedModule = "";
          editingModule = "";
          editModuleName = "";
          editModuleDescription = "";
          collapseMarkerPanels();
      }
        
  </script>

  <main style="--textColor: {textColor}; --borderColor: {borderColor}">
      <div id="main_container">

          <div id="mode_toggle">
              <button type="button" style="--viewBtnColor: {viewBtnColor}" class:active={mode === "view"} onclick={() => { mode = "view"; statusMessage = ""; }} id="viewedit_mod_btn">{@html ViewIcon}</button>
              <button type="button" style='--addBtnColor: {addBtnColor}' class:active={mode === "add"}  onclick={() => { mode = "add"; statusMessage = ""; }} class="add_btn">{@html AddIcon}</button>
            
              {#if statusMessage}
              <p id="status_msg" class:error={!statusOk}>{statusMessage}</p>
            {/if}
          </div>

            <div id="viewbox">
                <div class="main_header_container">
                    <h2>Modules</h2>
                </div>
          <!-- VIEW / EDIT MODE -->
          {#if mode === "view"}
              {#if appState.modules.length === 0}
                  <p>No modules found.</p>
              {/if}
              {#each appState.modules as mod}
                <div class="module_card" role="button" style="--cardColor: {cardColor}" tabindex="0" onclick={() => expandedModule === mod.module_id ? collapseModule() : (collapseModule(), expandedModule = mod.module_id)} onkeydown={(e) => e.key === 'Enter' && (expandedModule === mod.module_id ? collapseModule() : (collapseModule(), expandedModule = mod.module_id))}>
                    <div id="card_header_container">
                        <h2 class="card_header">{mod.module_name || mod.module_id}</h2>
                    </div>

                    <div id="card_actions">
                        <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={(e) => { e.stopPropagation(); toggleEditModule(mod); }}>
                            {@html EditIcon}
                        </button>
                        <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={(e) => { e.stopPropagation(); handleDeleteModule(mod.module_id); }}>
                            {@html DeleteIcon}
                        </button>
                    </div>

                    <span class="card_description"> {mod.description} </span>

                    {#if expandedModule === mod.module_id}
                        <div class="markers_section">

                              <h3 class="markers_section_header" >Markers</h3>

                              {#if mod.markers.length === 0}
                                  <p class="no_markers">No markers.</p>
                              {/if}
                              
                              {#each mod.markers as mk}
                                  <div style="--cardSectionColor: {cardSectionColor}" class="marker_row" role="button" tabindex="0"
                                      onclick={(e) => {
                                          e.stopPropagation();
                                          const isOpen = expandedMarkerDescription?.module_id === mod.module_id && expandedMarkerDescription?.marker_id === mk.marker_id;
                                          expandedMarkerDescription = isOpen ? null : { module_id: mod.module_id, marker_id: mk.marker_id };
                                      }}
                                      onkeydown={(e) => {
                                          if (e.key === 'Enter') {
                                              e.stopPropagation();
                                              const isOpen = expandedMarkerDescription?.module_id === mod.module_id && expandedMarkerDescription?.marker_id === mk.marker_id;
                                              expandedMarkerDescription = isOpen ? null : { module_id: mod.module_id, marker_id: mk.marker_id };
                                          }
                                      }}>
                                      <div class="marker_header_container">
                                        <span class="marker_id">{mk.marker_name || mk.marker_id}</span>
                                      </div>
                                      
                                      <div class="marker_buttons">
                                          <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={(e) => {e.stopPropagation(); toggleEditMarker(mod.module_id, mk)}}>{@html EditIcon}</button>
                                          <button style="--zoneRefBtnColor: {zoneRefBtnColor}" type="button" id="zone_refs_btn" onclick={(e) => {e.stopPropagation(); toggleZoneRef(mod.module_id, mk.marker_id)}}>{@html LevelsIcon}</button>
                                          <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={(e) => {e.stopPropagation(); handleDeleteMarker(mod.module_id, mk.marker_id)}}>{@html DeleteIcon}</button>
                                      </div>
                                      
                                      {#if expandedMarkerDescription?.module_id === mod.module_id && expandedMarkerDescription?.marker_id === mk.marker_id}
                                         <div class="marker_meta_container">
                                            <span class="marker_meta">{mk.description} — {mk.unit} ({mk.volatility_class})</span>
                                        </div>
                                      {/if}
                                  </div>

                                  {#if expandedZoneRef?.module_id === mod.module_id && expandedZoneRef?.marker_id === mk.marker_id}
                                      <div class="inline_form zone_refs_panel" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
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
                                                                      <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={() => handleEditDemoZone(mod.module_id, mk.marker_id, row.sex, row.age)}>Save</button>
                                                                      <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={() => editingDemoZone = null}>Cancel</button>
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
                                                                      <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={() => { editingDemoZone = { sex: row.sex, age: row.age }; editDemoZone = { healthy_min: row.healthy_min, healthy_max: row.healthy_max, vulnerability_margin: row.vulnerability_margin }; }}>{@html EditIcon}</button>
                                                                      <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={() => handleDeleteDemoZone(mod.module_id, mk.marker_id, row.sex, row.age)}>{@html DeleteIcon}</button>
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
                                              <div class="demo_zone_add_form" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
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

                                  {#if editingMarker && editingMarker.module_id === mod.module_id && editingMarker.marker_id === mk.marker_id}
                                      <div class="inline_form marker_edit_form" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
                                          <label>Marker Name <input type="text" bind:value={editMarker.marker_name}></label>
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
                                          <button style="--addBtnColor: {addBtnColor}" class="add_btn" type="button" onclick={() => handleEditMarker(mod.module_id, mk.marker_id)}>{@html AddIcon}</button>
                                          <button style="--deleteBtnColor: {deleteBtnColor}" class="delete_btn" type="button" onclick={() => editingMarker = null}>{@html DeleteIcon}</button>
                                      </div>
                                  {/if}
                              {/each}

                              <!-- Add marker form -->
                                {#if addingMarkerTo === mod.module_id}
                                  <div class="inline_form marker_edit_form" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
                                      <strong>New marker</strong>
                                      <label>Marker ID <input type="text" bind:value={newMarker.marker_id}></label>
                                      <label>Marker Name <input type="text" bind:value={newMarker.marker_name}></label>
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
                                  <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" id="add_marker_btn" onclick={(e) => { e.stopPropagation(); startAddMarker(mod.module_id); }}>{@html AddIcon}</button>
                              {/if}
                          </div>
                      {/if}

                      {#if editingModule && editingModule === mod.module_id}
                          <div class="inline_form" role="button" tabindex="0" onclick={(e) => { e.stopPropagation(); }} onkeydown={(e) => e.key === 'Enter' && e.stopPropagation()}>
                              <label>Name <input type="text" bind:value={editModuleName}></label>
                              <label>Description <input type="text" bind:value={editModuleDescription}></label>
                              <button type="button" onclick={() => handleEditModule(mod.module_id)}>Save</button>
                              <button type="button" onclick={() => editingModule = ""}>Cancel</button>
                          </div>
                      {/if}
                </div>
              {/each}
          {/if}

            {#if mode === "add"}
                <form id="new_mod_form">
                    <h2 id="new_mod_header">Add new module</h2>

                    <label for="new_module_name" id="new_mod_name">Module Name
                        <input type="text" id="new_module_name" bind:value={new_module_name}>
                    </label>
                    
                    <label for="new_module_id" id="new_mod_id">Module ID
                        <input type="text" id="new_module_id" bind:value={new_module_id}>
                    </label>
                    
                    <label for="new_module_description" id="new_mod_description">Description
                        <input type="text" id="new_module_description" bind:value={new_module_description}> 
                    </label>

                    <div id="add_new_mod_btn_container">
                        <button style="--addBtnColor: {addBtnColor}" type="button" class="add_btn" id="add_new_mod_btn" onclick={handleCreateModule}>{@html AddIcon}</button> 
                    </div>
                        
                </form>

                <div id="preview_container">
                    <h4>Preview:</h4>
                    <p>Module Name:{new_module_name}</p>
                    <p>Module ID: {new_module_id}</p>
                    <p>Description: {new_module_description}</p>
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
        box-shadow: 5px 5px 0px var(--borderColor);
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

    #viewedit_mod_btn {
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

    #add_marker_btn { 
        margin-top: 5px;
        justify-self: end;
    }

    #zone_refs_btn { 
        background-color: var(--zoneRefBtnColor); 
    }

    #add_new_mod_btn {
        justify-self: end;
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
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: var(--cardColor);
        box-shadow: 5px 5px 0px var(--borderColor);
        margin: 4px;
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

    .card_header{
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
        gap: 4px; 
    }

    /* .markers_header_container {
        grid-area: 3 / 1 / 4 / 2;
    } */

    .markers_section {
        grid-area: 4 / 1 / 5 / 3;
        display: grid;
        border-top: 2px solid var(--borderColor);
        margin-top: 8px;
        padding-top: 0;
    }

    .markers_section_header {
        padding: 4px 8px;
    }

    .marker_row {
        display: grid;
        grid-template: auto auto / auto auto;
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        box-shadow: 5px 5px 0px var(--borderColor);
        gap: 8px;
        padding: 4px 4px;
        background-color: var(--cardSectionColor);
        margin: 4px 4px;
        cursor: pointer;
    }

    .marker_header_container {
        grid-area: 1 / 1 / 2 / 2;
        display: flex;
        align-items: center;
    }

    .marker_id {
        font-weight: bold;
        flex: 1;
        min-width: 120px;
    }

    .marker_buttons {

        display: flex;
        justify-content: flex-end;
        align-items: center;
    }

    .marker_meta_container {
        grid-area: 2 / 1 / 3 / 3;
        padding: 8px 4px;
    }

    .marker_meta {
        width: 100%;
        padding: 8px 4px;
        border-top: 1px solid rgba(0,0,0,0.1);
        color: #555;
        font-size: 0.9em;
    }

    .no_markers { 
        color: #888; 
        font-style: italic; 
    }

    /* EDIT MARKERS INLINE FORM */
    .inline_form {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 5px;
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: lightyellow;
        padding: 8px;
        margin: 5px 0;
        box-shadow: 5px 5px 0px var(--borderColor);
    }

    .marker_edit_form label { 
        font-size: 0.85em; 
    }

    .marker_edit_form input, .marker_edit_form select { 
        width: 120px; 
    }

    /* ZONE REFERENCES INLINE FORM */
    .zone_refs_panel { 
        flex-direction: column; 
        align-items: flex-start; 
    }

    .zone_refs_table { 
        border-collapse: collapse; 
        font-size: 0.85em; 
        width: 100%; 
    }
    
    .zone_refs_table th, .zone_refs_table td { 
        border: 1px solid #ccc; 
        padding: 3px 6px; 
        text-align: center; 
    }
    
    .zone_refs_table th { 
        background: #eee; 
    }

    .demo_zone_add_form { 
        display: flex; 
        flex-wrap: wrap; gap: 5px; 
        align-items: center; 
        font-size: 0.85em; 
    }

    /* ADD MODE */
    #new_mod_form {
        display: grid;
        grid-template-columns: auto auto;
        grid-template-rows: auto auto auto auto;
        gap: 10px;
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px var(--borderColor);
        margin: 5px;
        padding: 5px;
    }

    #new_mod_form label {
        display: grid;
    }

    #new_mod_form input {
        margin-top: 5px;
        padding: 5px;
        border: 1px solid var(--borderColor);
        border-radius: 3px;
    }

    #preview_container {
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        background-color: #d0e8ff;
        box-shadow: 5px 5px 0px var(--borderColor);
        margin: 5px;
        padding: 5px;
    }

    #new_mod_header {
        grid-area: 1 / 1 / 2 / 3;
    }

    #new_mod_name {
        grid-area: 2 / 1 / 3 / 2;
    }

    #new_mod_id {
        grid-area: 2 / 2 / 3 / 3;
    }

    #new_mod_description {
        grid-area: 3 / 1 / 4 / 3;
    }

    #add_new_mod_btn_container {
        grid-area: 4 / 2 / 5 / 3;
        display: flex;
        justify-content: flex-end;
    }

  </style>
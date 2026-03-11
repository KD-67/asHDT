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
      import { gql } from "../lib/gql.js";

      let mode = $state("view");
      let modules = $state([]);
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

      onMount(loadModules);

      async function loadModules() {
          try {
              const data = await gql(
                  `query { modules { moduleId moduleName description markers {
                      markerId markerName description unit volatilityClass
                  } } }`
              );
              modules = data.modules.map(m => ({
                  module_id:   m.moduleId,
                  module_name: m.moduleName,
                  description: m.description,
                  markers:     m.markers.map(mk => ({
                      marker_id:        mk.markerId,
                      marker_name:      mk.markerName,
                      description:      mk.description,
                      unit:             mk.unit,
                      volatility_class: mk.volatilityClass,
                  })),
              }));
          } catch (e) {
              setStatus("Failed to load modules.", false);
          }
      }

      function setStatus(msg, ok = true) {
          statusMessage = msg;
          statusOk = ok;
      }

      // --- Module actions ---

      async function handleCreateModule() {
          if (!new_module_id.trim()) { setStatus("Module ID is required.", false); return; }
          try {
              await gql(
                  `mutation($input: ModuleInput!) { createModule(input: $input) { moduleId } }`,
                  { input: { moduleId: new_module_id.trim(), moduleName: new_module_name.trim(), description: new_module_description.trim() } }
              );
              setStatus(`Module "${new_module_id}" created.`);
              new_module_id = ""; new_module_description = "";
              mode = "view";
              await loadModules();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      function toggleEditModule(mod) {
          if (editingModule === mod.module_id) {
              editingModule = "";
              editModuleName = "";
              editModuleDescription = "";
          } else {
              editingModule = mod.module_id;
              editModuleName = mod.module_name ?? "";
              editModuleDescription = mod.description;
          }
          statusMessage = "";
      }

      async function handleEditModule(module_id) {
          try {
              await gql(
                  `mutation($id: String!, $input: ModuleUpdateInput!) { updateModule(moduleId: $id, input: $input) { moduleId } }`,
                  { id: module_id, input: { moduleName: editModuleName, description: editModuleDescription } }
              );
              setStatus(`Module "${module_id}" updated.`);
              editingModule = "";
              await loadModules();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      async function handleDeleteModule(module_id) {
          if (!confirm(`Delete module "${module_id}"? This cannot be undone.`)) return;
          try {
              await gql(
                  `mutation($id: String!) { deleteModule(moduleId: $id) }`,
                  { id: module_id }
              );
              setStatus(`Module "${module_id}" deleted.`);
              if (expandedModule === module_id) collapseModule();
              await loadModules();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      // --- Marker actions ---

      function startAddMarker(module_id) {
          addingMarkerTo = module_id;
          newMarker = emptyMarker();
          statusMessage = "";
      }

      async function handleAddMarker(module_id) {
          const hMin    = parseFloat(newMarker.healthy_min);
          const hMax    = parseFloat(newMarker.healthy_max);
          const vMargin = parseFloat(newMarker.vulnerability_margin);
          if (isNaN(hMin) || isNaN(hMax) || isNaN(vMargin)) {
              setStatus("Healthy min, max, and vulnerability margin must be numbers.", false);
              return;
          }
          try {
              await gql(
                  `mutation($mo: String!, $input: MarkerInput!) { createMarker(moduleId: $mo, input: $input) { markerId } }`,
                  {
                      mo: module_id,
                      input: {
                          markerId:            newMarker.marker_id.trim(),
                          markerName:          newMarker.marker_name.trim(),
                          description:         newMarker.description.trim(),
                          unit:                newMarker.unit.trim(),
                          volatilityClass:     newMarker.volatility_class.trim(),
                          healthyMin:          hMin,
                          healthyMax:          hMax,
                          vulnerabilityMargin: vMargin,
                      },
                  }
              );
              setStatus(`Marker "${newMarker.marker_id}" added to "${module_id}".`);
              addingMarkerTo = "";
              await loadModules();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      function toggleEditMarker(module_id, mk) {
          if (editingMarker?.module_id === module_id && editingMarker?.marker_id === mk.marker_id) {
              editingMarker = null;
              editMarker = emptyMarker();
          } else {
              editingMarker = { module_id, marker_id: mk.marker_id };
              editMarker = { ...mk };
          }
          statusMessage = "";
      }

      async function handleEditMarker(module_id, marker_id) {
          try {
              await gql(
                  `mutation($mo: String!, $ma: String!, $input: MarkerUpdateInput!) { updateMarker(moduleId: $mo, markerId: $ma, input: $input) { markerId } }`,
                  {
                      mo: module_id, ma: marker_id,
                      input: {
                          markerName:          editMarker.marker_name,
                          description:         editMarker.description,
                          unit:                editMarker.unit,
                          volatilityClass:     editMarker.volatility_class,
                          healthyMin:          parseFloat(editMarker.healthy_min),
                          healthyMax:          parseFloat(editMarker.healthy_max),
                          vulnerabilityMargin: parseFloat(editMarker.vulnerability_margin),
                      },
                  }
              );
              setStatus(`Marker "${marker_id}" updated.`);
              editingMarker = null;
              await loadModules();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
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
          try {
              const data = await gql(
                  `query($mo: String!, $ma: String!) {
                      demographicZones(moduleId: $mo, markerId: $ma) {
                          sex age healthyMin healthyMax vulnerabilityMargin
                      }
                  }`,
                  { mo: module_id, ma: marker_id }
              );
              zoneRefRows = data.demographicZones.map(r => ({
                  sex:                  r.sex,
                  age:                  r.age,
                  healthy_min:          r.healthyMin,
                  healthy_max:          r.healthyMax,
                  vulnerability_margin: r.vulnerabilityMargin,
              }));
          } catch (e) {
              setStatus("Failed to load zone references.", false);
          }
      }

      async function handleAddDemoZone(module_id, marker_id) {
          try {
              await gql(
                  `mutation($mo: String!, $ma: String!, $input: DemographicZoneInput!) {
                      addDemographicZone(moduleId: $mo, markerId: $ma, input: $input) { sex age }
                  }`,
                  {
                      mo: module_id, ma: marker_id,
                      input: {
                          sex:                 newDemoZone.sex,
                          age:                 parseInt(newDemoZone.age),
                          healthyMin:          parseFloat(newDemoZone.healthy_min),
                          healthyMax:          parseFloat(newDemoZone.healthy_max),
                          vulnerabilityMargin: parseFloat(newDemoZone.vulnerability_margin),
                      },
                  }
              );
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
              await gql(
                  `mutation($mo: String!, $ma: String!, $sex: String!, $age: Int!, $input: ZoneBoundaryInput!) {
                      updateDemographicZone(moduleId: $mo, markerId: $ma, sex: $sex, age: $age, input: $input) { sex age }
                  }`,
                  {
                      mo: module_id, ma: marker_id, sex, age,
                      input: {
                          healthyMin:          parseFloat(editDemoZone.healthy_min),
                          healthyMax:          parseFloat(editDemoZone.healthy_max),
                          vulnerabilityMargin: parseFloat(editDemoZone.vulnerability_margin),
                      },
                  }
              );
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
              await gql(
                  `mutation($mo: String!, $ma: String!, $sex: String!, $age: Int!) {
                      deleteDemographicZone(moduleId: $mo, markerId: $ma, sex: $sex, age: $age)
                  }`,
                  { mo: module_id, ma: marker_id, sex, age }
              );
              setStatus("Demographic zone row deleted.");
              await loadZoneRefs(module_id, marker_id);
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      async function handleDeleteMarker(module_id, marker_id) {
          if (!confirm(`Delete marker "${marker_id}" from "${module_id}"?`)) return;
          try {
              await gql(
                  `mutation($mo: String!, $ma: String!) { deleteMarker(moduleId: $mo, markerId: $ma) }`,
                  { mo: module_id, ma: marker_id }
              );
              setStatus(`Marker "${marker_id}" deleted.`);
              await loadModules();
          } catch (e) {
              setStatus(`Error: ${e.message}`, false);
          }
      }

      function collapseModule() {
            expandedModule = "";
            editingModule = "";
            editModuleName = "";
            editModuleDescription = "";
            addingMarkerTo = "";
            newMarker = emptyMarker();  
            editingMarker = null;
            editMarker = emptyMarker();
            expandedZoneRef = null;
            zoneRefRows = [];
            addingDemoZone = false;
            newDemoZone = { sex: "M", age: "", healthy_min: "", healthy_max: "", vulnerability_margin:  
        "" };
            editingDemoZone = null;
            editDemoZone = { healthy_min: "", healthy_max: "", vulnerability_margin: "" };
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
          <!-- VIEW / EDIT MODE -->
          {#if mode === "view"}
              {#if modules.length === 0}
                  <p>No modules found.</p>
              {/if}
              {#each modules as mod}
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
                                  <div style="--cardSectionColor: {cardSectionColor}" class="marker_row">
                                      <span class="marker_id">{mk.marker_name || mk.marker_id}</span>
                                      <span class="marker_meta">{mk.description} — {mk.unit} ({mk.volatility_class})</span>
                                      <button style="--editBtnColor: {editBtnColor}" type="button" class="edit_btn" onclick={(e) => {e.stopPropagation(); toggleEditMarker(mod.module_id, mk)}}>{@html EditIcon}</button>
                                      <button style="--zoneRefBtnColor: {zoneRefBtnColor}" type="button" id="zone_refs_btn" onclick={(e) => {e.stopPropagation(); toggleZoneRef(mod.module_id, mk.marker_id)}}>{@html LevelsIcon}</button>
                                      <button style="--deleteBtnColor: {deleteBtnColor}" type="button" class="delete_btn" onclick={(e) => {e.stopPropagation(); handleDeleteMarker(mod.module_id, mk.marker_id)}}>{@html DeleteIcon}</button>
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
        gap: 5px; 
    }

    /* .markers_header_container {
        grid-area: 3 / 1 / 4 / 2;
    } */

    .markers_section {
        grid-area: 4 / 1 / 5 / 3;
        display: grid;
        border-top: 2px solid var(--borderColor);
        margin-top: 10px;
        padding-top: 0;
    }

    .markers_section_header {
        padding-left: 10px;
    }

    .marker_row {
        display: flex;
        align-items: center;
        border: 2px solid var(--borderColor);
        border-radius: 0.5rem;
        box-shadow: 5px 5px 0px var(--borderColor);
        gap: 8px;
        padding: 3px 3px;
        background-color: var(--cardSectionColor);
        margin: 5px 5px;
    }

    .marker_id { 
        font-weight: bold; 
        min-width: 120px; 
    }
    
    .marker_meta { 
        flex: 1; 
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
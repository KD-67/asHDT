<script>
import SubjectManagement from "./subject_management.svelte";
import AddModulePage from "./add_module_page.svelte";
import DatasetManagement from "./dataset_management.svelte";
</script>


<main>

<div id="main_container">

    <div class="subpage_container" id="header_container">
        <h2>Data Management Options</h2>
    </div>

    <div class="subpage_container" id="subject_btn_container">
        <a class="subpage_button" href="http://localhost:5173/#subject_management">Subject Management</a>
        <ul>
            <li>Subject Profiles</li>
            <li>Associated Datasets</li>
        </ul>
    </div>
    
    <div class="subpage_container" id="module_btn_container">
        <a class="subpage_button" href="http://localhost:5173/#add_module_page">Module Management</a>
        <ul>
            <li>Active Modules</li>
            <li>Associated Markers</li>
        </ul>
    </div>
    
    <div class="subpage_container" id="dataset_btn_container">
        <a class="subpage_button" href="http://localhost:5173/#dataset_management">Dataset Management</a>
        <ul>
            <li>Markerset templates</li>
            <li>Analysis method optimization</li>
        </ul>
    </div>
       
</div>

</main>


<style>

#main_container {
    height: 25vh;
    width: 50vw;
    display: grid;
    grid-template-columns: auto auto auto;
    grid-template-rows: auto auto;
    padding: 1rem;
    margin: 0 auto;
    gap: 15px;
}

#header_container {
    grid-area: 1 / 2 / 2 / 3;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.subpage_container {
    display: flex;
    flex-direction: column;
    justify-content: center;
}

#subject_btn_container {
    grid-area: 2 / 1 / 3 / 2;
}

#module_btn_container {
    grid-area: 2 / 2 / 3 / 3;
}

#dataset_btn_container {
    grid-area: 2 / 3 / 3 / 4;
}

.subpage_button {
  background-color: #fbeee0;
  border: 2px solid #422800;
  border-radius: 30px;
  box-shadow: #422800 4px 4px 0 0;
  color: #422800;
  cursor: pointer;
  display: inline-block;
  font-weight: 600;
  font-size: 18px;
  padding: 0 18px;
  line-height: 50px;
  text-align: center;
  text-decoration: none;
}

.subpage_button:hover {
  background-color: #45c8fc;
  transform: scale(105%);
}

.subpage_button:active {
  box-shadow: #422800 2px 2px 0 0;
  transform: translate(2px, 2px);
}

</style>

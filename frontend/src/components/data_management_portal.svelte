<script>
import SubjectManagement from "./subject_management.svelte";
import AddModulePage from "./add_module_page.svelte";
import DatasetManagement from "./dataset_management.svelte";
</script>


<main>
<div id="test_div">TESTING DATA MANAGEMENT PORTAL</div>

<div id="main_container">

    <div class="subpage_container">
        <div>Click here to edit the subject list:</div>
        <a class="subpage_button" href="http://localhost:5173/#subject_management">Subject Management</a>
    </div>
    
    <div class="subpage_container">
        <div>Click here to edit the module list:</div>
        <a class="subpage_button" href="http://localhost:5173/#add_module_page">Module Management</a>
    </div>
    
    <div class="subpage_container">
        <div>Click here to edit datasets:</div>
        <a class="subpage_button" href="http://localhost:5173/#dataset_management">Dataset Management</a>
    </div>
       
</div>

</main>


<style>

#main_container {
    border: 1px solid black;
    display: flex;
    justify-content: space-evenly;
    padding: 1rem;
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
}

.subpage_button:active {
  box-shadow: #422800 2px 2px 0 0;
  transform: translate(2px, 2px);
}

</style>

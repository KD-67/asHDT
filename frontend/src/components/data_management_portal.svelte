<script>
import SubjectManagement from "./subject_management.svelte";
import AddModulePage from "./add_module_page.svelte";
import DatasetManagement from "./dataset_management.svelte";
</script>


<main>
<div id="test_div">TESTING DATA MANAGEMENT PORTAL</div>

<div id="main_container">
    <a href="http://localhost:5173/#new_user_form">Subject Management</a>
    <a href="http://localhost:5173/#add_module_page">Module Management</a>
    <a href="http://localhost:5173/#dataset_management">Dataset Management</a>
</div>

</main>


<style>

#main_container {
    border: 1px solid black;
    display: flex;
    justify-content: space-evenly;
    padding: 1rem;
}

</style>
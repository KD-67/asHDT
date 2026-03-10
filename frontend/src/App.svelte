<script>
    import { onMount } from "svelte";
    import HomeDiv from "./components/home_div.svelte";
    import DataManagementPortal from "./components/data_management_portal.svelte";
    import RequestReportForm from "./components/request_report_form.svelte";
    import SubjectManagement from "./components/subject_management.svelte";
    import AddModulePage from "./components/add_module_page.svelte";
    import DatasetManagement from "./components/dataset_management.svelte";
    import Help from "./components/help.svelte";                                                                              
    import Timegraph from "./components/timegraph_report_page.svelte";                                                                      
    

    let currentPage = window.location.hash.slice(1) || "home";

    onMount(() => {
      window.addEventListener("hashchange", () => {
        currentPage = window.location.hash.slice(1) || "home";
      });
    });
</script>

<main>
  <header>
    <a id="main_page_header" href="http://localhost:5173/#home">
    asHDT: Health Data Tracker 
    </a>

  <div class="nav_bar">
      <a class="nav_link" href="http://localhost:5173/#home">Home</a>
      <a class="nav_link" href="http://localhost:5173/#data_management_portal">Data Management Portal</a>
      <a class="nav_link" href="http://localhost:5173/#request_report_form">Request Report</a>
      <a class="nav_link" href="http://localhost:5173/#help">Help</a>
  </div>

</header>
  

  {#if currentPage == "home"}
    <HomeDiv />
  {:else if currentPage == "data_management_portal"}
    <DataManagementPortal />  
  {:else if currentPage == "request_report_form"}
    <RequestReportForm />
  {:else if currentPage == "subject_management"}
    <SubjectManagement />
  {:else if currentPage == "add_module_page"}
    <AddModulePage />
  {:else if currentPage == "dataset_management"}
    <DatasetManagement />
  {:else if currentPage == "help"}
    <Help />
  {:else if currentPage == "timegraph"}
    <Timegraph />
  {/if}
</main>

<style>
  * {
    font-family: sans-serif;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  #main_page_header {
    text-decoration: none;
    color: black;
    font-size: 50px;
  }

  .nav_bar {
    display: flex;
    justify-content: space-between;
    padding: 3px 1px;
  }

  .nav_link {
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
    margin: 0 4px;
    line-height: 50px;
    text-align: center;
    text-decoration: none;
  }

  .nav_link:hover {
  background-color: rgb(255, 189, 189);
  transform: scale(105%);
  }

  .nav_link:active {
  box-shadow: #422800 2px 2px 0 0;
  transform: translate(2px, 2px);
}

</style>

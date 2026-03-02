<script>
    import { onMount } from "svelte";
    import HomeDiv from "./components/home_div.svelte";
    import RequestReportForm from "./components/request_report_form.svelte";
    import NewUserForm from "./components/new_user_form.svelte";
    import AddModulePage from "./components/add_module_page.svelte";
    import Help from "./components/help.svelte";                                                                              
    import Timegraph from "./routes/timegraph_report_page.svelte";                                                                      
    

    let currentPage = window.location.hash.slice(1) || "home";

    onMount(() => {
      window.addEventListener("hashchange", () => {
        currentPage = window.location.hash.slice(1) || "home";
      });
    });
</script>

<main>
  <header>
    <h1>
    asHDT: Health Data Tracker 
  </h1>

  <nav id="nav_bar">
    <div class="nav_link_container">
      <a href="http://localhost:5173/#home">Home</a>
    </div>
    
    <div class="nav_link_container">
      <a href="http://localhost:5173/#request_report_form">Request Report</a>
    </div>

    <div class="nav_link_container">
      <a href="http://localhost:5173/#new_user_form">Add New User</a>
    </div>

    <div class="nav_link_container">
      <a href="http://localhost:5173/#add_module_page">Add New Module</a>
    </div>

    <div class="nav_link_container">
      <a href="http://localhost:5173/#help">Help</a>
    </div>
  </nav>
</header>
  

  {#if currentPage == "home"}
    <HomeDiv />  
  {:else if currentPage == "request_report_form"}
    <RequestReportForm />
  {:else if currentPage == "new_user_form"}
    <NewUserForm />
  {:else if currentPage == "add_module_page"}
    <AddModulePage />
  {:else if currentPage == "help"}
    <Help />
  {:else if currentPage == "timegraph"}
    <Timegraph />
  {/if}
</main>

<style>
  header {
    border: 1px solid black;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  h1 {
    border: 1px solid black;
  }

  #nav_bar {
    border: 2px solid black;
    display: flex;
    justify-content: space-between;
    padding: 3px 1px;
  }

  .nav_link_container {
    border: 1px solid black;
    margin: 1px 5px;
    padding: 25px 5px;
  }

  .nav_link_container:hover {
  background-color: rgb(255, 189, 189);
  }

  .nav_link_container:hover > a {
    font-weight: bold;
  }
</style>

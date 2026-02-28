<script>
    import { onMount } from "svelte";                                                                                       
    import Timegraph from "./routes/timegraph_report_page.svelte";                                                                      
    import RequestReportForm from "./components/Request_Report_Form.svelte";

    let currentPage = window.location.hash.slice(1) || "form";

    onMount(() => {
      window.addEventListener("hashchange", () => {
        currentPage = window.location.hash.slice(1) || "form";
      });
    });
</script>

<main>
  <h1>
    asHDT: Health Data Tracker 
  </h1>

  {#if currentPage == "form"}
  <RequestReportForm />
  {:else if currentPage == "timegraph"}
    <Timegraph />
  {/if}
</main>


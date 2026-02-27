<script>
    import { onMount } from "svelte";                                                                                       
    import Timegraph from "./routes/timegraph.svelte";                                                                      
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
    Health Trajectory Report Form
  </h1>

  {#if currentPage == "form"}
  <RequestReportForm on:reportSubmitted={() => {
    window.location.hash = "timegraph";
  }}/>
  {:else if currentPage == "timegraph"}
    <Timegraph />
  {/if}
</main>


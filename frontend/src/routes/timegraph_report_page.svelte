<script>
    import { onMount } from "svelte";
    import TimegraphChart from "../components/timegraph_chart.svelte";
    import TimegraphTable from "../components/timegraph_table.svelte";

    let reportData = $state({});

    onMount(() => {
         const stored = localStorage.getItem("timegraph_report");
         if (stored) {
            reportData = JSON.parse(stored);
         }
     });
  </script>

  <h1>Timegraph Report Page</h1>
  <TimegraphChart {reportData} />
  <TimegraphTable {reportData} />
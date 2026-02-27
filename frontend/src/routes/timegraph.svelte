<script>
      import { onMount } from "svelte";
      let reportData = {};

      onMount(() => {
          const stored = sessionStorage.getItem("timegraph_report");
          if (stored) {
              reportData = JSON.parse(stored);
          }
      });
  </script>

  <h1>Timegraph Report</h1>
  <pre>{JSON.stringify(reportData, null, 2)}</pre>
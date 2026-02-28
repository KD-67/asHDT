<script>
  // reportData is passed in from parent component (timegraph_report_page)
  let { reportData } = $props()

  // Background colors for each health zone row
  const ZONE_BG = {
    non_pathology: '#dcfce7',
    vulnerability:  '#fef9c3',
    pathology:      '#fee2e2',
  }

  // Formats a number to `dec` decimal places, returns '—' for null/undefined
  function fmt(v, dec = 4) {
    return v == null ? '—' : Number(v).toFixed(dec)
  }
</script>

<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Timestamp</th>
        <th>Health Score</th>
        <th>Raw Value</th>
        <th>Quality</th>
        <th>Zone</th>
        <th>f′</th>
        <th>f″</th>
        <th>State</th>
        <th>Time-to-Transition (h)</th>
      </tr>
    </thead>
    <tbody>
      {#each reportData.datapoints as dp}
        <tr style="background:{ZONE_BG[dp.zone]}">
          <td>{dp.timestamp}</td>
          <td>{fmt(dp.health_score)}</td>
          <td>{fmt(dp.raw_value, 2)}</td>
          <td>{dp.data_quality}</td>
          <td>{dp.zone}</td>
          <td>{fmt(dp.f_prime, 5)}</td>
          <td>{fmt(dp.f_double_prime, 5)}</td>
          <td>{dp.trajectory_state}</td>
          <td>{dp.time_to_transition_hours != null ? fmt(dp.time_to_transition_hours, 1) : '—'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .table-wrap {
    overflow-x: auto;
    margin-bottom: 2rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  th, td {
    padding: 0.35rem 0.6rem;
    border: 1px solid #e5e7eb;
    white-space: nowrap;
  }
  th {
    background: #f1f5f9;
    font-weight: 600;
    text-align: left;
  }
</style>

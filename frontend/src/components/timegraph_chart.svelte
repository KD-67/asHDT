<script>
    import Plotly from 'plotly.js-dist-min'

    let { reportData } = $props() // reportData is passed in from parent component (timegraph_report_page)

    let chartDiv

    const QUALITY_SIZE = { good: 12, degraded: 12, bad: 12 }
    const ZONE_COLOR   = { non_pathology: '#22c55e', vulnerability: '#f59e0b', pathology: '#ef4444' }

    // Evaluates a polynomial at x using Horner's method.
    function polyval(coeffs, x) {
      return coeffs.reduce((acc, c) => acc * x + c, 0)
    }

    // Builds the Plotly traces: scatter & fitted curve
    function buildTraces(report) {
      const { datapoints, fit_metadata } = report
      const { coefficients, t0_iso, zone_boundaries } = fit_metadata
      const vm = zone_boundaries.vulnerability_margin
      const t0 = new Date(t0_iso) // reference timestamp (x_hours = 0)

      // Trace 1: health score measurements, colored and sized by zone/quality
      const scatter = {
        name: 'Calculated H-score value',
        type: 'scatter',
        mode: 'markers',
        x: datapoints.map(d => d.timestamp),
        y: datapoints.map(d => d.health_score),
        marker: {
          size: datapoints.map(d => QUALITY_SIZE[d.data_quality] ?? 8),
          color: datapoints.map(d => ZONE_COLOR[d.zone]),
          line: { width: 1, color: '#fff' },
        },
        hovertemplate: '%{x}<br>h = %{y:.4f}<extra></extra>',
      }

      // Trace 2: fitted polynomial curve, evaluated client-side at 120 evenly-spaced points
      // x_hours values are converted back to ISO timestamps for the shared date x-axis
      const xMin = datapoints[0].x_hours
      const xMax = datapoints[datapoints.length - 1].x_hours
      const curveX = Array.from({ length: 120 }, (_, i) => xMin + (i / 119) * (xMax - xMin))
      const curveTimestamps = curveX.map(x => new Date(t0.getTime() + x * 3_600_000).toISOString())
      const curveY = curveX.map(x => polyval(coefficients, x))

      const fittedCurve = {
        name: 'Fitted curve',
        type: 'scatter',
        mode: 'lines',
        x: curveTimestamps,
        y: curveY,
        line: { color: '#3b82f6', width: 2, dash: 'dash' },
        hoverinfo: 'skip',
      }
      return [scatter, fittedCurve]
    }

    // Builds the Plotly layout: zone background shading, axes, legend
    function buildLayout(report) {
      const vm = report.fit_metadata.zone_boundaries.vulnerability_margin

      // Background rectangles shading the three health zones on the primary y-axis:
      const zoneShapes = [
        {
          type: 'rect', xref: 'paper', yref: 'y',
          x0: 0, x1: 1, y0: vm, y1: 1.15,
          fillcolor: 'rgba(34,197,94,0.12)', line: { width: 0 }, layer: 'below',
        },
        {
          type: 'rect', xref: 'paper', yref: 'y',
          x0: 0, x1: 1, y0: -vm, y1: vm,
          fillcolor: 'rgba(245,158,11,0.15)', line: { width: 0 }, layer: 'below',
        },
        {
          type: 'rect', xref: 'paper', yref: 'y',
          x0: 0, x1: 1, y0: -1.15, y1: -vm,
          fillcolor: 'rgba(239,68,68,0.12)', line: { width: 0 }, layer: 'below',
        },
      ]

      return {
        shapes: zoneShapes,
        margin: { t: 30, r: 80, b: 60, l: 60 },
        xaxis: { type: 'date', title: 'Time' },
        yaxis: { title: 'Health Score (h)', range: [-1.2, 1.2], zeroline: true },
        legend: { orientation: 'h', y: -0.15 },
      }
    }

    // Re-renders the chart whenever reportData or chartDiv changes.
    // Plotly.react() updates an existing plot in place (more efficient than newPlot on re-renders)
    $effect(() => {
      if (!reportData || !reportData.datapoints?.length || !chartDiv) return
      Plotly.react(chartDiv, buildTraces(reportData), buildLayout(reportData), { responsive: true })
    })
  </script>

  <div>
    <h2>Timegraph Chart</h2>
    <div bind:this={chartDiv}></div>
  </div>
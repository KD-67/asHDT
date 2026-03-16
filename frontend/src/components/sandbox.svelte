<script>
  import { appState } from "../lib/stores.svelte";
  import { gqlUpload } from "../lib/gql.js";

  let loading = $state(false);
  let selected_method = $state("PCA");
  let selected_subject = $state("please select a method");
  let result = $state(null);
  let error = $state(null);

  const COMPUTE_PCA = `
    mutation ComputePCA($file: Upload!) {
      computePca(file: $file) {
        components
        variance
      }
    }
  `;

  async function handleSubmit(e) {
    e.preventDefault();
    result = null;
    error = null;

    if (selected_method === "PCA") {
      const fileInput = document.getElementById("CSV_upload");
      if (!fileInput.files[0]) {
        error = "Please select a CSV file.";
        return;
      }
      loading = true;
      try {
        const data = await gqlUpload(COMPUTE_PCA, {}, "file", fileInput.files[0]);
        result = data.computePca;
      } catch (err) {
        error = err.message;
      } finally {
        loading = false;
      }
    }
  }
</script>

<main>
    <div id="main_container">
        <h3>SANDBOX!!</h3>
        <form onsubmit={handleSubmit}>
            <label for="method_select">Analysis method:</label>
            <select name="method_select" id="method_select" bind:value={selected_method}>
                <option value="PCA">Principal Component Analysis (PCA)</option>
                <option value="t-SNE">t=Distributed Stochastic Neighbor Embedding (Coming Soon)</option>
                <option value="UMAP">Uniform Manifold Approximation and Projection (Coming Soon)</option>
            </select>

            <label for="subject_select">Subject:</label>
            <select name="subject_select" id="subject_select" bind:value={selected_subject}>
                    {#each appState.subjects as subject}
                        <option value={subject}>{subject.first_name} {subject.last_name} ({subject.subject_id})</option>
                    {/each}
            </select>

                <br><br>

            <fieldset>
                <legend>{selected_method}</legend>
                {#if selected_method === "PCA"}
                    <label for="CSV_upload">Please upload CSV file with dataset:</label>
                    <input type="file" name="CSV_upload" id="CSV_upload" accept=".csv">
                    <button type="submit" disabled={loading}>{loading ? "Running..." : "Submit"}</button>
                {/if}
            </fieldset>
        </form>

        {#if error}
            <p style="color: red;">{error}</p>
        {/if}

        {#if result}
            <div id="pca_result">
                <h4>PCA Result</h4>
                <p><strong>Explained Variance Ratio:</strong></p>
                <pre>{result.variance.map((v, i) => `PC${i+1}: ${(v * 100).toFixed(2)}%`).join("\n")}</pre>
                <p><strong>Components (first 2 PCs, first 10 rows):</strong></p>
                <pre>{result.components.slice(0, 10).map((row, i) => `Row ${i+1}: [${row.map(v => v.toFixed(4)).join(", ")}]`).join("\n")}</pre>
            </div>
        {/if}
    </div>
</main>

<style>
    #main_container {
        border: 1px solid black;
        padding: 8px;
    }
</style>

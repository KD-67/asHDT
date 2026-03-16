<script>
  import { appState } from "../lib/stores.svelte";

    let loading = $state(false);
    let selected_method = $state("PCA");
    let selected_subject = $state("please select a method");

    

</script>

<main>
    <div id="main_container">
        <h3>SANDBOX!!</h3>
        <form>
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
                    <button type="submit">Submit</button>
                {/if}
            </fieldset>
        </form>

             
    </div>
</main>

<style>
    #main_container {
        border: 1px solid black;
        padding: 8px;
    }
</style>
<script>
    let loading = $state(false);
    let selected_method = $state("please select a method");
    let selected_subject = $state("please select a method");
    let subjects = $state([]);
    let subject_names = $state({});

    

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
            <p>Selected method: {selected_method}</p>
            
            <label for="subject_select">Subject:</label>
                <select name="subject_select" id="subject_select" bind:value={selected_subject}>
                    <option value="">
                        {#each subjects as subject}
                            <option value={subject}>{subject_names[subject] ?? subject}</option>
                        {/each}
                    </option>
                </select>
        </form>

             
    </div>
</main>

<style>
    #main_container {
        border: 1px solid black;
    }
</style>
<!-- This is a copy-pastable template for creating components that interact with backend ENDPOINTS.-->

<script>

// For GET requests:
    let data = [];

    async function fetchData() {                                                // defines async function
        const response = await fetch("http://localhost:8000/DESIRED_ENDPOINT"); // await == pause here until server responds, fetch == send GET request to specified URL. (response does not contain the requested data, just metadata)
        const data_json = await response.json();                                // converts server's response body into json (if needed)
        data = data_json                                                        // updates reactive svelte variable subjects
    }

    fetchData();                                                                // calls the function immediately when the component loads

// For POST requests:
      let result = null;

      async function postData() {
          const response = await fetch("http://localhost:8000/YOUR_ENDPOINT", 
            {
              method: "POST",                                                   // must specify method:POST (if you say nothing it assumes GET)
              headers: { "Content-Type": "application/json" },                  // must specify what type of data format you're sending
              body: JSON.stringify({                                            // request body must match the pydantic model defined in routes.py, the values will be bound to the declared variables
                  // your request body here, ex:
                  // subject_id: subject_id (from user input)
                  // module_id: module_id
                  // etc...
              })
            });
          result = await response.json();
      }

      postData();

</script>

<!-- Display the subjects returned from the backend -->
<h2>Data from backend:</h2>

<ul>
    {#each data as datum}
        <ul>{datum}</ul>
    {:else}
        <li>No subjects found (or backend not running)</li>
    {/each}
</ul>

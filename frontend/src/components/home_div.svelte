<script></script>

<main>
    <h3>HOMEPAGE: App architecture</h3>

    <div id="universe">
        <div id="main_app">
            <span>main app</span>

            <div id="frontend">
                <span>frontend</span>
                <div class="functional_file">home_div.svelte</div>
                <div class="functional_file">data_management_portal.svelte</div>
                <div class="functional_file">request_report_form.svelte</div>
                <div class="functional_file">subject_management.svelte</div>
                <div class="functional_file">add_module_page.svelte</div>
                <div class="functional_file">dataset_management.svelte</div>
                <div class="functional_file">help.svelte</div>
                <div>timegraph_report_page.svelte
                    <div class="functional_file">timegraph_chart.svelte</div>
                    <div class="functional_file">timegraph_table.svelte</div>
                </div>
                <div class="functional_file">lib/gql.js</div>
            </div>

            <div id="backend">
                <span>backend</span>
                <div class="functional_file">main.py</div>
                <div>
                    <span>startup</span>
                    <div class="functional_file">module_loader.py</div>
                    <div class="functional_file">database_logistics.py</div>
                </div>
                <div>
                    <span>graphql</span>
                    <div class="functional_file">schema.py</div>
                    <div class="functional_file">context.py</div>
                    <div class="functional_file">dataloaders.py</div>
                    <div>
                        <span>resolvers</span>
                        <div class="functional_file">queries.py</div>
                        <div class="functional_file">mutations.py</div>
                        <div class="functional_file">subscriptions.py</div>
                    </div>
                    <div>
                        <span>types</span>
                        <div class="functional_file">subject.py</div>
                        <div class="functional_file">module.py</div>
                        <div class="functional_file">datapoint.py</div>
                        <div class="functional_file">analysis.py</div>
                    </div>
                </div>
                <div id="core">
                    <span>core</span>
                    <div class="backend_core" id="analysis">
                        <span>analysis</span>
                        <div class="functional_file">trajectory_computer.py</div>
                    </div>
                    <div class="backend_core" id="storage">
                        <span>storage</span>
                        <div class="functional_file">data_reader.py</div>
                    </div>
                    <div class="backend_core" id="output">
                        <span>output</span>
                        <div class="functional_file">report_generator.py</div>
                    </div>
                </div>
                <div>
                    <span>workers</span>
                    <div class="functional_file">analysis_tasks.py</div>
                    <div class="functional_file">settings.py</div>
                </div>
            </div>

            <div id="database">
                <span>database (SQLite)</span>
                <div class="functional_file">table: subjects</div>
                <div class="functional_file">table: timegraph_reports</div>
                <div class="functional_file">table: zone_references</div>
                <div class="functional_file">table: modules</div>
                <div class="functional_file">table: markers</div>
                <div class="functional_file">table: {"{subject}__{module}__{marker}"} (dynamic)</div>
            </div>

            <div id="redis">
                <span>Redis</span>
                <div class="functional_file">job queue (ARQ)</div>
                <div class="functional_file">pub/sub: job:{"{job_id}"}</div>
            </div>
        </div>
        <div id="arch_guide">
            <h4>How the app works</h4>

            <p>The app is split into two main parts: a <strong>frontend</strong> (what you see in the browser) and a <strong>backend</strong> (a server running on your machine that does the heavy lifting).</p>

            <h5>Frontend</h5>
            <p>The frontend is built with <strong>Svelte</strong>, a framework for building interactive web pages. Each <code>.svelte</code> file is a self-contained page or component. Navigation between pages happens via URL hash (e.g. <code>#subject_management</code>). The frontend talks to the backend by sending <strong>GraphQL</strong> requests — a structured way of asking for exactly the data it needs, nothing more.</p>

            <h5>Backend</h5>
            <p>The backend is a <strong>Python</strong> server built with <strong>FastAPI</strong>. When it starts up, it reads data from the filesystem and syncs it into a local <strong>SQLite</strong> database (a simple file-based database). It then exposes a <strong>GraphQL API</strong> at <code>/graphql</code> — this is the single endpoint the frontend talks to for all reads and writes (fetching subjects, uploading data, requesting reports, etc.).</p>

            <h5>Analysis jobs</h5>
            <p>Running a trajectory analysis is slow, so it happens asynchronously — meaning the server doesn't freeze while it works. When you request a report, the backend puts a job into a queue managed by <strong>Redis</strong> (a fast in-memory data store). A separate <strong>worker process</strong> (ARQ) picks up the job and runs the analysis pipeline: reading raw data files → computing the trajectory → saving the report. While this runs, the frontend receives live progress updates via a <strong>WebSocket</strong> connection (a persistent two-way channel, as opposed to normal one-shot HTTP requests).</p>

            <h5>Core analysis pipeline</h5>
            <p><strong>data_reader.py</strong> reads raw JSON measurement files from the filesystem. <strong>trajectory_computer.py</strong> normalises the raw values into a health score (1 = optimal, 0 = edge of healthy range, negative = outside), fits a polynomial curve to the data using <strong>NumPy</strong>, and classifies each point into one of 27 trajectory states based on its value, slope, and curvature. <strong>report_generator.py</strong> saves the result both as a JSON file and as a row in the SQLite database.</p>

            <h5>Database</h5>
            <p>The SQLite database stores structured records: subjects, modules, markers, zone reference ranges, and report metadata. Raw measurement data lives as JSON files on the filesystem rather than in the database, keeping the database lightweight.</p>

            <h5>Redis</h5>
            <p>Redis serves two roles: it holds the <strong>job queue</strong> (the list of pending analysis jobs) and acts as a <strong>pub/sub message bus</strong> — the worker publishes progress updates to a channel named after the job ID, and the backend's subscription resolver forwards those updates to the browser over WebSocket in real time.</p>
        </div>

    </div>

</main>

<style>

    div {
        border: 1px solid black;
        margin: 5px;
        padding: 5px;
        font-weight: bold;
    }

    #universe {
        border: 1px solid black;
        display: flex;
        background-color: rgb(194, 246, 255);
    }

    #main_app {
        background-color: rgb(223, 188, 255);
        display: flex;
    }

    #frontend {
        background-color: rgb(196, 255, 188);
    }

    #backend {
        background-color: rgb(196, 255, 188);
    }

    .functional_file {
        background-color: aquamarine;
    }

    #database {
        background-color: rgb(196, 255, 188);
    }

    #redis {
        background-color: rgb(255, 220, 180);
    }

    #arch_guide {
        background-color: rgb(255, 253, 230);
        max-width: 380px;
        align-self: flex-start;
        font-weight: normal;
        line-height: 1.6;
        font-size: 0.92em;
    }

    #arch_guide h4 {
        border: none;
        font-size: 1.1em;
        margin-bottom: 8px;
    }

    #arch_guide h5 {
        border: none;
        margin-top: 12px;
        margin-bottom: 2px;
        font-size: 0.95em;
    }

    #arch_guide p {
        border: none;
        margin: 0;
        padding: 0;
    }

    #arch_guide code {
        background-color: #e8e8e8;
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 0.9em;
        border: none;
    }

</style>

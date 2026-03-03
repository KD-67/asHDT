<script></script>

<main>
    <h3>HOMEPAGE: App architecture</h3>

    <div id="universe"> universe
        <div id="main_app">
            <span>main app</span>
            <div id="frontend">
                <span>frontend</span>
                    <div class="functional_file">home_div.svelte</div>
                    <div class="functional_file">request_report_form.svelte</div>
                    <div class="functional_file">new_user_form.svelte</div>
                    <div class="functional_file">add_module_page.svelte</div>
                    <div class="functional_file">help.svelte</div>
                    <div>timegraph_report_page.svelte
                        <div class="functional_file">timegraph_chart.svelte</div>
                        <div class="functional_file">timegraph_table.svelte</div>
                    </div>               
                    
            </div>
            <div id="backend">
                <span>backend</span>
                <div class="functional_file">main.py</div>
                <div class="functional_file">routes.py</div>
                <div>
                    <span>startup</span>
                    <div class="functional_file">module_loader.py</div>
                    <div class="functional_file">database_logistics.py</div>
                    <div class="functional_file">module_list.json</div>
                </div>
                <div id="core">
                    <span>core</span>
                    <div class="backend_core" id="ingestion">
                        <span>ingestion</span>
                    </div>
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
            </div>
            <div id="database">
                <span>database</span>
                <div class="functional_file">table: subjects</div>
                <div class="functional_file">table: timegraph_reports</div>
            </div>
        </div>

        <div id="modules">
            <span>modules</span>
            <div>
                <span>fitness</span>
                <div class="functional_file">VO2max</div>
                <div class="functional_file">100m Sprint</div>
            </div>
            <div>vtf_stresstest</div>
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

    #modules {
        background-color: rgb(254, 255, 206);
        display: flex;
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

    .functional_file{
        background-color: aquamarine;
    }

    #database {
        background-color: rgb(196, 255, 188);
    }

</style>
<script>
    let loading = false;

    let new_last_name = $state("");
    let new_first_name = $state("");
    let new_sex = $state("");
    let new_dob = $state([]);
    let new_email = $state("");
    let new_phone = $state("");
    let new_notes = $state("");
</script>

<main>
    <div id="main_container">

    <form id="generate_new_subject_form">
            <h2>Create new user:</h2>

            <label for="last_name">Last name</label>
            <input type="text" id="last_name" bind:value={new_last_name}>
            
            <label for="first_name">First name</label>
            <input type="text" id="first_name" bind:value={new_first_name}>
        
            <fieldset name="sex_declarer">
                <legend>Sex</legend>

                <input type="radio" name="sex" id="sex_f" value="F" bind:group={new_sex}>
                <label for="sex_f">Female</label>
                    <br>
                <input type="radio" name="sex" id="sex_m" value="M" bind:group={new_sex}>
                <label for="sex_m">Male</label>
                    <br>
                <input type="radio" name="sex" id="sex_u" value="Undeclared" bind:group={new_sex}>
                <label for="sex_u">Undeclared</label>
            </fieldset>

            <label for="dob">Date of birth</label>
            <input type="date" id="dob" bind:value={new_dob}>

            <label for="email">Email address</label>
            <input type="text" id="email" bind:value={new_email}>
            
            <label for="phone">Phone number</label>
            <input type="number" id="phone" bind:value={new_phone}>

            <label for="notes">Notes</label>
            <input type="textarea" id="notes" bind:value={new_notes}>
                        
    </form>

    <div id="preview_container">
        <h4>Preview:</h4>

    <p> Name: {new_last_name} {new_first_name}</p>
    <p>Sex: {new_sex}</p>
    <p>DOB: {new_dob}</p>
    <p>Email: {new_email}</p>
    <p>Phone: {new_phone}</p>
    <p>Notes: {new_notes}</p>
    <button type="button">Create new user</button>
    </div>

    </div>
</main>

<style>
    #main_container {
        border: 1px solid black;
        display: flex;
    }

    form {
        background-color: lightblue;
        padding: 15px 10px;
        border: 1px solid black;
    }

    fieldset {
        border: 1px solid black;
    }

    #preview_container {
        border: 1px solid black;
        margin: 5px;
        padding: 3px;
    }
</style>
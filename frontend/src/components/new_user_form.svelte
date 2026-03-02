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
    <form id="generate_new_subject_form">

        <fieldset style='background:lightblue'>
            <legend style="font-size: large;">New user</legend>
            
            <label for="last_name">Last name</label>
            <input type="text" id="last_name" bind:value={new_last_name}>
            
            <label for="first_name">First name</label>
            <input type="text" id="first_name" bind:value={new_first_name}>
        
            <fieldset name="sex_declarer">
                <legend>Sex</legend>

                <label for="sex_f">Female</label>
                <input type="radio" name="sex" id="sex_f" value="F" bind:group={new_sex}>
                    <br>
                <label for="sex_m">Male</label>
                <input type="radio" name="sex" id="sex_m" value="M" bind:group={new_sex}>
                    <br>
                <label for="sex_u">Undeclared</label>
                <input type="radio" name="sex" id="sex_u" value="Undeclared" bind:group={new_sex}>
            </fieldset>

            <label for="dob">Date of birth</label>
            <input type="date" id="dob" bind:value={new_dob}>

            <label for="email">Email address</label>
            <input type="text" id="email" bind:value={new_email}>
            
            <label for="phone">Phone number</label>
            <input type="number" id="phone" bind:value={new_phone}>

            <label for="notes">Notes</label>
            <input type="textarea" id="notes" bind:value={new_notes}>
            
            <button type="button">Create new user</button>
        </fieldset>
    </form>
</main>

<style></style>
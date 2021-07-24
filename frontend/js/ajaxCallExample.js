function ajaxCall(triggered){

    var url = "<api end point>"

    $.get(url, function(data, status) {

        console.log(`Status: ${status}`)

        var tableContent = ''
        var count = 1

        $.each(data, function(idx, obj) {
            var firstname = obj.firstname;
            var lastname = obj.lastname;
            var email = obj.email;
            var updated = obj.updated.substring(0, 19);

            tableContent += `<tr>
            <th scope="row">${count}</th>
            <td>${firstname}</td>
            <td>${lastname}</td>
            <td>${email}</td>
            <td>${updated}</td>
            </tr>`
            count += 1
        })

        // console.log(tableContent)
        console.log("Updated User list")

        $("#tableContent").html(tableContent)
        if(triggered == true) {
            alert("User list has been updated successfully!")
        }
    })
    
}


var todoApiEndpoint = 'https://j3cv37qhud.execute-api.us-east-1.amazonaws.com/dev/';
var cognitoUserPoolId = 'us-east-1_fM3BzKm1u';
var cognitoUserPoolClientId = '4ajb6clml9vft00cof689o6c0p';
var awsRegion = 'us-east-1';

var gridScope;
var descriptionScope;

function loggedInDisplay() {
    $("#signInButton").addClass("d-none");
    $("#signOutButton").removeClass("d-none");
}

function loggedOutDisplay() {
    $("#signInButton").removeClass("d-none");
    $("#signOutButton").addClass("d-none");
}

function initializeStorage() {
  var identityPoolId = cognitoUserPoolId;//
  var userPoolId = cognitoUserPoolId; //
  var clientId = cognitoUserPoolClientId;//
  var loginPrefix = 'cognito-idp.' + awsRegion + '.amazonaws.com/' + identityPoolId;

  localStorage.setItem('identityPoolId', identityPoolId);
  localStorage.setItem('userPoolId', userPoolId);
  localStorage.setItem('clientId', clientId);
  localStorage.setItem('loginPrefix', loginPrefix);
}

function updateModalText(descriptionTodo) {
    applyDescriptionScope(descriptionTodo);
    if (descriptionTodo.completed == true) {
        markCompleted();
    } else {
        markNotCompleted();
    }
}

function markCompleted() {
    $("#completedButton").addClass("d-none");
    $("#alreadyCompletedButton").removeClass("d-none");
}

function markNotCompleted() {
    $("#completedButton").removeClass("d-none");
    $("#alreadyCompletedButton").addClass("d-none");
}

function applyGridScope(todosList) {
    gridScope.todos = todosList;
    gridScope.$apply();
}

function applyDescriptionScope(todo) {
    descriptionScope.descriptionTodo = todo;
    descriptionScope.$apply();
}

function login(){
    var userPoolId = localStorage.getItem('userPoolId');
    var clientId = localStorage.getItem('clientId');
    var identityPoolId = localStorage.getItem('identityPoolId');
    var loginPrefix = localStorage.getItem('loginPrefix');

    var poolData = {
        UserPoolId : userPoolId, // Your user pool id here
        ClientId : clientId // Your client id here
    };
    var userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);

    var username = $('#username').val();
    var authenticationData = {
        Username: username,
        Password: $('#password').val()
    };

    var authenticationDetails = new AmazonCognitoIdentity.AuthenticationDetails(authenticationData);

    var userData = {
        Username : username,
        Pool : userPool
    };
    var cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);

    console.log(cognitoUser);
    cognitoUser.authenticateUser(authenticationDetails, {
        onSuccess: function (result) {
        var accessToken = result.getAccessToken().getJwtToken();
        console.log('Authentication successful', accessToken);
        var sessionTokens =
        {
            IdToken: result.getIdToken(),
            AccessToken: result.getAccessToken(),
            RefreshToken: result.getRefreshToken()
        };
        localStorage.setItem('sessionTokens', JSON.stringify(sessionTokens))
        localStorage.setItem('userID', username);
        window.location = './home.html';
        },

        onFailure: function(err) {
        console.log('failed to authenticate');
        console.log(JSON.stringify(err));
        alert('Failed to Log in.\nPlease check your credentials.');
        },
    });
}

function checkLogin(redirectOnRec, redirectOnUnrec){
    var userPoolId = localStorage.getItem('userPoolId');
    var clientId = localStorage.getItem('clientId');
    var identityPoolId = localStorage.getItem('identityPoolId');
    var loginPrefix = localStorage.getItem('loginPrefix');

    var poolData = {
    UserPoolId : userPoolId, // Your user pool id here
    ClientId : clientId // Your client id here
    };
    var userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);
    var cognitoUser = userPool.getCurrentUser();

    if (cognitoUser != null) {
        console.log("user exists")
        if (redirectOnRec) {
            window.location = './home.html';
            loggedInDisplay();
        } else {
            $("#body").css({'visibility':'visible'});           
        }
    } else {
        if (redirectOnUnrec) {
            window.location = './index.html'
        } 
    }
}

function refreshAWSCredentials() {
    var userPoolId = localStorage.getItem('userPoolId');
    var clientId = localStorage.getItem('clientId');
    var identityPoolId = localStorage.getItem('identityPoolId');
    var loginPrefix = localStorage.getItem('loginPrefix');

    var poolData = {
    UserPoolId : userPoolId, // Your user pool id here
    ClientId : clientId // Your client id here
    };
    var userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);
    var cognitoUser = userPool.getCurrentUser();

    if (cognitoUser != null) {
        cognitoUser.getSession(function(err, result) {
            if (result) {
                console.log('You are now logged in.');
                cognitoUser.refreshSession(result.getRefreshToken(), function(err, result) {

                    if (err) {//throw err;
                        console.log('In the err: '+err);
                    }
                    else{
                        localStorage.setItem('awsConfig', JSON.stringify(AWS.config));
                        var sessionTokens =
                        {
                            IdToken: result.getIdToken(),
                            AccessToken: result.getAccessToken(),
                            RefreshToken: result.getRefreshToken()
                        };
                        localStorage.setItem("sessionTokens", JSON.stringify(sessionTokens));

                    }
                });

            }
        });
    }
}

function logOut() {
    localStorage.clear();
    document.location.reload();
    window.location = './index.html';
}

function getTodos(callback) {
    try{
        var userID = localStorage.getItem('userID');
        var todoApi = todoApiEndpoint + userID +'/todos';

        var sessionTokensString = localStorage.getItem('sessionTokens');
        var sessionTokens = JSON.parse(sessionTokensString);
        var IdToken = sessionTokens.IdToken;
        var idJwt = IdToken.jwtToken;

        $.ajax({
        url : todoApi,
        type : 'GET',
        headers : {'Authorization' : idJwt },
        success : function(response) {
            console.log("successfully loaded todos for " + userID);
            callback(response.todos);
        },
        error : function(response) {
            console.log("could not retrieve todos list.");
            if (response.status == "401") {
            refreshAWSCredentials();
            }
        }
        });
    }catch(err) {
        alert("Please log back in to retrieve your todo list");
        loggedOutDisplay()
        console.log(err.message);
    }
}

function getTodo(todoID, callback) {
    var userID = localStorage.getItem('userID');
    var todoApi = todoApiEndpoint + userID +'/todos/' + todoID;

    var sessionTokensString = localStorage.getItem('sessionTokens');
    var sessionTokens = JSON.parse(sessionTokensString);
    var IdToken = sessionTokens.IdToken;
    var idJwt = IdToken.jwtToken;

    $.ajax({
    url : todoApi,
    type : 'GET',
    headers : {'Authorization' : idJwt },
    success : function(response) {
        console.log('todoID: ' + todoID)
        callback(response);
    },
    error : function(response) {
        console.log("could not retrieve todo.");
        if (response.status == "401") {
        refreshAWSCredentials();
        }
    }
    });
}

function addTodo(dateDue, title, description){
    var userID = localStorage.getItem('userID');
    var todoApi = todoApiEndpoint + userID + "/todos/add";

    var sessionTokensString = localStorage.getItem('sessionTokens');
    var sessionTokens = JSON.parse(sessionTokensString);
    var IdToken = sessionTokens.IdToken;
    var idJwt = IdToken.jwtToken;

    todo = {
        title: title,
        description: description,
        dateDue: dateDue,
    }

    $.ajax({
    url : todoApi,
    type : 'POST',
    headers : {'Content-Type': 'application/json', 'Authorization' : idJwt},
    dataType: 'json',
    data : JSON.stringify(todo),
    success : function(response) {
        console.log("todo added!")
        window.location.reload();
        $("#success-addTodo").show();
        $("#success-addTodo").html("Todo successfully added (^_^)");
    },
    error : function(response) {
        console.log("could not add todo");
        $("#error-addTodo").show();
        $("#error-addTodo").html("Could not add todo (x_x) ");
        console.log(response);

    }
    });
}

function completeTodo(todoID, callback) {
    try {
        var userID = localStorage.getItem('userID');
        var todoApi = todoApiEndpoint + userID + "/todos/" + todoID + "/complete";

        var sessionTokensString = localStorage.getItem('sessionTokens');
        var sessionTokens = JSON.parse(sessionTokensString);
        var IdToken = sessionTokens.IdToken;
        var idJwt = IdToken.jwtToken;

        $.ajax({
            url : todoApi,
            async : false,
            type : 'POST',
            headers : {'Authorization' : idJwt },
            success : function(response) {
                console.log("marked as completed: " + todoID)
                callback();
            },
            error : function(response) {
            console.log("could not completed todo");
            if (response.status == "401") {
                refreshAWSCredentials();
            }
            }
        });
        } catch(err) {
        alert("You must be logged in");
        console.log(err.message);
        }
}

function addTodoNotes(todoID, notes) {
    try {
        var userID = localStorage.getItem('userID');
        var todoApi = todoApiEndpoint + userID + "/todos/" + todoID + "/addnotes";

        var sessionTokensString = localStorage.getItem('sessionTokens');
        var sessionTokens = JSON.parse(sessionTokensString);
        var IdToken = sessionTokens.IdToken;
        var idJwt = IdToken.jwtToken;

        inputNotes = {
            notes: notes,
        }
        $.ajax({
            url : todoApi,
            type : 'POST',
            headers : {'Content-Type': 'application/json','Authorization' : idJwt },
            dataType: 'json',
            data: JSON.stringify(inputNotes),
            success : function(response) {
                console.log("added notes for: " + todoID)
            },
            error : function(response) {
            console.log("could not add notes");
            if (response.status == "401") {
                refreshAWSCredentials();
            }
            }
        });
        } catch(err) {
        alert("You must be logged in to save notes");
        console.log(err.message);
        }
}

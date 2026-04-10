import { config } from './config';
import {
    CognitoUserPool,
    CognitoUser,
    CognitoUserAttribute,
    AuthenticationDetails,
    CognitoUserSession
} from 'amazon-cognito-identity-js';

const userPool = new CognitoUserPool ({
    UserPoolId: config.cognitoUserPoolId,
    ClientId: config.cognitoClientId
});

export function login(username: string, password: string): void {
    const authenticationDetails = new AuthenticationDetails({                                                                                                                                       
        Username: username,                                                                                                                                                                         
        Password: password                                                                                                                                                                          
    });

    const cognitoUser = new CognitoUser({                                                                                                                                                         
        Username: username,
        Pool: userPool
    });

    cognitoUser.authenticateUser(authenticationDetails, {
        onSuccess: ( result: CognitoUserSession ) => {
            console.log('Authentication successful');

            const sessionTokens = {
                IdToken: result.getIdToken(),
                AccessToken: result.getAccessToken(),
                RefreshToken: result.getRefreshToken()
            };
            localStorage.setItem('sessionTokens', JSON.stringify(sessionTokens));                                                                                                                   
            localStorage.setItem('userID', username);                                                                                                                                             
            window.location.href = './home.html'; 
        },
        onFailure: (err: Error) => {
            console.log('Failed to authenticate', err);
            alert('Failed to log in.\nPlease check your credentials.')
        }
    });
}

export function register(email: string, password: string, confirmPassword: string): void {                                                                                                        
    if (password !== confirmPassword) {                                                                                                                                                             
        alert('Passwords do not match.');                                                                                                                                                           
        return;                                                                                                                                                                                     
    }                                                                                                                                                                                               
                                                                                                                                                                                                
    const attributeList = [
        new CognitoUserAttribute({ Name: 'email', Value: email })
    ];                                                                                                                                                                                              

    userPool.signUp(email, password, attributeList, [], (err, result) => {                                                                                                                          
        if (err) {                                                                                                                                                                                
            alert(err.message);
            return;                                                                                                                                                                                 
        }
        console.log('registered user:', result?.user);                                                                                                                                              
        localStorage.setItem('email', email);                                                                                                                                                       
        window.location.href = './confirm.html';
    });                                                                                                                                                                                             
} 

export function confirmRegister(code: string): void {                                                                                                                                             
    const email = localStorage.getItem('email')!;                                                                                                                                                   
                                                                                                                                                                                                    
    const cognitoUser = new CognitoUser({                                                                                                                                                           
        Username: email,                                                                                                                                                                            
        Pool: userPool                                                                                                                                                                            
    });

    cognitoUser.confirmRegistration(code, true, (err, result) => {                                                                                                                                  
        if (err) {
            alert(err.message);                                                                                                                                                                     
            return;                                                                                                                                                                               
        }
        console.log('confirmed registration:', result);
        window.location.href = './index.html';                                                                                                                                                      
    });
}

export function logOut(): void {                                                                                                                                                                  
    const cognitoUser = userPool.getCurrentUser();                                                                                                                                                  
    if (cognitoUser) {                                                                                                                                                                              
        cognitoUser.signOut();                                                                                                                                                                      
    }                                                                                                                                                                                               
    localStorage.clear();                                                                                                                                                                           
    window.location.href = './index.html';                                                                                                                                                          
}                                                                                                                                                                                                   
                                                                                                                                                                                                
export function checkLogin(redirectOnRec: boolean, redirectOnUnrec: boolean): void {                                                                                                                
    const cognitoUser = userPool.getCurrentUser();
                                                                                                                                                                                                    
    if (cognitoUser) {                                                                                                                                                                              
        console.log('user exists');
        if (redirectOnRec) {                                                                                                                                                                        
            window.location.href = './home.html';                                                                                                                                                 
        } else {
            const body = document.getElementById('body');                                                                                                                                           
            if (body) body.style.visibility = 'visible';
        }                                                                                                                                                                                           
    } else {                                                                                                                                                                                      
        if (redirectOnUnrec) {
            window.location.href = './index.html';                                                                                                                                                  
        }                               
    }                                                                                                                                                                                               
} 
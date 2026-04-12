export const config = {
    todoApiEndpoint: (import.meta.env.VITE_TODO_API_ENDPOINT ?? '/api/').replace(/\/?$/, '/'),
    filesApiEndpoint: (import.meta.env.VITE_FILES_API_ENDPOINT ?? '/files-api/').replace(/\/?$/, '/'),
    cognitoUserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID as string,
    cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID as string,
    cognitoIdentityPoolId: import.meta.env.VITE_COGNITO_IDENTITY_POOL_ID as string,
    s3Bucket: import.meta.env.VITE_S3_BUCKET as string,
    awsRegion: import.meta.env.VITE_AWS_REGION as string,
    chatbotWsEndpoint: import.meta.env.VITE_CHATBOT_WS_ENDPOINT as string,
    cdnDomain: import.meta.env.VITE_CDN_DOMAIN as string,
};

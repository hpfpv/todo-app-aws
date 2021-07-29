# Sample todo app on AWS

Hi guys! In this blog, we'll be building a sample todo app on AWS with Python. We will build a website called  [todo.houessou.com](https://todo.houessou.com) that enables logged in visitors to create their todo list. We will use the AWS Serverless Application Model SAM Framework to deploy the backend services - API, Lambda, DynamoDB and Cognito) and will host the frontend on S3 behind a CloudFront distribution.
The frontend is basic with no fancy visuals (I am no frontend dev :p). Here we will focus on how the resources are created and deployed on AWS.

**Application Architecture**

The steps to build this application are:
- Build and deploy backend main resources - **DynamoDB, Lambda and API Gateway**
- Enable users authentication - **Cognito**
- Build a frontend website to serve the app - **S3, CloudFront**

**[Link to web app](https://todo.houessou.com)**

Alright, let's break this down.

### Build and deploy backend
Our backend is based on the Serverless Application Module. We will need a DynamoDb table to store users todo-list, lambda functions to query and write to the table and REST APIs to serve the lambda functions.

1- To keep things simple, each document in DynamoDb will represent one todo with attributes as follow:

- *todoID* : unique number identifying todo, will serve as primary key
- *userID* : ID of the user who created the todo, will serve as sort key
- *dateCreated* : date todo has been created, today's date
- *dateDue* : date the todo is due, user provided
- *title* : todo title, user provided
- *description* : todo description, user provided
- *notes* : additional notes for todo, can be added anytime after todo is created, black by default
- *completed* : TRUE or FALSE if todo is marked as completed

2- Our [lambda functions](https://github.com/hpfpv/todo-app-aws/tree/main/backend/functions) will perform CRUD operations on the DynamoDB Table as follow:

- *getTodos* : retrieve all todos for a userID
- *getTodo* : return detailed information about one todo based on the todoID attribute 
- *addTodo* : create a todo for a specific user based on the userID
- *completeTodo* : update todo record and set completed attribute to TRUE based on todoID 
- *addTodoNotes* : update todo record and set the notes attribute to the specified value based on todoID

3- Our REST API will have 5 routes to trigger the lambda functions based on the path and parameters provided:

- *getTodos* : /{**userID**}/todos
- *getTodo* : /{**userID**}/todos/{**todoID**}
- *addTodo* : /{**userID**}/todos/add
- *completeTodo* : /{**userID**}/todos/{**todoID**}/complete
- *addTodoNotes* : /{**userID**}/todos/{**todoID**}/addnotes

Since the retrieval of todos is per user based, we need to add the authentication layer using Cognito.
For that, we have to create a Cognito user pool, user pool client and domain. We also need to set the Auth property on the API by adding cognito as authorizers backed by *jwt*.

With all the information above, we can write the [SAM template](https://github.com/hpfpv/todo-app-aws/blob/main/backend/template.yaml) as follow:

**API**

```
MainHttpApi:
    Type: AWS::Serverless::HttpApi
    DependsOn: TodoUserPool
    Properties:
      StageName: dev
      Auth:
        Authorizers:
          TodoAuthorizer:
            IdentitySource: "$request.header.Authorization"
            JwtConfiguration:
              issuer: !Join [ '', [ 'https://cognito-idp.', '${AWS::Region}', '.amazonaws.com/', !Ref TodoUserPool ] ] 
              audience: 
                - !Ref TodoUserPoolClient 
        DefaultAuthorizer: TodoAuthorizer
      CorsConfiguration:
        AllowMethods:
          - GET
          - POST
        AllowOrigins:
          - https://todo.houessou.com
        AllowHeaders:
          - '*'
``` 

**Functions**

```
  getTodos:
    Type: AWS::Serverless::Function
    Properties:
      Environment: 
        Variables:
          TODO_TABLE: !Ref TodoTable 
      CodeUri: ./functions
      Handler: getTodos.lambda_handler
      Events:
        getTodosApi:
          Type: HttpApi
          Properties:
            ApiId: !Ref MainHttpApi
            Path: /{userID}/todos
            Method: GET
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: 'dynamodb:*'
              Resource:
                - !GetAtt 'TodoTable.Arn'
                - !Join [ '', [ !GetAtt 'TodoTable.Arn', '/index/*' ] ]  
                   
  getTodo:
    Type: AWS::Serverless::Function
    Properties:
      Environment: 
        Variables:
          TODO_TABLE: !Ref TodoTable 
      CodeUri: ./functions
      Handler: getTodo.lambda_handler
      Events:
        getTodoApi:
          Type: HttpApi
          Properties:
            ApiId: !Ref MainHttpApi
            Path: /{userID}/todos/{todoID}
            Method: GET
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: 'dynamodb:*'
              Resource:
                - !GetAtt 'TodoTable.Arn'
            
  addTodo:
    Type: AWS::Serverless::Function
    Properties:
      Environment: 
        Variables:
          TODO_TABLE: !Ref TodoTable 
      CodeUri: ./functions
      Handler: addTodo.lambda_handler
      Events:
        addTodoApi:
          Type: HttpApi
          Properties:
            ApiId: !Ref MainHttpApi
            Path: /{userID}/todos/add
            Method: POST
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: 'dynamodb:*'
              Resource:
                - !GetAtt 'TodoTable.Arn'
  
  completeTodo:
    Type: AWS::Serverless::Function
    Properties:
      Environment: 
        Variables:
          TODO_TABLE: !Ref TodoTable 
      CodeUri: ./functions
      Handler: completeTodo.lambda_handler
      Events:
        completeTodoApi:
          Type: HttpApi
          Properties:
            ApiId: !Ref MainHttpApi
            Path: /{userID}/todos/{todoID}/complete
            Method: POST
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: 'dynamodb:*'
              Resource:
                - !GetAtt 'TodoTable.Arn'

  addTodoNotes:
    Type: AWS::Serverless::Function
    Properties:
      Environment: 
        Variables:
          TODO_TABLE: !Ref TodoTable 
      CodeUri: ./functions
      Handler: addTodoNotes.lambda_handler
      Events:
        addTodoNotesApi:
          Type: HttpApi
          Properties:
            ApiId: !Ref MainHttpApi
            Path: /{userID}/todos/{todoID}/addnotes
            Method: POST
      Policies:
        - Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: 'dynamodb:*'
              Resource:
                - !GetAtt 'TodoTable.Arn'
``` 

**DynamoDb Table**

```
TodoTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub 'TodoTable-${AWS::StackName}'
      BillingMode: PROVISIONED
      ProvisionedThroughput:
        ReadCapacityUnits: 1
        WriteCapacityUnits: 1
      AttributeDefinitions: 
        - AttributeName: "todoID"
          AttributeType: "S"
        - AttributeName: "userID"
          AttributeType: "S"
      KeySchema: 
        - AttributeName: "todoID"
          KeyType: "HASH"
      GlobalSecondaryIndexes:
        - IndexName: "userIDIndex"
          KeySchema:
            - AttributeName: "userID"
              KeyType: "HASH"
            - AttributeName: "todoID"
              KeyType: "RANGE"
          Projection: 
            ProjectionType: "ALL"
          ProvisionedThroughput:
            ReadCapacityUnits: 1
            WriteCapacityUnits: 1
```

**Cognito**

```
TodoUserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub 'UserPool-${AWS::StackName}'
      UsernameAttributes:
        - email
      AutoVerifiedAttributes:
        - email
  
  TodoUserPoolClient:
      Type: AWS::Cognito::UserPoolClient
      Properties:
        ClientName: !Sub 'UserPoolClient-${AWS::StackName}'
        AllowedOAuthFlows:
          - implicit
        AllowedOAuthFlowsUserPoolClient: true
        AllowedOAuthScopes:
          - phone
          - email
          - openid
          - profile
          - aws.cognito.signin.user.admin
        UserPoolId:
          Ref: TodoUserPool
        CallbackURLs: 
          - https://todo.houessou.com
        ExplicitAuthFlows:
          - ALLOW_USER_SRP_AUTH
          - ALLOW_REFRESH_TOKEN_AUTH
        GenerateSecret: false
        SupportedIdentityProviders: 
          - COGNITO
  # Cognito user pool domain
  TodoUserPoolDomain:
    Type: AWS::Cognito::UserPoolDomain 
    Properties:
      UserPoolId: !Ref TodoUserPool
      Domain: auth-todo-houessou-com
```

# todo-app-aws
Sample Serverless Todo app on AWS - API, Lambda, DynamoDB
Hi guys! In this blog, we'll be building a sample todo app on AWS with Python. We will build a website called  [todo.houessou.com](https://todo.houessou.com) that enables logged in visitors to create their todo list. We will use the AWS Serverless Application Model SAM Framework to deploy the backend services - API, Lambda, DynamoDB and Cognito) and will host the frontend on S3 behind a CloudFront distribution.
The frontend is basic with no fancy visuals (I am no frontend dev :p). Here we will focus on how the resources are created and deployed on AWS.

**Application Architecture**

The steps to build this app are:
- Build and deploy backend main resources - **DynamoDB, Lambda and API Gateway**
- Enable users authentication - **Cognito**
- Build a static website to serve static content - **S3, CloudFront**

**GitHub repository: https://github.com/hpfpv/todo-app-aws**

**Created web app: https://todo.houessou.com**

Alright, let's break this down.

### Build and deploy backend
Our backend is based on the Serverless Application Module. We will need a DynamoDb table to store users todo-list, lambda functions to query and write to the table and REST APIs to serve the lambda functions.
To keep things simple, each document in DynamoDb will represent one todo with attributes as follow:
- *todoID* : unique number identifying todo, will serve as primary key
- *userID* : ID of the user who created the todo, will serve as sort key
- *dateCreated* : date todo has been created, today's date
- *dateDue* : date the todo is due, user provided
- *title* : todo title, user provided
- *description* : todo description, user provided
- *notes* : additional notes for todo, can be added anytime, user provided
- *completed* : true or false if todo is marked as completed

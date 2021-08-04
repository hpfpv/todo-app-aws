![cover.png](https://github.com/hpfpv/todo-app-aws/blob/main/blog-post/cover.png)

# Deploying a sample serverless to-do app on AWS

Hi guys! In this post, we'll be building a sample todo app on AWS with Python. We will build a web application which enables logged in visitors to manage their todo list. We will use the AWS Serverless Application Model SAM Framework to deploy the backend services - API, Lambda, DynamoDB and Cognito) and will host the frontend on S3 behind a CloudFront distribution.
The frontend is pretty basic with no fancy visuals (I am no frontend dev :p). We will try to focus on how the resources are created and deployed on AWS.

## Overview

In this post I will be going through the overall setup of the app and how I deployed it. Mostly this will be a theoretical post but I will be posting needed scripts wherever appropriate. All the code can be found in the **[GitHub repo](https://github.com/hpfpv/todo-app-aws)**.

**[Application web UI](https://todo.houessou.com)**

### About the App

Before I go into the architecture, let me describe what the app is about and what it does. The app is a todo list manager which helps a user manage and track his/her todo list along with their files or attachments. The user can also find specific todos through the search. 

### Basic Functionality

![appflow.png](https://cdn.hashnode.com/res/hashnode/image/upload/v1627647453541/A17idrTi1.png)
The image above should describe the app basic functionalities.

**User/Login Management**

*Users are able to login to the app using provided credentials. There is a self register functionality and once a user is registered, the app provides a capability to the user to login using those credentials. It also provides a logout option for the user.*

**Search Todo**
 
*Users are able to perform a keyword search and the app shows a list of todos which contain that keyword in the name. The search only searches on todos which the logged in user has created. So it has the access boundary and doesn’t show Recipes across users.*

**Add New Todo**

*Users can add new Todos to be stored in the app. There are various details which can be provided for each Todo. Users can also add notes for each Todo.*

**Support for files**

*Users can upload a todo files for each Todo. The app provides a capability where user can select and upload a local file or download existing files while adding notes to a Todo. The file can be anything, from a text file to an image file. The app stores it in a S3 bucket and serves it back to the user via CloudFront.*

### Application Components
Now that we have a basic functional understanding of the app, let's see how all of these functionalities translate to different technical components. Below image should provide a good overview of each layer of the app and the technical components involved in each layer.

![app-components.png](https://cdn.hashnode.com/res/hashnode/image/upload/v1628077958693/0vhPB3Gjx.png)

Let's go through each component:

**Frontend**

*The Front end for the app is built of simple HTML and Javascript. All operations and communications with backend are performed via various REST API endpoints.*

**Backend**

*Backend for the app is built Lambda Functions triggered by REST APIs. It provides various API endpoints to perform application functionalities such as adding or deleting todos, adding or deleting todo files etc. The REST APIs are built using API Gateway. The API endpoints perform all operations of connecting with the functions, authenticating, etc. CORS is enabled for the API so it only accepts requests from the frontend.*

**Data Layer**

*DynamoDB Table is used to store all todos and related data. The lambda functions will be performing all Database operations connecting to the Table and getting requests from the frontend. DynamoDB is a serverless service and it provides auto scaling along with high availability.* 

**Authentication**

*The authentication is handled by AWS Cognito. We use a Cognito user pool to store users data. When a user logs in and a session is established with the app, the session token and related data is stored at the FrontEnd and sent over the API endpoints. API Gateway then validate the session token against Cognito and allow users to perform application operations.*

**File Service**

*There is a separate service to handle files management for the application. The File service is composed of Javascript function using AWS SDK (for upload files operations), Lambda functions + API Gateway for API calls for various file operations like retrieve file info, delete file etc, S3 and DynamoDB to store files and files information. The files are served back to the user through the app using a CDN (Content Delivery Network). The CDN makes serving the static files faster and users can access/download them faster and easier.*


## Application Architecture

Now that we have some information about the various components and services involved in the app, let's move on to how to place and connect these various components to get the final working application. 

![architecture.png](https://cdn.hashnode.com/res/hashnode/image/upload/v1628029946699/pOk-oRHg4.png)

### Frontend

The static *html*, *javascript* and *css* files generated for the website will be stored in an S3 bucket. The S3 bucket is configured to host a website and will provide an endpoint through which the app can be accessed. To have a better performance on the frontend, the S3 bucket is selected as an Origin to a CloudFront distribution. The CloudFront will act as a CDN for the app frontend and provide faster access through the app pages.

### Lambda Functions for backend services logic

All the backend logic is deployed as AWS Lambda functions. Lambda functions are totally serverless and our task is to upload our code files to create the Lambda functions along with setting other parameters. . Below are the functions which are deployed as part of the backend service:

**Todos Service**

- getTodos : *retrieve all todos for a userID*
- getTodo : *return detailed information about one todo based on the todoID attribute* 
- addTodo : *create a todo for a specific user based on the userID*
- completeTodo : *update todo record and set completed attribute to TRUE based on todoID *
- addTodoNotes : *update todo record and set the notes attribute to the specified value based on todoID*
- deleteTodo : *delete a todo for a specific user based on the userID and todoID
*

**Files Service**
- getTodoFiles : *retrieve all files which belong to a specified todo*
- addTodoFiles : *add files to as attachment to a specified todo*
- deleteTodoFiles: *delete selected file for specified todo*

### API Gateway to expose Lambda Functions

To expose the Lambda functions and make them accessible by the Frontend, AWS API Gateway is deployed. API Gateway defines all the endpoints for the APIs and route the requests to proper Lambda function in the backend. These API gateway endpoints are called by the frontend. Each application service has its own API (keeping services as separate as possible for decoupling purpose) with deployed routes as follow:

**Todos Service**
- getTodos : /{**userID**}/todos
- getTodo : /{**userID**}/todos/{**todoID**}
- deleteTodo : /{**userID**}/todos/{**todoID**}/delete
- addTodo : /{**userID**}/todos/add
- completeTodo : /{**userID**}/todos/{**todoID**}/complete
- addTodoNotes : /{**userID**}/todos/{**todoID**}/addnotes

**Files Service**
- getTodoFiles : /{**todoID**}/files
- addTodoFiles : /{**todoID**}/files/upload
- deleteTodoFiles : /{**todoID**}/files/{**fileID**}/delete

The addTodoFiles API route triggers the addTodoFiles function which only record the file information like fine name and file path/key to a DynamoDB table. The same table is queried by the getTodoFiles function to display returned files information.
The actual operation to upload the files to S3 is perform by a Javascript function in the Frontend code. I found it better to do it that way to prevent large amount of data going through the lambda functions and thus increasing response time and cost.

### Database

DynamoDB tables are used to serve as database. We have two tables for respectively the Todos Service and the Files Service.
The search functionality of the app is handled by simple DynamoDB query requests. We can deployed a DynamoDB Accelerator in front of the tables to increase performance if needed. Below is the tables configuration:

**Todos Service**
To keep things simple, each document in DynamoDB will represent one todo with attributes as follow:

- todoID : *unique number identifying todo, will serve as primary key*
- userID : *ID of the user who created the todo, will serve as sort key*
- dateCreated : *date todo has been created, today's date*
- dateDue : *date the todo is due, user provided*
- title : *todo title, user provided*
- description : *todo description, user provided*
- notes : *additional notes for todo, can be added anytime after todo is created, blank by default*
- *completed* : *true or false if todo is marked as completed*

**Files Service**
- fileID : *unique number identifying file, will serve as primary key*
- todoID : *ID of belonging todo item, will serve as sort key*
- fileName : *name of the uploaded file*
- filePath : *URL of the uploaded file for downloads*

### File Storage

To support the file management capability of the application, a file storage need to be deployed. I am using an S3 bucket as the storage for the files which are uploaded from the app. The file service API calls the AWS S3 API to store the files in the bucket. To serve the files back to the user, a CloudFront distribution is created with the S3 bucket as the origin. This will serve as the CDN to distribute the static files faster to the end users.


## IaC and Deployment Method

The application backend services are defined as SAM templates. Each service has his own template and resources are configured to be as independent as possible.
I am using automated deployments for the whole application environment - frontend and 2 backend services. Each service is deployed using a separate deployment pipeline to maintain optimal decoupling. 
The components below are used as part of the deployment pipeline:

- One GitHub Repository for code commits
- A separate branch for Prod changes (master branch as Dev)
- Various paths, one per service - Frontend, Backend Todos Service and Backend Files Service
- Any commit to a service path in a specified branch (Prod or Dev) automatically tests deploys changes to the service in the appropriate environment.
- GitHub Actions backed by docker containers to build and deploy services

**FrontEnd**

![frontend-pipeline.png](https://cdn.hashnode.com/res/hashnode/image/upload/v1628077668965/DMv5htTiG.png)

**Backend**

![backend-pipeline.png](https://cdn.hashnode.com/res/hashnode/image/upload/v1628077651575/cMRfCM8MB.png)


## Takeaways

Hopefully, I was able to describe in detail about the system architecture which I would use for a basic todo-list management app. This application is designed solely for training purposes and there is a lot of room for improvement. I will continue working on making the deployment more secure, HA and fault tolerant. 
This post should give you a good idea about how to design a basic full stack and fully serverless architecture for an app using the microservices patter. 

from collections import defaultdict
from datetime import datetime
import json
import re



items = {
   "todos":[
      {
         "todoID":"879300c0-73e0-45a5-994f-9f712b08a97f",
         "userID":"hpf@houessou.com",
         "dateCreated":"2021-07-25 18:35:14.040809",
         "title":"Learn Ansible",
         "description":"For cloud computing",
         "notes":"- another another note\n- second note\n- third note\n- another note\n- note again\n\n\n\n\n",
         "dateDue":"2021-12-31",
         "completed":"false"
      },
      {
         "todoID":"396f518b-02da-4db9-a0a1-f1423fb2d60b",
         "userID":"hpf@houessou.com",
         "dateCreated":"2021-07-25 17:36:28.756252",
         "title":"Learn Python",
         "description":"Learn Python for coding and cloud administrative tasks",
         "notes":"- chapter dictionaries completed\n- chapter objects completed\n- project todo list completed\n- added notes on phone\n- another note\n- note on phone again\n- another one\n\n\n\n\n",
         "dateDue":"2021-12-31",
         "completed":"false"
      },
      {
         "todoID":"08e14ca1-91a8-49a3-9407-f0d17780de60",
         "userID":"hpf@houessou.com",
         "dateCreated":"2021-07-28 11:50:25.309564",
         "title":"New todo on phone",
         "description":"This todo has been added on the phone",
         "notes":"",
         "dateDue":"2022-01-08",
         "completed":"false"
      },
      {
         "todoID":"1b6e0cae-3653-44b2-b8bd-44bf122e8d8e",
         "userID":"hpf@houessou.com",
         "dateCreated":"2021-07-28 17:28:40.827547",
         "title":"Another todo",
         "description":"New todo with date",
         "notes":"- new note\n",
         "dateDue":"2021-08-06",
         "completed":"true"
      },
      {
         "todoID":"34fa3856-6811-4fca-bb2f-d372a21bf04e",
         "userID":"hpf@houessou.com",
         "dateCreated":"2021-07-24 15:59:40.156578",
         "title":"Todo title6",
         "description":"okokok",
         "notes":"- note for completed todo\n- another note\n",
         "dateDue":"2021-10-08",
         "completed":"true"
      }
   ]
}

def getSearchedTodos(filter):
    data = items
    response = defaultdict(list)
    
    for item in data["todos"]:
        todo = {}
        if re.search(filter, item["title"], re.IGNORECASE): 
            todo["todoID"] = item["todoID"]
            todo["userID"] = item["userID"]
            todo["dateCreated"] = item["dateCreated"]
            todo["title"] = item ["title"]
            todo["description"] = item["description"]
            todo["notes"] = item["notes"]
            todo["dateDue"] = item["dateDue"]
            todo["completed"] = item["completed"]
            response["todos"].append(todo)
    
    print(response)

getSearchedTodos("learn python")
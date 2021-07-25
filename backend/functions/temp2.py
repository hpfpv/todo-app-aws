from collections import defaultdict
from datetime import datetime
import json


dict = {
    "todos": [
        {
            "todoID": "0feeaed0-5718-4235-a849-fdc69f6d95ba",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-20 23:12:42.704467",
            "title": "Test Todo 222",
            "description": "Test Todo 222 for hpf",
            "dateDue": "2021-08-20",
            "completed": "false"
        },
        {
            "todoID": "0feeaed0-5718-4265-a889-fdb69f6d58dc",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-20 23:12:42.704467",
            "title": "Learn Python",
            "description": "Test Todo for hpf",
            "dateDue": "2021-08-20",
            "completed": "false"
        },
        {
            "todoID": "0feeaed0-5718-4265-a889-fdb69f6d95ba",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-20 23:12:42.704467",
            "title": "Test TODO 222",
            "description": "Test Todo 222 for hpf",
            "dateDue": "2021-08-20",
            "completed": "true"
        },
        {
            "todoID": "1c50a22f-e619-4400-b134-3bb3b19e0fa8",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-24 02:05:32.931922",
            "title": "Learn Digital Marketing",
            "description": "Learn Ansible fast fast",
            "dateDue": "2021-09-21",
            "completed": "false"
        },
        {
            "todoID": "78d5264e-02dd-4c99-8a74-00f5e6e4e383",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-24 14:53:30.958509",
            "title": "Test todo title4",
            "description": "You rock on AWS!",
            "dateDue": "2021-09-21",
            "completed": "false"
        },
        {
            "todoID": "a0f4f5b2-f222-4340-bc7a-c7dc912fab08",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-24 14:45:02.605238",
            "title": "Test todo title3",
            "description": "another test",
            "dateDue": "2021-09-21",
            "completed": "false"
        },
        {
            "todoID": "b44ddb19-5805-4fe2-9b06-0f5b0a6e5957",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-24 14:22:56.258710",
            "title": "Test todo title",
            "description": "Horray!",
            "dateDue": "2021-09-21",
            "completed": "false"
        }
    ]
}



#data = json.dumps(dict)
dict2 = sorted(dict["todos"], key = lambda i: i["dateCreated"], reverse=True)
dict3 = sorted(dict2, key = lambda i: i["dateDue"])
response = defaultdict(list)
for item in dict3:
    todo = {}

    todo["todoID"] = item["todoID"]
    todo["userID"] = item["userID"]
    todo["dateCreated"] = item["dateCreated"]
    todo["title"] = item ["title"]
    todo["description"] = item["description"]
    todo["dateDue"] = item["dateDue"]
    todo["completed"] = item["completed"]

    response["todos"].append(todo)

input = json.loads("{\"notes\":\"-new chapter: dictionaries | done\"}")
notes = input["notes"]
print (notes)


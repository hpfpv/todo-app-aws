from collections import defaultdict
import json


dict = {
    "todos": [
        {
            "todoID": "0feeaed0-5718-4265-a889-fdb69f6d58dc",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-20 23:12:42.704467",
            "description": "Test Todo for hpf",
            "dateDue": "2021-08-20",
            "completed": "true"
        },
        {
            "todoID": "0feeaed0-5718-4265-a889-fdb69f6d95ba",
            "userID": "hpf@houessou.com",
            "dateCreated": "2021-07-20 23:12:42.704467",
            "description": "Test Todo 222 for hpf",
            "dateDue": "2021-08-20",
            "completed": "false"
        }
    ]
}
response = defaultdict(list)
for item in dict["todos"]:
    todo = {}
    if str(item["completed"]) == "false":
        todo["todoID"] = item["todoID"]
        todo["userID"] = item["userID"]
        todo["dateCreated"] = item["dateCreated"]
        todo["description"] = item["description"]
        todo["dateDue"] = item["dateDue"]
        todo["completed"] = item["completed"]
        response["todos"].append(todo)

print (json.dumps(response))
data = dict["todos"].items()
print (data)
#print (dict["todos"])
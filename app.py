from fastapi import FastAPI
from pydantic import BaseModel
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from azure.messaging.webpubsubclient import WebPubSubClient
from fastapi.responses import StreamingResponse
import os,json
import base64
import websockets
import cv2
import numpy as np
import asyncio
import threading
import time
import imutils
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

origins = ["*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_connection_string():
    # connection_string=os.popen('az webpubsub key show --resource-group owlcontrol --name Orangewood --query primaryConnectionString --output json').read().splitlines()[0].strip('"')
    connection_string = 'Endpoint=https://orangewood.webpubsub.azure.com;AccessKey=hBt+5wyqVyCS6zAXwfz0FN7BDHnZX+ChpDW+iur2aeg=;Version=1.0;'
    return connection_string
# connection_string=os.popen('az webpubsub key show --resource-group owlcontrol --name Orangewood --query primaryConnectionString --output json').read().splitlines()[0].strip('"')

def get_client(hub_name):
    client=WebPubSubServiceClient.from_connection_string(get_connection_string(), hub=hub_name)
    token = client.get_client_access_token()["url"]
    return token
data = {
    "base": 0,
    "shoulder": 0,
    "elbow": 0,
    "wrist": 0,
    "wrist2": 0,
    "wrist3": 0,
}
class Pose(BaseModel):
    pose: dict
class Control(BaseModel):
    name: str
    value: int
class key(BaseModel):
    password:str

# Initialize the Web PubSub service clie

## MILESTONE ONE START ####################################

notif=""
@app.get("/")
async def root():
    """
    Return a welcome message.
    """
    return {"message": "Welcome to the Fleet Managemet System"}

@app.post("/connectionstring")
async def keys(password: key):
    """
    Return the connection string for the Web PubSub service.
    """
    if password.password == "owl":
        return {"message": get_connection_string()}
    else:
        return {"message": "Invalid Key"}
@app.post("/{robot_id}/client/{hub_name}")
async def client(robot_id: str, hub_name: str,password:key):
    """
    Return the client string for the Web PubSub service.
    """
    if password.password == "owl":
        return {"message": get_client(robot_id+"_"+hub_name)}
    else:
        return {"message": "Invalid Key"}

    
@app.get("/list")
async def pose():
    """
    Return the list of robots.
    """
    with open('list_robot.json') as json_file:
        data = json.load(json_file)

    return data
@app.post("/list/update")
async def update(message: dict):
    """
    Update the list of robots.
    """
    global notif
    # Send the pose data to the specified robot channel
    with open('list_robot.json', 'w') as outfile:
        json.dump(message, outfile)
        #get the robot name
        robot_name=message['robots'][-1]['name'] 
        notif=robot_name
    return {"message": "List updated successfully."}

@app.get("/notification")
async def notification():
    """
    Return the Notification of new robot added.
    """
    global notif
    if notif=="":
        return {"message": ["No new robot added","heofdha","sauidfashd"]}
    return {"message": ["No new robot added","heofdha","sauidfashd"]}


async def gen(video_feed):
    
    async with websockets.connect(video_feed) as ws:
        print(video_feed)
        print('connected')
        while True:
            global fps, st, frames_to_count, cnt
            data =await ws.recv()
            data = base64.b64decode(data, ' /')
            npdata = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
            # frame= imutils.resize(frame, width=640, height=480)
            frame = cv2.imencode('.jpg', frame)[1].tobytes()
            # yield b'--frame\r\nContent-Type: image/jpg\r\n\r\n'+frame+b'\r\n'
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(frame) + b'\r\n')

@app.get("/{robot_id}/video_feed")
async def stream(robot_id: str):
    """
    Stream video from the robot.
    """
    video=WebPubSubServiceClient.from_connection_string(get_connection_string(), hub=robot_id+"_video")
    video_feed=video.get_client_access_token()
    video_feed=video_feed['url']
    return StreamingResponse(gen(video_feed),media_type="multipart/x-mixed-replace;boundary=frame")



def sendButtons(robot_id,disable=False,upgrade=False,video_feed=False):
    """ button name and vaule is being sent"""
    button_json={"disabled":disable,"upgrade":upgrade,"video_feed":video_feed}
    buttons=WebPubSubServiceClient.from_connection_string(get_connection_string(), hub=robot_id+"_buttons")
    buttons.send_to_all(message =button_json,content_type='application/json')
    return {"message": "Buttons enabled"}                       

@app.post("/{robot_id}/upgrade")
async def upgrade(robot_id: str,message:dict):
    # print(message["upgrade"])
    sendButtons(robot_id,upgrade=message["upgrade"])
    """ button name and vaule is being sent"""
    return {"upgrade": True}

@app.post("/{robot_id}/disable")
async def disable(robot_id: str,message:dict):
    sendButtons(robot_id,disable=message["disable"])
    return {"disabled": True}

@app.post("/{robot_id}/enable_video")
async def enable_video(robot_id: str,message:dict):
    print(message["video_feed"])
    sendButtons(robot_id,video_feed=message["video_feed"])
    return {"message": "Video Feed enabled"}



@app.get("/{robot_id}")
async def robot_info(robot_id: str):
    """
    Return the information of the robot.
    """
    with open('list_robot.json') as json_file:
        data = json.load(json_file)
    for robot in data["robots"]:
        if robot["robot_id"] == robot_id:
            return robot
    return {"message": "Robot not found."}
## MILESTONE ONE END ####################################3








@app.get("/{robot_id}/pose")
async def pose(robot_id: str):
    get_pose=WebPubSubServiceClient.from_connection_string(get_connection_string(), hub=robot_id+"_pose")
    get_pose=get_pose.get_client_access_token()["url"]
    
    async with websockets.connect(get_pose) as ws:
        print("connected")
        while True:
            p=await ws.recv()
            print(p)
    # return {"message": p}
@app.post("/{robot_id}/setinitpose")
async def setinitpose(pose: Pose,password:key,robot_id:str):
    """
    Set the initial pose of the robot.
    """
    print(pose.pose)

    # Send the pose data to the specified robot channel
    with open('init_pose.json','w') as json_file:
        json.dump(pose.pose, json_file)
    return {"message": f"Initial pose set successfully for robot {robot_id}."}

def send_control(data,hub_name):
    service=WebPubSubServiceClient.from_connection_string(get_connection_string(), hub=hub_name)
    data= data
    service.send_to_all(message = data)
@app.post("{robot_id}/control")
async def contorl(robot_id: str,control: Control,password:key):
    """
    Send a control command to the robot.

    ### How this works?

    The frontend will send request to the backend with the position of the wrist, elbow, shoulder, etc.
    The backend will send the data to the robot and the robot will move accordingly.
    Please note that this data is not directly send to the robot rather it is send to the Azure Web PubSub service.
    """
    # Send the pose data to the specified robot channel
    if password.password != "owl":
        return {"message": "Invalid Key"}
    else:
        print(control)
        value = control.value
        print(control.name, value-180  )
        hub_name=robot_id+"_control"
        data[control.name] = value
        send_control(data,hub_name)

@app.post("/{robot_id}/speed")
async def speed(robot_id: str):
    """
    Set the speed of the robot.
    """
    # Send the speed data to the specified robot channel
    channel_name = f"robot-{robot_id}"
    return {"message": f"Speed set successfully for robot {robot_id}."}

@app.post("/{robot_id}/stop")
async def stop(robot_id: str):
    """
    Stop the robot.
    """
    # Send the stop command to the specified robot channel
    channel_name = f"robot-{robot_id}"
    await service_client.send_to_group(channel_name, {"command": "stop"})
    return {"message": f"Robot {robot_id} stopped."}

@app.post("/{robot_id}/resume")
async def resume(robot_id: str):
    """
    Resume the robot.
    """
    # Send the resume command to the specified robot channel
    channel_name = f"robot-{robot_id}"
    await service_client.send_to_group(channel_name, {"command": "resume"})
    return {"message": f"Robot {robot_id} resumed."}



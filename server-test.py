import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError
import random
import json

connected_clients = set()
active_sessions = {}


async def broadcast(message):
    if connected_clients:  # Check if there are any clients connected
        await asyncio.gather(*(client.send(message) for client in connected_clients))


async def periodic_processes():
    while True:
        print(active_sessions)
        await asyncio.sleep(10)  # Wait for 10 seconds
        await broadcast("Periodic message from server!")
        await broadcast(f"There are currently {len(connected_clients)} clients connected across {len(active_sessions)} sessions.")
        await broadcast("Active session info:\n"+str(active_sessions))


async def disconnect_client(websocket, sender_id):
    # remove client from connected_clients
    if websocket in connected_clients:
        connected_clients.remove(websocket)

    # List to store session_ids that need to be deleted
    sessions_to_delete = []

    for session_id in active_sessions:
        if sender_id in active_sessions[session_id]["clients"]:
            active_sessions[session_id]["clients"].remove(sender_id)
        if not active_sessions[session_id]["clients"]:
            sessions_to_delete.append(session_id)

    # Delete the sessions outside the loop
    for session_id in sessions_to_delete:
        del active_sessions[session_id]


async def echo(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            try:
                message = json.loads(message)
            except json.decoder.JSONDecodeError:
                await websocket.send("Invalid JSON")
                # disconnect client
                connected_clients.remove(websocket)
                continue

            sender_id = message["player_id"]
            await websocket.send(f"Echo: {message}")
            await broadcast(f"Incoming message: {message} from {sender_id}")

            # create a new session
            if (message["type"] == "request_create_session"):
                random_id = str(random.getrandbits(128))
                sender_id = message["player_id"]
                map_layout = message["map_layout"]
                active_sessions[random_id] = {
                    "clients": [sender_id],
                    "state": "waiting",
                    "action_list": [],
                    "host": sender_id,
                    "map_layout": map_layout
                }
                await websocket.send(f"Session {random_id} created by player {sender_id}")

            # start an existing session
            elif (message["type"] == "request_start_session"):
                session_id = message["session_id"]
                active_sessions[session_id]["state"] = "running"
                await websocket.send(f"Session {session_id} started")

            # join an existing session
            elif (message["type"] == "request_join_session"):
                sender_id = message["player_id"]
                session_id = message["session_id"]
                active_sessions[session_id]["clients"].append(sender_id)
                json_response = json.dumps(active_sessions[session_id])
                await websocket.send(json_response)
                await broadcast(f"Session {session_id} joined by player {sender_id}")

            # send an action to a session
            elif (message["type"] == "player_action"):
                # sender_id = message["player_id"]
                session_id = message["session_id"]
                active_sessions[session_id]["action_list"].append(message)
                for client in active_sessions[session_id]["clients"]:
                    if client != sender_id:
                        await client.send(json.dumps(active_sessions[session_id]["action_list"]))

            # invalid message type handling
            else:
                await websocket.send(f"Unknown message type: {message['type']}")
                await disconnect_client(websocket, sender_id)
    except ConnectionClosedError:
        print("Connection closed unexpectedly")
        await disconnect_client(websocket, sender_id)
    finally:
        await disconnect_client(websocket, sender_id)


start_server = websockets.serve(echo, "0.0.0.0", 5001)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().create_task(periodic_processes())
asyncio.get_event_loop().run_forever()

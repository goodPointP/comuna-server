import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError
import random
import json

connected_clients = set()
active_sessions = {}


async def broadcast(message):
    if connected_clients:  # Check if there are any clients connected
        await asyncio.wait([client.send(message) for client in connected_clients])


async def periodic_broadcast():
    while True:
        print(active_sessions)
        await asyncio.sleep(10)  # Wait for 10 seconds
        await broadcast("Periodic message from server!")
        await broadcast(f"There are currently {len(connected_clients)} clients connected across {len(active_sessions)} sessions.")
        await broadcast("Active session info:\n"+str(active_sessions))


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

            await websocket.send(f"Echo: {message}")
            await broadcast(f"Incoming message: {message} from {websocket}")

            # create a new session
            if (message["type"] == "request_create_session"):
                random_id = str(random.getrandbits(128))
                sender_id = message["player_id"]
                active_sessions[random_id] = {
                    "clients": [websocket], "state": "waiting", "action_list": [], "host": sender_id
                }
                await websocket.send(f"Session {random_id} created by player {sender_id}")

            # start an existing session
            elif (message["type"] == "request_start_session"):
                session_id = message["session_id"]
                active_sessions[session_id]["state"] = "running"
                await websocket.send(f"Session {session_id} started")

            # join an existing session
            elif (message["type"] == "request_join_session"):
                session_id = message["session_id"]
                active_sessions[session_id]["clients"].append(websocket)
                await websocket.send(active_sessions[session_id].to_json())
                await broadcast(f"Session {session_id} joined by player {websocket}")

            # send an action to a session
            elif (message["type"] == "player_action"):
                sender = message["player_id"]
                session_id = message["session_id"]
                active_sessions[session_id]["action_list"].append(message)
                for client in active_sessions[session_id]["clients"]:
                    if client != sender:
                        await client.send(json.dumps(active_sessions[session_id]["action_list"]))

            # invalid message type handling
            else:
                await websocket.send(f"Unknown message type: {message['type']}")
                connected_clients.remove(websocket)
    except ConnectionClosedError:
        print("Connection closed unexpectedly")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


start_server = websockets.serve(echo, "0.0.0.0", 5001)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().create_task(periodic_broadcast())
asyncio.get_event_loop().run_forever()

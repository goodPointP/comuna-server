import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError
import random
import json

connected_clients = set()
active_sessions = {}
client_websocket_pairs = {}


async def broadcast(message):
    if connected_clients:  # Check if there are any clients connected
        await asyncio.gather(*(client.send(message) for client in connected_clients))


async def periodic_broadcast():
    while True:
        print(json.dumps(active_sessions, sort_keys=True, indent=4))
        await asyncio.sleep(10)  # Wait for 10 seconds
        await broadcast("Periodic message from server!")
        await broadcast(f"There are currently {len(connected_clients)} clients connected across {len(active_sessions)} sessions.")
        await broadcast("Active session info:\n"+str(json.dumps(active_sessions, sort_keys=True, indent=4)))


async def disconnect_client(websocket, sender_id):
    # remove client from connected_clients
    if websocket in connected_clients:
        connected_clients.remove(websocket)
        print(f"Client {sender_id} removed from connected_clients")

    # List to store session_ids that need to be deleted
    sessions_to_delete = []

    for session_id in active_sessions:
        for client in active_sessions[session_id]["clients"]:
            if sender_id in active_sessions[session_id]["clients"]["player_id"]:
                active_sessions[session_id]["clients"].remove(client)
                print(f"Client {sender_id} removed from session {session_id}")
        if not active_sessions[session_id]["clients"]:
            sessions_to_delete.append(session_id)

    # Delete the sessions outside the loop
    for session_id in sessions_to_delete:
        del active_sessions[session_id]
        print(f"Session {session_id} deleted")


async def send_current_session_state(websocket, session_id):
    # make packet recognizable by client to be a session state packet
    package = active_sessions[session_id]
    package["message_type"] = "session_state"
    # make a JSON from active_sessions[session_id]
    json_response = json.dumps(active_sessions[session_id])
    await websocket.send(json_response)


async def serve(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            try:
                message = json.loads(message)
            except json.decoder.JSONDecodeError:
                await websocket.send("Invalid JSON")
                disconnect_client(websocket, sender_id)
                continue

            sender_id = message["player_id"]
            # await websocket.send(f"Echo: {message}")
            # await broadcast(f"Incoming message: {message} from {sender_id}")

            # create a new session
            if (message["type"] == "request_create_session"):
                session_id = str(random.getrandbits(128))
                sender_id = message["player_id"]
                map_layout = message["map_layout"]
                active_sessions[session_id] = {
                    "session_id": session_id,
                    "clients": [{"player_id": sender_id,
                                 "ready": True}],
                    "state": "waiting",
                    "action_list": [],
                    "host": sender_id,
                    "map_layout": map_layout
                }
                client_websocket_pairs[sender_id] = websocket
                await send_current_session_state(websocket, session_id)
                await websocket.send(f"Session {session_id} created by player {sender_id}")

            # start an existing session
            elif (message["type"] == "request_start_session"):
                session_id = message["session_id"]
                active_sessions[session_id]["state"] = "running"
                await broadcast(f"Session {session_id} started")

            # join an existing session
            elif (message["type"] == "request_join_session"):
                sender_id = message["player_id"]
                session_id = message["session_id"]
                # check if session exists
                if session_id not in active_sessions:
                    await websocket.send(f"Session {session_id} does not exist")
                    continue
                # check if player is already in session
                if sender_id in active_sessions[session_id]["clients"]:
                    await websocket.send(f"Player {sender_id} is already in session {session_id}")
                    continue
                client_to_add = {"player_id": sender_id,
                                 "ready": True}
                active_sessions[session_id]["clients"].append(client_to_add)
                client_websocket_pairs[sender_id] = websocket
                await send_current_session_state(websocket, session_id)
                await broadcast(f"Session {session_id} joined by player {sender_id}")

            # send an action to a session
            elif (message["type"] == "player_action"):
                # sender_id = message["player_id"]
                session_id = message["session_id"]
                move = message["move_data"]
                move_data = {
                    "player_id": sender_id, "move_data": move}
                active_sessions[session_id]["action_list"].append(move_data)
                for client in active_sessions[session_id]["clients"]:
                    if client["player_id"] != sender_id:
                        receiver_id = client["player_id"]
                        package = active_sessions[session_id]["action_list"][-1]
                        package["message_type"] = "new_player_action"
                        # make a JSON from active_sessions[session_id]
                        json_response = json.dumps(active_sessions[session_id])
                        await client_websocket_pairs[receiver_id].send(json_response)

            # invalid message type handling
            else:
                await websocket.send(f"Unknown message type: {message['type']}")
                await disconnect_client(websocket, sender_id)
    except ConnectionClosedError as e:
        if e.code == 1006:
            print("Connection closed by client")
        else:
            print("Connection closed error occurred:\n", e)
        await disconnect_client(websocket, sender_id)
    finally:
        await disconnect_client(websocket, sender_id)


start_server = websockets.serve(serve, "0.0.0.0", 5001)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().create_task(periodic_broadcast())
asyncio.get_event_loop().run_forever()

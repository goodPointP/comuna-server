# utils.py

import asyncio
from websockets.exceptions import ConnectionClosedError
import random
import json

from data import connected_clients, active_sessions, client_websocket_pairs


async def broadcast(message):
    # sends a message to ALL connected clients, disregarding session
    if connected_clients:  # Check if there are any clients connected
        await asyncio.gather(*(client.send(message) for client in connected_clients))


async def disconnect_client(websocket, sender_id):
    # remove client from connected_clients
    if websocket in connected_clients:
        connected_clients.remove(websocket)
        print(f"Client {sender_id} removed from connected_clients")

    # List to store session_ids that need to be deleted
    sessions_to_delete = []

    for session_id in active_sessions:
        # Use a list comprehension to remove the client with matching sender_id
        active_sessions[session_id]["clients"] = [
            client for client in active_sessions[session_id]["clients"] if client["player_id"] == int(sender_id)]

        if not active_sessions[session_id]["clients"]:
            sessions_to_delete.append(session_id)
            print(f"Session {session_id} marked for deletion")

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


async def get_current_session_state(session_id):
    # make packet recognizable by client to be a session state packet
    package = active_sessions[session_id]
    package["message_type"] = "session_state"
    # make a JSON from active_sessions[session_id]
    json_response = json.dumps(active_sessions[session_id])
    return json_response


async def send_message(websocket, message):
    await websocket.send(message)


async def prepare_message(message):
    # prepare message to be sent to client
    message = json.dumps(message)
    return message


async def handle_send_message_to_player(websocket, message):
    # prepare message to be sent to client
    message = await prepare_message(message)
    # send message to client
    await send_message(websocket, message)


async def handle_send_message_to_session(session_id, message, skip_sender=False, sender_id=None):
    # prepare message to be sent to client
    message = await prepare_message(message)
    # send message to client
    await send_message_to_session(session_id, message, skip_sender, sender_id)


async def send_message_to_session(session_id, message, skip_sender=False, sender_id=None):
    # send message to all clients in session
    for client in active_sessions[session_id]["clients"]:
        if skip_sender and client["player_id"] == sender_id:
            continue
        await send_message(client_websocket_pairs[client["player_id"]], message)


async def handle_event(message, websocket, sender_id):
    match message["type"]:
        # create a new session
        case "request_create_session":
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
        case "request_start_session":
            session_id = message["session_id"]
            active_sessions[session_id]["state"] = "running"
            await broadcast(f"Session {session_id} started")
            for client in active_sessions[session_id]["clients"]:
                # send session_start message to all clients, including the host
                receiver_id = client["player_id"]
                package = active_sessions[session_id]["state"]
                package["message_type"] = "session_start"
                # make a JSON from active_sessions[session_id]
                json_response = json.dumps(active_sessions[session_id])
                await client_websocket_pairs[receiver_id].send(json_response)

        # join an existing session
        case "request_join_session":
            sender_id = message["player_id"]
            session_id = message["session_id"]
            # check if session exists
            if session_id not in active_sessions:
                await websocket.send(f"Session {session_id} does not exist")
                # continue
            # check if player is already in session
            if sender_id in active_sessions[session_id]["clients"]:
                await websocket.send(f"Player {sender_id} is already in session {session_id}")
                # continue
            client_to_add = {"player_id": sender_id,
                             "ready": True}
            active_sessions[session_id]["clients"].append(client_to_add)
            client_websocket_pairs[sender_id] = websocket
            await send_current_session_state(websocket, session_id)
            await broadcast(f"Session {session_id} joined by player {sender_id}")

        # send an action to a session
        case "player_action":
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
        case _:
            await websocket.send(f"Unknown message type: {message['type']}")
            await disconnect_client(websocket, sender_id)

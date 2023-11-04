# module imports
import json
import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError

# local imports
from utility_functions import *

# global variables
connected_clients = set()
active_sessions = {}
client_websocket_pairs = {}

# broadcast sends a message to ALL connected clients (disregarding the session_id)
# send_to_client sends a message to a specific client (identified by the session_id)


async def periodic_broadcast():
    global connected_clients
    global active_sessions
    while True:
        print(json.dumps(active_sessions, sort_keys=True, indent=4))
        await asyncio.sleep(2)  # Wait for 10 seconds
        await broadcast("Periodic message from server!")
        await broadcast(f"There are currently {len(connected_clients)} clients connected across {len(active_sessions)} sessions.")
        await broadcast("Active session info:\n"+str(json.dumps(active_sessions, sort_keys=True, indent=4)))


async def serve(websocket, path):
    global connected_clients
    global active_sessions
    global client_websocket_pairs

    connected_clients.add(websocket)
    try:  # try to receive a message from the client
        async for message in websocket:  # wait for a message from the client
            try:  # try to parse the message as JSON
                message = json.loads(message)
            except json.decoder.JSONDecodeError:
                await websocket.send("Invalid JSON")
                disconnect_client(websocket, sender_id)
                continue

            sender_id = message["player_id"]

            handle_events(message, websocket, sender_id)

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

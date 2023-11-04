import asyncio
import websockets
# local imports
from data import connected_clients, active_sessions, client_websocket_pairs
from utils import *


async def serve(websocket, path):
    connected_clients.add(websocket)
    try:  # try to receive a message from the client
        async for message in websocket:
            try:  # try to parse the message as JSON
                message = json.loads(message)
            except json.decoder.JSONDecodeError:
                await websocket.send("Invalid JSON")
                disconnect_client(websocket, sender_id)
                continue

            sender_id = message["player_id"]
            # await websocket.send(f"Echo: {message}")
            # await broadcast(f"Incoming message: {message} from {sender_id}")
            handle_event(message, websocket, sender_id)

    except ConnectionClosedError as e:
        if e.code == 1006:
            print("Connection closed by client")
        else:
            print("Connection closed error occurred:\n", e)
        await disconnect_client(websocket, sender_id)
    finally:
        await disconnect_client(websocket, sender_id)


async def periodic_broadcast():
    while True:
        print(json.dumps(active_sessions, sort_keys=True, indent=4))
        await asyncio.sleep(2)  # Wait for 10 seconds
        await broadcast("Periodic message from server!")
        await broadcast(f"There are currently {len(connected_clients)} clients connected across {len(active_sessions)} sessions.")
        await broadcast("Active session info:\n"+str(json.dumps(active_sessions, sort_keys=True, indent=4)))

start_server = websockets.serve(serve, "0.0.0.0", 5001)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().create_task(periodic_broadcast())
asyncio.get_event_loop().run_forever()

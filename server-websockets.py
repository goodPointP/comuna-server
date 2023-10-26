import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError

connected_clients = set()

async def broadcast(message):
    if connected_clients:  # Check if there are any clients connected
        await asyncio.wait([client.send(message) for client in connected_clients])

async def periodic_broadcast():
    while True:
        await asyncio.sleep(10)  # Wait for 10 seconds
        await broadcast("Periodic message from server!")

async def echo(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received message: {message}")
            broadcast(message)
            await websocket.send(f"Echo: {message}")
    except ConnectionClosedError:
        print("Connection closed unexpectedly")
    finally:
        connected_clients.remove(websocket)



start_server = websockets.serve(echo, "0.0.0.0", 5000)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().create_task(periodic_broadcast())
asyncio.get_event_loop().run_forever()


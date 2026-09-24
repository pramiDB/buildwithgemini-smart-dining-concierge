import asyncio
import os
import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import AgentCard, Message, Part, Role, TextPart, TransportProtocol

RESOURCE = "projects/478456418698/locations/us-central1/reasoningEngines/692617008952377344"
A2A_BASE = f"https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1/{RESOURCE}/api/a2a/app"
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

async def test():
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(headers=headers, timeout=120) as client:
        resp = await client.get(A2A_CARD_URL)
        print("CARD STATUS:", resp.status_code)
        card = AgentCard(**resp.json())
        card.url = A2A_BASE
        
        factory = ClientFactory(ClientConfig(supported_transports=[TransportProtocol.jsonrpc, TransportProtocol.http_json], httpx_client=client))
        a2a_client = factory.create(card)
        
        msg = Message(
            message_id="test-msg-123",
            role=Role.user,
            parts=[Part(root=TextPart(text="Show me gluten-free options on the menu"))]
        )
        
        print("Sending message...")
        async for event in a2a_client.send_message(msg):
            print("EVENT:", type(event), event)

if __name__ == "__main__":
    asyncio.run(test())

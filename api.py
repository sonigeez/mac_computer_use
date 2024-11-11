import asyncio
import os
import json
from fastapi import FastAPI, HTTPException, Query

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from loop import (
    sampling_loop, 
    PROVIDER_TO_DEFAULT_MODEL_NAME,
    APIProvider
)
from tools import ToolResult
from dotenv import load_dotenv
from anthropic.types.beta import BetaTextBlock, BetaToolUseBlock

# Load environment variables
load_dotenv()

# FastAPI App
app = FastAPI()

# Request Model (simplified)
class ChatRequest(BaseModel):
    message: str
    system_prompt_suffix: Optional[str] = None
    only_n_most_recent_images: Optional[int] = 10

# Custom JSON serializable response model
class APIExchangeResponse(BaseModel):
    request_method: str
    request_url: str
    request_headers: Dict[str, str]
    response_status_code: int
    response_headers: Dict[str, str]
    response_text: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

# Response Model
class ChatResponse(BaseModel):
    full_response: str
    tools_used: List[Dict[str, Any]]
    api_exchanges: List[APIExchangeResponse]

async def process_chat_request(request: ChatRequest):
    # Retrieve configuration from environment variables
    api_key = os.getenv("ANTHROPIC_API_KEY")
    provider = os.getenv("API_PROVIDER", "anthropic")
    model = os.getenv("API_MODEL") or PROVIDER_TO_DEFAULT_MODEL_NAME.get(APIProvider(provider))

    if not api_key:
        raise ValueError("No API key found. Please set ANTHROPIC_API_KEY environment variable.")
    
    if not model:
        raise ValueError("No model specified. Please set API_MODEL environment variable.")

    # Set up initial messages structure
    messages = [
        {
            "role": "user", 
            "content": [{"type": "text", "text": request.message}]
        }
    ]

    # Track tools and responses
    tools_used = []
    api_exchanges = []

    def tool_output_callback(tool_output: ToolResult, tool_id: str):
        tools_used.append({
            "tool_id": tool_id,
            "output": str(tool_output)
        })

    def api_response_callback(response):
        try:
            api_exchanges.append(APIExchangeResponse(
                request_method=str(response.http_request.method),
                request_url=str(response.http_request.url),
                request_headers={str(k): str(v) for k, v in response.http_request.headers.items()},
                response_status_code=response.http_response.status_code,
                response_headers={str(k): str(v) for k, v in response.headers.items()},
                response_text=response.http_response.text
            ))
        except Exception as e:
            print(f"Error processing API response: {e}")

    # Run sampling loop
    processed_messages = await sampling_loop(
        system_prompt_suffix=request.system_prompt_suffix or "",
        model=model,
        provider=APIProvider(provider),
        messages=messages,
        output_callback=lambda msg: None,
        tool_output_callback=tool_output_callback,
        api_response_callback=api_response_callback,
        api_key=api_key,
        only_n_most_recent_images=request.only_n_most_recent_images
    )

    # Extract the final text response
    final_response = ""
    for message in processed_messages:
        if message.get('role') == 'assistant' and isinstance(message.get('content'), list):
            for block in message['content']:
                # Handle different block types
                if isinstance(block, BetaTextBlock):
                    final_response += block.text + "\n"
                elif isinstance(block, BetaToolUseBlock):
                    final_response += f"\nTool Used: {block.name} (ID: {block.id})\n"
                elif isinstance(block, dict):
                    # Handle dict-type blocks if needed
                    if block.get('type') == 'text':
                        final_response += block.get('text', '') + "\n"
                    elif block.get('type') == 'tool_use':
                        final_response += f"\nTool Used: {block.get('name', 'Unknown')}\n"

    return ChatResponse(
        full_response=final_response.strip(),
        tools_used=tools_used,
        api_exchanges=api_exchanges
    )

from fastapi import Query

@app.get("/chat")
async def chat_get_endpoint(
    message: str = Query(..., description="The message to process"),
    system_prompt_suffix: Optional[str] = Query(None, description="Optional system prompt suffix"),
    only_n_most_recent_images: Optional[int] = Query(10, description="Number of most recent images to consider")
):
    try:
        request = ChatRequest(
            message=message,
            system_prompt_suffix=system_prompt_suffix,
            only_n_most_recent_images=only_n_most_recent_images
        )
        response = await process_chat_request(request)
        return "done"
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        await process_chat_request(request)
        return "task done"
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "provider": os.getenv("API_PROVIDER", "Not set"),
        "model": os.getenv("API_MODEL", "Not set")
    }

# For running the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

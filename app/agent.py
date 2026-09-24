# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore, storage

load_dotenv()

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from .a2ui_utils import a2ui_callback

# Hardcoded project ID and GCS bucket name as strings to prevent Agent Platform project number resolution issues
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-e2b12085102f"
FIRESTORE_DATABASE = "smart-dining-db"
GCS_BUCKET_NAME = "smart-dining-assets-qwiklabs-gcp-01-e2b12085102f"

db = firestore.Client(project=FIRESTORE_PROJECT_ID, database=FIRESTORE_DATABASE)


def search_menu_items(cuisine: str = "", max_price: float = 0.0, dietary_tag: str = "") -> str:
    """Search menu items in the Firestore database filtered by cuisine, maximum price, or dietary tag.

    Args:
        cuisine: Optional filter for cuisine type (e.g., 'Italian', 'Thai', 'Seafood').
        max_price: Optional maximum price limit. Set 0.0 for no limit.
        dietary_tag: Optional dietary tag (e.g., 'vegan', 'vegetarian', 'gluten-free').

    Returns:
        A list of matching menu items with details.
    """
    collection_ref = db.collection("menu_items")
    docs = collection_ref.stream()

    matches = []
    for doc in docs:
        data = doc.to_dict()
        if cuisine and cuisine.lower() not in data.get("cuisine", "").lower():
            continue
        if max_price > 0 and data.get("price", 0) > max_price:
            continue
        if dietary_tag:
            dietary_list = [d.lower() for d in data.get("dietary", [])]
            if dietary_tag.lower() not in dietary_list:
                continue
        matches.append(data)

    if not matches:
        return "No menu items found matching your search criteria."

    result_lines = []
    for dish in matches:
        result_lines.append(
            f"- {dish.get('name')} (${dish.get('price'):.2f}): {dish.get('description')} "
            f"[Cuisine: {dish.get('cuisine')}, Dietary: {', '.join(dish.get('dietary', []))}]"
        )
    return "\n".join(result_lines)


def get_dish_details(dish_name: str) -> str:
    """Fetch complete details for a specific dish by its name from Firestore.

    Args:
        dish_name: The name or partial name of the dish to look up.

    Returns:
        Formatted string containing all details of the dish.
    """
    collection_ref = db.collection("menu_items")
    docs = collection_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        if dish_name.lower() in data.get("name", "").lower():
            return (
                f"Dish Details for '{data.get('name')}':\n"
                f"ID: {data.get('id')}\n"
                f"Category: {data.get('category')}\n"
                f"Cuisine: {data.get('cuisine')}\n"
                f"Price: ${data.get('price'):.2f}\n"
                f"Dietary: {', '.join(data.get('dietary', []))}\n"
                f"Description: {data.get('description')}\n"
                f"Calories: {data.get('calories')} kcal\n"
                f"Spice Level: {data.get('spice_level')}/5"
            )

    return f"No dish found matching '{dish_name}'."


def add_menu_item(
    id: str,
    name: str,
    category: str,
    cuisine: str,
    price: float,
    dietary: str,
    description: str,
    calories: int = 0,
    spice_level: int = 0,
) -> str:
    """Add a new dish or update an existing dish in the Firestore database.

    Args:
        id: Unique identifier for the dish (e.g., 'dish_006').
        name: Name of the dish.
        category: Category (e.g., 'Main', 'Appetizer', 'Dessert').
        cuisine: Cuisine type (e.g., 'French', 'Mexican').
        price: Dish price in USD.
        dietary: Comma-separated dietary tags (e.g., 'vegan, gluten-free').
        description: Short description of the dish.
        calories: Calorie count (optional).
        spice_level: Spice level from 0 to 5 (optional).

    Returns:
        Confirmation message.
    """
    dietary_list = [tag.strip() for tag in dietary.split(",") if tag.strip()]
    item_data = {
        "id": id,
        "name": name,
        "category": category,
        "cuisine": cuisine,
        "price": price,
        "dietary": dietary_list,
        "description": description,
        "calories": calories,
        "spice_level": spice_level,
    }
    db.collection("menu_items").document(id).set(item_data)
    return f"Successfully saved dish '{name}' ({id}) to Firestore."


def place_table_order(
    customer_name: str,
    table_number: int,
    dish_names: str,
    special_instructions: str = "",
) -> str:
    """Place a dining order for a table and save it to the Firestore database.

    Args:
        customer_name: Name of the customer placing the order.
        table_number: Table number for delivery (e.g. 5).
        dish_names: Comma-separated list of dish names ordered.
        special_instructions: Optional notes or dietary requests.

    Returns:
        Order confirmation message with Order ID and summary.
    """
    order_id = f"ord_{int(datetime.datetime.now().timestamp())}"
    items = [d.strip() for d in dish_names.split(",") if d.strip()]
    order_data = {
        "order_id": order_id,
        "customer_name": customer_name,
        "table_number": table_number,
        "items": items,
        "special_instructions": special_instructions,
        "status": "Confirmed",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    db.collection("orders").document(order_id).set(order_data)
    return (
        f"Order #{order_id} confirmed for {customer_name} at Table {table_number}!\n"
        f"Items: {', '.join(items)}\n"
        f"Special Notes: {special_instructions if special_instructions else 'None'}"
    )


def search_online_recipes(dish_or_ingredient: str) -> str:
    """Search public online recipe database (TheMealDB) for culinary ideas, ingredients, and preparation steps.

    Args:
        dish_or_ingredient: Dish name or key ingredient to search for (e.g., 'curry', 'pasta', 'salmon').

    Returns:
        Formatted recipe details including cuisine, area, ingredients list, preparation instructions, and image URL.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={urllib.parse.quote(dish_or_ingredient)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartDiningConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            meals = data.get("meals")
            if not meals:
                return f"No online recipes found for '{dish_or_ingredient}'."

            meal = meals[0]
            ingredients = []
            for i in range(1, 11):
                ing = meal.get(f"strIngredient{i}")
                measure = meal.get(f"strMeasure{i}")
                if ing and ing.strip():
                    ingredients.append(f"{measure.strip() if measure else ''} {ing.strip()}".strip())

            instructions = meal.get("strInstructions", "")
            if len(instructions) > 300:
                instructions = instructions[:297] + "..."

            return (
                f"Recipe: {meal.get('strMeal')} ({meal.get('strArea', 'Global')} {meal.get('strCategory', '')})\n"
                f"Image: {meal.get('strMealThumb')}\n"
                f"Key Ingredients: {', '.join(ingredients)}\n"
                f"Instructions: {instructions}"
            )
    except Exception as e:
        return f"Error querying online recipe API: {e}"


def geocode_address(address: str) -> str:
    """Convert a human-readable street address into geographical coordinates (latitude and longitude).

    Args:
        address: The street address or location string to geocode.

    Returns:
        Formatted details including formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data.get("status") != "OK" or not data.get("results"):
                return f"Could not geocode address: {data.get('status')}"

            result = data["results"][0]
            loc = result["geometry"]["location"]
            return (
                f"Address: {result.get('formatted_address')}\n"
                f"Location: latitude={loc.get('lat')}, longitude={loc.get('lng')}"
            )
    except Exception as e:
        return f"Error during geocoding request: {e}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "restaurant", radius_meters: float = 2000.0) -> str:
    """Find nearby places of a given type around a location using Places API (New).

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        place_type: Type of place to search for (e.g., 'restaurant', 'cafe', 'bakery').
        radius_meters: Search radius in meters (default 2000.0).

    Returns:
        List of nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            places = data.get("places", [])
            if not places:
                return f"No nearby '{place_type}' places found within {radius_meters}m."

            result_lines = []
            for p in places:
                display_name = p.get("displayName", {}).get("text", "Unknown")
                addr = p.get("formattedAddress", "N/A")
                loc = p.get("location", {})
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                result_lines.append(f"- Name: {display_name} | Address: {addr} | Location: ({lat}, {lng})")
            return "\n".join(result_lines)
    except Exception as e:
        return f"Error querying Places API (New): {e}"


import inspect

async def generate_dish_image(
    dish_name: str,
    prompt_details: str = "",
    tool_context: ToolContext = None,
) -> str:
    """Generate a visual plating image for a dish item using gemini-3.1-flash-lite-image in the global region, save it as a Playground artifact, and upload to public GCS bucket.

    Args:
        dish_name: Name of the dish or food item to generate an image for (e.g., 'Truffle Mushroom Risotto').
        prompt_details: Optional extra visual plating description details.
        tool_context: ToolContext object supplied by ADK for artifact saving.

    Returns:
        Public HTTPS URL of the uploaded image in Cloud Storage.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    prompt = f"A high quality gourmet restaurant dish plating presentation of {dish_name}. {prompt_details}".strip()

    try:
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )
        if not response.candidates or not response.candidates[0].content.parts:
            return "Error: Image generation model returned no content."

        img_part = response.candidates[0].content.parts[0]
        if not img_part.inline_data:
            return "Error: No inline image bytes returned."

        img_bytes = img_part.inline_data.data
        mime_type = img_part.inline_data.mime_type or "image/jpeg"
        ext = "png" if "png" in mime_type else "jpg"
        clean_name = "".join(c if c.isalnum() else "_" for c in dish_name.lower()).strip("_")
        filename = f"{clean_name}_{int(datetime.datetime.now().timestamp())}.{ext}"

        # 1. Save artifact to Playground Artifacts panel via tool_context
        if tool_context:
            artifact_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
            if inspect.isawaitable(res):
                await res

        # 2. Upload in-memory image bytes directly to public Cloud Storage bucket (no local file writing)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(img_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Successfully generated dish image!\nPublic URL: {public_url}"

    except Exception as e:
        return f"Error generating or uploading dish image: {e}"


async def generate_dish_video(
    dish_name: str,
    prompt_details: str = "",
    tool_context: ToolContext = None,
) -> str:
    """Generate a short video preview for a dish item using gemini-omni-flash-preview in the global region, save it as a Playground artifact, and upload to public GCS bucket.

    Args:
        dish_name: Name of the dish or food item to generate a video preview for (e.g., 'Truffle Mushroom Risotto').
        prompt_details: Optional extra video presentation details.
        tool_context: ToolContext object supplied by ADK for artifact saving.

    Returns:
        Public HTTPS URL of the uploaded video in Cloud Storage.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    prompt = f"A short video preview of gourmet restaurant culinary presentation for {dish_name}. {prompt_details}".strip()

    try:
        response = genai_client.models.generate_content(
            model="gemini-omni-flash-preview",
            contents=prompt,
        )
        if not response.candidates or not response.candidates[0].content.parts:
            return "Error: Video generation model returned no content."

        video_part = None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                video_part = part
                break

        if not video_part or not video_part.inline_data:
            return "Error: No inline video bytes returned."

        video_bytes = video_part.inline_data.data
        mime_type = video_part.inline_data.mime_type or "video/mp4"
        ext = "mp4"
        if "webm" in mime_type:
            ext = "webm"
        clean_name = "".join(c if c.isalnum() else "_" for c in dish_name.lower()).strip("_")
        filename = f"{clean_name}_video_{int(datetime.datetime.now().timestamp())}.{ext}"

        # 1. Save artifact to Playground Artifacts panel via tool_context
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
            if inspect.isawaitable(res):
                await res

        # 2. Upload in-memory video bytes directly to public Cloud Storage bucket (no local file writing)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Successfully generated dish video!\nPublic URL: {public_url}"

    except Exception as e:
        return f"Error generating or uploading dish video: {e}"



def get_weather(query: str) -> str:
    """Simulates a web search for weather.

    Args:
        query: Location query.

    Returns:
        Weather info string.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting current time.

    Args:
        query: City query.

    Returns:
        Time info string.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


# Memory Bank setup (Vertex AI Memory Bank service ID extracted from deployment_metadata.json)
MEMORY_BANK_ID = "4368257992328478720"


async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        logging.warning(f"Skipping memory generation (memory service unavailable): {e}")
    return None


def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-central1",
        agent_engine_id=MEMORY_BANK_ID,
    )


# Read Agent Engine resource name from deployment_metadata.json if present
agent_engine_resource_name = None
deployment_metadata_file = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
if os.path.exists(deployment_metadata_file):
    try:
        with open(deployment_metadata_file, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_system_prompt = schema_manager.generate_system_prompt(
    role_description=(
        "You are the Smart Dining Concierge. You help users explore restaurant menu items, "
        "find dishes matching their dietary preferences, look up detailed nutritional and price information, "
        "place table orders saved directly to Firestore, search online public recipe databases for culinary ideas, "
        "geocode addresses into location coordinates, locate nearby restaurants and cafes using Google Maps Places API, "
        "generate gourmet dish plating images using AI, execute Python code in your sandbox for bill splitting and dining math, "
        "and manage menu items using your tools."
    ),
    workflow_description="Analyze the user request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

allergy_instruction = (
    "\n\nIMPORTANT MEMORY & ALLERGY SAFETY RULES:\n"
    "- Pay critical attention to learning, remembering, and strictly enforcing all user food allergies, "
    "dietary restrictions, and medical/dietary intolerances (e.g., peanut/tree nut allergies, gluten intolerance, "
    "dairy-free, shellfish, vegan, etc.) mentioned in current or past conversations.\n"
    "- Always inspect preloaded memories from your Memory Bank at the start of each conversation.\n"
    "- Never recommend, suggest, or place an order for any dish containing ingredients that conflict with "
    "the user's remembered allergies or dietary restrictions."
)

agent_instruction = a2ui_system_prompt + allergy_instruction


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=agent_instruction,
    code_executor=code_executor,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        PreloadMemoryTool(),
        search_menu_items,
        get_dish_details,
        add_menu_item,
        place_table_order,
        search_online_recipes,
        geocode_address,
        find_nearby_places,
        generate_dish_image,
        generate_dish_video,
        get_weather,
        get_current_time,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

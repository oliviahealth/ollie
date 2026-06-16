import os
import uuid

from flask import Blueprint, render_template, request, Response
import time
import json

from utils.s3 import get_s3

from route_handlers.query_handlers import search_direct_questions, search_location_questions, determine_search_type

# from init_database import message_store, Location, db
from database import db, load_models
s3_bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
default_region = os.getenv("AWS_DEFAULT_REGION")

search_routes_bp = Blueprint('search_routes', __name__)

# Old ichild homepage
@search_routes_bp.route("/", methods=['POST', 'GET'])
def msg():
    return render_template('index.html')


@search_routes_bp.route("/resources", methods=["GET"])
def get_resources():
    models = load_models()
    results = {}

    for model in models:
        table_name = model.__table__.name

        # don't include the 'internal' tables
        if table_name in {"langchain_pg_collection", "langchain_pg_embedding", "message_store", "admin_user"}:
            continue

        resources = db.session.query(model).all()

        results[table_name] = [
            {
                column.name: getattr(resource, column.name)
                for column in model.__table__.columns
                if column.name != "embedding"  # don't include the embedding column if it exists
            }
            for resource in resources
        ]

    try:
        s3 = get_s3()
        professional_items = s3.list_objects_v2(
            Bucket=s3_bucket_name, Prefix="professional_items/", Delimiter="/")
        results["professional_items"] = [{
            "id": str(uuid.uuid4()),
            "title": item["Key"],
            "size": item["Size"],
            "lastModified": item["LastModified"],
            "path": item['Key']
        } for item in professional_items.get("Contents", []) if item["Size"] > 0]
    except Exception as e:
        results["professional_items"] = []  # set as an empty list for now

    return Response(
        json.dumps(results, default=str),
        mimetype="application/json"
    )

# Get all locations given a list of location ids
@search_routes_bp.route("/locations", methods=['POST'])
def get_locations():
    models = load_models()
    ids = request.form.getlist("location_ids")

    locations = []
    for id in ids:
        location = (
            db.session.query(models.Location)
            .filter_by(id=id)
            .first()
        )
        locations.append({
            'id': location.id,
            'address': location.address + ", " + location.city + ", " + location.state + " " + str(int(location.zip_code)),
            'addressLink': location.address_link,
            'description': location.description,
            'latitude': float(location.latitude),
            'longitude': float(location.longitude),
            'website': location.website,
            'name': location.name,
            'phone': location.phone,
            'hoursOfOperation': [{"sunday": location.sunday_hours}, {"monday": location.monday_hours}, {"tuesday": location.tuesday_hours}, {"wednesday": location.wednesday_hours}, {"thursday": location.thursday_hours}, {"friday": location.friday_hours}, {"saturday": location.saturday_hours}],
            'rating': float(location.rating) if (location.rating and location.rating.isalnum()) else None,
            'isSaved': False
        })

    return Response(
        json.dumps(locations),
        mimetype='application/json'
    )

# API route for ICHILD frontend
# Takes in a search_query and conversation_id to generate a response
@search_routes_bp.route("/formattedresults", methods=['POST', 'GET'])
def formatted_db_search():
    models = load_models()

    search_query = request.form.get('data')
    conversation_id = request.form.get('conversationId')
    allow_external = True if request.form.get(
        'allow_external') == "true" else False
    date_created = int(time.time() * 1000)

    # Reconstruct the conversation history given the conversation_id
    conversation_history = (
        db.session.query(models.message_store)
        .filter_by(session_id=conversation_id)
        .all()
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant. First, summarize the conversation history. Then determine if the user's query is location-based, direct-answer, or requires more information. Provide the summary explicitly."},
    ]

    for history in conversation_history:
        history = json.loads(history.message)

        history_type = history["type"]
        content = history["data"]["content"]

        role = None
        if (history_type == "human"):
            role = "user"
        elif (history_type == "ai"):
            role = "assistant"

        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": search_query})

    # Determine weather search_query is a direct question or location based
    # Select which tool to invoke (search_direct_question for direct questions, search_location_question for location based question)
    determine_search_type_response = determine_search_type(messages)
    tool_calls = determine_search_type_response.choices[0].message.tool_calls

    if (tool_calls):
        function_name = tool_calls[0].function.name
    else:
        '''
        Follow up question is needed for more information.
        Need to manually add the user query and ai response to the db
        '''

        response = determine_search_type_response.choices[0].message.content

        new_user_message = models.message_store(
            session_id=conversation_id,
            message=json.dumps({
                "type": "human",
                "data": {
                    "content": search_query
                }
            })
        )

        new_response_message = models.message_store(
            session_id=conversation_id,
            message=json.dumps({
                "type": "ai",
                "data": {
                    "content": response
                }
            })
        )

        db.session.add(new_user_message)
        db.session.add(new_response_message)

        db.session.commit()

        return {
            'userQuery': search_query,
            'response': response,
            'response_type': 'direct',
            'locations': [],
            'documents': [],
            'dateCreated': date_created,
            'conversationId': conversation_id
        }

    # determine_search_type() will also create a summary of the conversation history
    # Extract the summarized query and pass it into the search handler
    arguments = json.loads(tool_calls[0].function.arguments)
    summarized_query = arguments['query']

    if (function_name == 'search_direct_questions'):
        response_type = 'direct'

        response = None

        if (allow_external):
            response = search_direct_questions(
                conversation_id, summarized_query, True)
        else:
            response = search_direct_questions(
                conversation_id, summarized_query, False)

        answer = response.get('answer')
        documents = response.get('documents')

        return {
            'userQuery': search_query,
            'response': answer,
            'response_type': response_type,
            'locations': [],
            'documents': documents,
            'dateCreated': date_created,
            'conversationId': conversation_id
        }

    elif (function_name == 'search_location_questions'):
        response_type = 'location'

        data = search_location_questions(conversation_id, summarized_query)

        response = data.get("response")
        locations = data.get("locations")

        return {
            'userQuery': search_query,
            'response': response,
            'response_type': response_type,
            'locations': locations,
            'documents': [],
            'dateCreated': date_created,
            'conversationId': conversation_id
        }

    else:
        return "error"


@search_routes_bp.route("/conversations", methods=["DELETE"])
def delete_conversation():
    models = load_models()

    conversation_id = request.form.get("conversationId")

    if not conversation_id:
        return {"error": "conversationId is required"}, 400

    try:
        deleted_count = (
            db.session.query(models.message_store)
            .filter(models.message_store.session_id == conversation_id)
            .delete(synchronize_session=False)
        )

        db.session.commit()

        return {
            "status": "success",
            "deleted": deleted_count
        }, 200

    except Exception as e:
        db.session.rollback()
        return {
            "error": "Failed to delete messages",
            "details": str(e)
        }, 500

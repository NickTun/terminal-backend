import os
import time
from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from qdrant_client import AsyncQdrantClient

from db_schema import Users, Locations, Events, Images, Departments, Jobs


# PARAMETERS
SCORE_THR = -0.1


class EmbeddingRequest(BaseModel):
    location_id: int
    timestamp: float
    embedding: List[float]


class DisplayRequest(BaseModel):
    image: str


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

display_websockets: List[WebSocket] = []
admin_websockets: List[WebSocket] = []

engine = create_engine("sqlite:///demo_database.db", echo=True)
session = Session(engine)

vec_db_client = AsyncQdrantClient("http://localhost:6333")


@app.post("/embedding")
async def post_embedding(request: EmbeddingRequest):
    hits = await vec_db_client.search(
        collection_name="faces",
        query_vector=request.embedding,
        limit=1,
    )

    if len(hits) > 0:
        best_hit = hits[0]
        print(f">>> debug: {best_hit}")
        if best_hit.score > SCORE_THR:
            best_uid = best_hit.id

            user = session.get(Users, best_uid)            
            fullname = user.name

            location = session.get(Locations, request.location_id)

            new_event = Events(
                user_id=user.id,
                location_id=location.id,
                timestamp=request.timestamp
            )
            session.add(new_event)
            session.commit()

            for websocket in admin_websockets:
                print(">>> WS send")
                payload = {
                    "fullname": fullname,
                    "location": location.title,
                    "timestamp": request.timestamp
                }
                await websocket.send_json(payload)


@app.post("/display")
async def display_post(request: DisplayRequest):
    if not display_websockets:
        raise HTTPException(status_code=400, detail="No active WebSocket connections")

    for websocket in display_websockets:
        await websocket.send_text(request.image)


@app.websocket("/display/ws")
async def display_websocket(websocket: WebSocket):
    await websocket.accept()
    display_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            await websocket.send_bytes(data)
    except WebSocketDisconnect:
        display_websockets.remove(websocket)


@app.websocket("/admin/ws")
async def admin_websocket(websocket: WebSocket):
    await websocket.accept()
    admin_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            await websocket.send_bytes(data)
    except WebSocketDisconnect:
        admin_websockets.remove(websocket)



# -------------------------------------------------------------------------------------------------------------

class UserParams(BaseModel):
    name: str
    surname: str
    lastname: str
    age: int
    department_id: int
    job_id: int


class CreateParams(BaseModel):
    new_title: str


class DeleteParams(BaseModel):
    id: int


class UpdateParams(BaseModel):
    id: int
    new_title: str 


class AddEvent(BaseModel):
    user_id: int
    location_id: int
    timestamp: str

class UpdateUser(BaseModel):
    name: str
    surname: str
    lastname: str
    age: int
    department_id: int
    job_id: int


@app.get("/users/{id}")
async def get_user_data(id: int):
    stmt = select(Users).where(Users.id == id) # Запрос в БД
    user_data = session.scalars(stmt).fetchall()[0]
    # print(user_data)

    stmt = select(Images).where(Images.user_id == id)
    images = []

    for image in session.scalars(stmt):
        images.append({
            "id": image.id, 
            "user_id": image.user_id,
            "path": image.path,
        })  
    # paths = session.scalar(stmt1).path

    # stmt = select(Images)
    # paths = [image.path for image in session.scalars(stmt)]

    return JSONResponse({
        "id": user_data.id, 
        "name": user_data.name,
        "surname": user_data.surname,
        "lastname": user_data.lastname,
        "age": user_data.age,
        "department_id": user_data.department_id,
        "job_id": user_data.job_id,
        "last_seen": user_data.last_seen,
        "images": images
    })


@app.get("/users/")
async def get_all_users():
    stmt = select(Users) 

    user_list = []

    for user in session.scalars(stmt):
        job = session.get(Jobs, user.job_id).title   
        user_list.append({
            "id": user.id, 
            "name": user.name, 
            "surname": user.surname, 
            "lastname": user.lastname, 
            "job": job, 
            "last_seen": user.last_seen
        })  

    return JSONResponse(user_list)

@app.get("/locations")
async def get_locations():
    stmt = select(Locations) # Запрос в БД

    locations_list = JSONResponse([{"id": location.id,
                        "title": location.title}
                   for location in session.scalars(stmt)])

    return locations_list


@app.get("/departments") #
async def get_departments():
    stmt = select(Departments) # Запрос в БД

    departamenst_list = JSONResponse([{"id": department.id, 
                          "title": department.title}
                   for department in session.scalars(stmt)])

    return departamenst_list


@app.get("/jobs")
async def get_jobs(): 
    stmt = select(Jobs) # Запрос в БД

    jobs_list = JSONResponse([{"id": job.id, 
                  "title": job.title}
                   for job in session.scalars(stmt)])

    return jobs_list


@app.get("/events")
async def get_events():
    stmt = select(Events)
    events_list = []

    for event in session.scalars(stmt):
        location = session.get(Locations, event.location_id)
        user = session.get(Users, event.user_id)
        events_list.append({
            "id": event.id,
            "location": location.title,
            "timestamp": event.timestamp,
            "user": {
                "name": user.name,
                "surname": user.surname,
                "lastname": user.lastname
            }
        })


    return JSONResponse(events_list)


@app.get("/images/{id}/{src}")
async def get_image(id: int, src: str):
    return FileResponse(path=f"images/{id}/{src}")

@app.put("/images/put") 
async def upload_image(file: UploadFile, user_id: int):
    if not os.path.isdir('images'):
        os.mkdir(f'images')
    if str(user_id) not in os.listdir('images'):
        os.mkdir(f'images/{user_id}')

    filepath = f"images/{user_id}/{file.filename}"
    async with aiofiles.open(filepath, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    new_image_path = Images(
        user_id=user_id,
        path=filepath
    )

    session.add(new_image_path)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.delete("/images/{id}/delete")
async def image_delete(id: int):
    record_for_delete = session.get(Images, id)

    image_path = record_for_delete.path

    session.delete(record_for_delete)
    session.commit()

    os.remove(image_path)
    
    return JSONResponse({"message": "Successful"})


@app.post("/users/create")
async def add_user(params: UserParams):
    new_user = Users(
        name=params.name,
        surname=params.surname,
        lastname=params.lastname,
        department_id=params.department_id,
        age=params.age,
        job_id=params.job_id,
        last_seen=time.time()
    )

    session.add(new_user)
    session.commit()

    stmt = select(Users)
    new_user_id = session.scalars(stmt).fetchall()[-1].id

    return JSONResponse({"message": "Successful", "data": { 'id': new_user_id }})


@app.post("/users/{id}/update")
async def update_user(params: UpdateUser, id: int):
    stmt = select(Users).where(Users.id == id) 
    updated_record = session.scalar(stmt)

    print(updated_record)
    print(params)

    updated_record.name = params.name 
    updated_record.surname = params.surname
    updated_record.lastname = params.lastname
    updated_record.age = params.age
    updated_record.department_id = params.department_id
    updated_record.job_id = params.job_id

    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/users/{id}/delete")
async def delete_user(id: int):
    record_for_delete = session.get(Users, id)

    session.delete(record_for_delete)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/locations/create")
async def create_location(params: CreateParams):
    new_location = Locations(
        title=params.new_title
    )

    session.add(new_location)
    session.commit()


@app.post("/locations/{id}/update")
async def update_location(params: UpdateParams, id: int):
    stmt = select(Locations).where(Locations.id == id)
    updated_record = session.scalars(stmt).one()

    updated_record.title = params.new_title
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/locations/{id}/delete")
async def delete_location(params: DeleteParams, id: int):
    record_for_delete = session.get(Locations, id)
    session.delete(record_for_delete)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/departments/create")
async def create_department(params: CreateParams):
    new_department = Departments(
        title=params.new_title
    )

    session.add(new_department)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/departments/{id}/update")
async def update_departments(params: UpdateParams, id: int):
    stmt = select(Departments).where(Departments.id == id)
    updated_record = session.scalars(stmt).one()

    updated_record.title = params.new_title
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/departments/{id}/delete")
async def delete_departments(params: DeleteParams, id: int):
    record_for_delete = session.get(Departments, id)
    session.delete(record_for_delete)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/jobs/create")
async def create_job(params: CreateParams):
    new_job = Jobs(
        title=params.new_title
    )

    session.add(new_job)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/jobs/{id}/update")
async def update_jobs(params: UpdateParams, id: int):
    stmt = select(Jobs).where(Jobs.id == id)
    updated_record = session.scalars(stmt).one()

    updated_record.title = params.new_title
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/jobs/{id}/delete")
async def delete_jobs(params: DeleteParams, id: int):
    record_for_delete = session.get(Jobs, id)
    session.delete(record_for_delete)
    session.commit()

    return JSONResponse({"message": "Successful"})


@app.post("/events/add")
async def add_event(params: AddEvent):
    new_event = Events(
        user_id=params.user_id,
        location_id=params.location_id,
        timestamp=params.timestamp
    )

    session.add(new_event)
    session.commit()
    
    return JSONResponse({"message": "Successful"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

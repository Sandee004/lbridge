# Contains the route for uploading from the frontend before the parser is then used/called

from fastapi import APIRouter
router = APIRouter()

@router.post("/upload")
def upload_file():
    pass
from fastapi import APIRouter

from app.api.routes import assets, business_terms, chat, documentation, lineage, search

api_router = APIRouter()
api_router.include_router(assets.router)
api_router.include_router(business_terms.router)
api_router.include_router(chat.router)
api_router.include_router(documentation.router)
api_router.include_router(lineage.router)
api_router.include_router(search.router)

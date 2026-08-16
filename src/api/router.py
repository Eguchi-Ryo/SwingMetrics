from fastapi import APIRouter, Depends
import src.api.user_endpoints as user_endpoints
import src.api.swing_endpoints as swing_endpoints
import src.api.benchmark_model_endpoints as benchmark_model_endpoints

router = APIRouter()

# User endpoints
router.include_router(user_endpoints.router, prefix="/users", tags=["Users"])

# Swing endpoints
router.include_router(swing_endpoints.router, prefix="/swings", tags=["Swings"])

# Benchmark Model endpoints
router.include_router(benchmark_model_endpoints.router, prefix="/models", tags=["Benchmark Models"])

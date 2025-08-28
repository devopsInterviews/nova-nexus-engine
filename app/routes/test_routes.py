import logging
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db_session
from app.models import TestConfiguration as Test, User
from app.routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Tests"])

class TestParameter(BaseModel):
    name: str
    value: str

class TestData(BaseModel):
    endpoint_path: str
    method: str
    parameters: List[TestParameter]
    request_type: str

class CreateTestRequest(BaseModel):
    name: str
    endpoint_path: str
    method: str
    parameters: List[TestParameter]
    request_type: str
    test_category: str = "client"  # "client" or "server"
    server_id: Optional[str] = None  # For MCP server tests
    tool_name: Optional[str] = None  # For MCP server tests

class TestResponse(BaseModel):
    id: int
    name: str
    endpoint_path: str
    method: str
    parameters: List[TestParameter]
    request_type: str
    test_category: str = "client"
    server_id: Optional[str] = None
    tool_name: Optional[str] = None
    created_at: str

    class Config:
        orm_mode = True

@router.post("/tests", response_model=TestResponse)
async def save_test(
    test_in: CreateTestRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Saves a new test configuration for the authenticated user.
    Supports both MCP client and server tests.
    """
    logger.info(f"User {current_user.username} is saving a new test: {test_in.name} (category: {test_in.test_category})")
    try:
        # Build the test data based on test category
        test_data_json = json.dumps({
            "endpoint_path": test_in.endpoint_path,
            "method": test_in.method,
            "parameters": [p.dict() for p in test_in.parameters],
            "request_type": test_in.request_type,
            "test_category": test_in.test_category,
            "server_id": test_in.server_id,
            "tool_name": test_in.tool_name,
        })

        new_test = Test(
            user_id=current_user.id,
            name=test_in.name,
            test_type=test_in.test_category,  # Use test_category as test_type
            configuration=test_data_json
        )
        db.add(new_test)
        db.commit()
        db.refresh(new_test)
        
        test_data = json.loads(new_test.configuration)
        response = TestResponse(
            id=new_test.id,
            name=new_test.name,
            created_at=new_test.created_at.isoformat(),
            **test_data
        )
        logger.info(f"Test '{new_test.name}' saved successfully with ID {new_test.id}")
        return response
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving test for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while saving the test.")

@router.get("/tests", response_model=List[TestResponse])
async def get_saved_tests(
    test_category: str = None,  # Optional filter for "client" or "server"
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all saved tests for the authenticated user.
    Can optionally filter by test category (client/server).
    """
    logger.info(f"Fetching saved tests for user {current_user.username} (category: {test_category or 'all'})")
    try:
        tests = db.query(Test).filter(Test.user_id == current_user.id).order_by(Test.created_at.desc()).all()
        response = []
        for test in tests:
            test_data = json.loads(test.configuration)
            
            # Filter by category if specified
            if test_category and test_data.get("test_category", "client") != test_category:
                continue
                
            # Ensure backward compatibility for old tests without category
            test_data.setdefault("test_category", "client")
            test_data.setdefault("server_id", None)
            test_data.setdefault("tool_name", None)
            
            response.append(TestResponse(
                id=test.id,
                name=test.name,
                created_at=test.created_at.isoformat(),
                **test_data
            ))
        logger.info(f"Found {len(response)} tests for user {current_user.username}")
        return response
    except Exception as e:
        logger.error(f"Error fetching tests for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while fetching tests.")

@router.delete("/tests/{test_id}", status_code=204)
async def delete_saved_test(
    test_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a specific test for the authenticated user.
    """
    logger.info(f"User {current_user.username} attempting to delete test with ID {test_id}")
    try:
        test = db.query(Test).filter(Test.id == test_id, Test.user_id == current_user.id).first()
        if not test:
            logger.warning(f"Test with ID {test_id} not found for user {current_user.username}")
            raise HTTPException(status_code=404, detail="Test not found or you do not have permission to delete it.")
        
        db.delete(test)
        db.commit()
        logger.info(f"Test with ID {test_id} deleted successfully for user {current_user.username}")
        return
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting test {test_id} for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while deleting the test.")

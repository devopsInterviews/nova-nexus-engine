"""
Test configuration management API routes for MCP Client.

This module provides REST API endpoints for managing user test configurations,
allowing users to save, load, and manage their MCP server and client test setups.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.database import get_db
from app.models import User, TestConfiguration
from app.auth import get_current_user, log_user_activity

logger = logging.getLogger("uvicorn.error")

# Create router for test configuration endpoints
router = APIRouter(prefix="/tests", tags=["test-configurations"])

# Pydantic models for request/response validation

class TestConfigurationCreate(BaseModel):
    """Schema for creating a test configuration."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the test configuration")
    test_type: str = Field(..., description="Type of test (mcp-server, mcp-client)")
    configuration: Dict[str, Any] = Field(..., description="Test configuration data")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")

class TestConfigurationUpdate(BaseModel):
    """Schema for updating a test configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    configuration: Optional[Dict[str, Any]] = None
    description: Optional[str] = Field(None, max_length=1000)

class TestConfigurationResponse(BaseModel):
    """Schema for test configuration response."""
    id: int
    name: str
    test_type: str
    configuration: Dict[str, Any]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class TestExecutionCreate(BaseModel):
    """Schema for creating a test execution record."""
    test_config_id: int
    execution_data: Dict[str, Any]
    result: Dict[str, Any]
    status: str = Field(..., description="success, failure, error")
    execution_time_ms: Optional[int] = None

class TestExecutionResponse(BaseModel):
    """Schema for test execution response."""
    id: int
    test_config_id: int
    execution_data: Dict[str, Any]
    result: Dict[str, Any]
    status: str
    execution_time_ms: Optional[int]
    executed_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/configurations", response_model=TestConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_test_configuration(
    config_data: TestConfigurationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new test configuration."""
    try:
        # Check if name already exists for this user
        existing_config = db.query(TestConfiguration).filter(
            and_(
                TestConfiguration.user_id == current_user.id,
                TestConfiguration.name == config_data.name,
                TestConfiguration.test_type == config_data.test_type
            )
        ).first()
        
        if existing_config:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Test configuration with name '{config_data.name}' already exists for {config_data.test_type}"
            )
        
        # Create new test configuration
        test_config = TestConfiguration(
            user_id=current_user.id,
            name=config_data.name,
            test_type=config_data.test_type,
            configuration=config_data.configuration,
            description=config_data.description,
            created_at=datetime.utcnow()
        )
        
        db.add(test_config)
        db.commit()
        db.refresh(test_config)
        
        # Log the activity
        await log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="test_management",
            action=f"Created test configuration '{config_data.name}'",
            status="success",
            metadata={
                "test_config_id": test_config.id,
                "test_type": config_data.test_type,
                "config_name": config_data.name
            }
        )
        
        logger.info(f"Test configuration '{config_data.name}' created by user {current_user.username}")
        
        return test_config
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create test configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create test configuration"
        )


@router.get("/configurations", response_model=List[TestConfigurationResponse])
async def get_test_configurations(
    test_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's test configurations."""
    query = db.query(TestConfiguration).filter(TestConfiguration.user_id == current_user.id)
    
    if test_type:
        query = query.filter(TestConfiguration.test_type == test_type)
    
    configurations = query.order_by(desc(TestConfiguration.created_at)).offset(skip).limit(limit).all()
    
    return configurations


@router.get("/configurations/{config_id}", response_model=TestConfigurationResponse)
async def get_test_configuration(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific test configuration."""
    config = db.query(TestConfiguration).filter(
        and_(
            TestConfiguration.id == config_id,
            TestConfiguration.user_id == current_user.id
        )
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test configuration not found"
        )
    
    return config


@router.put("/configurations/{config_id}", response_model=TestConfigurationResponse)
async def update_test_configuration(
    config_id: int,
    config_update: TestConfigurationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a test configuration."""
    try:
        # Get the configuration to update
        config = db.query(TestConfiguration).filter(
            and_(
                TestConfiguration.id == config_id,
                TestConfiguration.user_id == current_user.id
            )
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test configuration not found"
            )
        
        # Check for name conflicts if name is being updated
        if config_update.name and config_update.name != config.name:
            existing_config = db.query(TestConfiguration).filter(
                and_(
                    TestConfiguration.user_id == current_user.id,
                    TestConfiguration.name == config_update.name,
                    TestConfiguration.test_type == config.test_type,
                    TestConfiguration.id != config_id
                )
            ).first()
            
            if existing_config:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Test configuration with name '{config_update.name}' already exists"
                )
        
        # Update fields
        if config_update.name is not None:
            config.name = config_update.name
        if config_update.configuration is not None:
            config.configuration = config_update.configuration
        if config_update.description is not None:
            config.description = config_update.description
        
        config.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(config)
        
        # Log the activity
        await log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="test_management",
            action=f"Updated test configuration '{config.name}'",
            status="success",
            metadata={
                "test_config_id": config.id,
                "test_type": config.test_type,
                "updated_fields": config_update.dict(exclude_none=True)
            }
        )
        
        logger.info(f"Test configuration {config_id} updated by user {current_user.username}")
        
        return config
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update test configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update test configuration"
        )


@router.delete("/configurations/{config_id}")
async def delete_test_configuration(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a test configuration."""
    try:
        # Get the configuration to delete
        config = db.query(TestConfiguration).filter(
            and_(
                TestConfiguration.id == config_id,
                TestConfiguration.user_id == current_user.id
            )
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test configuration not found"
            )
        
        config_name = config.name
        config_type = config.test_type
        
        # Delete the configuration
        db.delete(config)
        db.commit()
        
        # Log the activity
        await log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="test_management",
            action=f"Deleted test configuration '{config_name}'",
            status="success",
            metadata={
                "deleted_config_id": config_id,
                "test_type": config_type,
                "config_name": config_name
            }
        )
        
        logger.info(f"Test configuration {config_id} deleted by user {current_user.username}")
        
        return {"message": f"Test configuration '{config_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete test configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete test configuration"
        )


@router.post("/configurations/{config_id}/execute", response_model=TestExecutionResponse)
async def execute_test_configuration(
    config_id: int,
    execution_data: TestExecutionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a test configuration and record the result."""
    try:
        # Verify the configuration exists and belongs to user
        config = db.query(TestConfiguration).filter(
            and_(
                TestConfiguration.id == config_id,
                TestConfiguration.user_id == current_user.id
            )
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test configuration not found"
            )
        
        # Create execution record
        from app.models import TestExecution
        
        execution = TestExecution(
            test_config_id=config_id,
            user_id=current_user.id,
            execution_data=execution_data.execution_data,
            result=execution_data.result,
            status=execution_data.status,
            execution_time_ms=execution_data.execution_time_ms,
            executed_at=datetime.utcnow()
        )
        
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        # Log the activity
        await log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="test_execution",
            action=f"Executed test configuration '{config.name}'",
            status=execution_data.status,
            metadata={
                "test_config_id": config_id,
                "execution_id": execution.id,
                "test_type": config.test_type,
                "execution_status": execution_data.status,
                "execution_time_ms": execution_data.execution_time_ms
            }
        )
        
        logger.info(f"Test configuration {config_id} executed by user {current_user.username} with status {execution_data.status}")
        
        return execution
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record test execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record test execution"
        )


@router.get("/configurations/{config_id}/executions", response_model=List[TestExecutionResponse])
async def get_test_executions(
    config_id: int,
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get execution history for a test configuration."""
    # Verify the configuration exists and belongs to user
    config = db.query(TestConfiguration).filter(
        and_(
            TestConfiguration.id == config_id,
            TestConfiguration.user_id == current_user.id
        )
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test configuration not found"
        )
    
    from app.models import TestExecution
    
    query = db.query(TestExecution).filter(TestExecution.test_config_id == config_id)
    
    if status_filter:
        query = query.filter(TestExecution.status == status_filter)
    
    executions = query.order_by(desc(TestExecution.executed_at)).offset(skip).limit(limit).all()
    
    return executions

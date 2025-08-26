import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import User, get_db_session
from app.routes.auth_routes import get_current_user

router = APIRouter(tags=["Users"])

# Pydantic Models for User management
class UserResponse(BaseModel):
    id: int
    username: str
    creation_date: datetime.datetime | None
    last_login: datetime.datetime | None
    login_count: int

    class Config:
        orm_mode = True

class UserCreate(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None


def is_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency function to check if the current user is an administrator.
    Raises an HTTPException with status 403 if the user is not 'admin'.

    This is used as a dependency in routes that should only be accessible
    by an administrator, providing role-based access control.

    Args:
        current_user (User): The user object, injected by `get_current_user`.

    Returns:
        User: The user object if they are an admin.
    """
    if current_user.username != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")
    return current_user

@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(is_admin)])
async def get_all_users(db: Session = Depends(get_db_session)):
    """
    Retrieves a list of all users from the database.

    This endpoint is protected and can only be accessed by an admin user.
    It is used in the 'Users' tab of the admin panel to display all registered users.

    Args:
        db (Session): The database session, injected by FastAPI.

    Returns:
        List[UserResponse]: A list of user objects.
    """
    users = db.query(User).all()
    return users

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(is_admin)])
async def create_user(user: UserCreate, db: Session = Depends(get_db_session)):
    """
    Creates a new user in the database.

    This endpoint is protected and can only be accessed by an admin user.
    It is used in the 'Users' tab to add new users to the system.

    Args:
        user (UserCreate): The user data (username and password) from the request body.
        db (Session): The database session, injected by FastAPI.

    Returns:
        UserResponse: The newly created user object.
    """
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = User(username=user.username)
    new_user.set_password(user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(is_admin)])
async def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db_session)):
    """
    Updates an existing user's information.

    This endpoint is protected and can only be accessed by an admin user.
    It allows changing a user's username and/or password from the 'Users' tab.

    Args:
        user_id (int): The ID of the user to update.
        user_update (UserUpdate): The new user data from the request body.
        db (Session): The database session, injected by FastAPI.

    Returns:
        UserResponse: The updated user object.
    """
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.username:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Username already registered")
        db_user.username = user_update.username
        
    if user_update.password:
        db_user.set_password(user_update.password)
        
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(is_admin)])
async def delete_user(user_id: int, db: Session = Depends(get_db_session)):
    """
    Deletes a user from the database.

    This endpoint is protected and can only be accessed by an admin user.
    It is used in the 'Users' tab to remove users. The admin user cannot be deleted.

    Args:
        user_id (int): The ID of the user to delete.
        db (Session): The database session, injected by FastAPI.

    Returns:
        None
    """
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if db_user.username == 'admin':
        raise HTTPException(status_code=403, detail="Cannot delete admin user")
        
    db.delete(db_user)
    db.commit()
    return None

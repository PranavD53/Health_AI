import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user

router = APIRouter(prefix="/palettes", tags=["Color Palettes"])

# --- Pydantic Schemas ---
class PaletteCreate(BaseModel):
    primary_color: str
    secondary_color: str
    background_color: str
    accent_color: str

class PaletteResponse(BaseModel):
    id: str
    user_id: int
    primary_color: str
    secondary_color: str
    background_color: str
    accent_color: str
    is_active: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class PalettesSummaryResponse(BaseModel):
    active: Optional[PaletteResponse] = None
    history: List[PaletteResponse] = []

# --- Endpoints ---

@router.get("", response_model=PalettesSummaryResponse)
def get_user_palettes(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Fetch active palette
        active = db.query(models.UserColorPalette).filter(
            models.UserColorPalette.user_id == current_user.id,
            models.UserColorPalette.is_active == True
        ).order_by(models.UserColorPalette.created_at.desc()).first()

        # Fetch history (last 5 palettes, most recent first)
        history = db.query(models.UserColorPalette).filter(
            models.UserColorPalette.user_id == current_user.id
        ).order_by(models.UserColorPalette.created_at.desc()).limit(5).all()

        return PalettesSummaryResponse(
            active=active,
            history=history
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user palettes: {str(e)}"
        )

@router.post("", response_model=PaletteResponse, status_code=status.HTTP_201_CREATED)
def save_user_palette(
    palette_data: PaletteCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Validate hex color format slightly (e.g. starting with #)
        for name, col in [
            ("primary_color", palette_data.primary_color),
            ("secondary_color", palette_data.secondary_color),
            ("background_color", palette_data.background_color),
            ("accent_color", palette_data.accent_color),
        ]:
            if not col.startswith("#") or len(col) != 7:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid hex format for {name}. Must be 7 characters starting with '#'"
                )

        # Start transaction to deactivate previous palettes and activate new one
        # Deactivate all other user palettes
        db.query(models.UserColorPalette).filter(
            models.UserColorPalette.user_id == current_user.id
        ).update({models.UserColorPalette.is_active: False})

        # Insert new palette as active
        new_palette = models.UserColorPalette(
            user_id=current_user.id,
            primary_color=palette_data.primary_color,
            secondary_color=palette_data.secondary_color,
            background_color=palette_data.background_color,
            accent_color=palette_data.accent_color,
            is_active=True
        )
        db.add(new_palette)
        db.commit()
        db.refresh(new_palette)

        return new_palette
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save user palette: {str(e)}"
        )

@router.post("/activate/{palette_id}", response_model=PaletteResponse)
def activate_user_palette(
    palette_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Find the palette
        palette = db.query(models.UserColorPalette).filter(
            models.UserColorPalette.id == palette_id,
            models.UserColorPalette.user_id == current_user.id
        ).first()

        if not palette:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Palette not found"
            )

        # Deactivate all others
        db.query(models.UserColorPalette).filter(
            models.UserColorPalette.user_id == current_user.id
        ).update({models.UserColorPalette.is_active: False})

        # Activate this one
        palette.is_active = True
        db.commit()
        db.refresh(palette)

        return palette
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user palette: {str(e)}"
        )

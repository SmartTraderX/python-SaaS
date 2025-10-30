from fastapi import APIRouter , HTTPException  , Body
from app.services.user_service import  (get_user_profile)

router = APIRouter(prefix='/user-management' , tags=['user'])

@router.get('/user-profile')
async get_profile():
    try:
        user= await get_user_profile(id)
        if  not user:
            raise HTTPException(status_code=404 , detail = str('User Not Found'))
        return {"message":'success', "data": user}
    except  Exception as e:
        raise HTTPException(status_code=500 , detail = str(e))

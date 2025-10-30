from app.models.user_model import UserModel
from beanie import PydanticObjectId

async def get_user_profile(id):
    user = await UserModel.get(PydanticObjectId(user_id))
    return user


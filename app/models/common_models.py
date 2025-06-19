# app/models/common_models.py
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from bson import ObjectId

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, field_info):
        # 允许已经是ObjectId或UUID实例的情况
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, uuid.UUID):
            return str(v)
        
        # 主要处理字符串输入
        if isinstance(v, str):
            # 尝试将其验证为UUID字符串
            try:
                uuid.UUID(v)
                return v # 如果是有效的UUID字符串，直接返回
            except ValueError:
                # 如果不是UUID，再尝试是否是有效的ObjectId字符串
                try:
                    ObjectId(v)
                    return v
                except Exception:
                     raise TypeError(f"'{v}' is not a valid UUID or ObjectId string")
        raise TypeError(f"Value must be a string, ObjectId or UUID, got {type(v)}")


class BaseDBModel(BaseModel):
    id: PyObjectId = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True # 允许使用alias _id
        from_attributes = True  # Pydantic v2: 允许从ORM对象属性创建模型 (虽然我们是NoSQL)
        json_encoders = { # Pydantic v1, v2中可以用 model_serializer_json
            datetime: lambda dt: dt.isoformat(),
            ObjectId: str, # 确保ObjectId能正确序列化为字符串
            # PyObjectId: str # PyObjectId本身就是str
        }
        # Pydantic v2 推荐使用 @model_serializer 或 @field_serializer 进行更细致的序列化控制

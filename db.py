from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import yaml
import pytz

with open("config.yaml") as f:
    config = yaml.safe_load(f)

engine = create_engine(config["db"]["url"], echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# 设置东八区时区
tz_shanghai = pytz.timezone('Asia/Shanghai')

def get_shanghai_time():
    """获取东八区当前时间"""
    return datetime.datetime.now(tz_shanghai)

class MacEntry(Base):
    __tablename__ = "mac_table"
    id = Column(Integer, primary_key=True, index=True)
    device = Column(String)
    vlan = Column(String)
    mac = Column(String)
    port = Column(String)
    timestamp = Column(DateTime, default=get_shanghai_time)

class LogEntry(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)
    timestamp = Column(DateTime, default=get_shanghai_time)

Base.metadata.create_all(bind=engine)
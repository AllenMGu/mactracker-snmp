import ipaddress
import datetime
import yaml
from easysnmp import Session
from db import SessionLocal, MacEntry, LogEntry

OID_MAC_TABLE = "1.3.6.1.2.1.17.4.3.1.2"  # dot1dTpFdbPort

def collect_snmp():
    """使用配置文件中的设置进行采集"""
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    community = config["snmp"]["community"]
    network = ipaddress.ip_network(config["snmp"]["network"])
    
    _perform_snmp_collection(network, community)

def collect_snmp_manual(network_str, community_str):
    """手动指定网络和community进行采集"""
    try:
        network = ipaddress.ip_network(network_str)
        _perform_snmp_collection(network, community_str)
    except ValueError as e:
        raise Exception(f"无效的网络地址: {network_str} - {str(e)}")

def _perform_snmp_collection(network, community):
    """执行SNMP采集的核心函数"""
    db = SessionLocal()
    try:
        host_count = len(list(network.hosts()))
        processed = 0
        
        for host in network.hosts():
            processed += 1
            try:
                # 创建 SNMP 会话
                session = Session(
                    hostname=str(host),
                    community=community,
                    version=2,  # SNMP v2c
                    timeout=1,  # 1秒超时
                    retries=0   # 不重试
                )
                
                # 使用 walk 方法获取 MAC 地址表
                mac_entries = session.walk(OID_MAC_TABLE)
                
                for entry in mac_entries:
                    # 从 OID 中提取 MAC 地址
                    oid_parts = entry.oid.split('.')
                    mac_parts = oid_parts[-6:]  # 获取最后6个部分（MAC地址）
                    mac = ":".join(["%02x" % int(x) for x in mac_parts])
                    
                    # 端口号是 entry 的值
                    port = entry.value
                    
                    # 保存到数据库
                    db_entry = MacEntry(
                        device=str(host),
                        vlan="unknown",
                        mac=mac,
                        port=port
                    )
                    db.add(db_entry)
                
                db.commit()
                db.add(LogEntry(message=f"SNMP scan success: {host}"))
                db.commit()
                
            except Exception as e:
                db.add(LogEntry(message=f"SNMP scan failed: {host} {e}"))
                db.commit()
        
        db.add(LogEntry(message=f"采集完成: 扫描了 {processed}/{host_count} 个主机"))
        db.commit()
                
    finally:
        db.close()
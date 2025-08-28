import ipaddress
import datetime
import yaml
from easysnmp import Session
from db import SessionLocal, MacEntry, LogEntry

# OID 定义
OID_MAC_TABLE = "1.3.6.1.2.1.17.4.3.1.2"  # dot1dTpFdbPort (传统网桥MIB)
OID_VLAN_NAME = "1.3.6.1.2.1.17.7.1.4.3.1.1"  # dot1qVlanStaticName
OID_DOT1Q_VLAN = "1.3.6.1.2.1.17.7.1.4.5.1.1"  # dot1qPvid (标准 802.1Q PVID)

def collect_snmp():
    """使用配置文件中的设置进行采集"""
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    community = config["snmp"]["community"]
    network = ipaddress.ip_network(config["snmp"]["network"])
    
    # 从配置文件中获取超时和重试设置，如果没有则使用默认值
    timeout = config["snmp"].get("timeout", 2)
    retries = config["snmp"].get("retries", 1)
    
    _perform_snmp_collection(network, community, timeout, retries)

def collect_snmp_manual(network_str, community_str):
    """手动指定网络和community进行采集"""
    try:
        network = ipaddress.ip_network(network_str)
        # 使用默认的超时和重试设置
        _perform_snmp_collection(network, community_str)
    except ValueError as e:
        raise Exception(f"无效的网络地址: {network_str} - {str(e)}")

def _get_interface_vlan(session, port_number, vlan_names):
    """尝试获取接口的 VLAN 信息"""
    try:
        # 尝试标准 802.1Q PVID OID
        vlan_oid = f"{OID_DOT1Q_VLAN}.{port_number}"
        vlan_entry = session.get(vlan_oid)
        if vlan_entry and vlan_entry.value != '0':
            vlan_id = vlan_entry.value
            # 查找 VLAN 名称，如果找不到则使用 VLAN ID
            vlan_name = vlan_names.get(vlan_id, f"VLAN {vlan_id}")
            return vlan_name
    except Exception as e:
        # 记录错误但继续尝试其他方法
        pass
    
    # 如果无法获取接口 VLAN 信息，使用默认 VLAN（VLAN 1）
    default_vlan = "1"
    return vlan_names.get(default_vlan, f"VLAN {default_vlan}")

def _perform_snmp_collection(network, community, timeout=2, retries=1):
    """执行SNMP采集的核心函数"""
    db = SessionLocal()
    try:
        host_count = len(list(network.hosts()))
        processed = 0
        successful_hosts = 0
        
        for host in network.hosts():
            processed += 1
            host_str = str(host)
            try:
                # 创建 SNMP 会话
                session = Session(
                    hostname=host_str,
                    community=community,
                    version=2,  # SNMP v2c
                    timeout=timeout,  # 增加超时时间
                    retries=retries   # 增加重试次数
                )
                
                # 获取 VLAN 名称映射表
                vlan_names = {}
                try:
                    vlan_entries = session.walk(OID_VLAN_NAME)
                    for entry in vlan_entries:
                        vlan_id = entry.oid.split('.')[-1]
                        vlan_names[vlan_id] = entry.value
                    db.add(LogEntry(message=f"成功获取VLAN名称: {host_str}"))
                except Exception as e:
                    db.add(LogEntry(message=f"获取VLAN名称失败: {host_str} - {str(e)}"))
                    db.commit()
                
                # 使用 walk 方法获取 MAC 地址表
                mac_entries = session.walk(OID_MAC_TABLE)
                
                mac_count = 0
                for entry in mac_entries:
                    # 从 OID 中提取 MAC 地址
                    oid_parts = entry.oid.split('.')
                    mac_parts = oid_parts[-6:]  # 获取最后6个部分（MAC地址）
                    mac = ":".join(["%02x" % int(x) for x in mac_parts])
                    
                    # 端口号是 entry 的值
                    port = entry.value
                    
                    # 获取接口的 VLAN 信息
                    vlan_name = _get_interface_vlan(session, port, vlan_names)
                    
                    # 保存到数据库
                    db_entry = MacEntry(
                        device=host_str,
                        vlan=vlan_name,
                        mac=mac,
                        port=port
                    )
                    db.add(db_entry)
                    mac_count += 1
                
                db.commit()
                db.add(LogEntry(message=f"SNMP扫描成功: {host_str}, 发现 {mac_count} 个MAC地址"))
                db.commit()
                successful_hosts += 1
                
            except Exception as e:
                error_msg = f"SNMP扫描失败: {host_str} - {str(e)}"
                db.add(LogEntry(message=error_msg))
                db.commit()
                print(error_msg)  # 同时输出到控制台
        
        summary_msg = f"采集完成: 成功扫描 {successful_hosts}/{processed} 个主机"
        db.add(LogEntry(message=summary_msg))
        db.commit()
        print(summary_msg)
                
    except Exception as e:
        error_msg = f"采集过程中发生错误: {str(e)}"
        db.add(LogEntry(message=error_msg))
        db.commit()
        print(error_msg)
    finally:
        db.close()
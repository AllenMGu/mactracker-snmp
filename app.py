from flask import Flask, render_template, request, redirect, url_for, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from db import SessionLocal, MacEntry, LogEntry, tz_shanghai
from collector import collect_snmp, collect_snmp_manual
import datetime
import threading
import yaml
from sqlalchemy import func, distinct

app = Flask(__name__)

# 读取配置文件
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# 存储后台采集任务的状态
collection_tasks = {}

def clean_old_data():
    """清理超过30天的数据，返回删除的记录数"""
    db = SessionLocal()
    try:
        # 计算30天前的日期
        thirty_days_ago = datetime.datetime.now(tz_shanghai) - datetime.timedelta(days=30)
        
        # 查询并删除旧数据
        result = db.query(MacEntry).filter(MacEntry.timestamp < thirty_days_ago).delete()
        db.commit()
        
        # 添加日志记录
        db.add(LogEntry(message=f"清理了 {result} 条超过30天的旧数据"))
        db.commit()
        
        return result
    except Exception as e:
        db.rollback()
        db.add(LogEntry(message=f"清理旧数据失败: {str(e)}"))
        db.commit()
        raise e
    finally:
        db.close()

# 初始化调度器
scheduler = BackgroundScheduler()

# 从配置文件中获取定时设置
interval_minutes = config["schedule"]["interval_minutes"]
cleanup_hour = config["schedule"]["cleanup_hour"]
cleanup_minute = config["schedule"]["cleanup_minute"]

# 使用配置的定时设置
scheduler.add_job(func=collect_snmp, trigger="interval", minutes=interval_minutes)
# 添加每天指定时间执行的数据清理任务
scheduler.add_job(func=clean_old_data, trigger="cron", hour=cleanup_hour, minute=cleanup_minute)
scheduler.start()

@app.route("/")
def index():
    return render_template("search.html")

@app.route("/search")
def search():
    q = request.args.get("q", "").lower()
    
    # 标准化 MAC 地址格式（移除分隔符并转换为小写）
    normalized_q = q.replace(':', '').replace('-', '').lower()
    
    db = SessionLocal()
    try:
        # 查询时也标准化数据库中的 MAC 地址进行比较
        results = db.query(MacEntry).filter(
            func.replace(func.replace(MacEntry.mac, ':', ''), '-', '').ilike(f"%{normalized_q}%")
        ).all()
        
        return render_template("search.html", results=results, query=q)
    finally:
        db.close()

@app.route("/by_date")
def by_date():
    """按日期查看采集结果"""
    date_str = request.args.get("date", "")
    
    db = SessionLocal()
    try:
        # 获取所有有数据的日期
        dates = db.query(
            func.date(MacEntry.timestamp).label('collection_date')
        ).distinct().order_by(func.date(MacEntry.timestamp).desc()).all()
        
        results = []
        selected_date = None
        error_message = None  # 添加错误消息变量
        
        if date_str:
            try:
                selected_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                # 创建时区感知的日期时间范围
                start_datetime = datetime.datetime.combine(selected_date, datetime.time.min)
                end_datetime = datetime.datetime.combine(selected_date, datetime.time.max)
                
                # 转换为时区感知的时间
                start_datetime = tz_shanghai.localize(start_datetime)
                end_datetime = tz_shanghai.localize(end_datetime)
                
                results = db.query(MacEntry).filter(
                    MacEntry.timestamp >= start_datetime,
                    MacEntry.timestamp <= end_datetime
                ).order_by(MacEntry.timestamp.desc()).all()
                
            except ValueError as e:
                # 日期格式错误
                app.logger.error(f"日期格式错误: {e}")
                error_message = "日期格式错误，请使用 YYYY-MM-DD 格式"
        
        # 将日期对象转换为字符串，以便在模板中使用
        date_strings = [d[0].strftime('%Y-%m-%d') if isinstance(d[0], datetime.date) else d[0] for d in dates]
        selected_date_str = selected_date.strftime('%Y-%m-%d') if selected_date else None
        
        return render_template("by_date.html", 
                              dates=date_strings, 
                              results=results, 
                              selected_date=selected_date_str,
                              error_message=error_message)  # 传递错误消息到模板
    except Exception as e:
        app.logger.error(f"按日期查看时发生错误: {e}")
        error_message = f"发生错误: {e}"
        return render_template("by_date.html", 
                              dates=[], 
                              results=[], 
                              selected_date=None,
                              error_message=error_message)
    finally:
        db.close()

@app.route("/trigger")
def trigger():
    # 启动后台采集任务
    task_id = str(datetime.datetime.now().timestamp())
    collection_tasks[task_id] = {"status": "running", "message": "开始采集..."}
    
    # 在新线程中运行采集任务
    thread = threading.Thread(target=run_collection_task, args=(task_id,))
    thread.start()
    
    return redirect(url_for("logs"))

@app.route("/manual_collect", methods=["POST"])
def manual_collect():
    network = request.form.get("network", "")
    community = request.form.get("community", "")
    
    if not network or not community:
        return jsonify({"error": "网络地址和community不能为空"}), 400
    
    # 启动后台采集任务
    task_id = str(datetime.datetime.now().timestamp())
    collection_tasks[task_id] = {
        "status": "running", 
        "message": f"开始手动采集: {network}",
        "network": network,
        "community": community
    }
    
    # 在新线程中运行采集任务
    thread = threading.Thread(target=run_manual_collection_task, args=(task_id, network, community))
    thread.start()
    
    return jsonify({"success": True, "task_id": task_id})

@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = collection_tasks.get(task_id, {})
    return jsonify(task)

@app.route("/logs")
def logs():
    db = SessionLocal()
    try:
        logs = db.query(LogEntry).order_by(LogEntry.timestamp.desc()).limit(50).all()
        return render_template("logs.html", logs=logs)
    finally:
        db.close()

@app.route("/cleanup", methods=["GET", "POST"])
def cleanup():
    """清理超过30天的数据"""
    if request.method == "POST":
        # 启动后台清理任务
        task_id = str(datetime.datetime.now().timestamp())
        collection_tasks[task_id] = {"status": "running", "message": "开始清理数据..."}
        
        # 在新线程中运行清理任务
        thread = threading.Thread(target=run_cleanup_task, args=(task_id,))
        thread.start()
        
        return jsonify({"success": True, "task_id": task_id})
    
    # GET请求显示清理页面
    db = SessionLocal()
    try:
        # 获取最早和最晚的数据日期
        oldest_date = db.query(func.min(MacEntry.timestamp)).scalar()
        newest_date = db.query(func.max(MacEntry.timestamp)).scalar()
        total_count = db.query(MacEntry).count()
        
        # 计算30天前的日期
        thirty_days_ago = datetime.datetime.now(tz_shanghai) - datetime.timedelta(days=30)
        old_count = db.query(MacEntry).filter(MacEntry.timestamp < thirty_days_ago).count()
        
        return render_template("cleanup.html", 
                              oldest_date=oldest_date, 
                              newest_date=newest_date,
                              total_count=total_count,
                              old_count=old_count)
    finally:
        db.close()

def run_collection_task(task_id):
    try:
        collect_snmp()
        collection_tasks[task_id]["status"] = "completed"
        collection_tasks[task_id]["message"] = "采集完成"
    except Exception as e:
        collection_tasks[task_id]["status"] = "failed"
        collection_tasks[task_id]["message"] = f"采集失败: {str(e)}"

def run_manual_collection_task(task_id, network, community):
    try:
        collect_snmp_manual(network, community)
        collection_tasks[task_id]["status"] = "completed"
        collection_tasks[task_id]["message"] = f"手动采集完成: {network}"
    except Exception as e:
        collection_tasks[task_id]["status"] = "failed"
        collection_tasks[task_id]["message"] = f"手动采集失败: {str(e)}"

def run_cleanup_task(task_id):
    try:
        deleted_count = clean_old_data()
        collection_tasks[task_id]["status"] = "completed"
        collection_tasks[task_id]["message"] = f"清理完成，删除了 {deleted_count} 条旧数据"
    except Exception as e:
        collection_tasks[task_id]["status"] = "failed"
        collection_tasks[task_id]["message"] = f"清理失败: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8500)
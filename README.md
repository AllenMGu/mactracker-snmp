
# MAC Address Tracker / MAC 地址跟踪系统

A Flask-based web application for automatically discovering and tracking MAC addresses on your network via SNMP.  
一个基于 Flask 的 Web 应用程序，用于通过 SNMP 自动发现和跟踪网络中的 MAC 地址。

---

## Features / 功能
- **Automated SNMP Collection** — Periodic scans across configured network ranges.  
  自动 SNMP 采集 — 定期扫描配置的网络段。
- **Manual Collection** — Trigger on-demand scans for specific networks or IPs.  
  手动采集 — 针对特定网络或 IP 触发按需扫描。
- **Web Interface** — Search, view by date, inspect logs, and trigger cleanup.  
  Web 界面 — 搜索、按日期查看、查看日志、手动触发清理。
- **Background Processing** — Long-running tasks run asynchronously (APScheduler).  
  后台处理 — 长任务异步运行（APScheduler）。
- **SQLite Persistence** — Simple file-based storage via SQLAlchemy.  
  SQLite 持久化 — 使用 SQLAlchemy 的文件数据库。
- **Docker Compose** — Easy deployment with Docker.  
  Docker Compose — 使用 Docker 简化部署。

---

## Quick Start (Docker 推荐)
1. Clone the repository  
   ```bash
   git clone <your-repository-url>
   cd mactracker
   ```
2. Edit `config.yaml` (see example below).  
3. Start with Docker Compose:
   ```bash
   docker-compose up -d
   ```
4. Open the web UI at `http://<your-server-ip>:8500`.

---

## Configuration 示例 (`config.yaml`)
```yaml
snmp:
  community: "pulic"
  network: "10.80.1.0/24"

db:
  url: sqlite:///data/mactracker.db

schedule:
  interval_minutes: 60
  cleanup_hour: 1
  cleanup_minute: 0
```

**Important / 注意**
- Ensure SNMP is enabled on your network devices and that the host running the app can reach the target network.  
  确保目标交换机/路由器开启 SNMP，并且运行该应用的主机能访问目标网络。
- The web UI listens on port `8500` by default (Docker / compose maps this port).  
  默认 Web 界面监听端口 8500（Docker compose 映射该端口）。

---

## Run Locally (without Docker)
```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
# venv\Scripts\activate       # Windows

pip install -r requirements.txt
mkdir -p data
python app.py
# Open http://localhost:8500
```

---

## Endpoints (简要)
- `/` — Search & manual collection form  
- `/by_date` — View entries filtered by date  
- `/logs` — Collection logs (auto-refresh)  
- `/cleanup` — Cleanup old data (older than 30 days)

---

## File Structure
```
mactracker/
├── app.py
├── collector.py
├── db.py
├── config.yaml
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── data/
└── templates/
    ├── search.html
    ├── by_date.html
    ├── logs.html
    └── cleanup.html
```

---

## Common Troubleshooting / 常见问题
- **No SNMP responses**: verify community string, device SNMP version, firewall rules, and network reachability.  
  无 SNMP 响应：检查 community、SNMP 版本、防火墙和网络连通性。
- **SQLite errors**: ensure `data/` directory exists and is writable by the container/user.  
  SQLite 错误：确保 `data/` 目录存在并且容器/用户有写权限。
- **Port conflicts**: change container or host port mapping in `docker-compose.yml`.  
  端口冲突：修改 `docker-compose.yml` 中的端口映射。

---

## Development notes / 开发说明
- Background scheduling is handled by APScheduler; adjust `interval_minutes` in `config.yaml`.  
- SNMP interactions use `easy_snmp` — devices must support SNMP and allow the community string.  
- Database models live in `db.py` (SQLAlchemy). Migrations are not included; SQLite file is the single source of truth.

---

## License
MIT License — see `LICENSE` (add one to the repo if you publish).

---

## Contributing / 贡献
Patches, bug reports, and enhancements are welcome. Please open issues or pull requests on the repository.

---

## Contact
For questions or help, open an issue on the repository or contact the project maintainer.



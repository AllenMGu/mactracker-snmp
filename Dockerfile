FROM python:3.10-slim

WORKDIR /app

# 设置时区为上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 备份并替换所有源为阿里云源
RUN echo "deb https://mirrors.aliyun.com/debian/ trixie main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ trixie-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security trixie-security main contrib non-free" >> /etc/apt/sources.list && \
    # 删除所有可能的其他源文件
    rm -f /etc/apt/sources.list.d/* && \
    # 更新包列表
    apt-get update && \
    # 安装必要的包
    apt-get install -y libsnmp-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

COPY . .

CMD ["python", "app.py"]
git clone https://github.com/AllenMGu/mactracker-snmp.git

sudo unzip mactracker-snmp.zip -d /opt/

cd /opt/mactracker-snmp

docker-compose build --no-cache

docker-compose up -d

web to http:// server ip :8500
